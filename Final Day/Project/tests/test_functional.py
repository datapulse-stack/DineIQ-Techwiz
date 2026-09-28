"""functional tests: the dataset exists and meets the SRS scale minimums."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent


def test_scale_minimums(raw):
    assert len(raw["order_items"]) >= 1_000_000
    assert len(raw["orders"]) >= 100_000
    assert len(raw["customers"]) >= 50_000
    assert len(raw["menu_items"]) >= 150
    assert len(raw["menu_categories"]) >= 10
    assert len(raw["locations"]) >= 20


def test_referential_integrity(raw):
    items = set(raw["menu_items"].item_id)
    locs = set(raw["locations"].location_id)
    # every order-line points at a real item
    assert set(raw["order_items"].item_id).issubset(items)
    # every order points at a real location
    assert set(raw["orders"].location_id).issubset(locs)


def test_dashboard_payload_present():
    p = ROOT / "outputs" / "dashboard_data.json"
    assert p.exists(), "run the pipeline first (python run_all.py)"
    d = json.load(open(p))
    for key in ["kpis", "menu", "forecast", "segments", "models",
                "churn", "peak", "forecast_groups"]:
        assert key in d, f"missing dashboard section: {key}"
    assert d["kpis"]["total_orders"] >= 100_000
