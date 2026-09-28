# Building DineIQ: turning a million restaurant order-lines into decisions

*How we built a dual-pipeline, Big-Data + Data-Science platform that tells a
restaurant chain which dishes make money, which ones only look busy, and what to
do about it.*

---

## Why we built this

Restaurants sit on a surprising amount of data and use almost none of it. A busy
20-outlet chain will push hundreds of thousands of orders through the tills every
year, each one a little bundle of signals: what sold, at what price, on which
channel, with which discount, and whether the customer ever came back. Most teams
still look at that through a monthly spreadsheet and a gut feeling.

The problem with the spreadsheet view is that it rewards the wrong things. The
dish at the top of the "units sold" column feels like a winner. But if it's
discounted into the ground on a combo, or it wastes half its prep every night, it
can be quietly losing money on every plate. Meanwhile a high-margin, well-rated
dish that nobody ever sees on the menu stays invisible — the spreadsheet has no
column for "opportunity we're missing."

DineIQ (product name *MenuMatrix*, shipped under the *Data Pulse* brand) is our
answer. It ingests the raw transactional data, cleans it, engineers features,
runs two independent machine-learning pipelines, and surfaces the result as an
interactive dashboard with plain-English recommendations. Everything is computed
by our own code — there is no external "AI" API making the calls.

This post walks through how it works and the engineering decisions we're most
proud of.

---

## The data: realistic, not just big

The brief asked for scale — at least a million order-lines, a hundred thousand
orders, fifty thousand customers, a full year of history across twenty locations.
Rather than hunt for a public dataset that fit, we wrote a generator so we could
control the *shape* of the data, not just its size.

Our final estate is:

- **1,209,427** order-line records
- **312,503** orders across **20** locations and **4** channels
- **52,000** customers over **12** months
- **150** menu items in **10** categories, plus ratings, inventory, wastage,
  pricing history and promotions

The generator is deliberately mischievous. It plants loss-leaders (dishes priced
below a sensible margin), promotions that discount already-profitable mains (the
classic "promotion trap"), seasonal and weekend rhythms, rating anomalies, and a
sprinkling of dirty data — duplicate lines, negative quantities, missing customer
IDs, out-of-range star ratings. If we're going to claim our pipeline catches bad
data and tricky business cases, the data has to actually contain them.

Because the whole thing is seeded, a grader can regenerate the exact same dataset
and every downstream number with one command. Reproducibility isn't a
nice-to-have here; it's the difference between "trust me" and "run it yourself."

---

## Cleaning: quarantine, don't delete

The first real stage is data quality. We assess the raw tables, then clean them
with documented rules and write a cleaning log so nothing happens silently:

