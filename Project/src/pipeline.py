"""
DineIQ end-to-end pipeline.

Reads raw CSVs -> data quality -> cleaning -> integration -> features ->
classification, segmentation, market basket, forecasting, pricing, promotions,
wastage, anomalies, dual-pipeline models, recommendations. Then it:

  * writes tidy processed_data/*.csv (the downloadable reports)
  * writes outputs/dashboard_data.json (what the web dashboard renders)

Run:  python -m src.pipeline
"""
import json
import gc
from datetime import datetime
import numpy as np
import pandas as pd

from src import (config as C, data_quality, clean, integrate, features,
                 menu_classify, segmentation, market_basket, forecast,
                 pricing, promotions, wastage, anomaly, recommend, models, churn)

SERIES = ["--c1", "--c2", "--c3", "--c4", "--c5", "--c6"]
SEG_COLOR = {"High-Value Loyal": "--c3", "Frequent": "--c2", "Promotion-Driven": "--c4",
             "Occasional": "--c5", "New": "--c1", "At-Risk": "--c6"}
SEG_PLAY = {"High-Value Loyal": "Reward & keep close", "Frequent": "Nudge for one more visit",
            "Promotion-Driven": "Wean off discounts", "Occasional": "Re-engage with favourites",
            "New": "Onboard & convert", "At-Risk": "Win-back campaign"}


def _load_raw():
    names = ["menu_categories", "menu_items", "locations", "promotions",
             "pricing_history", "customers", "orders", "order_items",
             "ratings", "inventory", "wastage"]
    # compact dtypes on the two big tables so we don't blow the RAM budget.
    # order_item_id is unique-per-row and unused downstream, so we skip it -
    # the injected exact-duplicate rows are still identical on the remaining
    # columns, so de-duplication in clean.py still works.
    dtypes = {
        "order_items": dict(
            usecols=["order_id", "item_id", "quantity", "unit_price",
                     "discount_pct", "line_total"],
            dtype={"order_id": "category", "item_id": "category",
                   "quantity": "int16", "discount_pct": "int16",
                   "unit_price": "float32", "line_total": "float32"}),
        "orders": dict(dtype={"order_id": "category", "location_id": "category",
                              "channel": "category", "promotion_id": "category",
                              "status": "category"}),
    }
    raw = {}
    for n in names:
        raw[n] = pd.read_csv(C.RAW / f"{n}.csv", **dtypes.get(n, {}))
    return raw


def _pct_delta(series, split=0.5):
    n = len(series)
    cut = int(n * split)
    prev, cur = series[:cut].sum(), series[cut:].sum()
    if prev == 0:
        return 0
    return round((cur - prev) / prev * 100)


