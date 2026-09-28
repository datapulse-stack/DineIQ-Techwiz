# AI Usage Declaration

Per the competition integrity rules, this file declares how AI tooling was used
while building DineIQ Analytics. All generated code was reviewed, edited where
needed, understood and tested by the team.

| Tool | Purpose | Files / modules affected | Changes made | Testing performed |
|------|---------|--------------------------|--------------|-------------------|
| AI coding assistant | Scaffolding boilerplate and the SVG chart helpers | `static/dashboard.js`, `static/style.css` | Rewrote page renderers to read our real pipeline output; tuned layout, colours and copy | Rendered all 12 dashboard views against live pipeline JSON; checked in browser (light + dark) |
| AI coding assistant | Draft of analytics module structure | `src/*.py` | Implemented and adjusted the classification rules, RFM logic, forecasting split, promotion-trap logic and thresholds ourselves; verified formulas by hand | Ran `python run_all.py`, inspected `outputs/dashboard_data.json` and every `processed_data/*.csv` |
| AI coding assistant | Draft of the PySpark mirror | `spark_jobs/spark_pipeline.py` | Aligned the Spark logic with our pandas rules; confirmed schema and join semantics | Reviewed logic; runs where a JVM + Spark are available |

Notes:
- No external generative-AI decision API is called at analysis, prediction or
  recommendation time. All insights are computed by our own code from the data.
- The Spark and Python pipelines produce their results independently; predictions
  are never copied from one into the other.
- Each team member can explain the modules assigned to them and the reasoning
  behind the thresholds and formulas used.
