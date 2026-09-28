"""data-quality + boundary / hidden-defect tests."""
import pandas as pd
from src import clean, data_quality


def test_quality_report_flags_issues(raw):
    rep = data_quality.assess(raw)
    assert not rep.empty
    assert {"issue", "records", "action"}.issubset(rep.columns)


def test_cleaning_removes_bad_rows(defective_raw):
    """the cleaner must drop dup lines, impossible quantities, unknown items,
    out-of-range ratings and negative wastage, and flag guest orders."""
    cleaned, log = clean.clean(defective_raw)
    oi = cleaned["order_items"]
    assert (oi["quantity"] > 0).all(), "non-positive quantities survived cleaning"
    assert (oi["unit_price"] > 0).all(), "non-positive prices survived cleaning"
    assert oi.duplicated().sum() == 0, "duplicate order-line survived"
    # unknown item reference (ZZZ) must be quarantined
    assert "ZZZ" not in set(oi["item_id"])
    # ratings clamped to 1..5
    assert cleaned["ratings"]["stars"].between(1, 5).all()
    # negative wastage removed
    assert (cleaned["wastage"]["wasted_qty"] >= 0).all()
    # guest order flagged, not dropped
    assert (cleaned["orders"]["customer_id"] == "GUEST").any()


def test_full_clean_is_consistent(raw):
    cleaned, log = clean.clean(raw)
    oi = cleaned["order_items"]
    assert (oi["quantity"] > 0).all()
    assert (oi["unit_price"] > 0).all()
    assert not log.empty
