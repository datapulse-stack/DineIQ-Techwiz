"""
Data integration.

Joins the cleaned tables into one wide "fact" table at the order-line grain -
every row is one item in one order, with its order, customer, location, category
and promotion context attached. Almost every downstream metric is a groupby on
this frame, so it's built once and reused.

At ~1.2M rows on a small box, memory matters: we store the repeated string keys
as pandas 'category' dtype and downcast the numerics, which keeps the whole fact
table to a couple hundred MB instead of pushing past a gigabyte.
"""
import pandas as pd

_CAT_COLS = ["order_id", "item_id", "customer_id", "location_id", "channel",
             "promotion_id", "name", "category_id", "category_name", "location_name"]


def build_fact(tables):
    orders = tables["orders"]
    oitems = tables["order_items"]
    items = tables["menu_items"]
    cats = tables["menu_categories"]
    locs = tables["locations"]

    fact = (oitems
            .merge(orders[["order_id", "customer_id", "location_id", "channel",
                           "order_ts", "promotion_id", "is_guest"]],
                   on="order_id", how="inner")
            .merge(items[["item_id", "name", "category_id", "base_price", "food_cost"]],
                   on="item_id", how="left")
            .merge(cats, on="category_id", how="left")
            .merge(locs.rename(columns={"name": "location_name"})[["location_id", "location_name"]],
                   on="location_id", how="left"))

    fact["order_ts"] = pd.to_datetime(fact.order_ts)
    fact["date"] = fact.order_ts.dt.date
    fact["hour"] = fact.order_ts.dt.hour.astype("int8")
    fact["dow"] = fact.order_ts.dt.dayofweek.astype("int8")
    fact["is_weekend"] = fact.dow >= 4
    # line economics (float32 is plenty of precision for money aggregates here)
    fact["revenue"] = fact.line_total.astype("float32")
    fact["cost"] = (fact.quantity * fact.food_cost).astype("float32")
    fact["profit"] = (fact.revenue - fact.cost).astype("float32")
    fact["has_promo"] = fact.promotion_id.astype(str).fillna("") != ""

    # shrink: repeated strings -> category codes, prices -> float32
    for c in _CAT_COLS:
        if c in fact.columns:
            fact[c] = fact[c].astype("category")
    for c in ["base_price", "food_cost", "unit_price", "line_total"]:
        if c in fact.columns:
            fact[c] = fact[c].astype("float32")
    if "quantity" in fact.columns:
        fact["quantity"] = fact.quantity.astype("int16")
    return fact