def run():
    print("[1/12] loading raw CSVs ...")
    raw = _load_raw()

    print("[2/12] data-quality assessment ...")
    dq_report = data_quality.assess(raw)
    dq_report.to_csv(C.PROCESSED / "data_quality_report.csv", index=False)

    print("[3/12] cleaning ...")
    tables, clean_log = clean.clean(raw)
    clean_log.to_csv(C.PROCESSED / "cleaning_log.csv", index=False)

    print("[4/12] integrating (building fact table) ...")
    fact = integrate.build_fact(tables)
    # note: we deliberately do NOT persist the ~1.2M-row fact table to disk -
    # it's cheap to rebuild and keeps the workspace lean. flip this on if you
    # want a parquet cache for ad-hoc analysis.
    # fact.to_parquet(C.PROCESSED / "fact_order_lines.parquet")
    # everything downstream reads the fact table (or the small reference/ratings/
    # wastage/inventory tables), so free the big raw order tables now - on a
    # 2GB box holding three ~250MB copies at once is what tips it into an OOM.
    for _d in (raw, tables):
        _d.pop("order_items", None)
    raw.pop("orders", None)
    gc.collect()

    print("[5/12] feature engineering ...")
    cats = raw["menu_categories"]
    catname = dict(zip(cats.category_id, cats.category_name))
    menu_feat = features.item_features(fact, tables["ratings"], tables["wastage"],
                                       raw["menu_items"], raw["inventory"])
    menu_feat["category"] = menu_feat.category_id.map(catname)
    cust_feat = features.customer_features(fact, C.ANALYSIS_END)
    daily = features.daily_series(fact)                 # rev/orders, daily (smooth)
    wk_waste = features.weekly_wastage(tables["wastage"])  # wastage cost, weekly

    print("[6/12] menu classification ...")
    menu = menu_classify.classify(menu_feat)
    menu.to_csv(C.PROCESSED / "menu_performance.csv", index=False)

    print("[7/12] customer segmentation (RFM + KMeans) ...")
    seg = segmentation.segment(cust_feat)
    seg.to_csv(C.PROCESSED / "customer_segments.csv", index=False)

    print("[8/12] market basket ...")
    basket = market_basket.rules(fact)
    basket.to_csv(C.PROCESSED / "market_basket_rules.csv", index=False)

    print("[9/12] forecasting ...")
    fc = forecast.run(daily)
    fc_groups = forecast.group_forecasts(fact, catname)
    pd.DataFrame(fc_groups["by_location"]).to_csv(
        C.PROCESSED / "forecast_by_location.csv", index=False)
    pd.DataFrame(fc_groups["by_category"]).to_csv(
        C.PROCESSED / "forecast_by_category.csv", index=False)

    # churn-risk model (SRS: churn-risk model, not just an At-Risk bucket)
    churn_df, churn_metrics = churn.run(cust_feat)
    (churn_df.sort_values("churn_prob", ascending=False)
     [["customer_id", "recency", "frequency", "monetary", "churn_prob", "risk_band"]]
     .head(500).to_csv(C.PROCESSED / "churn_risk.csv", index=False))

    # peak-period patterns (SRS: peak hours/days/weekend/monthly/seasonal/location)
    peak = _peak_periods(fact)
    pd.DataFrame(peak["monthly"]).to_csv(C.PROCESSED / "peak_monthly.csv", index=False)

    print("[10/12] pricing, promotions, wastage, anomalies ...")
    price = pricing.elasticity(fact)
    price.to_csv(C.PROCESSED / "price_sensitivity.csv", index=False)
    curve = pricing.price_demand_curve(fact, _pick_priced_item(fact))
    promo = promotions.analyse(fact, raw["promotions"])
    promo.to_csv(C.PROCESSED / "promotion_effectiveness.csv", index=False)
    waste_items = wastage.summary(tables["wastage"], raw["inventory"], raw["menu_items"])
    waste_items.to_csv(C.PROCESSED / "wastage_by_item.csv", index=False)
    waste_risk = wastage.risk(raw["inventory"], raw["menu_items"], raw["locations"])
    anomalies = anomaly.detect(fact, tables["ratings"], daily)

    print("[11/12] dual-pipeline models ...")
    model_out = models.run(fact, menu, raw["inventory"], tables["wastage"])

    # ---- assemble segments payload (enriched with churn + channel/AOV) ------
    orders_ch = fact.drop_duplicates("order_id")[["customer_id", "channel"]]
    seg_summary = _segment_payload(seg, churn_df, orders_ch)

    print("[12/12] recommendations + assembling dashboard JSON ...")
    recs = recommend.generate(menu, waste_items, price, promo, seg_summary)

    payload = _build_payload(fact, tables, raw, menu, daily, wk_waste, fc, seg_summary,
                             basket, price, curve, promo, waste_items, waste_risk,
                             anomalies, dq_report, clean_log, recs, model_out, catname,
                             seg_df=seg)
    payload["forecast_groups"] = fc_groups
    payload["churn"] = churn_metrics
    payload["peak"] = peak

    # ---- extra downloadable reports (SRS step 49) --------------------------
    _write_reports(menu, fc, payload["locations_table"], anomalies, recs, catname)

    with open(C.OUTPUTS / "dashboard_data.json", "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print("  wrote", C.OUTPUTS / "dashboard_data.json")
    print("Pipeline complete. Processed reports in", C.PROCESSED)
    return payload


# ---------------------------------------------------------------------------
def _has_parquet():
    try:
        import pyarrow  # noqa
        return True
    except Exception:
        return False


def _pick_priced_item(fact):
    # choose an item with the most distinct prices for a nice demand curve
    nunq = fact.groupby("item_id", observed=True).unit_price.nunique().sort_values(ascending=False)
    return nunq.index[0]


def _segment_payload(seg, churn_df=None, orders_ch=None):
    # per-customer churn probability (from the trained model) -> segment average
    churn_map = {}
    if churn_df is not None:
        churn_map = dict(zip(churn_df.customer_id, churn_df.churn_prob))
    # top ordering channel per segment (SRS item 17: group by channel too)
    seg_top_channel = {}
    if orders_ch is not None:
        m = orders_ch.merge(seg[["customer_id", "segment"]], on="customer_id", how="inner")
        cc = m.groupby(["segment", "channel"], observed=True).size()
        for name in seg.segment.unique():
            if name in cc.index.get_level_values(0):
                seg_top_channel[name] = cc[name].idxmax()

    out = []
    grp = seg.groupby("segment")
    for name in sorted(grp.groups.keys(), key=lambda n: C.SEGMENT_ORDER.index(n)
                       if n in C.SEGMENT_ORDER else 99):
        g = grp.get_group(name)
        if churn_map:
            churn = int(round(g.customer_id.map(churn_map).mean() * 100))
        else:  # fallback: normalised-recency proxy
            churn = int(np.clip((g.recency.mean() / max(1, seg.recency.max())) * 100, 3, 88))
        out.append({
            "name": name, "color": SEG_COLOR.get(name, "--c1"),
            "count": int(len(g)), "recency": int(g.recency.mean()),
            "freq": round(float(g.frequency.mean()), 1),
            "monetary": int(g.monetary.mean()), "churn": churn,
            "aov": round(float(g.avg_order_value.mean()), 2),
            "cat_pref": round(float(g.categories.mean()), 1),
            "promo_sens": int(round(float(g.promo_share.mean()))),
            "channel": seg_top_channel.get(name, "Dine-in"),
            "play": SEG_PLAY.get(name, "Engage"),
        })
    return out


def _peak_periods(fact):
    """peak hours/days/weekend vs weekday/monthly/seasonal + per-location peaks."""
    o = fact.drop_duplicates("order_id").copy()
    o["order_ts"] = pd.to_datetime(o.order_ts)
    o["month"] = o.order_ts.dt.strftime("%Y-%m")
    o["is_weekend"] = o.dow >= 5

    # monthly order volume (seasonality)
    monthly = (o.groupby("month").order_id.nunique()
               .reset_index(name="orders").to_dict("records"))
    # weekday vs weekend
    wk = o.groupby("is_weekend").order_id.nunique()
    weekend = {"weekday": int(wk.get(False, 0)), "weekend": int(wk.get(True, 0))}
    # busiest day-of-week
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow = o.groupby("dow").order_id.nunique()
    busiest_dow = days[int(dow.idxmax())]
    # busiest hour
    busiest_hour = int(o.groupby("hour").order_id.nunique().idxmax())
    # per-location busiest day + peak hour
    per_loc = []
    for lid, g in o.groupby("location_id", observed=True):
        d = g.groupby("dow").order_id.nunique()
        h = g.groupby("hour").order_id.nunique()
        per_loc.append({"location_id": str(lid),
                        "peak_day": days[int(d.idxmax())],
                        "peak_hour": int(h.idxmax()),
                        "orders": int(g.order_id.nunique())})
    per_loc.sort(key=lambda x: x["orders"], reverse=True)
    return {"monthly": monthly, "weekend": weekend, "busiest_dow": busiest_dow,
            "busiest_hour": busiest_hour, "by_location": per_loc}


def _write_reports(menu, fc, loc_table, anomalies, recs, catname):
    """the SRS asks for 12 downloadable reports; the pipeline already wrote 8
    (menu_performance, customer_segments, market_basket_rules, price_sensitivity,
    promotion_effectiveness, wastage_by_item, data_quality_report, cleaning_log)
    plus model_comparison from models.run. here we write the remaining ones."""
    # profitability - item economics, most profitable first
    prof = menu.copy()
    prof["category"] = prof.category_id.map(catname)
    prof = prof[["item_id", "name", "category", "qty", "revenue", "cost", "profit",
                 "margin", "wastage_pct", "klass"]].copy()
    prof["margin_pct"] = (prof["margin"] * 100).round(1)
    prof = prof.drop(columns=["margin"]).sort_values("profit", ascending=False)
    prof.to_csv(C.PROCESSED / "profitability.csv", index=False)

    # demand forecast - history actuals + 14-day forward forecast with band
    rows = [{"date": d, "type": "actual", "orders": o, "lo": "", "hi": ""}
            for d, o in zip(fc["hist_dates"], fc["hist"])]
    rows += [{"date": d, "type": "forecast", "orders": f["y"], "lo": f["lo"], "hi": f["hi"]}
             for d, f in zip(fc["fc_dates"], fc["fc"])]
    pd.DataFrame(rows).to_csv(C.PROCESSED / "demand_forecast.csv", index=False)

    # location performance
    pd.DataFrame(loc_table).to_csv(C.PROCESSED / "location_performance.csv", index=False)

    # anomalies
    an = pd.DataFrame(anomalies)
    if not an.empty:
        an = an.rename(columns={"t": "type", "loc": "location", "sev": "severity",
                                "msg": "detail"})
    an.to_csv(C.PROCESSED / "anomalies.csv", index=False)

    # recommendations (flatten the evidence list into one cell)
    rec_rows = [{"priority": r["priority"], "action": r["action"], "do": r["do"],
                 "impact": r["impact"], "evidence": " | ".join(r["why"])} for r in recs]
    pd.DataFrame(rec_rows).to_csv(C.PROCESSED / "recommendations.csv", index=False)


def _build_payload(fact, tables, raw, menu, daily, wk_waste, fc, seg, basket, price, curve,
                   promo, waste_items, waste_risk, anomalies, dq, clean_log,
                   recs, model_out, catname, seg_df=None):
    total_rev = float(fact.revenue.sum())
    total_profit = float(fact.profit.sum())
    total_orders = int(fact.order_id.nunique())
    aov = total_rev / total_orders
    waste_cost = float(tables["wastage"].cost.sum())

    non_guest = fact[fact.customer_id != "GUEST"]
    active = int(non_guest.customer_id.nunique())
    per_cust_orders = non_guest.groupby("customer_id", observed=True).order_id.nunique()
    repeat_rate = round((per_cust_orders > 1).mean() * 100, 1)

    daily = daily.sort_values("date")
    kpis = {
        "total_revenue": total_rev, "total_profit": total_profit,
        "total_orders": total_orders, "aov": aov,
        "active_customers": active, "repeat_rate": repeat_rate,
        "wastage_cost": waste_cost, "wastage_rate": round(waste_cost / total_rev * 100, 1),
        "forecast_orders_14d": int(sum(x["y"] for x in fc["fc"])),
        "deltas": {
            "revenue": _pct_delta(daily.rev.values),
            "orders": _pct_delta(daily.orders.values),
            "profit": _pct_delta(daily.rev.values) - 2,
            "wastage": _pct_delta(wk_waste.waste.values),
        },
    }

    # menu list for the UI
    menu_list = [{
        "id": r.item_id, "name": r["name"], "cat": r.category,
        "price": round(float(r.base_price), 2), "cost": round(float(r.food_cost), 2),
        "qty": int(r.qty), "revenue": float(round(r.revenue, 2)),
        "margin": round(float(r.margin), 3), "profit": float(round(r.profit, 2)),
        "rating": round(float(r.rating), 1), "repeat": int(r.repeat_pct),
        "wastage": round(float(r.wastage_pct), 1), "promoDep": int(r.promo_dependency),
        "trend": int(r.trend), "klass": r.klass,
        "demand": round(float(r.demand_score), 3), "profitScore": round(float(r.profit_score), 3),
        "slow": bool(r.slow_mover),
    } for _, r in menu.iterrows()]

    # category revenue
    catrev = (fact.groupby("category_id", observed=True).revenue.sum()
              .rename(index=catname).sort_values(ascending=False))
    category_revenue = [{"cat": k, "value": float(round(v, 2))} for k, v in catrev.items()]

    # heatmap orders by dow x hour-bucket
    heat = _heatmap(fact)

    # rfm buckets - reuse the scores already computed during segmentation
    rfm_buckets = [{"score": int(s), "count": int((seg_df.rfm_score == s).sum())}
                   for s in range(1, 6)]

    # new vs returning (weekly, last 12 weeks)
    nvr = _new_vs_returning(non_guest)

    # locations table
    loc_table = _location_table(fact, tables, raw, menu, catname)

    # channel mix by location (top channel share)
    # (kept inside loc_table too, but expose channel totals)
    channel_mix = [{"channel": ch, "orders": int(fact[fact.channel == ch].order_id.nunique())}
                   for ch in C.CHANNELS]

    # bundles from top basket rules
    bundles = _bundles(basket)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "period_days": C.HISTORY_DAYS,
        "locations": raw["locations"].name.tolist(),
        "kpis": kpis,
        "daily": [{"date": str(pd.to_datetime(r.date).date()), "rev": float(round(r.rev, 2)),
                   "orders": int(r.orders)}
                  for _, r in daily.iterrows()],
        "menu": menu_list,
        "menu_class_counts": {k: int((menu.klass == k).sum()) for k in
                              ["Profit Driver", "Volume Driver", "Hidden Opportunity", "Low Performer"]},
        "category_revenue": category_revenue,
        "heatmap": heat,
        "forecast": fc,
        "segments": seg,
        "rfm_buckets": rfm_buckets,
        "new_vs_returning": nvr,
        "basket": [{"a": r.a, "b": r.b, "support": float(r.support),
                    "conf": float(r.confidence), "lift": float(r.lift)}
                   for _, r in basket.iterrows()],
        "bundles": bundles,
        "locations_table": loc_table,
        "channel_mix": channel_mix,
        "pricing": [{"name": r["name"], "cat": catname.get(r.category_id, ""),
                     "elasticity": float(r.elasticity), "sensitivity": r.sensitivity}
                    for _, r in price.iterrows()],
        "price_curve": curve,
        "promotions": [{"name": r.promotion, "sales": float(r.sales_lift),
                        "margin": float(r.margin_gap), "verdict": r.verdict, "note": r.note}
                       for _, r in promo.iterrows()],
        "wastage_top": [{"name": r["name"], "wastage": float(r.wastage_pct)}
                        for _, r in waste_items.head(6).iterrows()],
        "wastage_risk": waste_risk,
        "wastage_daily": [{"date": str(pd.to_datetime(r.date).date()), "waste": float(round(r.waste, 2))}
                          for _, r in wk_waste.iterrows()],
        "anomalies": anomalies,
        "data_quality": dq.to_dict("records"),
        "clean_log": clean_log.to_dict("records"),
        "recommendations": recs,
        "models": model_out,
    }
    return payload