- Exact-duplicate order-lines are collapsed.
- Non-positive quantities are dropped (you can't sell −1 of something).
- Invalid prices are *recovered* from the item's base price rather than thrown
  away, so we don't lose the revenue.
- Order-lines pointing at unknown items are quarantined.
- Out-of-range ratings are dropped; negative wastage is removed.
- Missing-customer orders are **flagged as guests, not deleted** — that revenue
  is real even if we don't know who spent it.

The principle throughout is *quarantine over deletion*. Every action is counted
and shown on the dashboard's data-quality view, so the cleaning is auditable.

---

## Feature engineering and the four-quadrant classifier

Once we have a clean order-line **fact table**, we engineer the features the rest
of the system needs: contribution margin, wastage percentage, repeat-purchase
rate, a sales trend (last third of the window versus the first third), RFM inputs
per customer, and daily time series.

The centrepiece is the menu classifier. Every dish is scored on two axes —
**demand** and **profitability** — but with two twists that make it more honest
than a naive sales ranking:

1. **Profitability is penalised for wastage and weak ratings** before we bucket.
   High sales alone never make a dish a "winner."
2. **The label is location-specific.** Scores are normalised *within* each branch,
   so the same dish can be a Profit Driver at a busy downtown site and a Low
   Performer at a quiet suburban one. This matters — a chain doesn't run one menu
   strategy, it runs twenty.

The four quadrants come out as:

- **Profit Driver** — high volume *and* high margin
- **Volume Driver** — high volume but thin margin (watch these)
- **Hidden Opportunity** — high margin, well-rated, but barely sold
- **Low Performer** — low volume, poor margin, high waste

On our estate that's 20 Profit Drivers, 15 Volume Drivers, 66 Hidden
Opportunities and 49 Low Performers. The Hidden Opportunities are where the money
usually hides.

---

## The bit we're proudest of: two pipelines that never talk

The brief asked for two *independent* pipelines whose results are compared. It
would have been easy to fake this — train one model, copy its predictions, call
it a day. We didn't.

**Pipeline A** is a genuine Apache Spark job (`spark_jobs/spark_pipeline.py`). It:

- ingests the raw CSVs with an explicit `StructType` schema on the 1.2M-row
  order-lines table (and inference on the small reference tables),
- joins them with **Spark SQL** into a fact table,
- engineers features with **window functions** (min/max normalisation partitioned
  by location — the same location-specific idea, done the Spark way),
- writes a **partitioned Parquet** processed layer (one partition per location),
- and trains **three Spark MLlib classifiers** — Random Forest, Decision Tree and
  Logistic Regression — comparing them on accuracy and macro-F1.

The best Spark model (Random Forest, 91% accuracy, macro-F1 **0.898**) is saved to
disk, and its per-row predictions are written to `spark_predictions.csv`.

**Pipeline B** is the Python Data-Science track (`src/models.py`): pandas
preprocessing and scikit-learn models (a gradient-boosted machine, extra-trees,
logistic regression), selecting the best by macro-F1 and saving the model as a
pickle.

The two pipelines **never share predictions**. They only meet in the comparison
engine, which lines up both prediction sets on the same 3,000 item×location cells
and measures agreement. The result: **95% agreement (2,838 of 3,000)**, with all
162 disagreements written out with the item, the location, and each side's call.
Those disagreements are genuinely interesting — they cluster on the boundary
cases, exactly where two differently-built models *should* diverge. A dish whose
margin sits right on the profit cut-line gets called "Profit Driver" by one and
"Hidden Opportunity" by the other. That's not a bug; that's the honest edge of the
model, and we surface it rather than paper over it.

One practical note for anyone reproducing this: Spark 4.x needs a Java 17+ JVM,
and if Spark isn't present the Python side trains a second, differently-configured
family as a clearly-labelled stand-in so the comparison always runs. We document
that fallback rather than hiding it.

---

## Forecasting, churn, and knowing when the rush hits

Beyond classification, DineIQ runs a suite of operational analytics:

- **Demand forecasting.** We forecast daily orders with a day-of-week seasonal
  model plus a linear trend, validated on a held-out tail with no leakage. It
  scores MAE 31, RMSE 40.3, **MAPE 3.9%** and **R² 0.86**, against a naive
  baseline of 14.6% MAPE — a 73% error reduction. The same model runs per
  location and per category so managers can see where growth is coming from.
- **Churn-risk model.** A logistic-regression classifier scores each customer's
  probability of churning from behaviour features — frequency, spend, category
  breadth, promo reliance, average order value. We deliberately *exclude recency*
  from the features because the churn label is derived from it; leaving it in
  would be textbook leakage. Customers are banded Low / Medium / High risk.
- **Market-basket analysis** for cross-sell bundles (Support / Confidence /
  Lift), **pricing elasticity** and sensitivity bands, **promotion-effectiveness**
  with automatic trap detection, **wastage** analysis and risk, **anomaly
  detection** on sales and ratings, and **peak-period** analysis by hour, day,
  weekday-vs-weekend, month and location. (Our estate peaks Fridays at 7 pm — no
  surprise to anyone who's worked a dinner shift.)

Every recommendation the system makes carries its evidence. "Promote Fish Tacos"
isn't a hunch — it comes stapled to "71% contribution margin, 4.1★, only 10.4%
wastage, currently a Hidden Opportunity." A manager can agree or disagree, but
they can always see *why*.

---

## The dashboard: fast because the hard work is already done

The web layer is a Flask app with a hand-built SVG chart toolkit — no chart CDN,
no heavy front-end framework. The design choice that makes it feel instant is
simple: **all the heavy computation happens once, offline, in the pipeline**, and
the results are persisted to a single `dashboard_data.json` plus a set of report
CSVs. The web tier only reads and renders. Standard views respond well under the
five-second target, and the report endpoints come back in under 100 ms.

On top of that sit the things that make it usable by a real team:

- **Role-based access** — Admin, Manager and Analyst with genuinely different
  capabilities (Analyst views, Manager exports, Admin manages users and sees the
  audit trail), all backed by SQLite with hashed passwords.
- **An in-app report viewer** so analysts can read the CSVs as Excel-like tables
  without downloading them.
- **CSV and Excel export** for the roles allowed to have it.
- **A rule-based assistant** that answers questions straight from the computed
  results.
- **Light and dark themes**, a restaurant-ambience backdrop, and small, tasteful
  motion — premium, not childish.

---

## Testing, and designing for the "surprise dataset"

Competitions like this often end with a twist: the graders swap in their own
dataset, full of realistic defects, and see whether your system copes. We built
for that from the start.

The config file centralises the menu, the locations, the channel mix and the
classifier thresholds, so a "surprise modification" — add a location, change a
cut-point, add a category — is a one-line edit, not a treasure hunt. And an
automated **pytest suite (18 tests, all green)** guards the behaviour across six
categories: functional (scale + integrity), data-quality and boundary (a frame of
injected defects the cleaner must catch), integration (the fact table reconciles),
model (comparison coverage, ≥3 Spark algorithms, saved models, forecast beats
baseline), and security (passwords hashed, wrong passwords rejected, role
permissions enforced).

The boundary test doubles as our hidden-defective-dataset readiness check: we hand
the cleaner a tiny table containing every defect we can think of and assert that
each one is caught or quarantined.

---

## A few lessons from the build

Three things bit us hard enough to be worth passing on.

First, **pandas 2.x with PyArrow-backed columns breaks `.values`** in a way that
sends scikit-learn's `train_test_split` into a cryptic "only integer scalar arrays
can be converted to a scalar index" error. The fix is to materialise real NumPy
arrays with `.to_numpy(dtype=...)` before handing data to scikit-learn. It cost us
an afternoon; hopefully it costs you five minutes.

Second, **`merge_asof` in pandas 2.x is fussy about datetime resolution** — a
`datetime64[us]` key won't join against a `datetime64[s]` one, and the error
doesn't say so. Normalising both sides to `datetime64[ns]` before the merge fixed
it.

Third, **stale session cookies after a data regen** produced a 500 on login,
because the cookie pointed at a user ID that no longer existed. The lesson: always
validate the *user*, not just the presence of a session, and clear the session
gracefully when the lookup fails.

None of these are glamorous, but shipping software is mostly about the unglamorous
edges.

## What we'd do next

A few honest edges remain. The Python GBM's macro-F1 (0.76) trails the Spark
Random Forest's (0.90) because the four classes are imbalanced; class-weighting or
SMOTE would close that gap. The forecaster is intentionally simple — swapping in
Prophet or ARIMA is a drop-in change we left as future work. And while the design
scales to five-million-plus rows through Parquet and Spark, we validated at 1.2M.

But the core is solid, reproducible, and honest about its own limits. DineIQ takes
a million raw order-lines and turns them into a handful of decisions a restaurant
manager can act on tomorrow morning — which is the only metric that really counts.

*Built entirely in Python, with a real Apache Spark Big-Data track. Data in CSV,
processed layer in Parquet, models in scikit-learn and Spark MLlib. All insights
computed by our own code — no external decision AI in the loop.*
