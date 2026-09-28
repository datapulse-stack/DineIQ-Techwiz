"""
Customer churn-risk model.

the SRS asks for a churn-risk model (not just an At-Risk bucket). we frame churn
as a supervised problem: a customer counts as churned when we haven't seen them
for noticeably longer than their own usual gap between visits. we then train a
logistic-regression classifier on behaviour features that DON'T include recency
(so the label isn't trivially leaked), score every customer's churn probability,
and band them low / medium / high.

outputs a per-customer churn table + headline metrics for the dashboard.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
from src import config as C

# features used to PREDICT churn - deliberately excludes recency (the label is
# derived from recency, so using it would be leakage).
FEATURES = ["frequency", "monetary", "categories", "promo_share", "avg_order_value"]


def run(cust):
    """cust = customer_features frame (has recency/frequency/monetary/... per customer)."""
    df = cust.copy()

    # label: churned if recency is beyond the 70th percentile of the base - i.e.
    # they've gone quiet relative to everyone else. a simple, defensible rule.
    cut = df.recency.quantile(0.70)
    df["churned"] = (df.recency > cut).astype(int)

    X = df[FEATURES].fillna(0).to_numpy(dtype="float64")
    y = df["churned"].to_numpy(dtype=int)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.3,
                                          random_state=C.SEED, stratify=y)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    proba_te = clf.predict_proba(Xte)[:, 1]
    acc = accuracy_score(yte, pred)
    try:
        auc = roc_auc_score(yte, proba_te)
    except ValueError:
        auc = float("nan")

    df["churn_prob"] = clf.predict_proba(Xs)[:, 1]
    df["risk_band"] = pd.cut(df.churn_prob, [-0.01, 0.35, 0.55, 1.01],
                             labels=["Low", "Medium", "High"]).astype(str)

    band_counts = df.risk_band.value_counts().to_dict()
    metrics = {
        "model": "Logistic Regression",
        "accuracy": round(float(acc), 3),
        "auc": None if np.isnan(auc) else round(float(auc), 3),
        "features": FEATURES,
        "churn_rule": f"recency > {int(cut)} days (70th pct)",
        "high_risk": int(band_counts.get("High", 0)),
        "medium_risk": int(band_counts.get("Medium", 0)),
        "low_risk": int(band_counts.get("Low", 0)),
        "n_customers": int(len(df)),
    }
    return df, metrics
