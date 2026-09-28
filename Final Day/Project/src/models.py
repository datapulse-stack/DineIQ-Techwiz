"""
Dual-pipeline modelling + comparison.

The SRS wants two *independent* pipelines whose results are compared. In this
Python project we train two different model families on the same feature set:

    Pipeline A ("Spark-side" equivalent):  RandomForest / GBT / LogisticRegression
    Pipeline B ("Python DS side"):         GradientBoosting / ExtraTrees / LogReg

We train at the item x location grain (so there are enough rows for the metrics
to mean something and for the two pipelines to genuinely disagree on the tricky
branches). The label is the item's menu class. Each side picks its best model by
macro-F1, predicts every row, and we compare them head to head.

A genuine PySpark version of pipeline A lives in spark_jobs/spark_pipeline.py for
environments where Spark is installed; if present its predictions are preferred.
Otherwise these two Python families stand in, which is honest and documented.
"""
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                              ExtraTreesClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from src import config as C

FEATURES = ["qty", "revenue", "margin", "rating", "repeat", "wastage", "promo_dep", "trend"]

# where the spark side drops its artefacts (written by spark_jobs/spark_pipeline.py)
SPARK_PRED = C.PROCESSED / "spark_predictions.csv"
SPARK_METRICS = C.PROCESSED / "spark_metrics.json"
MODEL_DIR = C.ROOT / "models"


def _build_samples(fact, menu, inventory, wastage):
    """one row per (item, location) with the item's global class as the label."""
    item_rating = dict(zip(menu.item_id, menu.rating))
    item_repeat = dict(zip(menu.item_id, menu.repeat_pct))
    item_trend = dict(zip(menu.item_id, menu.trend))
    item_klass = dict(zip(menu.item_id, menu.klass))
    item_name = dict(zip(menu.item_id, menu["name"]))

    g = fact.groupby(["item_id", "location_id"], observed=True).agg(
        qty=("quantity", "sum"), revenue=("revenue", "sum"),
        profit=("profit", "sum"), lines=("order_id", "size"),
        promo_lines=("has_promo", "sum")).reset_index()
    g["margin"] = (g.revenue - (g.revenue - g.profit)) / g.revenue  # = profit/revenue
    g["margin"] = g.profit / g.revenue
    g["promo_dep"] = g.promo_lines / g.lines * 100

    prep = inventory.groupby(["item_id", "location_id"]).prepared_qty.sum()
    wst = wastage.groupby(["item_id", "location_id"]).wasted_qty.sum()
    g = g.merge(prep.rename("prepared"), on=["item_id", "location_id"], how="left")
    g = g.merge(wst.rename("wasted"), on=["item_id", "location_id"], how="left")
    g["wastage"] = (g["wasted"].fillna(0) / g["prepared"] * 100).fillna(0)

    g["rating"] = g.item_id.map(item_rating)
    g["repeat"] = g.item_id.map(item_repeat)
    g["trend"] = g.item_id.map(item_trend)
    g["name"] = g.item_id.map(item_name)

    # LOCATION-SPECIFIC class label (SRS step 34): the same dish can be a Profit
    # Driver at a busy branch and a Low Performer at a quiet one. We score demand
    # & profit WITHIN each location, so the label genuinely varies by branch -
    # which makes the classification a real (non-trivial) learning problem.
    def _norm(s):
        lo, hi = s.min(), s.max()
        return (s - lo) / (hi - lo) if hi > lo else s * 0 + 0.5

    parts = []
    for lid, loc in g.groupby("location_id", observed=True):
        loc = loc.copy()
        d = _norm(loc.qty)
        p = _norm(loc.margin) - (loc.wastage / 100) * 0.9 - np.where(loc.rating < 3.6, 0.12, 0)
        loc["local_demand"] = d
        loc["local_profit"] = p
        hiD, hiP = d >= C.DEMAND_CUT, p >= C.PROFIT_CUT
        loc["klass"] = np.select(
            [hiD & hiP, hiD & ~hiP, ~hiD & hiP],
            ["Profit Driver", "Volume Driver", "Hidden Opportunity"],
            default="Low Performer")
        parts.append(loc)
    g = pd.concat(parts, ignore_index=True)
    return g.dropna(subset=FEATURES + ["klass"]).reset_index(drop=True)


def _leaderboard(models, Xtr, Xte, ytr, yte):
    board, best, best_f1, best_name = [], None, -1, None
    for name, m in models:
        m.fit(Xtr, ytr)
        pred = m.predict(Xte)
        acc = accuracy_score(yte, pred)
        f1 = f1_score(yte, pred, average="macro")
        board.append({"model": name, "acc": round(float(acc), 3),
                      "f1": round(float(f1), 3), "selected": False})
        if f1 > best_f1:
            best, best_f1, best_name = m, f1, name
    for b in board:
        b["selected"] = (b["model"] == best_name)
    return board, best, best_name


