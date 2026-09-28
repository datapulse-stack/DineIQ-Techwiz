"""
PySpark Big-Data pipeline for DineIQ (the Spark side of the dual-pipeline).

this is a real, self-contained spark job - it reads the same raw csvs the pandas
side reads, but solves the menu-classification problem completely independently:

  * schema-defined ingestion (explicit StructType) + a schema-inference example
  * spark sql joins to build the order-line fact table
  * window-function feature engineering at the item x location grain
  * partitioned parquet output for the processed layer
  * THREE spark mllib classifiers trained + compared (RandomForest, DecisionTree,
    LogisticRegression) with the best chosen on macro-F1
  * best model saved to disk, plus per-row predictions written to csv

nothing is shared with the pandas pipeline - the two only meet later in
src/models.py, which lines the two prediction sets up and measures agreement.

run (needs a jvm 17+ and pyspark):
    python spark_jobs/spark_pipeline.py

outputs:
    processed_data/spark/fact_order_lines.parquet/   (partitioned by location_id)
    processed_data/spark_predictions.csv             (item x location predictions)
    processed_data/spark_metrics.json                (leaderboard + selected model)
    spark_jobs/models/spark_best_model/              (saved mllib PipelineModel)
    spark_jobs/logs/spark_run.log                    (full run log)
"""
import os
import sys
import json
import time
import logging
from datetime import datetime

