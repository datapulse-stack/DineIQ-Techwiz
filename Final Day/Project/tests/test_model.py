"""model tests: dual-pipeline artefacts exist and the comparison is sane."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "processed_data"


def test_comparison_report_covers_enough_records():
    comp = pd.read_csv(PROCESSED / "model_comparison.csv")
    assert len(comp) >= 100, "dual-pipeline comparison needs >=100 records"
    assert {"spark_model", "python_model", "agree"}.issubset(comp.columns)


def test_agreement_is_reasonable():
    comp = pd.read_csv(PROCESSED / "model_comparison.csv")
    rate = comp["agree"].mean()
    # two independent pipelines should mostly agree but not be identical
    assert 0.6 <= rate <= 0.999, f"suspicious agreement rate {rate:.3f}"


def test_saved_models_exist():
    assert (ROOT / "models" / "python_best_model.pkl").exists()
    # the spark artefacts are written by the (optional) spark run
    assert (PROCESSED / "spark_predictions.csv").exists()
    assert (PROCESSED / "spark_metrics.json").exists()


def test_spark_leaderboard_has_three_algorithms():
    m = json.load(open(PROCESSED / "spark_metrics.json"))
    assert len(m["leaderboard"]) >= 3, "need >=3 Spark MLlib algorithms compared"
    assert any(r["selected"] for r in m["leaderboard"])


def test_forecast_beats_baseline():
    d = json.load(open(ROOT / "outputs" / "dashboard_data.json"))
    fc = d["forecast"]
    assert fc["mape"] < fc["baseline_mape"], "model must beat the naive baseline"
    assert 0.0 <= fc["r2"] <= 1.0


def test_churn_model_metrics():
    d = json.load(open(ROOT / "outputs" / "dashboard_data.json"))
    ch = d["churn"]
    assert ch["accuracy"] >= 0.5
    assert ch["n_customers"] >= 50_000
