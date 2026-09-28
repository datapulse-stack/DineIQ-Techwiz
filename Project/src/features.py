"""
Feature engineering.

Turns the order-line fact table into the analytical features the SRS lists:
per-item economics + behaviour, per-customer RFM inputs, and daily series.
These frames feed classification, segmentation, forecasting and the models.
"""
import numpy as np
import pandas as pd


def item_features(fact, ratings, wastage, items, inventory):
    g = fact.groupby("item_id", observed=True)
    feat = pd.DataFrame({
        "qty": g.quantity.sum(),
        "revenue": g.revenue.sum(),
        "cost": g.cost.sum(),
        "profit": g.profit.sum(),
        "orders": g.order_id.nunique(),
        "promo_lines": g.has_promo.sum(),
        "lines": g.size(),
    })
    feat["margin"] = (feat.revenue - feat.cost) / feat.revenue          # contribution margin ratio
    feat["promo_dependency"] = (feat.promo_lines / feat.lines * 100).round(1)

    # average rating per item
    r = ratings.groupby("item_id").stars.agg(["mean", "count"])
    feat["rating"] = r["mean"].round(2)
    feat["rating_count"] = r["count"]

    # wastage % = wasted / prepared, from inventory
    inv = inventory.groupby("item_id").agg(prepared=("prepared_qty", "sum"),
                                           consumed=("consumed_qty", "sum"))
    w = wastage.groupby("item_id").wasted_qty.sum()
    feat = feat.join(inv).join(w.rename("wasted"))
    feat["wastage_pct"] = (feat["wasted"] / feat["prepared"] * 100).round(1)

    # repeat purchase rate: share of buyers who bought the item more than once
    buyers = fact.groupby(["item_id", "customer_id"], observed=True).order_id.nunique()
    repeat = buyers.groupby("item_id", observed=True).apply(lambda s: (s > 1).mean() * 100, include_groups=False)
    feat["repeat_pct"] = repeat.round(0)

    # sales trend: last-third vs first-third of the window
    fact = fact.copy()
    fact["date"] = pd.to_datetime(fact.date)
    dmin, dmax = fact.date.min(), fact.date.max()
    third = (dmax - dmin) / 3
    early = fact[fact.date <= dmin + third].groupby("item_id", observed=True).quantity.sum()
    late = fact[fact.date > dmax - third].groupby("item_id", observed=True).quantity.sum()
    trend = ((late - early) / early.replace(0, np.nan) * 100)
    feat["trend"] = trend.round(0)

    feat = feat.join(items.set_index("item_id")[["name", "category_id", "base_price", "food_cost"]])
    cats = None  # category name filled by caller if needed
    feat = feat.reset_index().rename(columns={"index": "item_id"})
    feat = feat.fillna({"rating": 3.8, "rating_count": 0, "wastage_pct": 0,
                        "repeat_pct": 0, "trend": 0, "promo_dependency": 0})
    return feat


def customer_features(fact, analysis_end):
    """RFM building blocks per (non-guest) customer."""
    f = fact[fact.customer_id != "GUEST"].copy()
    f["order_ts"] = pd.to_datetime(f.order_ts)
    end = pd.to_datetime(analysis_end)
    g = f.groupby("customer_id", observed=True)
    cust = pd.DataFrame({
        "recency": (end - g.order_ts.max()).dt.days,
        "frequency": g.order_id.nunique(),
        "monetary": g.revenue.sum().round(2),
        "categories": f.groupby("customer_id", observed=True).category_id.nunique(),
        "promo_share": (g.has_promo.mean() * 100).round(0),
        "avg_order_value": (g.revenue.sum() / g.order_id.nunique()).round(2),
    })
    return cust.reset_index()


def daily_series(fact):
    f = fact.copy()
    f["date"] = pd.to_datetime(f.date)
    daily = f.groupby("date").agg(
        rev=("revenue", "sum"),
        orders=("order_id", "nunique"),
    ).reset_index()
    return daily


def daily_wastage(wastage):
    w = wastage.copy()
    w["date"] = pd.to_datetime(w.date)
    return w.groupby("date").cost.sum().reset_index().rename(columns={"cost": "waste"})


def weekly_wastage(wastage):
    """wastage cost per week (inventory/wastage is recorded at weekly grain)."""
    w = wastage.copy()
    w["date"] = pd.to_datetime(w.date)
    return (w.groupby("date").cost.sum().reset_index()
            .rename(columns={"cost": "waste"}).sort_values("date"))
