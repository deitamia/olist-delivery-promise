#!/usr/bin/env python3
"""First look at the Olist orders table: shape, nulls, statuses, and whether
the delivery promise is systematically padded."""

import sys
import pandas as pd

RAW = sys.argv[1]

orders = pd.read_csv(f"{RAW}/olist_orders_dataset.csv")

TS = ["order_purchase_timestamp", "order_approved_at",
      "order_delivered_carrier_date", "order_delivered_customer_date",
      "order_estimated_delivery_date"]
for c in TS:
    orders[c] = pd.to_datetime(orders[c], errors="coerce")

print("=" * 64)
print(f"orders: {len(orders):,} rows  x  {orders.shape[1]} columns")
print("=" * 64)

print("\n--- null counts ---")
n = orders.isna().sum()
for c in orders.columns:
    if n[c]:
        print(f"  {c:34s} {n[c]:>7,}  ({n[c]/len(orders)*100:5.2f}%)")

print("\n--- order_status ---")
vc = orders["order_status"].value_counts()
for k, v in vc.items():
    print(f"  {k:16s} {v:>7,}  ({v/len(orders)*100:5.2f}%)")

print("\n--- purchase date range ---")
print(f"  {orders.order_purchase_timestamp.min()}  ->  "
      f"{orders.order_purchase_timestamp.max()}")

# ---------- the core question ----------
d = orders[orders.order_delivered_customer_date.notna()].copy()
d["promise_error_days"] = (
    d.order_delivered_customer_date - d.order_estimated_delivery_date
).dt.total_seconds() / 86400

print("\n" + "=" * 64)
print(f"DELIVERED ORDERS: {len(d):,}")
print("=" * 64)
print("promise_error = actual delivery - promised date   (negative = early)")
q = d.promise_error_days.describe(percentiles=[.05, .25, .5, .75, .95])
for k in ["mean", "std", "min", "5%", "25%", "50%", "75%", "95%", "max"]:
    print(f"  {k:>5s}  {q[k]:9.2f}")

late = (d.promise_error_days > 0).sum()
early = (d.promise_error_days < 0).sum()
print(f"\n  late  (arrived after promise): {late:>7,}  ({late/len(d)*100:5.2f}%)")
print(f"  early (arrived before promise): {early:>7,}  ({early/len(d)*100:5.2f}%)")
print(f"  median earliness among early  : {-d.loc[d.promise_error_days < 0, 'promise_error_days'].median():.1f} days")
print(f"  more than 10 days early       : {(d.promise_error_days < -10).sum():,} "
      f"({(d.promise_error_days < -10).sum()/len(d)*100:.1f}%)")

# ---------- data quality flags ----------
print("\n" + "=" * 64)
print("DATA QUALITY FLAGS")
print("=" * 64)
checks = {
    "status='delivered' but no delivery date":
        ((orders.order_status == "delivered") & orders.order_delivered_customer_date.isna()).sum(),
    "has delivery date but status != 'delivered'":
        ((orders.order_status != "delivered") & orders.order_delivered_customer_date.notna()).sum(),
    "delivered to customer BEFORE carrier pickup":
        (orders.order_delivered_customer_date < orders.order_delivered_carrier_date).sum(),
    "approved BEFORE purchase":
        (orders.order_approved_at < orders.order_purchase_timestamp).sum(),
    "carrier pickup BEFORE approval":
        (orders.order_delivered_carrier_date < orders.order_approved_at).sum(),
    "estimated date BEFORE purchase":
        (orders.order_estimated_delivery_date < orders.order_purchase_timestamp).sum(),
}
for k, v in checks.items():
    flag = "  <-- investigate" if v else ""
    print(f"  {v:>6,}  {k}{flag}")
