#!/usr/bin/env python3
"""
Run sql/01_order_model.sql against the database and write the result to
outputs/order_model.csv — the single table Power BI will read.

Why a script rather than exporting from DBeaver by hand: anyone who clones
this repo can rebuild the exact same file with one command. A manual export
cannot be checked, repeated, or trusted.

Every run re-validates the grain before writing. If the query ever stops
producing one row per order, this script fails loudly instead of quietly
writing a wrong file.

Run:  python3 scripts/03_run_model.py data/olist.db sql/01_order_model.sql outputs/order_model.csv
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

DB = Path(sys.argv[1])
SQL_FILE = Path(sys.argv[2])
OUT = Path(sys.argv[3])


def main() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB)

    print(f"running {SQL_FILE.name} against {DB.name}")
    df = pd.read_sql_query(sql, conn)

    # ---- grain check -------------------------------------------------
    # The single most important assertion in this project. If it fails,
    # every downstream number is weighted wrong.
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()

    if len(df) != df["order_id"].nunique():
        raise SystemExit(
            f"GRAIN BROKEN: {len(df):,} rows but only "
            f"{df['order_id'].nunique():,} distinct order_id. "
            "A join is duplicating orders — fix before using this output."
        )
    if len(df) != total_orders:
        raise SystemExit(
            f"ROW COUNT MISMATCH: model has {len(df):,} rows, "
            f"orders table has {total_orders:,}. Orders were dropped or added."
        )
    print(f"  grain OK: {len(df):,} rows, one per order")

    # ---- a short summary so each run is self-reporting ---------------
    delivered = df[df["promise_error_days"].notna()]
    late_rate = delivered["is_late"].mean() * 100
    print(f"  delivered orders      : {len(delivered):,}")
    print(f"  late                  : {int(delivered['is_late'].sum()):,} "
          f"({late_rate:.2f}%)")
    print(f"  median promise error  : {delivered['promise_error_days'].median():.2f} days")
    print(f"  flagged: dispatch-before-approval {int(df['flag_dispatch_before_approval'].sum()):,}, "
          f"impossible transit {int(df['flag_impossible_transit'].sum()):,}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\nwrote {OUT}  ({OUT.stat().st_size / 1e6:.1f} MB, "
          f"{len(df):,} rows x {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
