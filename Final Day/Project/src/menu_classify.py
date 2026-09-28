"""
Menu performance classification.

The rule the SRS keeps stressing: high sales alone must NOT make a dish a winner.
So we score demand and profitability on a 0..1 scale relative to the whole menu,
knock profit down for wastage and poor ratings, then split into four quadrants.
Nothing keys off a single hard-coded column - change the thresholds in config to
re-shape the buckets.
"""
import numpy as np
from src import config as C


def _norm(s):
    lo, hi = s.min(), s.max()
    if hi == lo:
        return s * 0 + 0.5
    return (s - lo) / (hi - lo)


def classify(feat):
    df = feat.copy()
    df["demand_score"] = _norm(df["qty"])
    profit = _norm(df["margin"]).astype(float)
    # wastage eats effective profitability; weak ratings hurt too
    profit = profit - (df["wastage_pct"] / 100) * 0.9
    profit = profit - np.where(df["rating"] < 3.6, 0.12, 0.0)
    df["profit_score"] = profit

    hiD = df.demand_score >= C.DEMAND_CUT
    hiP = df.profit_score >= C.PROFIT_CUT

    def label(row_hiD, row_hiP):
        if row_hiD and row_hiP:
            return "Profit Driver"
        if row_hiD and not row_hiP:
            return "Volume Driver"
        if not row_hiD and row_hiP:
            return "Hidden Opportunity"
        return "Low Performer"

    df["klass"] = [label(d, p) for d, p in zip(hiD, hiP)]

    # slow-mover flag: weak on volume AND (waste-heavy or trending down)
    df["slow_mover"] = (df.demand_score < 0.35) & ((df.wastage_pct > 8) | (df.trend < 0))
    return df
