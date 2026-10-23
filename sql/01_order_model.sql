-- =====================================================================
-- Order-level analysis model
--
-- Produces exactly ONE ROW PER ORDER, carrying everything the delivery
-- promise analysis needs.
--
-- The grain is the whole point. order_items has 112,650 rows for 98,666
-- orders, and order_reviews has 99,224 rows for 98,673 orders. Joining
-- either one directly to orders would duplicate orders and silently
-- weight every delivery metric by basket size. Both are therefore
-- collapsed to one row per order BEFORE the join.
-- =====================================================================

WITH

-- ---------------------------------------------------------------------
-- Collapse order_items (one row per item) down to one row per order.
-- ---------------------------------------------------------------------
items_per_order AS (
    SELECT
        order_id,
        COUNT(*)                   AS n_items,
        COUNT(DISTINCT seller_id)  AS n_sellers,
        ROUND(SUM(price), 2)       AS items_value,
        ROUND(SUM(freight_value), 2) AS freight_value
    FROM order_items
    GROUP BY order_id
),

-- ---------------------------------------------------------------------
-- Collapse order_reviews down to one row per order.
-- 551 orders carry more than one review. Rather than pick one, we keep
-- the count (so the duplicates stay visible) alongside the average and
-- the worst score.
-- ---------------------------------------------------------------------
reviews_per_order AS (
    SELECT
        order_id,
        COUNT(*)                      AS n_reviews,
        ROUND(AVG(review_score), 2)   AS review_score_avg,
        MIN(review_score)             AS review_score_min
    FROM order_reviews
    GROUP BY order_id
)

-- ---------------------------------------------------------------------
-- Main query: one row per order.
-- ---------------------------------------------------------------------
SELECT
    o.order_id,
    o.order_status,

    -- Who and where. customer_unique_id is the actual person;
    -- customer_id is a per-order record and must never be counted
    -- as a customer.
    c.customer_unique_id,
    c.customer_state,
    c.customer_city,

    -- The raw timestamp chain, kept so any figure can be traced back.
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    -- -----------------------------------------------------------------
    -- Derived durations, in days.
    -- julianday() converts an ISO date string to a number of days, so
    -- subtracting two of them gives the gap between them. This is why
    -- the loader wrote every date in ISO format.
    -- -----------------------------------------------------------------
    ROUND(julianday(o.order_approved_at)
        - julianday(o.order_purchase_timestamp), 3)        AS approval_days,

    ROUND(julianday(o.order_delivered_carrier_date)
        - julianday(o.order_approved_at), 3)               AS dispatch_days,

    ROUND(julianday(o.order_delivered_customer_date)
        - julianday(o.order_delivered_carrier_date), 3)    AS transit_days,

    ROUND(julianday(o.order_delivered_customer_date)
        - julianday(o.order_purchase_timestamp), 3)        AS fulfilment_days,

    -- What the customer was promised at checkout.
    ROUND(julianday(o.order_estimated_delivery_date)
        - julianday(o.order_purchase_timestamp), 3)        AS promised_days,

    -- THE MEASURE THIS PROJECT IS ABOUT.
    -- Negative = arrived early. Positive = arrived late.
    ROUND(julianday(o.order_delivered_customer_date)
        - julianday(o.order_estimated_delivery_date), 3)   AS promise_error_days,

    -- -----------------------------------------------------------------
    -- Flags. CASE WHEN is SQL's if/else.
    -- NULL where the order never arrived: unknown is not the same as
    -- "not late", and must not be counted as either.
    -- -----------------------------------------------------------------
    CASE
        WHEN o.order_delivered_customer_date IS NULL THEN NULL
        WHEN julianday(o.order_delivered_customer_date)
           > julianday(o.order_estimated_delivery_date) THEN 1
        ELSE 0
    END AS is_late,

    -- Flags issue 5 in the issues log: carrier collected the order
    -- before payment was approved. 1,359 orders, kept but marked.
    CASE
        WHEN o.order_delivered_carrier_date IS NOT NULL
         AND o.order_approved_at IS NOT NULL
         AND julianday(o.order_delivered_carrier_date)
           < julianday(o.order_approved_at) THEN 1
        ELSE 0
    END AS flag_dispatch_before_approval,

    -- Flags issue 4: delivered before the carrier collected it.
    -- Physically impossible, so transit_days is not trustworthy here.
    CASE
        WHEN o.order_delivered_customer_date IS NOT NULL
         AND o.order_delivered_carrier_date IS NOT NULL
         AND julianday(o.order_delivered_customer_date)
           < julianday(o.order_delivered_carrier_date) THEN 1
        ELSE 0
    END AS flag_impossible_transit,

    -- -----------------------------------------------------------------
    -- Basket and review, already collapsed to order grain above.
    -- -----------------------------------------------------------------
    i.n_items,
    i.n_sellers,
    i.items_value,
    i.freight_value,
    r.n_reviews,
    r.review_score_avg,
    r.review_score_min

FROM orders o

-- INNER JOIN: every order has a customer record (verified 100%).
JOIN customers c
  ON c.customer_id = o.customer_id

-- LEFT JOIN: keep the order even when there is no match on the right.
-- 775 orders have no items and ~750 have no review; a LEFT JOIN keeps
-- them with NULLs rather than dropping them from the analysis.
LEFT JOIN items_per_order i
  ON i.order_id = o.order_id

LEFT JOIN reviews_per_order r
  ON r.order_id = o.order_id;
