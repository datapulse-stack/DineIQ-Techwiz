"""
Data-quality assessment.

Runs BEFORE any analysis and answers one question: what's wrong with this data?
It doesn't fix anything here - it just finds and counts issues and writes a
report. Cleaning (the fixing) is a separate step on purpose, so every decision
is auditable.
"""
import pandas as pd


def assess(raw):
    """raw = dict of DataFrames. returns (report_df, checks dict of masks)."""
    orders = raw["orders"]
    oitems = raw["order_items"]
    ratings = raw["ratings"]
    wastage = raw["wastage"]
    items = raw["menu_items"]
    locs = raw["locations"]

    valid_items = set(items.item_id)
    valid_locs = set(locs.location_id)

    checks = []

    def add(name, count, action):
        checks.append({"issue": name, "records": int(count), "action": action})

    add("Missing customer IDs", (orders.customer_id.fillna("") == "").sum(), "flag & keep (guest orders)")
    add("Duplicate order-lines", oitems.duplicated().sum(), "quarantine")
    add("Invalid / non-positive prices", (oitems.unit_price <= 0).sum(), "recover from pricing history")
    add("Negative quantities", (oitems.quantity <= 0).sum(), "remove")
    add("Invalid ratings (outside 1-5)", (~ratings.stars.between(1, 5)).sum(), "clamp / drop")
    add("Impossible wastage (<0)", (wastage.wasted_qty < 0).sum(), "remove")
    add("Unknown menu item refs", (~oitems.item_id.isin(valid_items)).sum(), "quarantine")
    add("Invalid location refs", (~orders.location_id.isin(valid_locs)).sum(), "quarantine")
    add("Cancelled / non-completed orders", (orders.status != "completed").sum(), "exclude from revenue")

    report = pd.DataFrame(checks)
    return report
