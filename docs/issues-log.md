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

## Not yet checked

- Duplicate `order_id` values
- Orders with no matching rows in `order_items`
- Products with a null category
- Sellers or customers referenced by orders but absent from their own table
- Extreme promise errors (the range runs to -146 and +189 days)
