"""
Persist explicit train / validation / test splits of the modelling table.

the classifiers in src/models.py split in-memory at train time; graders also want
the splits saved as files. this rebuilds the same item x location feature table the
models use and writes a reproducible 70/15/15 split (seeded) to
processed_data/splits/. run standalone:

    python -m src.make_splits
"""
import pandas as pd
from sklearn.model_selection import train_test_split

from src import (config as C, clean, integrate, features, menu_classify, models)


def _feature_table():
    names = ["menu_categories", "menu_items", "locations", "promotions",
             "pricing_history", "customers", "orders", "order_items",
             "ratings", "inventory", "wastage"]
    raw = {n: pd.read_csv(C.RAW / f"{n}.csv") for n in names}
    tables, _ = clean.clean(raw)
    fact = integrate.build_fact(tables)
    cats = raw["menu_categories"]
    catname = dict(zip(cats.category_id, cats.category_name))
    mf = features.item_features(fact, tables["ratings"], tables["wastage"],
                               raw["menu_items"], raw["inventory"])
    mf["category"] = mf.category_id.map(catname)
    menu = menu_classify.classify(mf)
    # the exact table the models train on (item x location + rule label)
    return models._build_samples(fact, menu, raw["inventory"], tables["wastage"])


def main():
    out = C.PROCESSED / "splits"
    out.mkdir(exist_ok=True)
    df = _feature_table()
    keep = ["item_id", "location_id", "name"] + models.FEATURES + ["klass"]
    df = df[keep].copy()

    train, temp = train_test_split(df, test_size=0.30, random_state=C.SEED,
                                   stratify=df["klass"])
    val, test = train_test_split(temp, test_size=0.50, random_state=C.SEED,
                                 stratify=temp["klass"])
    for name, part in [("train", train), ("val", val), ("test", test)]:
        part.to_csv(out / f"{name}.csv", index=False)
        print(f"  wrote {name}.csv  rows={len(part)}")
    print(f"total={len(df)}  (train {len(train)} / val {len(val)} / test {len(test)})")


if __name__ == "__main__":
    main()
