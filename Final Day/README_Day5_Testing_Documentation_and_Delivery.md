# Day 5: Testing, Documentation and Delivery

**Project:** DineIQ Analytics | **Goal:** everything tested, documented, deployed and submitted.
**Checklist items:** 33, 34, 36, 37, 39, 42, 43, 44, 49, 50, 51, 52, 53, 54, 55, 56, 57

---

## Morning: Testing and Hardening

- [ ] **Non-functional checks** [33, 34, 36]
  - Predictions returned within 5 seconds
  - Design supports 5M+ order lines without redesign
  - Classification at least 85% accuracy or macro F1 of at least 0.80, forecast beats baseline
- [ ] **Hidden-dataset test** [42]
  - Run the full pipeline on a new dataset with missing values, duplicates, unknown items, new locations, price changes, extreme wastage, seasonal shifts, outliers
- [ ] **Test cases** [51]
  - Functional, integration, ingestion, schema, data quality, Spark transformation, Spark SQL, Spark model, Python model, dual-pipeline, forecast, basket, wastage, promotion, pricing, anomaly, security, boundary, hidden-data
  - Include the difficult cases: high-selling loss-making dish, low-selling high-margin dish, promotion increasing sales but reducing profit, new item, churn, rating anomaly, Spark/Python disagreement
- [ ] **Viva and surprise-task practice** [39]
  - Each member explains their modules
  - Practice: add a location, add a category, change a threshold, add a KPI, add an anomaly rule, change the forecast window, add a filter

## Afternoon: Documents and Deployment

- [ ] **Project Report** [43]
  - Problem, background, solution, scope, assumptions, constraints, requirements
  - Architecture, ERD, data dictionary, DFD, use case, activity and sequence diagrams
  - Methodology for data generation, quality, Spark, features, models, comparison, testing, security, privacy, limitations, future work
- [ ] **Dual-Pipeline Comparison Report** on 100+ unseen records [49]
- [ ] **Restaurant Intelligence Report** [50]
  - Profitable and volume dishes, hidden opportunities, low performers, slow movers, high wastage, peaks, segments, churn risk, combinations, forecasts, promotions, price-sensitive items, locations, anomalies, final recommendations
- [ ] **Installation and execution instructions** in the main README [52]
- [ ] **Source code cleanup** [44]
  - Remove unused code, confirm requirements.txt, confirm repo structure, remove hard-coded insights
- [ ] **Deploy the app** and prepare evaluator and admin credentials [37, 54]

## Evening: Media and Submission

- [ ] **Demo video (.mp4)** [55]
  - Login, dataset generation, ingestion, Spark processing, data quality and cleaning, Spark SQL, features
  - Menu profitability and classification, segmentation, RFM, basket, peaks, forecast, wastage, pricing, promotions, anomalies
  - Spark prediction, Python prediction, dual comparison, recommendations, what-if, dashboards, report export
  - At least one difficult contradictory business case
- [ ] **Technical blog** of 2,000+ words on a free platform, linked in the README [56]
- [ ] **AI_USAGE.md complete** [57]
  - Tool, purpose, assistance type, files affected, modifications, testing, verifier name
- [ ] **Final GitHub check** [53]
  - Public, commits from every member across all days, screenshots, credentials, test results, links to report, blog and video

## Final Submission Checklist

- [ ] Project report
- [ ] Public GitHub URL
- [ ] Complete source code
- [ ] Dataset-generation scripts and Big Data dataset
- [ ] Data dictionary
- [ ] Spark jobs and Spark SQL scripts
- [ ] Parquet datasets
- [ ] Spark MLlib and Python models
- [ ] Dual-pipeline comparison report
- [ ] Restaurant Intelligence report
- [ ] Test cases and results
- [ ] Installation and execution instructions
- [ ] Deployment URL
- [ ] Demo video
- [ ] Technical blog
- [ ] Project presentation
- [ ] AI_USAGE.md
- [ ] Team contribution record

Keep about 2 hours as a buffer for deployment problems.

## Development Log: Day 5

| Item | Notes |
|---|---|
| Work completed | |
| Dataset changes | |
| Data-quality problems | |
| Spark failures | |
| Model failures | |
| Changes made | |
| Tests performed | |
| Performance improvements | |
