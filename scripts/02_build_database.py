#!/usr/bin/env python3
"""
Load the raw Olist CSVs into a single SQLite database.

Why: the raw data is eight loose CSV files. Answering anything useful means
joining them, and joins are what SQL is for. This script is the one-time
bridge from "files on disk" to "a database I can query".

Run:  python3 scripts/02_build_database.py data/raw data/olist.db
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

RAW = Path(sys.argv[1])
DB = Path(sys.argv[2])

# Map each CSV to the table name we want in the database.
# The raw filenames are long and repetitive ("olist_orders_dataset"); short,
# consistent table names make every query that follows easier to read.
TABLES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_customers_dataset.csv": "customers",
    "olist_sellers_dataset.csv": "sellers",
    "olist_products_dataset.csv": "products",
    "product_category_name_translation.csv": "category_translation",
}

# Columns holding dates. SQLite has no real date type — it stores dates as
# text. That is fine *provided* the text is ISO format (YYYY-MM-DD HH:MM:SS),
# because ISO text sorts and compares in the same order as the dates it
# represents. Writing them any other way would silently break date comparisons.
DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "order_reviews": ["review_creation_date", "review_answer_timestamp"],
}

# Indexes on the columns we join on. Without these, SQLite scans every row of
# a table for every row of the other one — fine on 100 rows, painfully slow on
# 100,000. An index is a lookup structure that makes those joins fast.
INDEXES = [
    ("orders", "order_id"),
    ("orders", "customer_id"),
    ("order_items", "order_id"),
    ("order_items", "seller_id"),
    ("order_items", "product_id"),
    ("order_payments", "order_id"),
    ("order_reviews", "order_id"),
    ("customers", "customer_id"),
    ("sellers", "seller_id"),
    ("products", "product_id"),
]


def main() -> None:
    if DB.exists():
        DB.unlink()  # rebuild from scratch so the script is repeatable
    DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    print(f"building {DB}\n")

    for filename, table in TABLES.items():
        path = RAW / filename
        if not path.exists():
            print(f"  SKIP   {table:22s} (missing {filename})")
            continue

        df = pd.read_csv(path)

        # Normalise dates to ISO text so date comparisons work in SQL.
        for col in DATE_COLUMNS.get(table, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

        df.to_sql(table, conn, index=False, if_exists="replace")
        print(f"  loaded {table:22s} {len(df):>7,} rows  x {df.shape[1]:>2} cols")

    print()
    for table, column in INDEXES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_{column} "
                f"ON {table}({column})"
            )
    conn.commit()
    print(f"  created {len(INDEXES)} indexes on join keys")

    # Sanity check: can we actually join orders to customers?
    n = conn.execute(
        """
        SELECT COUNT(*)
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        """
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"\n  join check: {n:,} of {total:,} orders matched a customer "
          f"({n / total * 100:.2f}%)")

    conn.close()
    print(f"\ndone — {DB.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