# ---- paths ---------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
PROCESSED = os.path.join(ROOT, "processed_data")
SPARK_OUT = os.path.join(PROCESSED, "spark")
MODEL_DIR = os.path.join(ROOT, "spark_jobs", "models", "spark_best_model")
LOG_DIR = os.path.join(ROOT, "spark_jobs", "logs")
os.makedirs(SPARK_OUT, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ---- logging (console + file, so there's a run log artefact) -------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, "spark_run.log"), mode="w"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("dineiq.spark")

try:
    from pyspark.sql import SparkSession, functions as F, Window
    from pyspark.sql.types import (StructType, StructField, StringType,
                                   IntegerType, DoubleType)
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import VectorAssembler, StringIndexer, StandardScaler
    from pyspark.ml.classification import (RandomForestClassifier,
                                           DecisionTreeClassifier,
                                           LogisticRegression)
    from pyspark.ml.evaluation import MulticlassClassificationEvaluator
except ImportError:
    log.error("PySpark is not installed. `pip install pyspark` (needs a JVM 17+). "
              "The pandas pipeline in src/ is the reference implementation.")
    sys.exit(0)

# the four business classes, and the same cut-points the pandas side uses
DEMAND_CUT = 0.55
PROFIT_CUT = 0.45
SEED = 20260926


def build_spark():
    return (SparkSession.builder
            .appName("DineIQ-BigData")
            .master(os.environ.get("SPARK_MASTER", "local[*]"))
            .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEM", "1g"))
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.ui.enabled", "false")
            .config("spark.local.dir", os.environ.get("SPARK_LOCAL_DIRS",
                    os.path.join(ROOT, ".tmp", "sparklocal")))
            .getOrCreate())


def ingest(spark):
    """schema-defined ingestion of the big table + inference for the small ones."""
    # explicit schema on the 1.2M-row order-lines table (SRS: demonstrate schema
    # definition, not just inference - and it's faster/safer on the big file)
    oi_schema = StructType([
        StructField("order_item_id", StringType(), False),
        StructField("order_id", StringType(), False),
        StructField("item_id", StringType(), True),
        StructField("quantity", IntegerType(), True),
        StructField("unit_price", DoubleType(), True),
        StructField("discount_pct", DoubleType(), True),
        StructField("line_total", DoubleType(), True),
    ])
    oitems = spark.read.csv(f"{RAW}/order_items.csv", header=True, schema=oi_schema)
    # schema inference on the smaller reference tables
    orders = spark.read.csv(f"{RAW}/orders.csv", header=True, inferSchema=True)
    items = spark.read.csv(f"{RAW}/menu_items.csv", header=True, inferSchema=True)
    ratings = spark.read.csv(f"{RAW}/ratings.csv", header=True, inferSchema=True)
    wastage = spark.read.csv(f"{RAW}/wastage.csv", header=True, inferSchema=True)
    inventory = spark.read.csv(f"{RAW}/inventory.csv", header=True, inferSchema=True)
    log.info("ingested: order_items=%d orders=%d menu_items=%d ratings=%d wastage=%d",
             oitems.count(), orders.count(), items.count(),
             ratings.count(), wastage.count())
    return oitems, orders, items, ratings, wastage, inventory


def clean(oitems):
    """mirror of the pandas cleaning rules: drop dup lines + impossible values."""
    before = oitems.count()
    out = (oitems.dropDuplicates(["order_id", "item_id", "quantity",
                                  "unit_price", "discount_pct", "line_total"])
           .filter(F.col("quantity") > 0)
           .filter(F.col("unit_price") > 0))
    log.info("cleaning: %d -> %d rows (dropped %d)", before, out.count(),
             before - out.count())
    return out


def integrate(spark, oitems, orders, items):
    """spark sql join -> order-line fact table at item x location grain."""
    oitems.createOrReplaceTempView("oi")
    orders.createOrReplaceTempView("o")
    items.createOrReplaceTempView("mi")
    fact = spark.sql("""
        SELECT oi.item_id,
               o.location_id,
               oi.quantity,
               oi.line_total                              AS revenue,
               (oi.line_total - oi.quantity*mi.food_cost) AS profit,
               CASE WHEN o.promotion_id IS NOT NULL AND o.promotion_id <> ''
                    THEN 1 ELSE 0 END                     AS has_promo
        FROM oi
        JOIN o  ON oi.order_id = o.order_id
        JOIN mi ON oi.item_id  = mi.item_id
        WHERE o.location_id IS NOT NULL
    """)
    return fact


def features(fact, ratings, wastage, inventory):
    """aggregate to item x location, add wastage% + rating, then the rule label."""
    agg = (fact.groupBy("item_id", "location_id")
           .agg(F.sum("quantity").alias("qty"),
                F.sum("revenue").alias("revenue"),
                F.sum("profit").alias("profit"),
                F.count(F.lit(1)).alias("lines"),
                F.sum("has_promo").alias("promo_lines")))
    agg = agg.withColumn("margin", F.col("profit") / F.col("revenue")) \
             .withColumn("promo_dep", F.col("promo_lines") / F.col("lines") * 100)

    # wastage % at item x location
    prep = inventory.groupBy("item_id", "location_id") \
                    .agg(F.sum("prepared_qty").alias("prepared"))
    wst = wastage.groupBy("item_id", "location_id") \
                 .agg(F.sum("wasted_qty").alias("wasted"))
    agg = (agg.join(prep, ["item_id", "location_id"], "left")
              .join(wst, ["item_id", "location_id"], "left"))
    agg = agg.withColumn("wastage",
                         F.when(F.col("prepared") > 0,
                                F.coalesce(F.col("wasted"), F.lit(0.0)) /
                                F.col("prepared") * 100).otherwise(0.0))

    # item-level average rating
    rat = ratings.groupBy("item_id").agg(F.avg("stars").alias("rating"))
    agg = agg.join(rat, "item_id", "left").fillna({"rating": 4.0})

    # ---- LOCATION-SPECIFIC rule label (same formula as the pandas side) ----
    # normalise demand & profit WITHIN each location using window min/max
    w = Window.partitionBy("location_id")
    qmin, qmax = F.min("qty").over(w), F.max("qty").over(w)
    mmin, mmax = F.min("margin").over(w), F.max("margin").over(w)
    agg = agg.withColumn("d",
              F.when(qmax > qmin, (F.col("qty") - qmin) / (qmax - qmin)).otherwise(F.lit(0.5)))
    agg = agg.withColumn("p_raw",
              F.when(mmax > mmin, (F.col("margin") - mmin) / (mmax - mmin)).otherwise(F.lit(0.5)))
    agg = agg.withColumn("p",
              F.col("p_raw") - (F.col("wastage") / 100) * 0.9
              - F.when(F.col("rating") < 3.6, F.lit(0.12)).otherwise(F.lit(0.0)))
    agg = agg.withColumn("label_str",
              F.when((F.col("d") >= DEMAND_CUT) & (F.col("p") >= PROFIT_CUT), "Profit Driver")
               .when((F.col("d") >= DEMAND_CUT) & (F.col("p") < PROFIT_CUT), "Volume Driver")
               .when((F.col("d") < DEMAND_CUT) & (F.col("p") >= PROFIT_CUT), "Hidden Opportunity")
               .otherwise("Low Performer"))
    return agg.fillna({"margin": 0.0, "promo_dep": 0.0, "wastage": 0.0}).cache()


FEATURES = ["qty", "revenue", "margin", "rating", "wastage", "promo_dep"]


def train_and_compare(data):
    """train 3 mllib classifiers, compare on a held-out split, pick best by F1."""
    idx = StringIndexer(inputCol="label_str", outputCol="label", handleInvalid="keep")
    asm = VectorAssembler(inputCols=FEATURES, outputCol="raw_features")
    scl = StandardScaler(inputCol="raw_features", outputCol="features")

    train, test = data.randomSplit([0.7, 0.3], seed=SEED)
    train, test = train.cache(), test.cache()
    log.info("train rows=%d  test rows=%d", train.count(), test.count())

    candidates = [
        ("Random Forest", RandomForestClassifier(labelCol="label", featuresCol="features",
                                                  numTrees=120, maxDepth=8, seed=SEED)),
        ("Decision Tree", DecisionTreeClassifier(labelCol="label", featuresCol="features",
                                                 maxDepth=8, seed=SEED)),
        ("Logistic Regression", LogisticRegression(labelCol="label", featuresCol="features",
                                                    maxIter=100, regParam=0.02)),
    ]
    acc_eval = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction",
                                                 metricName="accuracy")
    f1_eval = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction",
                                                metricName="f1")

    board, best = [], None
    for name, clf in candidates:
        pipe = Pipeline(stages=[idx, asm, scl, clf])
        model = pipe.fit(train)
        pred = model.transform(test)
        acc = acc_eval.evaluate(pred)
        f1 = f1_eval.evaluate(pred)
        log.info("[Spark MLlib] %-20s accuracy=%.3f  macro-F1=%.3f", name, acc, f1)
        row = {"model": name, "acc": round(acc, 3), "f1": round(f1, 3), "selected": False}
        board.append(row)
        if best is None or f1 > best[2]:
            best = (name, model, f1)
    for r in board:
        r["selected"] = (r["model"] == best[0])
    log.info("selected best spark model: %s (macro-F1=%.3f)", best[0], best[2])
    return board, best[0], best[1]


