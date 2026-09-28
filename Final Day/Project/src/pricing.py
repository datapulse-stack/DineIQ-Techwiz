"""
Price intelligence & sensitivity.

For each item we look at how weekly demand moved against its price over the
window (prices change thanks to the pricing-history table). The slope of
log(demand) vs log(price) is a rough price elasticity. More negative = more
sensitive. Items with too few distinct price points fall back to a category
prior so we never fabricate a precise number from nothing.
"""
import numpy as np
import pandas as pd


def elasticity(fact):
    f = fact.copy()
    f["date"] = pd.to_datetime(f.date)
    f["week"] = f.date.dt.isocalendar().week
    out = []
    for iid, grp in f.groupby("item_id", observed=True):
        wk = grp.groupby("week").agg(qty=("quantity", "sum"),
                                     price=("unit_price", "mean")).reset_index()
        wk = wk[(wk.qty > 0) & (wk.price > 0)]
        name = grp.name.iloc[0]
        cat = grp.category_id.iloc[0]
        if wk.price.nunique() >= 3:
            # elasticity = d(log q)/d(log p)
            lp, lq = np.log(wk.price.values), np.log(wk.qty.values)
            slope = np.polyfit(lp, lq, 1)[0]
            elast = float(np.clip(slope, -4, 1))
            basis = "observed"
        else:
            elast = -0.9        # neutral category prior
            basis = "prior (few price points)"
        if elast < -1.4:
            sens = "Highly Price Sensitive"
        elif elast < -0.8:
            sens = "Moderately Price Sensitive"
        else:
            sens = "Low Price Sensitivity"
        out.append({"item_id": iid, "name": name, "category_id": cat,
                    "elasticity": round(elast, 2), "sensitivity": sens, "basis": basis})
    return pd.DataFrame(out).sort_values("elasticity").reset_index(drop=True)


def price_demand_curve(fact, item_id):
    """binned price->avg weekly demand, for the little curve on the pricing page."""
    f = fact[fact.item_id == item_id].copy()
    f["date"] = pd.to_datetime(f.date)
    f["week"] = f.date.dt.isocalendar().week
    wk = f.groupby("week").agg(qty=("quantity", "sum"), price=("unit_price", "mean")).reset_index()
    wk = wk.sort_values("price")
    return {"item": f.name.iloc[0] if len(f) else item_id,
            "prices": wk.price.round(2).tolist(), "demand": wk.qty.tolist()}
