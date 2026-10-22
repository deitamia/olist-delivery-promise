#!/usr/bin/env python3
"""
Register sql/01_order_model.sql in the database as a view named `order_model`.

Why: the model is a 130-line query. Without a view, every analysis question
means re-pasting all of it. With one, analysis queries are a few lines and
read like plain questions of the data.

The view is built FROM the .sql file rather than a second copy of the query,
so there is exactly one definition of the model. Edit the SQL file, re-run
this, and the view follows. Two copies of a query that must agree is how
analyses quietly start disagreeing with themselves.

Run:  python3 scripts/04_create_view.py data/olist.db sql/01_order_model.sql
"""

import sqlite3
import sys
from pathlib import Path

DB = Path(sys.argv[1])
SQL_FILE = Path(sys.argv[2])
VIEW = "order_model"


def main() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8").strip()

    # A view definition cannot end with a semicolon in the middle of the
    # CREATE VIEW statement, so strip the trailing one from the file.
    if sql.endswith(";"):
        sql = sql[:-1]

    conn = sqlite3.connect(DB)

    # Drop and recreate, so re-running after editing the SQL always gives
    # the current definition rather than silently keeping the old one.
    conn.execute(f"DROP VIEW IF EXISTS {VIEW}")
    conn.execute(f"CREATE VIEW {VIEW} AS\n{sql}")
    conn.commit()
    print(f"created view `{VIEW}` in {DB.name}")

    # Prove it works, and re-check the grain through the view itself.
    rows = conn.execute(f"SELECT COUNT(*) FROM {VIEW}").fetchone()[0]
    distinct = conn.execute(
        f"SELECT COUNT(DISTINCT order_id) FROM {VIEW}"
    ).fetchone()[0]
    cols = len(conn.execute(f"SELECT * FROM {VIEW} LIMIT 1").description)
    conn.close()

    print(f"  {rows:,} rows x {cols} columns")
    if rows == distinct:
        print(f"  grain OK: one row per order")
    else:
        raise SystemExit(
            f"GRAIN BROKEN: {rows:,} rows but {distinct:,} distinct order_id"
        )

    print(f"\nYou can now query it directly:  SELECT * FROM {VIEW} LIMIT 10;")


if __name__ == "__main__":
    main()