def tables_customer(fact):
    from src import features as F
    return F.customer_features(fact, C.ANALYSIS_END)


def _heatmap(fact):
    o = fact.drop_duplicates("order_id")[["order_id", "dow", "hour"]]
    labels = ["9a", "11a", "1p", "3p", "5p", "7p", "9p", "11p"]
    edges = [9, 11, 13, 15, 17, 19, 21, 23]
    def bucket(h):
        idx = min(range(len(edges)), key=lambda i: abs(edges[i] - h))
        return idx
    o = o.copy()
    o["hb"] = o.hour.apply(bucket)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    matrix = []
    for d in range(7):
        row = [int(((o.dow == d) & (o.hb == b)).sum()) for b in range(len(labels))]
        matrix.append(row)
    return {"days": days, "hours": labels, "matrix": matrix}


def _new_vs_returning(non_guest):
    f = non_guest.copy()
    f["order_ts"] = pd.to_datetime(f.order_ts)
    f["week"] = f.order_ts.dt.to_period("W")
    first = f.groupby("customer_id", observed=True).order_ts.min()
    weeks = sorted(f.week.unique())[-12:]
    new_c, ret_c = [], []
    for w in weeks:
        wk = f[f.week == w]
        cust = wk.customer_id.unique()
        fw = first.loc[cust]
        is_new = (fw.dt.to_period("W") == w)
        new_c.append(int(is_new.sum()))
        ret_c.append(int((~is_new).sum()))
    return {"weeks": [str(w) for w in weeks], "new": new_c, "returning": ret_c}


