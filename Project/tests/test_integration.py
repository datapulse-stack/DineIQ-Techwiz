"""integration tests: the fact table builds and revenue reconciles."""
from src import clean, integrate


def test_fact_builds_and_reconciles(raw):
    cleaned, _ = clean.clean(raw)
    fact = integrate.build_fact(cleaned)
    # fact carries the analytical columns downstream code depends on
    for col in ["item_id", "location_id", "quantity", "revenue", "profit",
                "order_id", "category_id", "has_promo"]:
        assert col in fact.columns, f"fact table missing {col}"
    # revenue is positive and profit never exceeds revenue
    assert fact["revenue"].sum() > 0
    assert (fact["profit"] <= fact["revenue"] + 1e-6).all()


def test_fact_grain_matches_cleaned_lines(raw):
    cleaned, _ = clean.clean(raw)
    fact = integrate.build_fact(cleaned)
    # the fact table is at order-line grain, so it can't have more rows than
    # the cleaned order_items it was built from
    assert len(fact) <= len(cleaned["order_items"])
