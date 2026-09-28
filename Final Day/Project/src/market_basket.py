"""
Market-basket analysis.

Hand-rolled association-rule mining (no mlxtend dependency) over item pairs:
support, confidence and lift for every pair that clears a minimum support.
Lift > 1 means the two items sell together more than chance would predict.
"""
from itertools import combinations
from collections import Counter
import pandas as pd


def rules(fact, min_support=0.004, top=20):
    # build baskets = set of items per order
    baskets = fact.groupby("order_id", observed=True).item_id.apply(set)
    n = len(baskets)

    single = Counter()
    pair = Counter()
    for items in baskets:
        for i in items:
            single[i] += 1
        for a, b in combinations(sorted(items), 2):
            pair[(a, b)] += 1

    name = dict(zip(fact.item_id, fact.name))

    def _mine(supp):
        rows = []
        for (a, b), c in pair.items():
            sup = c / n
            if sup < supp:
                continue
            conf = c / single[a]          # P(b | a)
            lift = conf / (single[b] / n)
            rows.append({
                "a_id": a, "b_id": b,
                "a": name.get(a, a), "b": name.get(b, b),
                "support": round(sup, 4),
                "confidence": round(conf, 3),
                "lift": round(lift, 2),
            })
        return rows

    # with 150 items pairs get sparse - relax the support floor until we surface
    # a useful number of rules (still an honest support figure, just a lower bar).
    supp = min_support
    out = _mine(supp)
    while len(out) < top and supp > 0.0004:
        supp /= 2
        out = _mine(supp)

    df = pd.DataFrame(out)
    if df.empty:
        return df
    return df.sort_values("lift", ascending=False).head(top).reset_index(drop=True)