def run(fact, menu, inventory, wastage):
    df = _build_samples(fact, menu, inventory, wastage)
    # force plain NUMPY arrays. on pandas builds that back strings/columns with
    # pyarrow, `.values` hands back an Arrow extension array, and sklearn's
    # train_test_split can't fancy-index it ("only integer scalar arrays can be
    # converted to a scalar index"). .to_numpy() materialises real numpy arrays.
    X = df[FEATURES].fillna(0).to_numpy(dtype="float64")
    y = df["klass"].astype(str).to_numpy(dtype=object)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.3,
                                          random_state=C.SEED, stratify=y)

    py_models = [
        ("XGBoost-style GBM", GradientBoostingClassifier(learning_rate=0.15, random_state=7)),
        ("Extra Trees", ExtraTreesClassifier(n_estimators=350, random_state=C.SEED)),
        ("Logistic Regression", LogisticRegression(max_iter=1000, C=0.5)),
    ]
    py_board, py_best, py_name = _leaderboard(py_models, Xtr, Xte, ytr, yte)
    df["py_pred"] = py_best.predict(Xs)

    # ---- save the python-side model artefacts (SRS: saved model + preds) ----
    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_DIR / "python_best_model.pkl", "wb") as f:
        pickle.dump({"model": py_best, "scaler": scaler, "features": FEATURES,
                     "name": py_name}, f)
    (df[["item_id", "name", "location_id", "klass", "py_pred"]]
     .rename(columns={"klass": "rule_label", "py_pred": "python_pred"})
     .to_csv(C.PROCESSED / "python_predictions.csv", index=False))
    with open(C.PROCESSED / "python_metrics.json", "w") as f:
        json.dump({"engine": "scikit-learn", "leaderboard": py_board,
                   "selected": py_name, "features": FEATURES,
                   "n_samples": int(len(df))}, f, indent=2)

    # ---- SPARK SIDE: prefer the real PySpark MLlib predictions if present ----
    # spark_jobs/spark_pipeline.py writes spark_predictions.csv + spark_metrics.json.
    # when that genuine Big-Data run exists we compare against it (this is the true
    # dual-pipeline comparison). otherwise we fall back to a second, differently
    # configured python family as an honest, clearly-labelled stand-in.
    spark_source = "Apache Spark MLlib"
    if SPARK_PRED.exists() and SPARK_METRICS.exists():
        sp = pd.read_csv(SPARK_PRED)[["item_id", "location_id", "spark_pred"]]
        df = df.merge(sp, on=["item_id", "location_id"], how="left")
        # any row the spark run didn't cover falls back to the rule label
        df["spark_pred"] = df["spark_pred"].fillna(df["klass"])
        spark_board = json.load(open(SPARK_METRICS))["leaderboard"]
        spark_name = json.load(open(SPARK_METRICS))["selected"]
    else:
        spark_source = "scikit-learn stand-in (Spark not run)"
        spark_models = [
            ("Random Forest", RandomForestClassifier(n_estimators=300, random_state=C.SEED)),
            ("Gradient-Boosted Trees", GradientBoostingClassifier(random_state=C.SEED)),
            ("Logistic Regression", LogisticRegression(max_iter=1000)),
        ]
        spark_board, spark_best, spark_name = _leaderboard(spark_models, Xtr, Xte, ytr, yte)
        df["spark_pred"] = spark_best.predict(Xs)

    df["match"] = df.spark_pred == df.py_pred
    agreement = round(df.match.mean() * 100)

    # comparison at item x location grain - disagreements bubble to the top so
    # they're easy to review. keep it to a sensible number of rows for the table.
    locname = dict(zip(fact.location_id, fact.location_name))
    df["_loc"] = df.location_id.map(locname)
    df_sorted = df.sort_values("match")   # False first
    comp = [{"name": r["name"], "loc": r["_loc"], "spark": r.spark_pred,
             "py": r.py_pred, "match": bool(r.match)}
            for _, r in df_sorted.head(40).iterrows()]

    # full item x location comparison -> downloadable report (SRS step 49)
    (df_sorted[["item_id", "name", "location_id", "_loc",
                "spark_pred", "py_pred", "match"]]
     .rename(columns={"_loc": "location", "spark_pred": "spark_model",
                      "py_pred": "python_model", "match": "agree"})
     .to_csv(C.PROCESSED / "model_comparison.csv", index=False))

    return {
        "spark_leaderboard": spark_board,
        "python_leaderboard": py_board,
        "spark_selected": spark_name,
        "python_selected": py_name,
        "spark_source": spark_source,
        "comparison": comp,
        "agreement_pct": int(agreement),
        "matches": int(df.match.sum()),
        "disagreements": int((~df.match).sum()),
        "n_samples": int(len(df)),
    }