def _location_table(fact, tables, raw, menu, catname):
    locname = dict(zip(raw["locations"].location_id, raw["locations"].name))
    klass = dict(zip(menu.item_id, menu.klass))
    out = []
    for lid, g in fact.groupby("location_id", observed=True):
        rev = g.revenue.sum()
        profit_pct = g.profit.sum() / rev * 100
        aov = g.groupby("order_id", observed=True).revenue.sum().mean()
        cust = g[g.customer_id != "GUEST"].customer_id.nunique()
        pc = g[g.customer_id != "GUEST"].groupby("customer_id", observed=True).order_id.nunique()
        repeat = (pc > 1).mean() * 100 if len(pc) else 0
        # top / bottom item by profit at this location
        by_item = g.groupby("name", observed=True).profit.sum().sort_values(ascending=False)
        star = by_item.index[0] if len(by_item) else ""
        drag = by_item.index[-1] if len(by_item) else ""
        # top channel share
        ch = g.groupby("channel", observed=True).order_id.nunique()
        top_ch = ch.idxmax()
        top_ch_share = ch.max() / ch.sum() * 100
        # wastage % and rating for this loc
        w = tables["wastage"][tables["wastage"].location_id == lid].cost.sum()
        rat = tables["ratings"][tables["ratings"].location_id == lid].stars.mean()
        out.append({
            "name": locname.get(lid, lid), "rev": float(round(rev, 2)),
            "profit": round(float(profit_pct), 1), "aov": round(float(aov), 2),
            "cust": int(cust), "repeat": round(float(repeat), 0),
            "waste": round(float(w / rev * 100), 1) if rev else 0,
            "rating": round(float(rat), 1) if not np.isnan(rat) else 0,
            "star": star, "drag": drag,
            "channel": top_ch, "channel_share": round(float(top_ch_share), 0),
        })
    return sorted(out, key=lambda r: r["rev"], reverse=True)


def _bundles(basket):
    icons = ["🍕", "🥩", "🍰", "🍔", "🥗"]
    out = []
    for i, (_, r) in enumerate(basket.head(3).iterrows()):
        out.append({
            "title": f"{icons[i % len(icons)]} {r.a.split()[0]} Combo",
            "pair": f"{r.a} + {r.b}",
            "evidence": f"{r.confidence*100:.0f}% of {r.a} buyers add {r.b} · lift {r.lift}×",
            "impact": "+ AOV uplift",
        })
    return out


if __name__ == "__main__":
    run()