def main():
    t0 = time.time()
    log.info("=== DineIQ Spark pipeline starting @ %s ===", datetime.now().isoformat())
    spark = build_spark()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        oitems, orders, items, ratings, wastage, inventory = ingest(spark)
        oitems = clean(oitems)
        fact = integrate(spark, oitems, orders, items)

        # ---- partitioned parquet processed layer (SRS: parquet output) ----
        out_parq = os.path.join(SPARK_OUT, "fact_order_lines.parquet")
        (fact.write.mode("overwrite").partitionBy("location_id").parquet(out_parq))
        log.info("wrote partitioned parquet -> %s", out_parq)

        data = features(fact, ratings, wastage, inventory)
        n = data.count()
        log.info("feature table: %d item x location rows", n)

        board, best_name, best_model = train_and_compare(data)

        # ---- predict every item x location row with the best model ----
        idx_labels = best_model.stages[0].labels   # StringIndexer label order
        preds = best_model.transform(data).select(
            "item_id", "location_id", "label_str", "prediction")
        # map numeric prediction back to the class string
        mapping = F.create_map([F.lit(x) for pair in enumerate(idx_labels)
                                for x in (float(pair[0]), pair[1])])
        preds = preds.withColumn("spark_pred", mapping[F.col("prediction")])
        pdf = preds.select("item_id", "location_id", "spark_pred", "label_str").toPandas()
        pred_csv = os.path.join(PROCESSED, "spark_predictions.csv")
        pdf.to_csv(pred_csv, index=False)
        log.info("wrote %d spark predictions -> %s", len(pdf), pred_csv)

        # ---- save the best mllib model ----
        best_model.write().overwrite().save(MODEL_DIR)
        log.info("saved spark model -> %s", MODEL_DIR)

        # ---- metrics artefact ----
        metrics = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "engine": "Apache Spark MLlib " + spark.version,
            "n_samples": int(len(pdf)),
            "leaderboard": board,
            "selected": best_name,
            "features": FEATURES,
            "runtime_sec": round(time.time() - t0, 1),
        }
        with open(os.path.join(PROCESSED, "spark_metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)
        log.info("wrote spark_metrics.json")
        log.info("=== Spark pipeline complete in %.1fs ===", time.time() - t0)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
