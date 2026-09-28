# DineIQ — Data Dictionary

This document describes every table DineIQ reads and writes. The **raw layer**
(`raw_data/`) is produced by `data_generator/generate_data.py`; the **processed
layer** (`processed_data/`) is produced by the analytics pipeline (`src/`) and the
Spark job (`spark_jobs/`).

Dataset scale (12 months, 20 locations): 1,209,427 order-lines · 312,503 orders ·
52,000 customers · 150 menu items · 10 categories.

---

## 1. Raw layer — `raw_data/`

### `menu_categories.csv` — the 10 menu categories
| Column | Type | Description |
|---|---|---|
| category_id | string (PK) | Category identifier, e.g. `C01`. |
| category_name | string | Human name, e.g. "Seafood". |

### `menu_items.csv` — 150 dishes
| Column | Type | Description |
|---|---|---|
| item_id | string (PK) | Item identifier, e.g. `M058`. |
| name | string | Dish name. |
| category_id | string (FK → menu_categories) | Owning category. |
| base_price | float | List price. |
| food_cost | float | Unit ingredient cost (drives margin). |

### `locations.csv` — 20 outlets
| Column | Type | Description |
|---|---|---|
| location_id | string (PK) | Outlet id, e.g. `L05`. |
| name | string | Outlet name, e.g. "Riverside". |
| city | string | City the outlet sits in. |

### `customers.csv` — 52,000 customers
| Column | Type | Description |
|---|---|---|
| customer_id | string (PK) | Customer id. |
| name | string | Display name. |
| signup_date | date | First registration date. |
| ctype | string | Customer type/tier tag used when generating behaviour. |

### `promotions.csv` — 9 promotions
| Column | Type | Description |
|---|---|---|
| promotion_id | string (PK) | Promotion id. |
| name | string | Promotion name, e.g. "Family Combo". |
| type | string | combo / channel / upsell / timed / loyalty. |
| discount_pct | int | Headline discount. |
| start_date, end_date | date | Active window. |

### `pricing_history.csv` — price changes over time
| Column | Type | Description |
|---|---|---|
| item_id | string (FK → menu_items) | Item repriced. |
| price | float | New price. |
| effective_date | date | Date the price took effect. |

### `orders.csv` — 312,503 order headers
| Column | Type | Description |
|---|---|---|
| order_id | string (PK) | Order id. |
| customer_id | string (FK → customers) | Buyer (`GUEST` for guest orders). |
| location_id | string (FK → locations) | Outlet. |
| channel | string | Dine-in / Takeaway / Website-App / Delivery. |
| order_ts | timestamp | Order date-time. |
| promotion_id | string (FK → promotions, nullable) | Promotion applied, if any. |
| total_amount | float | Order total. |
| status | string | Order status. |

### `order_items.csv` — 1,209,427 order-lines (transactional grain)
| Column | Type | Description |
|---|---|---|
| order_item_id | string (PK) | Line id. |
| order_id | string (FK → orders) | Parent order. |
| item_id | string (FK → menu_items) | Item bought. |
| quantity | int | Units on the line. |
| unit_price | float | Price charged per unit. |
| discount_pct | int | Line discount. |
| line_total | float | Extended line revenue. |

### `ratings.csv` — 157,007 ratings
| Column | Type | Description |
|---|---|---|
| rating_id | string (PK) | Rating id. |
| item_id | string (FK) | Item rated. |
| customer_id | string (FK) | Rater. |
| location_id | string (FK) | Where it was rated. |
| stars | int (1–5) | Score. |
| rating_ts | timestamp | When rated. |

### `inventory.csv` — 152,901 prep records
| Column | Type | Description |
|---|---|---|
| item_id | string (FK) | Item. |
| location_id | string (FK) | Outlet. |
| date | date | Prep day. |
| prepared_qty | int | Units prepared. |
| consumed_qty | int | Units sold/used. |

### `wastage.csv` — 152,901 wastage records
| Column | Type | Description |
|---|---|---|
| wastage_id | string (PK) | Record id. |
| item_id, location_id | string (FK) | Item + outlet. |
| date | date | Day. |
| wasted_qty | int | Units wasted. |
| reason | string | Spoilage / over-prep / etc. |
| cost | float | Money value of the waste. |

---

## 2. Processed layer — `processed_data/` (downloadable reports)

| File | Grain | Key columns |
|---|---|---|
| `data_quality_report.csv` | issue | issue, records, action |
| `cleaning_log.csv` | step | step, records |
| `menu_performance.csv` | item | qty, revenue, cost, profit, margin, rating, wastage_pct, repeat_pct, trend, demand_score, profit_score, **klass** |
| `profitability.csv` | item | qty, revenue, cost, profit, margin_pct, wastage_pct, klass |
| `customer_segments.csv` | customer | recency, frequency, monetary, categories, promo_share, avg_order_value, R, F, M, rfm_score, cluster, **segment** |
| `churn_risk.csv` | customer | recency, frequency, monetary, **churn_prob**, risk_band |
| `market_basket_rules.csv` | rule | a, b, support, confidence, lift |
| `demand_forecast.csv` | date | type (actual/forecast), orders, lo, hi |
| `forecast_by_location.csv` | location | next, last, change_pct |
| `forecast_by_category.csv` | category | next, last, change_pct |
| `price_sensitivity.csv` | item | elasticity, sensitivity, basis |
| `promotion_effectiveness.csv` | promotion | sales_lift, margin_gap, aov, verdict, note |
| `wastage_by_item.csv` | item | wasted, prepared, wastage_pct, cost |
| `peak_monthly.csv` | month | orders |
| `location_performance.csv` | location | rev, profit, aov, cust, repeat, waste, rating, star, drag, channel, channel_share |
| `anomalies.csv` | event | type, location, date, severity, detail |
| `recommendations.csv` | action | priority, action, do, impact, evidence |
| `model_comparison.csv` | item×location | spark_model, python_model, **agree** |
| `spark_predictions.csv` | item×location | spark_pred, label_str *(from the real Spark MLlib run)* |
| `python_predictions.csv` | item×location | rule_label, python_pred *(from the scikit-learn model)* |

### Big-Data / model artefacts
| Path | Description |
|---|---|
| `processed_data/spark/fact_order_lines.parquet/` | Spark output, **partitioned by `location_id`** (20 partitions). |
| `processed_data/spark_metrics.json` | Spark MLlib leaderboard (3 algorithms) + selected model. |
| `processed_data/python_metrics.json` | scikit-learn leaderboard + selected model. |
| `models/python_best_model.pkl` | Saved Python model + scaler + feature list. |
| `spark_jobs/models/spark_best_model/` | Saved Spark MLlib `PipelineModel`. |
| `processed_data/splits/{train,val,test}.csv` | Reproducible 70/15/15 stratified split of the modelling table. |
| `outputs/dashboard_data.json` | Everything the web dashboard renders. |

---

## 3. Derived / engineered fields (key formulas)

| Field | Definition |
|---|---|
| margin | `(revenue − cost) / revenue` (contribution margin ratio). |
| wastage_pct | `wasted_qty / prepared_qty × 100`. |
| repeat_pct | share of an item's buyers who bought it more than once. |
| trend | last-third vs first-third quantity change (%) over the window. |
| RFM (R,F,M) | quintile scores (1–5) of Recency, Frequency, Monetary. |
| demand_score / profit_score | min–max normalised **within each location** (location-specific). |
| klass | 4-quadrant label: Profit Driver / Volume Driver / Hidden Opportunity / Low Performer. |
| churn_prob | probability from the logistic churn model (features exclude recency to avoid leakage). |
