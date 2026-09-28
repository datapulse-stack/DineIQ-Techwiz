"""shared fixtures for the DineIQ test-suite."""
import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RAW = ROOT / "raw_data"
PROCESSED = ROOT / "processed_data"


@pytest.fixture(scope="session")
def raw():
    """load the raw tables once for the whole session."""
    names = ["menu_categories", "menu_items", "locations", "promotions",
             "pricing_history", "customers", "orders", "order_items",
             "ratings", "inventory", "wastage"]
    return {n: pd.read_csv(RAW / f"{n}.csv") for n in names}


@pytest.fixture
def defective_raw():
    """a tiny but COMPLETE raw dict with deliberately injected defects, used to
    prove the cleaning rules catch them (boundary / hidden-defect readiness).

    injected defects: a duplicate order-line, a negative quantity, a zero
    quantity, a negative price, an unknown/none item reference, an out-of-range
    rating, a negative wastage row, and a guest (missing customer) order.
    """
    order_items = pd.DataFrame({
        "order_item_id": ["A1", "A1", "A2", "A3", "A4", "A5"],  # A1 duplicated
        "order_id":      ["O1", "O1", "O2", "O3", "O4", "O5"],
        "item_id":       ["M001", "M001", "M002", "M003", "ZZZ", "M002"],  # ZZZ unknown
        "quantity":      [2, 2, -1, 0, 3, 1],                    # negative + zero qty
        "unit_price":    [9.5, 9.5, 5.0, -4.0, 7.0, 6.0],        # a negative price
        "discount_pct":  [0, 0, 0, 0, 0, 0],
        "line_total":    [19.0, 19.0, -5.0, 0.0, 21.0, 6.0],
    })
    orders = pd.DataFrame({
        "order_id":    ["O1", "O2", "O3", "O4", "O5"],
        "customer_id": ["C1", "C2", None, "C4", "C5"],          # O3 is a guest
        "location_id": ["L01"] * 5,
        "channel":     ["Dine-in"] * 5,
        "order_ts":    ["2026-01-01 12:00:00"] * 5,
        "promotion_id": [None] * 5,
        "total_amount": [19, 5, 0, 21, 6],
        "status":      ["completed"] * 5,
    })
    return {
        "order_items": order_items,
        "orders": orders,
        "menu_items": pd.DataFrame({"item_id": ["M001", "M002", "M003"],
                                    "name": ["A", "B", "C"],
                                    "category_id": ["C01", "C01", "C02"],
                                    "base_price": [9.5, 6.0, 8.0],
                                    "food_cost": [3.0, 2.0, 3.0]}),
        "pricing_history": pd.DataFrame({"item_id": ["M001"], "price": [9.5],
                                         "effective_date": ["2026-01-01"]}),
        "ratings": pd.DataFrame({"rating_id": ["R1", "R2"], "item_id": ["M001", "M002"],
                                 "customer_id": ["C1", "C2"], "location_id": ["L01", "L01"],
                                 "stars": [5, 9], "rating_ts": ["2026-01-01 13:00:00"] * 2}),
        "wastage": pd.DataFrame({"wastage_id": ["W1", "W2"], "item_id": ["M001", "M002"],
                                 "location_id": ["L01", "L01"], "date": ["2026-01-01"] * 2,
                                 "wasted_qty": [2, -3], "reason": ["spoil", "spoil"],
                                 "cost": [4.0, 6.0]}),
    }
