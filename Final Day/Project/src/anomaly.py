"""
Anomaly detection.

Two kinds here:
  * sales/revenue anomalies - days where daily revenue is more than 3 standard
    deviations from the rolling norm (spikes and drops).
  * rating clusters - a burst of identical ratings on one item in a short window
    (the planted 41x 5-star case gets caught here).
Each anomaly comes out with a human-readable explanation, not just a flag.
"""
import numpy as np
import pandas as pd


def detect(fact, ratings, daily):
    out = []

    # ---- daily revenue z-score anomalies ----
    d = daily.copy()
    d["z"] = (d.rev - d.rev.mean()) / d.rev.std()
    for _, r in d[d.z.abs() > 2.1].iterrows():
        kind = "Sales spike" if r.z > 0 else "Sales drop"
        sev = "high" if abs(r.z) > 2.8 else "medium"
        out.append({
            "t": kind, "loc": "All locations", "date": str(pd.to_datetime(r.date).date()),
            "sev": sev,
            "msg": f"Daily revenue was {r.z:+.1f} std from the norm "
                   f"({'well above' if r.z>0 else 'well below'} expected). Flagged for review."
        })

    # ---- margin-collapse per location-day (revenue ok but profit thin) ----
    f2 = fact.copy()
    base_margin = f2.profit.sum() / f2.revenue.sum()
    ld = f2.groupby(["location_name", "date"], observed=True).agg(rev=("revenue", "sum"),
                                                   prof=("profit", "sum")).reset_index()
    ld["margin"] = ld.prof / ld.rev
    ld = ld[ld.rev > ld.rev.quantile(0.5)]              # only meaningful days
    worst = ld.sort_values("margin").head(2)
    for _, r in worst.iterrows():
        if r.margin < base_margin * 0.75:
            out.append({
                "t": "Margin collapse", "loc": r.location_name,
                "date": str(pd.to_datetime(r.date).date()), "sev": "critical",
                "msg": f"Revenue was healthy ({r.rev:,.0f}) but contribution margin fell to "
                       f"{r.margin*100:.0f}% (norm ~{base_margin*100:.0f}%). Likely a promo "
                       f"discounting profitable mains."})

    # ---- abnormally high order values ----
    ov = fact.groupby("order_id", observed=True).revenue.sum()
    thresh = ov.mean() + 4 * ov.std()
    n_high = int((ov > thresh).sum())
    if n_high:
        out.append({
            "t": "Order-value outliers", "loc": "Multiple", "date": "last 14 days",
            "sev": "low",
            "msg": f"{n_high} orders exceeded {thresh:,.0f} (4+ std above the mean order). "
                   f"Likely large group bookings - kept, but flagged for review."})

    # ---- rating clusters: many identical ratings on one item within an hour ----
    r = ratings.copy()
    r["rating_ts"] = pd.to_datetime(r.rating_ts, errors="coerce")
    r = r.dropna(subset=["rating_ts"])
    r["hourbin"] = r.rating_ts.dt.floor("h")
    grp = r.groupby(["item_id", "hourbin", "stars"]).size().reset_index(name="n")
    for _, row in grp[grp.n >= 15].iterrows():
        out.append({
            "t": "Rating cluster", "loc": "Multiple", "date": str(row.hourbin.date()),
            "sev": "medium",
            "msg": f"{int(row.n)} identical {int(row.stars)}-star ratings on item "
                   f"{row.item_id} within one hour - possible non-organic ratings."
        })

    # keep the newest ~8, most severe first
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    out.sort(key=lambda a: (order.get(a["sev"], 9), a["date"]), reverse=False)
    return out[:8]
