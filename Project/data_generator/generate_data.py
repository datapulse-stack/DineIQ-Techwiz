"""
DineIQ dataset generator.

Builds a believable, multi-table restaurant dataset and writes it to raw_data/
as CSV. This is synthetic on purpose - the real app would ingest the client's
POS export instead, but the schema is the same.

Sized to clear the SRS minimums (>=1M order-lines, >=100k orders, >=50k
customers, 150 items, 10 categories, 20 locations, 12 months, >=100k ratings,
>=50k wastage records). Because that's a lot of rows, the whole thing is
vectorised with numpy - no per-order python loops - so a full generate takes
seconds, not hours.

A few things worth calling out:
  * demand has weekday/weekend and lunch/dinner rhythm so peak-period analysis
    actually finds peaks.
  * every location gets its own popularity twist, so the same dish can be a star
    in one branch and a dud in another (the SRS wants that).
  * we intentionally inject dirty rows (missing ids, dupes, bad prices, negative
    quantities, impossible wastage) so the data-quality module has real work.

Run:  python -m data_generator.generate_data
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src import config as C

rng = np.random.default_rng(C.SEED)
END = datetime.fromisoformat(C.ANALYSIS_END)
START = END - timedelta(days=C.HISTORY_DAYS)


def _ids(prefix, n, width):
    """vectorised id builder e.g. O0000001 - fast for millions of rows."""
    return np.char.add(prefix, np.char.zfill((np.arange(n) + 1).astype(str), width))


# --------------------------------------------------------------------------
# 1. reference tables
# --------------------------------------------------------------------------
def build_reference():
    cats = pd.DataFrame({
        "category_id": [f"C{i+1:02d}" for i in range(len(C.CATEGORIES))],
        "category_name": C.CATEGORIES,
    })
    cat_id = dict(zip(cats.category_name, cats.category_id))

    items = pd.DataFrame({
        "item_id": [f"M{i+1:03d}" for i in range(len(C.DISHES))],
        "name": [d[0] for d in C.DISHES],
        "category_id": [cat_id[d[1]] for d in C.DISHES],
        "base_price": [d[2] for d in C.DISHES],
        "food_cost": [d[3] for d in C.DISHES],
        "popularity": [d[4] for d in C.DISHES],
    })

    locs = pd.DataFrame({
        "location_id": [f"L{i+1:02d}" for i in range(len(C.LOCATIONS))],
        "name": [l[0] for l in C.LOCATIONS],
        "city": [l[1] for l in C.LOCATIONS],
        # give each branch a demand multiplier - some are just busier
        "size_factor": np.round(rng.uniform(0.7, 1.4, len(C.LOCATIONS)), 2),
    })

    promos = pd.DataFrame({
        "promotion_id": [f"P{i+1:02d}" for i in range(len(C.PROMOTIONS))],
        "name": [p[0] for p in C.PROMOTIONS],
        "type": [p[1] for p in C.PROMOTIONS],
        "discount_pct": [p[2] for p in C.PROMOTIONS],
        "start_date": [(START + timedelta(days=int(rng.integers(0, 60)))).date() for _ in C.PROMOTIONS],
        "end_date": [END.date() for _ in C.PROMOTIONS],
    })
    return cats, items, locs, promos


# --------------------------------------------------------------------------
# 2. price history - several real price changes per item over the window
# --------------------------------------------------------------------------
def build_pricing_history(items):
    rows = []
    for _, it in items.iterrows():
        price = it.base_price
        rows.append((it.item_id, round(price, 2), START.date()))
        # 2-4 changes so there's genuine price movement to measure elasticity on
        n_changes = int(rng.integers(2, 5))
        days = sorted(int(rng.integers(20, C.HISTORY_DAYS - 5)) for _ in range(n_changes))
        for d in days:
            when = START + timedelta(days=d)
            price = round(price * rng.uniform(0.93, 1.13), 2)
            rows.append((it.item_id, price, when.date()))
    ph = pd.DataFrame(rows, columns=["item_id", "price", "effective_date"])
    ph["effective_date"] = pd.to_datetime(ph.effective_date)
    return ph.sort_values(["item_id", "effective_date"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 3. customers
# --------------------------------------------------------------------------
FIRST = ["Alex","Sam","Jordan","Taylor","Morgan","Casey","Riley","Jamie","Avery","Quinn",
         "Noah","Liam","Emma","Olivia","Ava","Sophia","Zoe","Omar","Aisha","Hana",
         "Yusuf","Bilal","Sara","Imran","Nadia","Leo","Mia","Ethan","Hina","Ali",
         "Maya","Ibrahim","Zara","Daniyal","Fatima","Hassan","Ayesha","Rohan","Priya","Arjun"]
LAST = ["Khan","Ahmed","Smith","Patel","Lee","Garcia","Nguyen","Brown","Malik","Shah",
        "Iqbal","Raza","Jones","Wang","Chen","Ali","Farooq","Butt","Sheikh","Baig",
        "Kumar","Singh","Hussain","Qureshi","Ansari","Williams","Kim","Lopez","Haider","Mirza"]


def build_customers(n=None):
    n = n or C.N_CUSTOMERS
    ids = _ids("U", n, 6)
    fi = rng.integers(0, len(FIRST), n)
    la = rng.integers(0, len(LAST), n)
    names = np.char.add(np.char.add(np.array(FIRST)[fi], " "), np.array(LAST)[la])
    # signups spread over the last ~2.5 years, some brand new
    offs = rng.integers(1, 900, n)
    signup = (np.datetime64(END.date()) - offs.astype("timedelta64[D]"))
    ctype = rng.choice(["loyal", "frequent", "promo", "occasional", "new"],
                       size=n, p=[0.14, 0.24, 0.18, 0.32, 0.12])
    return pd.DataFrame({"customer_id": ids, "name": names,
                         "signup_date": signup, "ctype": ctype})


# --------------------------------------------------------------------------
# 4. the big one - orders + order_items (fully vectorised)
# --------------------------------------------------------------------------
def build_orders(items, locs, promos, customers, pricing):
    days = pd.date_range(START, END, freq="D")
    ndays, nloc = len(days), len(locs)
    item_ids = items.item_id.to_numpy()
    n_items = len(item_ids)
    pop = items.popularity.to_numpy(dtype=float)

    # ---- how many orders per (day, location): demand rhythm ----------------
    dow = days.dayofweek.to_numpy()
    weekend = np.where(dow >= 4, 1.30, 1.0)           # Fri/Sat/Sun lift
    season = 1 + 0.10 * np.sin(np.arange(ndays) / 30.0)
    size_factor = locs.size_factor.to_numpy()
    lam = C.ORDERS_PER_CELL * (weekend * season)[:, None] * size_factor[None, :]
    counts = np.maximum(rng.poisson(lam), 1)          # [ndays, nloc]

    cell_day = np.repeat(np.arange(ndays), nloc)
    cell_loc = np.tile(np.arange(nloc), ndays)
    cell_n = counts.reshape(-1)
    day_of_order = np.repeat(cell_day, cell_n)
    loc_of_order = np.repeat(cell_loc, cell_n)
    N = day_of_order.size

    # ---- order timestamps: lunch + dinner peaks ---------------------------
    hour_choices = np.array([11,12,13,14,17,18,19,20,21,15,16,22])
    hour_p = np.array([0.10,0.15,0.13,0.05,0.08,0.14,0.16,0.09,0.05,0.02,0.02,0.01])
    hours = rng.choice(hour_choices, size=N, p=hour_p)
    minutes = rng.integers(0, 60, N)
    ts = (days.to_numpy()[day_of_order]
          + (hours * 60 + minutes).astype("timedelta64[m]"))

    # ---- channel ----------------------------------------------------------
    ch_idx = rng.choice(len(C.CHANNELS), size=N, p=C.CHANNEL_WEIGHTS)
    channel = np.array(C.CHANNELS)[ch_idx]

    # ---- who is ordering: pick a customer-type, then a customer -----------
    types = ["loyal", "frequent", "promo", "occasional", "new"]
    order_type = rng.choice(types, size=N, p=[0.16, 0.26, 0.18, 0.28, 0.12])
    cust_by_type = {t: customers.customer_id.to_numpy()[customers.ctype.to_numpy() == t]
                    for t in types}
    cust_of_order = np.empty(N, dtype=object)
    for t in types:
        m = order_type == t
        pool = cust_by_type[t]
        cust_of_order[m] = pool[rng.integers(0, len(pool), m.sum())]

    # ---- maybe a promotion (promo-types & weekends more likely) -----------
    p_prob = np.where(order_type == "promo", 0.45, 0.18)
    p_prob = p_prob + np.where(weekend[day_of_order] > 1, 0.06, 0.0)
    has_promo = rng.random(N) < p_prob
    promo_ids = promos.promotion_id.to_numpy()
    promo_disc = dict(zip(promos.promotion_id, promos.discount_pct))
    order_promo = np.where(has_promo,
                           promo_ids[rng.integers(0, len(promo_ids), N)], "")
    order_disc = np.array([promo_disc.get(p, 0) for p in order_promo], dtype=float)

    # ---- basket sizes (delivery/app baskets a touch bigger) ---------------
    extra = np.where(np.isin(ch_idx, [2, 3]), 0.6, 0.0)   # Website/App, Delivery
    bsize = 1 + rng.poisson(C.BASKET_LAMBDA + extra)
    L = int(bsize.sum())

    line_order = np.repeat(np.arange(N), bsize)           # order index per line
    line_loc = loc_of_order[line_order]

    # ---- per-location popularity twist, then sample items per line --------
    line_item_idx = np.empty(L, dtype=np.int64)
    for l in range(nloc):
        boost = np.ones(n_items)
        boost[rng.choice(n_items, size=8, replace=False)] = rng.uniform(1.4, 2.4, 8)
        w = pop * boost
        w = w / w.sum()
        m = line_loc == l
        line_item_idx[m] = rng.choice(n_items, size=int(m.sum()), p=w)

    line_item = item_ids[line_item_idx]
    qty = rng.integers(1, 4, size=L)
    line_date = pd.to_datetime(days.to_numpy()[day_of_order][line_order])

    # ---- unit price in effect on the line's date (step function) ----------
    lines = pd.DataFrame({"_ln": np.arange(L), "item_id": line_item, "date": line_date})
    ph = pricing.rename(columns={"effective_date": "date"})
    # pandas 2.x merge_asof requires the join keys to share the SAME datetime
    # resolution. depending on how each frame was built, one side can come out
    # as datetime64[us] and the other as datetime64[s], which raises a
    # MergeError. force both "date" columns to a common ns resolution first.
    lines["date"] = pd.to_datetime(lines["date"]).astype("datetime64[ns]")
    ph["date"] = pd.to_datetime(ph["date"]).astype("datetime64[ns]")
    lines = lines.sort_values("date")
    ph = ph.sort_values("date")
    priced = pd.merge_asof(lines, ph, on="date", by="item_id", direction="backward")
    # any line before an item's first price row falls back to base price
    base_price = dict(zip(items.item_id, items.base_price))
    priced["price"] = priced["price"].fillna(priced.item_id.map(base_price))
    priced = priced.sort_values("_ln")
    unit_price = priced.price.to_numpy()

    line_disc = order_disc[line_order]
    line_total = np.round(qty * unit_price * (1 - line_disc / 100), 2)

    # ---- assemble order_items --------------------------------------------
    order_id_str = _ids("O", N, 7)
    oitems = pd.DataFrame({
        "order_item_id": _ids("OI", L, 8),
        "order_id": order_id_str[line_order],
        "item_id": line_item,
        "quantity": qty,
        "unit_price": np.round(unit_price, 2),
        "discount_pct": line_disc.astype(int),
        "line_total": line_total,
    })

    # ---- order totals + assemble orders ----------------------------------
    totals = np.zeros(N)
    np.add.at(totals, line_order, line_total)
    orders = pd.DataFrame({
        "order_id": order_id_str,
        "customer_id": cust_of_order,
        "location_id": locs.location_id.to_numpy()[loc_of_order],
        "channel": channel,
        "order_ts": pd.to_datetime(ts),
        "promotion_id": order_promo,
        "total_amount": np.round(totals, 2),
        "status": "completed",
    })
    orders["order_ts"] = orders.order_ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    return orders, oitems


# --------------------------------------------------------------------------
# 5. ratings - correlated with an item's "true" quality + a planted anomaly
# --------------------------------------------------------------------------
def build_ratings(orders, oitems, items, frac=0.13):
    quality = {iid: rng.uniform(3.2, 4.9) for iid in items.item_id}
    sample = oitems[["order_id", "item_id"]].sample(frac=frac, random_state=C.SEED)
    merged = sample.merge(orders[["order_id", "customer_id", "location_id", "order_ts"]],
                          on="order_id", how="left")
    q = merged.item_id.map(quality).to_numpy()
    stars = np.clip(np.round(rng.normal(q, 0.6)), 1, 5).astype(int)
    ratings = pd.DataFrame({
        "rating_id": _ids("R", len(merged), 7),
        "item_id": merged.item_id.to_numpy(),
        "customer_id": merged.customer_id.to_numpy(),
        "location_id": merged.location_id.to_numpy(),
        "stars": stars,
        "rating_ts": merged.order_ts.to_numpy(),
    })
    return ratings, quality


# --------------------------------------------------------------------------
# 6. inventory + wastage (per item / location / week - keeps the file honest
#    in size while still giving 50k+ records and a real over-prep signal)
# --------------------------------------------------------------------------
def build_inventory_wastage(orders, oitems, items):
    merged = oitems[["order_id", "item_id", "quantity"]].merge(
        orders[["order_id", "location_id", "order_ts"]], on="order_id", how="left")
    merged["date"] = pd.to_datetime(merged.order_ts)
    merged["week"] = merged.date.dt.to_period("W").dt.start_time
    consumed = (merged.groupby(["item_id", "location_id", "week"], observed=True)
                .quantity.sum().reset_index(name="consumed_qty"))

    n = len(consumed)
    # kitchens prepare a bit more than they sell; some items chronically over-prep
    chronic = set(rng.choice(items.item_id.to_numpy(), size=15, replace=False))
    is_chronic = consumed.item_id.isin(chronic).to_numpy()
    bias = np.where(is_chronic, rng.uniform(1.28, 1.45, n), rng.uniform(1.03, 1.16, n))
    prepared = np.ceil(consumed.consumed_qty.to_numpy() * bias).astype(int)
    wasted = np.maximum(0, prepared - consumed.consumed_qty.to_numpy())

    inventory = pd.DataFrame({
        "item_id": consumed.item_id.to_numpy(),
        "location_id": consumed.location_id.to_numpy(),
        "date": consumed.week.dt.date.astype(str).to_numpy(),
        "prepared_qty": prepared,
        "consumed_qty": consumed.consumed_qty.to_numpy(),
    })

    food_cost = dict(zip(items.item_id, items.food_cost))
    keep = wasted > 0
    w = consumed[keep].copy()
    reasons = np.array(["overprep", "spoilage", "expired", "prep_error", "returned"])
    wastage = pd.DataFrame({
        "wastage_id": _ids("W", int(keep.sum()), 7),
        "item_id": w.item_id.to_numpy(),
        "location_id": w.location_id.to_numpy(),
        "date": w.week.dt.date.astype(str).to_numpy(),
        "wasted_qty": wasted[keep],
        "reason": reasons[rng.integers(0, len(reasons), int(keep.sum()))],
        "cost": np.round(wasted[keep] * w.item_id.map(food_cost).to_numpy(), 2),
    })
    return inventory, wastage


# --------------------------------------------------------------------------
# 7. inject dirty data so data-quality has something real to catch
# --------------------------------------------------------------------------
def dirty_it_up(orders, oitems, ratings, wastage):
    o = orders.copy(); oi = oitems.copy(); ra = ratings.copy(); wa = wastage.copy()

    # missing customer ids on some orders (~0.8%)
    idx = o.sample(frac=0.008, random_state=1).index
    o.loc[idx, "customer_id"] = ""

    # duplicate order-lines (exact copies)
    dupes = oi.sample(n=2000, random_state=2).copy()
    oi = pd.concat([oi, dupes], ignore_index=True)

    # invalid menu prices (zero / negative)
    idx = oi.sample(n=350, random_state=3).index
    oi.loc[idx, "unit_price"] = rng.choice([0, -5, -1], size=len(idx))

    # negative quantities
    idx = oi.sample(n=120, random_state=4).index
    oi.loc[idx, "quantity"] = -1

    # impossible ratings (>5 / 0)
    idx = ra.sample(n=200, random_state=5).index
    ra.loc[idx, "stars"] = rng.choice([6, 7, 0], size=len(idx))

    # impossible wastage (negative)
    idx = wa.sample(n=90, random_state=6).index
    wa.loc[idx, "wasted_qty"] = -3

    # a planted rating anomaly: 41 identical 5-star on one item in a short window
    burst = pd.DataFrame({
        "rating_id": [f"RX{i:04d}" for i in range(41)],
        "item_id": "M063",  # Truffle Carbonara (Pizza & Pasta)
        "customer_id": rng.choice(o.customer_id.replace("", np.nan).dropna().to_numpy(), 41),
        "location_id": "L03",
        "stars": 5,
        "rating_ts": "2026-09-17 20:15:00",
    })
    ra = pd.concat([ra, burst], ignore_index=True)
    return o, oi, ra, wa


# --------------------------------------------------------------------------
def main():
    print("Generating DineIQ dataset (this builds ~1M+ rows) ...")
    cats, items, locs, promos = build_reference()
    pricing = build_pricing_history(items)
    customers = build_customers()
    print(f"  customers built: {len(customers):,}")
    orders, oitems = build_orders(items, locs, promos, customers, pricing)
    print(f"  orders: {len(orders):,}   order-lines: {len(oitems):,}")
    ratings, _ = build_ratings(orders, oitems, items)
    print(f"  ratings: {len(ratings):,}")
    inventory, wastage = build_inventory_wastage(orders, oitems, items)
    print(f"  inventory: {len(inventory):,}   wastage: {len(wastage):,}")
    orders, oitems, ratings, wastage = dirty_it_up(orders, oitems, ratings, wastage)

    # pricing_history back to plain date strings for the CSV
    pricing_out = pricing.copy()
    pricing_out["effective_date"] = pricing_out.effective_date.dt.date.astype(str)

    tables = {
        "menu_categories": cats,
        "menu_items": items.drop(columns=["popularity"]),
        "locations": locs.drop(columns=["size_factor"]),
        "promotions": promos,
        "pricing_history": pricing_out,
        "customers": customers,
        "orders": orders,
        "order_items": oitems,
        "ratings": ratings,
        "inventory": inventory,
        "wastage": wastage,
    }
    for name, df in tables.items():
        path = C.RAW / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  {name:18s} {len(df):>9,} rows  -> {path.name}")
    print("Done. Raw CSVs written to", C.RAW)


if __name__ == "__main__":
    main()
