# builds the formal project report .docx from the real dineiq facts.
# follows the structure of the provided sample template, section for section,
# and embeds the generated DFD / use-case / activity / sequence diagrams.
import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.dirname(os.path.abspath(__file__))
DIAG = os.path.join(ROOT, "docs", "diagrams")

TEAL = RGBColor(0x0E, 0x6E, 0x63)
TEAL_D = RGBColor(0x0A, 0x4A, 0x43)
INK = RGBColor(0x1B, 0x2A, 0x28)
GREY = RGBColor(0x5A, 0x6A, 0x67)
HEADFILL = "0E6E63"
ZEBRA = "EAF4F2"

doc = Document()
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
normal.font.color.rgb = INK
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.15

for i, col in ((1, TEAL_D), (2, TEAL), (3, TEAL)):
    st = doc.styles[f"Heading {i}"]
    st.font.name = "Calibri"
    st.font.color.rgb = col
    st.font.bold = True
    st.font.size = Pt(16 - (i - 1) * 3)
    st.paragraph_format.space_before = Pt(14 if i == 1 else 8)
    st.paragraph_format.space_after = Pt(4)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hexcolor)
    tcPr.append(sh)


def set_cell_text(cell, text, bold=False, color=None, size=9.5, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    if align:
        p.alignment = align
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.space_before = Pt(1)
    for j, line in enumerate(str(text).split("\n")):
        if j:
            p.add_run().add_break()
        r = p.add_run(line)
        r.bold = bold
        r.font.size = Pt(size)
        r.font.name = "Calibri"
        if color:
            r.font.color.rgb = color


def add_table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        set_cell_text(hdr[i], h, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade(hdr[i], HEADFILL)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for ci, val in enumerate(row):
            set_cell_text(cells[ci], val)
            if ri % 2 == 1:
                shade(cells[ci], ZEBRA)
    if widths:
        for row in t.rows:
            for ci, w in enumerate(widths):
                row.cells[ci].width = Inches(w)
    doc.add_paragraph()
    return t


def mono(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.12)
    p.paragraph_format.space_after = Pt(8)
    for j, line in enumerate(text.strip("\n").split("\n")):
        if j:
            p.add_run().add_break()
        r = p.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(8.5)
        r.font.color.rgb = TEAL_D
    return p


def bullets(items, style="List Bullet"):
    for it in items:
        if isinstance(it, tuple):
            lead, rest = it
            p = doc.add_paragraph(style=style)
            r = p.add_run(lead)
            r.bold = True
            p.add_run(rest)
        else:
            doc.add_paragraph(it, style=style)


def caption(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(8.5)
    r.font.color.rgb = GREY
    p.paragraph_format.space_after = Pt(10)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def figure(path, cap, width=6.3):
    if os.path.exists(path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(path, width=Inches(width))
    caption(cap)


# =====================================================================
# COVER
# =====================================================================
def cover_line(text, size, color, bold=False, italic=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.bold = bold
    r.italic = italic


cover_line("Project Report Document", 13, GREY, bold=True)
cover_line("DineIQ Analytics", 30, TEAL_D, bold=True)
cover_line("MenuMatrix Dining Intelligence", 15, TEAL)
cover_line("A Big-Data & Data-Science platform for restaurant operational intelligence",
           10.5, GREY, italic=True)
doc.add_paragraph()
add_table(
    ["Field", "Detail"],
    [
        ["Application name", "DineIQ Analytics (brand: Data Pulse)"],
        ["Document type", "Comprehensive Project Report"],
        ["Version", "2.0"],
        ["Date", "28 September 2026"],
        ["Implementation", "Python analytics + Flask dashboard; Apache Spark Big-Data track"],
        ["Dataset scale", "1.21M order-lines · 312.5K orders · 52K customers · 150 items · 20 outlets · 12 months"],
        ["Dual pipeline", "Spark MLlib (Random Forest) vs Python DS (GBM) — 95% agreement on 3,000 cases"],
    ],
    widths=[1.7, 4.6],
)
doc.add_page_break()

# =====================================================================
# EXECUTIVE SUMMARY
# =====================================================================
doc.add_heading("Executive Summary", level=1)
doc.add_paragraph(
    "This report details the end-to-end design, implementation, and evaluation of DineIQ Analytics "
    "(product name MenuMatrix, presented under the Data Pulse brand) — a Big-Data and Data-Science-driven "
    "analytical platform for multi-outlet restaurant chains. Engineered to replace static spreadsheets and "
    "fragmented reporting, the platform ingests high-volume transactional data through a reproducible pipeline "
    "and applies machine-learning models to deliver actionable operational intelligence, predictive forecasts, "
    "and evidence-backed recommendations that support strategic decision-making."
)
doc.add_paragraph(
    "The system processes a synthetic yet realistic estate of 20 restaurant locations over 12 continuous "
    "months: 1,209,427 order-line records across 312,502 orders placed by 51,850 active customers. On this "
    "estate DineIQ measures $33.75M in revenue and $18.27M in contribution profit, an average order value of "
    "$108, a 7.3% wastage rate ($2.46M cost), and produces a 14-day demand forecast with a 3.9% MAPE "
    "(R² = 0.86) — a 73% error reduction over a naive baseline. Two genuinely independent modelling pipelines "
    "— a PySpark MLlib track and a Python Data-Science track — classify every item×location cell and agree on "
    "95% of 3,000 validation cases, with all 162 disagreements logged and explained."
)

# =====================================================================
# 1. BACKGROUND
# =====================================================================
doc.add_heading("1. Project Background & Proposed Solution", level=1)
doc.add_heading("1.1 Problem Statement & Business Necessity", level=2)
doc.add_paragraph(
    "A modern multi-outlet restaurant generates multi-dimensional transactional and operational data across "
    "several channels (dine-in, takeaway, website/app, delivery). Legacy tools rely on basic aggregations and "
    "manual month-on-month comparisons, and so fail to surface non-linear relationships, hidden margin erosion, "
    "and subtle behavioural patterns. Without automated ingestion, predictive forecasting, and anomaly "
    "detection, operators risk margin loss, unoptimised pricing and promotions, and stock/wastage "
    "misallocation. A dish that sells in huge volume can quietly lose money on every plate; a high-margin, "
    "well-rated dish can stay invisible because it is never surfaced. These are the blind spots DineIQ closes."
)
doc.add_heading("1.2 Proposed Solution", level=2)
doc.add_paragraph(
    "DineIQ deploys a web-based intelligence suite that cleans, models and visualises large datasets. Two "
    "independent analytical engines process the same source data and their results are compared, so no single "
    "model is trusted blindly:"
)
mono(
    "[ 11 raw CSV tables ]\n"
    "        |\n"
    "        v\n"
    "[ Data-quality + cleaning ] --> [ Integration: order-line fact table ] --> [ Feature engineering ]\n"
    "        |                                                                            |\n"
    "        |                                    +---------------------------------------+\n"
    "        v                                    v\n"
    "[ Python DS pipeline (src/) ]      [ Big-Data pipeline (spark_jobs/) ]\n"
    "  pandas + scikit-learn               PySpark + Spark SQL + MLlib\n"
    "        \\                                    /\n"
    "         v                                  v\n"
    "        [ Model-comparison engine ] --> [ dashboard_data.json ] --> [ Flask web dashboard ]"
)
caption("Figure 1 — High-level data flow. Both modelling tracks read identical inputs and never share predictions.")
bullets([
    ("Reproducible data pipeline. ", "A single seeded run generates the dataset and executes 12 ordered stages."),
    ("Dual machine-learning verification. ", "A real Apache Spark MLlib pipeline and a Python scikit-learn "
     "pipeline run side-by-side verification on identical core data."),
    ("Actionable analytics & dashboard. ", "Classifications, forecasts, anomaly flags and evidence-backed "
     "recommendations delivered through an interactive, role-aware dashboard with CSV/Excel export."),
])

# =====================================================================
# 2. SCOPE
# =====================================================================
doc.add_heading("2. Project Scope & Operational Constraints", level=1)
doc.add_heading("2.1 Scope", level=2)
bullets([
    ("In-Scope: ", "Large-scale synthetic dataset generation; batch ETL; feature engineering; 4-quadrant menu "
     "classification; RFM + K-Means segmentation; market-basket mining; time-aware forecasting (overall + per "
     "location/category); dual ML pipelines with automated comparison; pricing elasticity, promotion-trap "
     "detection, wastage analysis, anomaly detection and a churn-risk model; peak-period analysis; a what-if "
     "simulation engine; role-based authentication and audit trail; and an interactive dashboard with CSV + "
     "Excel export, an in-app report viewer and a rule-based assistant."),
])
bullets([
    ("Out-of-Scope: ", "Live transactional POS / payment-gateway execution; hardware terminal integrations; "
     "automated live third-party API write-backs; and any external generative-AI decision API in the "
     "analysis, prediction or recommendation path (all insights are computed by the project's own code)."),
])
doc.add_heading("2.2 System Constraints", level=2)
bullets([
    ("Data-quality dependency. ", "Accuracy is bound to input completeness and cleanliness; the pipeline "
     "quarantines bad records before modelling and logs every action."),
    ("Computational footprint. ", "The reference Python pipeline runs on a standard multi-core machine and "
     "processes the full 1.2M-line estate in one pass using compact dtypes, column-pruned loads and explicit "
     "garbage collection. The Spark track needs a JVM (17+) and benefits from ≥8 GB RAM for larger estates."),
    ("Model-convergence drift. ", "Small variances between Spark MLlib and scikit-learn are expected; the "
     "comparison engine measures and reports this divergence rather than hiding it."),
])

# =====================================================================
# 3. REQUIREMENTS
# =====================================================================
doc.add_heading("3. System Requirements & Specifications", level=1)
doc.add_heading("3.1 Functional Requirements Matrix", level=2)
add_table(
    ["ID", "Module Category", "Functional Requirement Description"],
    [
        ["FR-01", "Authentication & RBAC", "Secure multi-role access (Admin, Manager, Analyst) with SQLite audit trail."],
        ["FR-02", "Data Ingestion & Storage", "Ingestion of 11 CSV tables; Spark writes a partitioned Parquet processed layer."],
        ["FR-03", "Data Quality & Cleaning", "Identify and quarantine missing/duplicate/negative/anomalous records, with a cleaning log."],
        ["FR-04", "Feature Engineering", "Margin %, moving averages, RFM, trend indicators, demand/profit scores relative to the menu."],
        ["FR-05", "Performance Classification", "Location-specific 4-quadrant menu classification."],
        ["FR-06", "Customer Segmentation", "RFM + K-Means into six tiers, with order-value, category-preference, promo-sensitivity and channel."],
        ["FR-07", "Market-Basket Analysis", "Support / Confidence / Lift association rules and cross-sell bundles."],
        ["FR-08", "Demand Forecasting", "Time-aware forecast overall and per location/category with a configurable horizon."],
        ["FR-09", "Dual ML Pipelines", "Real Spark MLlib and Python DS pipelines with automated result comparison."],
        ["FR-10", "Anomaly & Churn", "Sales/rating anomaly detection, promotion-trap detection, and a churn-risk model."],
        ["FR-11", "Simulation Engine", "Interactive what-if modelling for price, margin and demand shifts."],
        ["FR-12", "Dashboards & Reporting", "Executive, menu, customer, forecast, wastage and model-comparison views; CSV + Excel export; in-app report viewer."],
        ["FR-13", "Self-Service & Assistant", "Forgot-password self-service reset for all roles and a rule-based analytics assistant."],
    ],
    widths=[0.6, 1.9, 3.8],
)
doc.add_heading("3.2 Non-Functional Requirements", level=2)
bullets([
    ("Performance. ", "The dashboard renders from a precomputed JSON payload; standard views respond well "
     "within the < 5-second target and report endpoints return in under 100 ms in testing."),
    ("Scalability. ", "The pipeline handles the full 1.21M order-line estate without redesign; the Parquet "
     "layer and the distributed Spark track provide the path to 5M+ records."),
    ("Model accuracy. ", "Target ≥ 85% accuracy or macro-F1 ≥ 0.80. Achieved: the selected Spark MLlib Random "
     "Forest reaches 91% accuracy and macro-F1 = 0.898 — both thresholds met; the Python GBM reaches 91% "
     "accuracy. Forecast beats the baseline (MAPE 3.9% vs 14.6%, R² 0.86)."),
    ("Availability & Reproducibility. ", "≥ 99% uptime target; a fixed seed makes the whole dataset and every "
     "downstream result regenerable with one command."),
])

# =====================================================================
# 4. ARCHITECTURE
# =====================================================================
doc.add_heading("4. System Architecture & Methodology", level=1)
doc.add_heading("4.1 System Technology Stack", level=2)
add_table(
    ["Layer", "Component / Technology"],
    [
        ["User Interface", "HTML5, CSS3, JavaScript; hand-drawn inline SVG charts; light + dark themes"],
        ["Application Backend", "Flask (Python); role-based routing and audit logging"],
        ["Big-Data Platform", "Apache Spark 4.2, PySpark, Spark SQL, Spark MLlib"],
        ["Data Storage", "CSV (source), Apache Parquet (Spark processed layer), SQLite (users/audit)"],
        ["Machine Learning (Dual)", "Pipeline A: Spark MLlib  |  Pipeline B: scikit-learn, pandas, NumPy, SciPy"],
        ["Visualization & Reporting", "Custom SVG chart toolkit; CSV + Excel export via openpyxl"],
    ],
    widths=[1.9, 4.4],
)
doc.add_heading("4.2 Layered Architecture", level=2)
doc.add_paragraph(
    "DineIQ follows an offline-compute / online-serve design. Heavy analytics run once in the pipeline and "
    "persist their results; the web tier only reads and renders them, which keeps the interface fast and the "
    "compute reproducible."
)
mono(
    "+----------------------------------------------------------------------+\n"
    "|  PRESENTATION   Flask templates + SVG dashboard (light/dark themes)   |\n"
    "+----------------------------------------------------------------------+\n"
    "|  SERVICE        routes | auth + RBAC | live filters | report + chat   |\n"
    "|                 API | export (CSV/Excel)                              |\n"
    "+----------------------------------------------------------------------+\n"
    "|  ANALYTICS      src/ pipeline (12 stages) + spark_jobs/ Spark MLlib   |\n"
    "+----------------------------------------------------------------------+\n"
    "|  DATA           raw_data/*.csv -> processed_data/*.csv + Parquet |    |\n"
    "|                 outputs/dashboard_data.json | database/dineiq.db      |\n"
    "+----------------------------------------------------------------------+"
)
caption("Figure 2 — Layered architecture: analytics compute offline and persist; the web tier serves the results.")

doc.add_heading("4.3 Design Diagrams (DFD, Use-Case, Activity, Sequence)", level=2)
doc.add_paragraph(
    "The following diagrams document the system from four standard viewpoints: how data flows, what each role "
    "can do, how the pipeline executes, and how a typical request is served."
)
figure(os.path.join(DIAG, "dfd.png"), "Figure A — Data-Flow Diagram (Level 1).")
figure(os.path.join(DIAG, "usecase.png"), "Figure B — Use-Case Diagram (Admin / Manager / Analyst).")
figure(os.path.join(DIAG, "activity.png"), "Figure C — Activity Diagram of the analytics pipeline.", width=4.7)
figure(os.path.join(DIAG, "sequence.png"), "Figure D — Sequence Diagram: viewing a report.")

# =====================================================================
# 5. DATASET
# =====================================================================
doc.add_heading("5. Dataset Engineering & Synthetic Data Generation", level=1)
doc.add_paragraph(
    "A seeded synthetic data generator builds an internally consistent restaurant estate. Prices sit inside "
    "per-category bands; food-cost fractions and popularity are drawn independently so the menu naturally spans "
    "all four performance quadrants, including deliberate loss-leaders so the classifier has genuine "
    "volume-driver traps to catch. A full column-level data dictionary is provided in DATA_DICTIONARY.md."
)
doc.add_heading("5.1 Dataset Scale Specifications", level=2)
add_table(
    ["Entity / Table", "SRS Minimum", "Delivered", "Status"],
    [
        ["Order-line records (order_items)", "≥ 1,000,000", "1,209,427", "Met"],
        ["Orders (headers)", "≥ 100,000", "312,503", "Met"],
        ["Customers", "≥ 50,000", "52,000", "Met"],
        ["Menu items", "≥ 150", "150", "Met"],
        ["Menu categories", "≥ 10", "10", "Met"],
        ["Operating locations", "≥ 20", "20", "Met"],
        ["Temporal horizon", "≥ 12 months", "365 days", "Met"],
        ["Customer ratings", "≥ 100,000", "157,007", "Met"],
        ["Wastage records", "≥ 50,000", "152,901", "Met"],
        ["Pricing history / Promotions", "multi-point", "598 / 9", "Met"],
    ],
    widths=[2.6, 1.3, 1.3, 0.9],
)
caption("Table 1 — All SRS minimum data volumes are met.")
doc.add_heading("5.2 Entity Relationship Schema", level=2)
doc.add_paragraph(
    "Eleven tables connected by strict foreign keys; the order-line (order_items) table is the transactional "
    "grain the pipeline integrates into a single fact table. Reproducible train/validation/test splits of the "
    "modelling table (70/15/15, stratified) are saved under processed_data/splits/."
)
mono(
    "locations (location_id PK)                 menu_categories (category_id PK)\n"
    "     |  1                                          |  1\n"
    "     |  *                                          |  *\n"
    "  orders (order_id PK) ------------------->  menu_items (item_id PK)\n"
    "   | location_id FK -> locations               | category_id FK -> menu_categories\n"
    "   | customer_id  FK -> customers              /\n"
    "   | promotion_id FK -> promotions            /\n"
    "     |  1                                     /  *\n"
    "     |  *                                    /\n"
    "  order_items (order_item_id PK) ----------+\n"
    "   | order_id FK -> orders,  item_id FK -> menu_items\n"
    "\n"
    "customers (customer_id PK)     ratings (item_id, customer_id FK)\n"
    "promotions (promotion_id PK)   pricing_history (item_id FK, effective_date)\n"
    "inventory (item_id, location_id FK)   wastage (item_id, location_id FK, date)"
)
caption("Figure 3 — Entity relationships. order_items is the ≥1M-row transactional grain.")

# =====================================================================
# 6. ML
# =====================================================================
doc.add_heading("6. Machine Learning Implementation & Dual-Pipeline Verification", level=1)
doc.add_heading("6.1 Performance Classification & Modeling Rules", level=2)
doc.add_paragraph(
    "Every item×location cell is scored for demand and profitability relative to the whole menu; profitability "
    "is then knocked down for wastage and weak ratings before bucketing, so high sales alone never make a dish "
    "a winner. The label is location-specific — the same dish can be a Profit Driver at a busy branch and a Low "
    "Performer at a quiet one. Across the 150-item menu the four quadrants resolve as:"
)
add_table(
    ["Class", "Rule (relative to menu)", "Items"],
    [
        ["Profit Driver", "High volume AND high margin (≥ baseline)", "20"],
        ["Volume Driver", "High volume BUT low contribution margin", "15"],
        ["Hidden Opportunity", "High margin & strong ratings BUT low exposure", "66"],
        ["Low Performer", "Low volume, poor margin, high wastage/cost", "49"],
    ],
    widths=[1.7, 3.7, 0.9],
)
doc.add_heading("6.2 Dual Pipeline Architecture", level=2)
bullets([
    ("Pipeline A — Big Data (spark_jobs/spark_pipeline.py). ", "A real Apache Spark job: schema-defined "
     "ingestion, Spark SQL joins, Window-function features, a partitioned-Parquet processed layer, and three "
     "Spark MLlib classifiers (Random Forest, Decision Tree, Logistic Regression). It saves the best model and "
     "writes per-row predictions to spark_predictions.csv."),
    ("Pipeline B — Python DS (src/models.py). ", "Independently preprocesses with pandas and trains several "
     "scikit-learn families, selecting the best by macro-F1 and saving models/python_best_model.pkl."),
])
doc.add_paragraph(
    "The two tracks never share predictions. Where Spark is unavailable, the Python side trains a second, "
    "differently-configured family as an honest, clearly-labelled stand-in so the comparison always runs. "
    "The selected models and leaderboards from the current run:"
)
add_table(
    ["Pipeline", "Model", "Accuracy", "Macro-F1", "Selected"],
    [
        ["A · Spark MLlib", "Random Forest", "0.910", "0.898", "Yes"],
        ["A · Spark MLlib", "Decision Tree", "0.894", "0.884", "No"],
        ["A · Spark MLlib", "Logistic Regression", "0.868", "0.845", "No"],
        ["B · Python DS", "XGBoost-style GBM", "0.910", "0.757", "Yes"],
        ["B · Python DS", "Extra Trees", "0.906", "0.752", "No"],
        ["B · Python DS", "Logistic Regression", "0.890", "0.738", "No"],
    ],
    widths=[1.6, 2.1, 1.0, 1.0, 0.9],
)
doc.add_heading("6.3 Model Verification & Discrepancy Matrix", level=2)
doc.add_paragraph(
    "Both pipelines predict across 3,000 item×location validation cells. They agree on 2,838 of them — a "
    "dual-pipeline agreement rate of 95%, with all 162 disagreements recorded and explained. Sample rows from "
    "the genuine PySpark MLlib run versus the Python model:"
)
add_table(
    ["Item", "Location", "Spark MLlib", "Python DS", "Status", "Note"],
    [
        ["Steak Sandwich", "Grand Mall", "Hidden Opp.", "Profit Driver", "MISMATCH", "Margin near the profit cut-line."],
        ["Hummus Platter", "Palm Court", "Low Performer", "Volume Driver", "MISMATCH", "Demand near the volume cut-line."],
        ["Beef Wellington", "Central Station", "Hidden Opp.", "Profit Driver", "MISMATCH", "Exposure threshold differs."],
        ["Vegetable Pulao", "Riverside", "Volume Driver", "Low Performer", "MISMATCH", "Contribution-margin weight variance."],
        ["Seafood Linguine", "Lakeside", "Profit Driver", "Profit Driver", "MATCH", "Exact agreement."],
    ],
    widths=[1.6, 1.4, 1.3, 1.3, 0.9, 1.6],
)
caption("Table 2 — Rows from processed_data/model_comparison.csv. Overall agreement: 95% (2,838 / 3,000).")

# =====================================================================
# 7. OPERATIONAL ANALYTICS
# =====================================================================
doc.add_heading("7. Operational Analytics & Recommendation Engine", level=1)
doc.add_heading("7.1 Market-Basket Analysis", level=2)
doc.add_paragraph(
    "Association-rule mining over the order baskets computes Support, Confidence and Lift to surface items that "
    "sell together, driving automated cross-sell bundling.")
bullets([
    ("Sample rule: ", "{Mixed Grill} → {Four Cheese Pasta} (Support 0.002, Confidence 0.046, Lift 1.05)."),
    ("Actionable output: ", "Auto-generated combo suggestions and checkout add-on prompts."),
])
doc.add_heading("7.2 Demand Forecasting & Segmentation Depth", level=2)
doc.add_paragraph(
    "The overall daily-orders forecast uses a seasonal (day-of-week) + trend model validated on a held-out "
    "tail (MAE 31, RMSE 40.3, MAPE 3.9%, R² 0.86) and benchmarked against a naive baseline (MAPE 14.6%). The "
    "same model is applied per location and per category (forecast_by_location.csv, forecast_by_category.csv). "
    "Customer segmentation groups by RFM plus order value, category preference, promotion sensitivity and top "
    "channel, so each of the six tiers carries a full behavioural profile."
)
doc.add_heading("7.3 Churn-Risk Model & Peak-Period Analysis", level=2)
bullets([
    ("Churn model. ", "A logistic-regression classifier scores every customer's churn probability from "
     "behaviour features (frequency, monetary, category breadth, promo share, AOV — recency is deliberately "
     "excluded to avoid label leakage). Test accuracy 0.72, AUC 0.70; customers are banded Low / Medium / High "
     "risk (3,406 currently High)."),
    ("Peak periods. ", "Order volume is analysed by hour, day-of-week, weekday-vs-weekend, month (seasonality) "
     "and per location. The estate peaks on Fridays around 7 pm; each outlet also has its own peak day/hour."),
])
doc.add_heading("7.4 Evidence-Based Recommendations & Simulation", level=2)
doc.add_paragraph("Every recommendation carries the empirical evidence behind it — nothing is a black box:")
mono(
    "RECOMMENDED ACTION:  Promote 'Fish Tacos'\n"
    "  Priority:   CRITICAL\n"
    "  Evidence:   - 71% contribution margin (among the highest on the menu)\n"
    "              - 4.1 / 5.0 average rating   - only 10.4% wastage\n"
    "              - currently a Hidden Opportunity (low order frequency)\n"
    "  Strategy:   Feature on the homepage and suggest at checkout\n"
    "  Impact:     + estimated profit uplift"
)
doc.add_paragraph(
    "The what-if simulation engine lets managers adjust base prices, discounts or volume assumptions and "
    "immediately estimate the resulting revenue and margin change before committing."
)

# =====================================================================
# 8. QA
# =====================================================================
doc.add_heading("8. Verification, Quality Assurance & Edge-Case Scenarios", level=1)
doc.add_heading("8.1 Automated Test Suite", level=2)
doc.add_paragraph(
    "An automated pytest suite (tests/, 18 tests, all passing) covers six categories:"
)
bullets([
    ("Functional. ", "Dataset scale minimums and referential integrity; dashboard payload completeness."),
    ("Data-quality & boundary. ", "A synthetic frame with injected defects (duplicates, negative/zero "
     "quantities, negative prices, unknown items, out-of-range ratings, negative wastage, guest orders) proves "
     "the cleaning rules catch each one — the hidden-defective-dataset readiness check."),
    ("Integration. ", "The fact table builds and revenue reconciles; profit never exceeds revenue."),
    ("Model. ", "Comparison covers ≥100 records, agreement is in a sane band, ≥3 Spark algorithms compared, "
     "saved models exist, the forecast beats the baseline, and churn metrics are valid."),
    ("Security. ", "Passwords are hashed (never plaintext), wrong passwords are rejected, role permissions are "
     "enforced (Analyst view-only, Manager export, Admin all), and password reset changes the stored hash."),
])
doc.add_heading("8.2 Contradictory & Edge-Case Evaluation", level=2)
add_table(
    ["Scenario", "Edge Behaviour / Anomaly", "System Handling & Output"],
    [
        ["High volume / negative margin", "High order count but priced below cost (e.g. Weekday Lunch Combo)", "Flagged as a Promotion Trap / loss-making Volume Driver (verdict: TRAP)."],
        ["High rating / near-zero orders", "5-star item with very few lifetime orders", "Classified Hidden Opportunity with a cold-start caveat."],
        ["Unusual rating spikes", "Burst of identical extreme ratings in a narrow window", "Flagged by the rating-anomaly detector."],
        ["Revenue spike", "Daily revenue > 2σ from the norm", "Raised as a medium-severity anomaly."],
        ["Stale session after data regen", "Old cookie points to a user that no longer exists", "Session cleared and redirected to login instead of erroring."],
    ],
    widths=[1.6, 2.4, 2.3],
)

# =====================================================================
# 9. ARTIFACTS
# =====================================================================
doc.add_heading("9. Project Execution & Submission Artifacts", level=1)
doc.add_heading("9.1 Source-Code Directory Layout", level=2)
mono(
    "dineiq/\n"
    "|- run_all.py             generate data + run pipeline\n"
    "|- app.py  auth.py        Flask dashboard + auth/RBAC/audit\n"
    "|- requirements.txt  README.md  AI_USAGE.md  DATA_DICTIONARY.md\n"
    "|- TECHNICAL_BLOG.md  DEMO_VIDEO_SCRIPT.md  SUBMISSION_CHECKLIST.md\n"
    "|- data_generator/        generate_data.py (11 CSV tables)\n"
    "|- raw_data/              generated raw CSVs\n"
    "|- processed_data/        report CSVs + spark/ (Parquet) + splits/\n"
    "|- outputs/               dashboard_data.json\n"
    "|- src/                   pipeline + 17 analytics modules (incl. churn.py)\n"
    "|- spark_jobs/            spark_pipeline.py + models/ + logs/\n"
    "|- models/                python_best_model.pkl\n"
    "|- tests/                 pytest suite (functional/integration/dq/model/security)\n"
    "|- docs/diagrams/         DFD, use-case, activity, sequence PNGs\n"
    "|- templates/  static/    dashboard, auth pages, CSS/JS, scene\n"
    "|- database/              dineiq.db + session key (auto-created)"
)
doc.add_heading("9.2 Submission Verification Checklist", level=2)
for item in [
    "Comprehensive project report — architecture, DFD/use-case/activity/sequence diagrams, data dictionary, dual-pipeline evaluation.",
    "Dataset generator — produces ≥ 1,000,000 compliant order-line records from one seed.",
    "Big-Data evidence — Spark ingestion, SQL joins, partitioned Parquet output, run log, 3 MLlib algorithms + saved model.",
    "Dual ML pipelines — genuine Spark MLlib vs Python DS producing independent predictions.",
    "Model-comparison report — model_comparison.csv over 3,000 records with agreement + disagreements.",
    "Interactive dashboard suite — executive, menu, customer, forecast, wastage, locations, anomalies, model-comparison, reports.",
    "Role-based access & audit trail — Admin / Manager / Analyst with real, visible differences.",
    "Automated test suite — 18 pytest cases across all six categories, all passing.",
    "Data dictionary + train/val/test splits saved to disk.",
    "AI-usage declaration (AI_USAGE.md), README with setup steps, technical blog and demo-video script.",
]:
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run("[x] ")
    r.bold = True
    r.font.color.rgb = TEAL
    p.add_run(item)

doc.add_paragraph()
p = doc.add_paragraph()
r = p.add_run(
    "All figures are drawn from the project's own computed outputs (outputs/dashboard_data.json, "
    "processed_data/*.csv and spark_metrics.json) and are regenerable with a single seeded run.")
r.italic = True
r.font.size = Pt(8.5)
r.font.color.rgb = GREY

doc.save(os.path.join(ROOT, "DineIQ_Project_Report.docx"))
print("saved DineIQ_Project_Report.docx")
