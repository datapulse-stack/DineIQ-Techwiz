"""
Promotion effectiveness + trap detection.

A sales bump is not success. For each promotion we compare orders that used it
against the baseline and check what happened to CONTRIBUTION MARGIN, not just
revenue. If sales go up while margin collapses, it's flagged as a trap.
"""
import numpy as np
import pandas as pd


def analyse(fact, promos):
    f = fact.copy()
    baseline_margin = (f.profit.sum() / f.revenue.sum())    # overall margin ratio
    baseline_aov = f.groupby("order_id").revenue.sum().mean()

    out = []
    for _, p in promos.iterrows():
        pid = p.promotion_id
        used = f[f.promotion_id == pid]
        if used.empty:
            continue
        margin = used.profit.sum() / used.revenue.sum()
        orders_share = used.order_id.nunique()
        aov = used.groupby("order_id").revenue.sum().mean()
        sales_lift = round((orders_share / f.order_id.nunique()) * 100, 1)
        margin_gap = round((margin - baseline_margin) * 100, 1)   # points vs baseline

        # verdict logic: a discount ALWAYS trims margin a little - that's fine.
        # a "trap" is when margin collapses hard, not when it dips a couple of points.
        if margin_gap <= -9:
            verdict, note = "TRAP", "Margin collapses - discount is eating profitable items"
        elif margin < 0.50:
            verdict, note = "TRAP", "Promoted orders barely break even"
        elif margin >= 0.58 and sales_lift >= 6:
            verdict, note = "GOOD", "Healthy margin held while driving volume"
        else:
            verdict, note = "OK", "Works, but margin is on the thin side"

        out.append({
            "promotion": p["name"], "type": p["type"], "discount": int(p.discount_pct),
            "sales_lift": sales_lift, "margin_gap": margin_gap,
            "aov": round(float(aov), 2), "verdict": verdict, "note": note,
        })
    return pd.DataFrame(out)
