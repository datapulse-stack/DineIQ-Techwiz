"""
RFM + customer segmentation.

Two steps:
  1. classic RFM scoring (1-5 on each of Recency, Frequency, Monetary via quintiles)
  2. KMeans on the scaled RFM space to find natural groups, which we then name
     with human labels based on each cluster's centre.
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from src import config as C


def rfm_scores(cust):
    df = cust.copy()
    # recency: lower is better, so reverse the score
    df["R"] = pd.qcut(df.recency.rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    df["F"] = pd.qcut(df.frequency.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    df["M"] = pd.qcut(df.monetary.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    df["rfm_score"] = df[["R", "F", "M"]].mean(axis=1).round().astype(int)
    return df


def segment(cust, k=6):
    df = rfm_scores(cust)
    X = StandardScaler().fit_transform(df[["recency", "frequency", "monetary",
                                           "categories", "promo_share"]])
    km = KMeans(n_clusters=k, n_init=10, random_state=C.SEED)
    df["cluster"] = km.fit_predict(X)

    # name clusters from their profile - the busiest/richest = loyal, etc.
    prof = df.groupby("cluster").agg(
        recency=("recency", "mean"), frequency=("frequency", "mean"),
        monetary=("monetary", "mean"), promo=("promo_share", "mean"),
        n=("customer_id", "count")).reset_index()

    names = {}
    ranked_money = prof.sort_values("monetary", ascending=False).cluster.tolist()
    for c in prof.cluster:
        row = prof[prof.cluster == c].iloc[0]
        if row.recency > prof.recency.mean() * 1.5 and row.frequency < prof.frequency.mean():
            names[c] = "At-Risk"
        elif c == ranked_money[0]:
            names[c] = "High-Value Loyal"
        elif row.promo > prof.promo.mean() * 1.25:
            names[c] = "Promotion-Driven"
        elif row.frequency > prof.frequency.mean():
            names[c] = "Frequent"
        elif row.recency < prof.recency.mean() * 0.6:
            names[c] = "New"
        else:
            names[c] = "Occasional"
    # de-duplicate names if two clusters map to the same label
    seen = {}
    for c in prof.sort_values("monetary", ascending=False).cluster:
        base = names[c]
        if base in seen.values():
            for alt in C.SEGMENT_ORDER:
                if alt not in seen.values():
                    names[c] = alt
                    break
        seen[c] = names[c]

    df["segment"] = df.cluster.map(names)
    return df
