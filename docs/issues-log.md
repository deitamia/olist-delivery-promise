# Data issues log

Every problem found in the raw data, what was decided, and why. Kept as the
analysis runs rather than written up afterwards.

A record is only excluded when keeping it would make a number wrong. Exclusions
are counted so their effect on the result is visible.

---

## 1. Orders that never reached the customer

**Found:** 2,965 of 99,441 orders (2.98%) have no `order_delivered_customer_date`.

**Cause:** mostly legitimate — orders still in flight, cancelled, or unavailable
at the time the dataset was cut.

**Decision:** excluded from delivery-timing measures. They cannot have a promise
error, because they have no actual delivery date. They are kept for order-volume
counts.

**Effect:** the delivery analysis runs on 96,476 orders.

---

## 2. Status says delivered, but no delivery date

**Found:** 8 orders with `order_status = 'delivered'` and a null
`order_delivered_customer_date`.

**Cause:** unknown. Too few to be a systematic process; most likely a recording
failure.

**Decision:** excluded from timing measures, flagged here. At 8 records out of
96,476 the effect on any aggregate is nil.

**Status:** closed.

---

## 3. Delivery date present, but status is not 'delivered'

**Found:** 6 orders.

**Cause:** unknown — possibly a status that was never updated after delivery.

**Decision:** treated as delivered for timing purposes, since the delivery
timestamp is the stronger evidence. Flagged here.

**Status:** closed.

---

## 4. Delivered to the customer before the carrier collected it

**Found:** 23 orders where `order_delivered_customer_date` precedes
`order_delivered_carrier_date`.

**Cause:** physically impossible, so one of the two timestamps is wrong. Which
one is wrong cannot be determined from the data.

**Decision:** excluded from transit-time measures, retained for promise-error
measures, which depend only on the delivery and estimated dates.

**Status:** closed.

---

## 5. Carrier collected the order before payment was approved

**Found:** 1,359 orders (1.4% of all orders) where
`order_delivered_carrier_date` precedes `order_approved_at`.

**Cause:** at 1.4% this is too frequent to be noise. The likely explanation is a
business process rather than bad data — goods dispatched before payment clears,
or approval recorded in a batch after the fact.

**Decision:** **not excluded.** These orders have valid delivery and estimated
dates, so their promise error is sound. They are flagged as a separate segment so
their behaviour can be compared against the rest.

**Open question:** does this segment have a different promise error than the rest?
If so, it is worth reporting, because it would mean the approval process affects
the customer's delivered experience.

**Status:** open — to be tested during modelling.

---

## 6. `order_items` has more rows than `orders` — grain mismatch

**Found:** 112,650 item rows covering 98,666 orders. One order contains 21 items.

**Why it matters:** joining `orders` to `order_items` directly multiplies each
order by its item count. Every delivery metric computed on that join would be
weighted by basket size — a 21-item order would count 21 times toward the late
rate. The output would look plausible and be wrong.

**Decision:** aggregate `order_items` to one row per order *before* joining
(count of items, count of distinct sellers, sum of price and freight). The
analysis table holds exactly one row per order.

**Status:** closed — handled in the model.

---

## 7. 775 orders have no item rows at all

**Found:** `orders` holds 99,441 order_ids; `order_items` references only 98,666.

**Cause:** most are cancelled or unavailable orders that never had items
allocated.

**Decision:** retained, with item counts and values as nulls rather than zeros —
"unknown" is not the same as "zero". They are excluded from any value-weighted
measure.

**Status:** closed.

---

## 8. `customer_id` is not a customer

**Found:** the `customers` table has 99,441 `customer_id` values and exactly
99,441 orders — one per order. But it holds only 96,096 distinct
`customer_unique_id` values.

**What this means:** `customer_id` identifies an *order's* customer record, not
a person. The real person is `customer_unique_id`. 3,345 orders were placed by
someone who had ordered before.

**Why it matters:** counting distinct `customer_id` would report 99,441
customers when there are 96,096 — a 3.5% overstatement, and it would make
repeat-purchase analysis impossible, since every repeat buyer would look new.

**Decision:** `customer_unique_id` is carried into the model and used wherever a
person is meant. `customer_id` is used only to join.

**Status:** closed.

---

## 9. Duplicate reviews

**Found:** `order_reviews` has 99,224 rows but only 98,673 distinct order_ids —
551 orders carry more than one review.

**Why it matters:** the same grain trap as issue 6. Joining reviews directly
would duplicate those orders.

**Decision:** to be resolved during modelling — either take the latest review
per order or the lowest score. Choice and reasoning to be recorded here.

**Status:** open.

---

## Not yet checked

- Products with a null category
- Sellers referenced by order items but absent from the `sellers` table
- Extreme promise errors (the range runs to -146 and +189 days)
