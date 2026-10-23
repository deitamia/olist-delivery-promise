#!/usr/bin/env python3
"""
The analysis. Every figure quoted in the README is produced here.

Why a script and not a notebook of ad-hoc queries: a reviewer should be able
to run one command and get the same numbers. A finding you cannot reproduce
is an anecdote.

Python rather than SQL for this stage because the analysis needs medians,
percentiles and correlations, none of which SQLite provides. The modelling —
joins, grain, derived fields — stays in SQL where it belongs.

Run:  python3 scripts/05_analysis.py data/olist.db outputs
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

DB = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# Months to exclude from any time series.
#   2016-09..2016-12 : 4, 324 and 1 orders. Too few to mean anything.
#   2018-09, 2018-10 : every order still undelivered at the data cut-off.
CENSORED_MONTHS = {"2016-09", "2016-10", "2016-12", "2018-09", "2018-10"}

# Minimum orders before a state's rates are reported. Chosen before looking
# at results, so the threshold cannot be tuned to favour a conclusion.
MIN_ORDERS = 300

BANDS = [
    (0,      None,  "late (after promise)"),
    (-5,     0,     "early by 0-5 days"),
    (-10,    -5,    "early by 5-10 days"),
    (-20,    -10,   "early by 10-20 days"),
    (None,   -20,   "early by 20+ days"),
]


def band_of(x):
    if pd.isna(x):
        return None
    if x > 0:
        return "late (after promise)"
    if x > -5:
        return "early by 0-5 days"
    if x > -10:
        return "early by 5-10 days"
    if x > -20:
        return "early by 10-20 days"
    return "early by 20+ days"


BAND_ORDER = ["early by 20+ days", "early by 10-20 days", "early by 5-10 days",
              "early by 0-5 days", "late (after promise)"]


def header(title):
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM order_model", conn)
    conn.close()

    df["month"] = df.order_purchase_timestamp.str.slice(0, 7)
    df["band"] = df.promise_error_days.map(band_of)
    delivered = df[df.promise_error_days.notna()].copy()

    print(f"orders in model     : {len(df):,}")
    print(f"delivered (analysed): {len(delivered):,}")

    # ---------------------------------------------------------------- 1
    header("1. HOW WRONG IS THE PROMISE?")
    dist = (delivered.groupby("band")
            .agg(orders=("order_id", "size"))
            .reindex(BAND_ORDER))
    dist["pct"] = (dist.orders / dist.orders.sum() * 100).round(1)
    print(dist.to_string())
    print(f"\nmedian promise error : {delivered.promise_error_days.median():.2f} days"
          f"   (negative = arrived early)")
    print(f"late rate            : {delivered.is_late.mean() * 100:.2f}%")
    dist.to_csv(OUT / "promise_error_distribution.csv")

    # ---------------------------------------------------------------- 2
    header("2. BY STATE — IS THE PROMISE CALIBRATED TO REALITY?")
    g = delivered.groupby("customer_state")
    state = pd.DataFrame({
        "orders":        g.size(),
        "now_promised":  g.promised_days.mean().round(1),
        "median_actual": g.fulfilment_days.median().round(1),
        "p95_actual":    g.fulfilment_days.quantile(0.95).round(1),
        "late_pct":      (g.is_late.mean() * 100).round(1),
        "pct_over_30d":  ((g.fulfilment_days.apply(lambda s: (s > 30).mean())) * 100).round(1),
    })
    state = state[state.orders >= MIN_ORDERS].copy()
    # A promise set at the 95th percentile would have been met 95% of the time.
    state["promise_gap"] = (state.now_promised - state.p95_actual).round(1)
    state = state.sort_values("promise_gap")
    print(state.to_string())
    print("\npromise_gap = current promise minus the 95th-percentile actual.")
    print("Negative means the promise is SHORTER than a 95% service level needs.")
    print(f"states where the promise is long enough for 95%: "
          f"{(state.promise_gap >= 0).sum()} of {len(state)}")
    state.to_csv(OUT / "state_calibration.csv")

    # ---------------------------------------------------------------- 3
    header("3. WHAT PREDICTS LATENESS?")
    sd = g.fulfilment_days.std().round(1)
    corr_base = state.join(sd.rename("sd_days"))
    for col in ["sd_days", "median_actual", "pct_over_30d"]:
        r = corr_base[col].corr(corr_base.late_pct)
        print(f"  corr({col:14s}, late_pct) = {r:+.3f}")
    print("\nSpread, slowness and the tail all track lateness, and they track")
    print("each other — this data cannot separate their individual effects.")

    # ---------------------------------------------------------------- 4
    header("4. DOES ARRIVING EARLIER EARN BETTER REVIEWS?")
    rev = delivered[delivered.review_score_avg.notna()]
    rv = (rev.groupby("band")
          .agg(orders=("order_id", "size"),
               avg_review=("review_score_avg", "mean"),
               pct_1_2_star=("review_score_avg", lambda s: (s <= 2).mean() * 100),
               pct_5_star=("review_score_avg", lambda s: (s >= 5).mean() * 100))
          .reindex(BAND_ORDER).round(2))
    print(rv.to_string())
    early = rv.drop("late (after promise)")
    print(f"\nspread across the four EARLY bands : "
          f"{early.avg_review.max() - early.avg_review.min():.2f} review points")
    print(f"drop from best early band to late  : "
          f"{early.avg_review.max() - rv.loc['late (after promise)', 'avg_review']:.2f} review points")
    rv.to_csv(OUT / "reviews_by_promise_band.csv")

    # ---------------------------------------------------------------- 5
    header("5. WHICH STAGE OF THE JOURNEY CAUSES THE TAIL?")
    stages = delivered[
        (delivered.flag_impossible_transit == 0)
        & delivered.approval_days.notna()
        & delivered.dispatch_days.notna()
        & delivered.transit_days.notna()
    ].copy()
    stages["is_tail"] = stages.fulfilment_days > 30
    st = (stages.groupby("is_tail")[
              ["approval_days", "dispatch_days", "transit_days", "fulfilment_days"]]
          .median().round(2))
    st.index = ["normal (<=30d)", "TAIL (>30d)"]
    print(st.to_string())
    extra = st.loc["TAIL (>30d)"] - st.loc["normal (<=30d)"]
    tot = extra[["approval_days", "dispatch_days", "transit_days"]].sum()
    print("\nextra days on a tail order, by stage:")
    for col in ["approval_days", "dispatch_days", "transit_days"]:
        print(f"  {col:15s} +{extra[col]:6.2f} days   ({extra[col] / tot * 100:4.1f}% of the excess)")
    st.to_csv(OUT / "stage_decomposition.csv")

    # ---------------------------------------------------------------- 6
    header("6. MONTHLY TREND (censored months excluded)")
    m = df[~df.month.isin(CENSORED_MONTHS)]
    monthly = pd.DataFrame({
        "orders":        m.groupby("month").size(),
        "avg_promised":  m.groupby("month").promised_days.mean().round(1),
        "median_actual": m.groupby("month").fulfilment_days.median().round(1),
        "late_pct":      (m.groupby("month").is_late.mean() * 100).round(1),
    })
    print(monthly.to_string())
    print(f"\npromise shortened from {monthly.avg_promised.iloc[0]:.1f} days "
          f"({monthly.index[0]}) to {monthly.avg_promised.iloc[-1]:.1f} days "
          f"({monthly.index[-1]})")
    monthly.to_csv(OUT / "monthly_trend.csv")

    print(f"\n\nwrote 6 summary tables to {OUT}/")


if __name__ == "__main__":
    main()
