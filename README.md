# Do we deliver late, or promise wrong?

A delivery-promise analysis of **96,476 completed e-commerce orders**.

> **Status:** in progress. Data acquired and validated; modelling underway.

---

## The question

Most delivery analyses ask *"why are orders late?"* and answer with distance and
geography. That question has a hidden assumption: that the promised delivery date
was reasonable in the first place.

This analysis separates two different failures that usually get averaged together:

| Failure | What it looks like | Who owns the fix |
|---|---|---|
| **Execution** | A realistic promise was missed | Logistics |
| **Forecasting** | The promise was never realistic | Commercial / pricing |

They have opposite remedies, and a single "on-time %" metric hides both.

## Early findings

From a first pass over the 96,476 orders that reached the customer:

- **91.9% arrived early.** Only 8.1% arrived after the promised date.
- **The median order arrived 12.3 days ahead of its promised date.**
- **59.3% arrived more than ten days early.**

An over-padded promise is not free. A customer shown "arrives in 18 days" at
checkout may not wait to find out it was really six. That cost never appears on a
delivery dashboard, because the dashboard only counts failures in one direction.

Quantifying that trade-off is what the rest of this analysis is for.

## Data

**Brazilian E-Commerce Public Dataset by Olist** — ~100,000 orders placed between
September 2016 and October 2018, published by Olist on Kaggle under CC BY-NC-SA 4.0.

Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Eight related tables are used: orders, order items, order payments, order reviews,
customers, sellers, products, and the product-category translation. The
`geolocation` table is not used; customer and seller records already carry state
and city.

The raw CSVs are **not committed** to this repository (see `.gitignore`). Download
them from the link above and place them in `data/raw/`.

### Provenance note

The files used here were verified against two independent public copies; the five
tables present in both were byte-for-byte identical, confirming the data is
unmodified.

## Repository structure

```
scripts/     Python — acquisition checks, cleaning, modelling
sql/         SQL — the joins and derived fields behind the model
docs/        Issues log, data dictionary, final recommendation
outputs/     Modelled tables that feed the Power BI report
```

## Tools

SQL · Python (pandas) · Power BI (DAX, Power Query)

---

*Mia Deita — [LinkedIn](https://www.linkedin.com/in/deitamia/)*
