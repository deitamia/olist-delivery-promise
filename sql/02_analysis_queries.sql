-- =====================================================================
-- Exploratory analysis queries, run against the `order_model` view.
--
-- These are the interactive queries used to work out what the data was
-- saying. The authoritative figures in the README come from
-- scripts/05_analysis.py, which uses medians and percentiles that SQLite
-- does not provide. These queries use averages instead, so a few numbers
-- differ slightly — the patterns do not.
--
-- Kept separate from 01_order_model.sql on purpose: that file must
-- contain exactly one statement, because scripts/04_create_view.py wraps
-- it in CREATE VIEW.
--
-- Run one at a time (place the cursor in a query and press Ctrl+Enter in
-- DBeaver), not the whole file at once.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. How wrong is the promise?
--    Buckets every delivered order by how far it missed its promised date.
--    A median alone hides the shape; this shows it.
-- ---------------------------------------------------------------------
SELECT
    CASE
        WHEN promise_error_days >   0 THEN 'late (after promise)'
        WHEN promise_error_days >  -5 THEN 'early by 0-5 days'
        WHEN promise_error_days > -10 THEN 'early by 5-10 days'
        WHEN promise_error_days > -20 THEN 'early by 10-20 days'
        ELSE                               'early by 20+ days'
    END AS promise_bucket,
    COUNT(*) AS orders,
    ROUND(100.0 * COUNT(*) /
        (SELECT COUNT(*) FROM order_model WHERE promise_error_days IS NOT NULL), 1) AS pct
FROM order_model
WHERE promise_error_days IS NOT NULL
GROUP BY promise_bucket
ORDER BY MIN(promise_error_days);


-- ---------------------------------------------------------------------
-- 2. Promise versus reality, by state.
--    HAVING filters groups (not rows), so states with thin samples are
--    dropped before their rates can mislead. The 300 threshold was set
--    before looking at any results.
-- ---------------------------------------------------------------------
SELECT
    customer_state,
    COUNT(*)                            AS orders,
    ROUND(AVG(promised_days), 1)        AS avg_promised,
    ROUND(AVG(fulfilment_days), 1)      AS avg_actual,
    ROUND(AVG(promise_error_days), 1)   AS avg_error,
    ROUND(100.0 * AVG(is_late), 1)      AS late_pct
FROM order_model
WHERE promise_error_days IS NOT NULL
GROUP BY customer_state
HAVING COUNT(*) >= 300
ORDER BY avg_error;


-- ---------------------------------------------------------------------
-- 3. Spread and tail, by state.
--    SQLite has no STDDEV, so it is computed from the identity
--    variance = mean(x^2) - mean(x)^2.
--    pct_over_30d is a one-sided tail measure: standard deviation treats
--    "5 days early" and "5 days late" alike, and customers do not.
-- ---------------------------------------------------------------------
SELECT
    customer_state,
    COUNT(*)                        AS orders,
    ROUND(AVG(fulfilment_days), 1)  AS avg_days,
    ROUND(SQRT(AVG(fulfilment_days * fulfilment_days)
             - AVG(fulfilment_days) * AVG(fulfilment_days)), 1) AS sd_days,
    ROUND(100.0 * AVG(CASE WHEN fulfilment_days > 30 THEN 1 ELSE 0 END), 1) AS pct_over_30d,
    ROUND(100.0 * AVG(is_late), 1)  AS late_pct
FROM order_model
WHERE fulfilment_days IS NOT NULL
GROUP BY customer_state
HAVING COUNT(*) >= 300
ORDER BY sd_days DESC;


-- ---------------------------------------------------------------------
-- 4. Do earlier deliveries earn better reviews?
--    Compare the four early bands against each other, not just against
--    the late band.
-- ---------------------------------------------------------------------
SELECT
    CASE
        WHEN promise_error_days >   0 THEN 'late (after promise)'
        WHEN promise_error_days >  -5 THEN 'early by 0-5 days'
        WHEN promise_error_days > -10 THEN 'early by 5-10 days'
        WHEN promise_error_days > -20 THEN 'early by 10-20 days'
        ELSE                               'early by 20+ days'
    END AS promise_bucket,
    COUNT(*)                          AS orders,
    ROUND(AVG(review_score_avg), 2)   AS avg_review,
    ROUND(100.0 * AVG(CASE WHEN review_score_avg <= 2 THEN 1 ELSE 0 END), 1) AS pct_1_2_star,
    ROUND(100.0 * AVG(CASE WHEN review_score_avg >= 5 THEN 1 ELSE 0 END), 1) AS pct_5_star
FROM order_model
WHERE promise_error_days IS NOT NULL AND review_score_avg IS NOT NULL
GROUP BY promise_bucket
ORDER BY MIN(promise_error_days);


-- ---------------------------------------------------------------------
-- 5. Which stage of the journey produces the tail?
--    Excludes the 23 orders flagged as delivered before carrier pickup,
--    where transit_days cannot be trusted.
-- ---------------------------------------------------------------------
SELECT
    CASE WHEN fulfilment_days > 30 THEN 'TAIL (>30d)' ELSE 'normal' END AS band,
    COUNT(*)                            AS orders,
    ROUND(AVG(approval_days), 2)        AS avg_approval,
    ROUND(AVG(dispatch_days), 2)        AS avg_dispatch,
    ROUND(AVG(transit_days), 2)         AS avg_transit,
    ROUND(AVG(fulfilment_days), 2)      AS avg_total
FROM order_model
WHERE fulfilment_days IS NOT NULL AND flag_impossible_transit = 0
GROUP BY band;


-- ---------------------------------------------------------------------
-- 6. Monthly trend.
--    strftime('%Y-%m', ...) truncates a timestamp to year-month, and that
--    format sorts chronologically as plain text.
--    not_delivered exposes right-censoring: the final months of any
--    operational dataset contain orders that have not had time to arrive.
--    2016-09..2016-12 and 2018-09..2018-10 must be excluded before
--    reading any trend from this.
-- ---------------------------------------------------------------------
SELECT
    strftime('%Y-%m', order_purchase_timestamp)      AS month,
    COUNT(*)                                          AS orders_placed,
    SUM(CASE WHEN is_late IS NULL THEN 1 ELSE 0 END)  AS not_delivered,
    ROUND(AVG(fulfilment_days), 1)                    AS avg_days,
    ROUND(100.0 * AVG(is_late), 1)                    AS late_pct,
    ROUND(AVG(promised_days), 1)                      AS avg_promised
FROM order_model
GROUP BY month
ORDER BY month;
