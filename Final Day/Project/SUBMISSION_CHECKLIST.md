# DineIQ — Final Submission Checklist

Mapped to the 57-item requirement list. **Status:** ✅ done · ⏳ needs you (external).

## Dataset (1–4)
- [x] Own large-scale interconnected dataset (11 tables, FK-linked)
- [x] Meets minimum scale: 1.21M order-lines · 312.5K orders · 52K customers · 150 items · 20 locations · 12 months
- [x] Realistic complexity injected (missing values, duplicates, anomalies, seasonal/weekend/peak patterns, promotions)
- [x] Dataset-generation script submitted (`data_generator/generate_data.py`) — not a ready-made set

## Big Data & Ingestion (5–8)
- [x] Data stored in CSV/JSON **and Parquet** (`processed_data/spark/fact_order_lines.parquet/`, partitioned by location)
- [x] Apache Spark/PySpark ingestion with explicit schema + inference + multi-file + partitioning (`spark_jobs/spark_pipeline.py`)
- [x] Data-quality report identifies missing/duplicate/invalid; cleaning rules documented (`data_quality_report.csv`, `cleaning_log.csv`)
- [x] Integration via Spark SQL joins (Spark side) and pandas joins (reference side)

## Analytics & Features (9–13)
- [x] Feature engineering (revenue, cost, margin, profit %, RFM, wastage %, promo dependency, trend)
- [x] EDA: top/lowest-selling, highest revenue/profit/margin, high-wastage, best/poorly-rated dishes
- [x] Menu profitability across multiple dimensions
- [x] Menu classification (Profit/Volume/Hidden/Low), data-driven, location-specific
- [x] Tricky cases handled (high-selling loss-making, low-selling high-margin, seasonal, new items)

## Modelling (14–16)
- [x] **≥3 Spark MLlib algorithms** trained + compared, best selected (RF 0.91/0.898, DT, LogReg — `spark_metrics.json`)
- [x] Independent Python DS pipeline (pandas + scikit-learn) on the same data
- [x] Dual-pipeline comparison: match/mismatch/difference/agreement (`model_comparison.csv`, 95% over 3,000)

## Customer & operational analytics (17–30)
- [x] Segmentation by RFM + order value + category preference + promo sensitivity + channel
- [x] RFM (Recency/Frequency/Monetary) per customer (`customer_segments.csv`)
- [x] Market-basket with Support/Confidence/Lift + bundles
- [x] Peak-period analysis (hours/days/weekend/monthly/seasonal/location) (`peak_monthly.csv`, dashboard `peak`)
- [x] Demand forecasting per item/category/location, configurable horizon (`forecast_by_*.csv`)
- [x] Time-aware validation (chronological split, no leakage); MAE/RMSE/MAPE/**R²**
- [x] Wastage intelligence by item/category/location/day/time + risk prediction
- [x] Pricing intelligence (elasticity + sensitivity bands)
- [x] Promotion analytics (volume/revenue/margin/repeat/wastage) + trap detection
- [x] Rating & anomaly detection (rating vs performance, rating + sales anomalies)
- [x] Multi-location intelligence + location-specific classification
- [x] Ordering-channel analysis (dine-in/takeaway/web-app/delivery)
- [x] **Churn-risk model** (logistic; `churn.py`, `churn_risk.csv`) + evidence-based recommendations with priorities
- [x] What-if simulation engine

## Platform & non-functional (31–37)
- [x] Dashboards: Executive, Menu, Customer, Wastage, Forecast, Dual-Pipeline Comparison
- [x] Search/Reports/Export: filtering + downloadable reports + CSV/Excel for permitted roles + in-app viewer
- [x] Performance < 5s (precomputed JSON)
- [x] Scalability: 1.21M handled; Parquet + Spark path to 5M+ (documented)
- [x] Usability: intuitive web UI, light/dark
- [x] Accuracy ≥85% / macro-F1 ≥0.80 (Spark RF 0.91 / 0.898); forecast beats baseline
- [x] Availability target ≥99% during evaluation

## Competition integrity (38–42)
- [ ] ⏳ **Meaningful GitHub commits across all days + dev log** — commit as you go (only you can do this)
- [x] Each member can explain modules; config-driven for surprise modification (`src/config.py`)
- [x] Spark and Python models proven to run independently (no copy-paste) — real Spark run + comparison
- [x] AI tool usage declared (`AI_USAGE.md`)
- [x] Tested against defective data (boundary/hidden-defect test in `tests/test_data_quality.py`)

## Deliverables (43–57)
- [x] Project Report — full architecture, database, **DFD/Use-Case/Activity/Sequence diagrams**, methodology (`DineIQ_Project_Report.docx`)
- [x] Complete source (README, AI_USAGE.md, requirements.txt, src/, spark_jobs/, models/, tests/)
- [x] Big-Data dataset with generation scripts, **data dictionary** (`DATA_DICTIONARY.md`), schemas, **train/val/test splits** (`processed_data/splits/`)
- [x] Spark processing evidence (ingestion, schema, quality, joins, SQL, Parquet output, **logs** in `spark_jobs/logs/`)
- [x] Spark MLlib evidence (features, algorithms, metrics, **saved model** `spark_jobs/models/`, sample predictions)
- [x] Python model evidence (preprocessing, features, algorithms, metrics, **saved model** `models/python_best_model.pkl`, predictions)
- [x] Dual-Pipeline Comparison Report on ≥100 unseen records (3,000)
- [x] Restaurant Intelligence Report (dishes, segments, forecasts, anomalies, recommendations)
- [x] Test cases (functional, integration, data-quality, model, security, boundary, hidden-data)
- [x] Installation & execution instructions in README.md
- [ ] ⏳ **Public GitHub repository URL with commits from every member** (only you can do this)
- [x] Deployed app or local install instructions (README) + admin credentials (`admin@dineiq.local` / `admin123`)
- [ ] ⏳ **Demo video (.mp4)** — record using `DEMO_VIDEO_SCRIPT.md`
- [x] Technical blog (2,000+ words) drafted (`TECHNICAL_BLOG.md`) — ⏳ publish on an approved platform
- [x] AI_USAGE.md completed + this checklist

---

### What's left for you (3 items — all external by nature)
1. **Commit history + public GitHub URL** (items 38, 53) — push regularly so each member has commits.
2. **Demo video .mp4** (item 55) — record with the provided script; ~10 minutes of work.
3. **Publish the blog** (item 56) — the 2,000-word draft is ready in `TECHNICAL_BLOG.md`.
