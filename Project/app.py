"""
DineIQ Analytics - web dashboard (Flask) with login, roles and an audit trail.

The dashboard renders whatever the batch pipeline last computed into
outputs/dashboard_data.json - it never runs Spark/ML on a request, so pages are
instant. Everything sits behind authentication.

Roles:  Admin (view+export+manage users+audit) · Manager (view+export) · Analyst (view)

Routes:
    /login  /signup  /logout        auth
    /                               the dashboard (login required)
    /admin                          user management + audit log (admin only)
    /api/data                       computed JSON (login required)
    /download/<report>              stream a processed CSV (export permission)
    /health                         liveness check (open)

Run:  python app.py     ->  http://localhost:5000
      first login:  admin@dineiq.local / admin123   (change it in the admin panel)
"""
import io
import json
from functools import wraps
from pathlib import Path
from flask import (Flask, render_template, jsonify, abort, send_file,
                   request, redirect, url_for, session, flash)

import auth

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "outputs" / "dashboard_data.json"
PROCESSED = ROOT / "processed_data"

app = Flask(__name__)
app.secret_key = auth.get_secret_key()
auth.init_db()


# ---- helpers -------------------------------------------------------------
def current_user():
    uid = session.get("uid")
    return auth.get_user(uid) if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        # not just "is there a uid in the session?" — the user must still exist
        # and be active. otherwise a stale cookie (e.g. the DB was regenerated)
        # would sail through and blow up the template with user=None.
        if not current_user():
            session.clear()
            return redirect(url_for("login", next=request.path))
        return view(*a, **k)
    return wrapped


def permission_required(perm):
    def deco(view):
        @wraps(view)
        def wrapped(*a, **k):
            u = current_user()
            if not u:
                session.clear()
                return redirect(url_for("login"))
            if not auth.can(u["role"], perm):
                abort(403)
            return view(*a, **k)
        return wrapped
    return deco


def load_data():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)


# make the current user available to every template
@app.context_processor
def inject_user():
    u = current_user()
    perms = auth.PERMISSIONS.get(u["role"], set()) if u else set()
    return {"user": u, "perms": perms}


# ---- auth routes ---------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        pw = request.form.get("password", "")
        u = auth.authenticate(email, pw)
        if u:
            session["uid"] = u["id"]
            auth.log("login", f"{u['role']}", email=u["email"], ip=request.remote_addr)
            nxt = request.args.get("next") or url_for("home")
            return redirect(nxt)
        auth.log("login_failed", email=email, ip=request.remote_addr)
        flash("Wrong email or password.", "error")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        if not name or not email or len(pw) < 6:
            flash("Please fill everything in (password at least 6 characters).", "error")
        else:
            # open signup, but everyone lands on the read-only Analyst role
            ok, msg = auth.create_user(name, email, pw, role="Analyst")
            if ok:
                auth.log("signup", "role=Analyst", email=email, ip=request.remote_addr)
                u = auth.authenticate(email, pw)
                session["uid"] = u["id"]
                flash("Welcome! You have Analyst (view-only) access until an admin upgrades you.", "ok")
                return redirect(url_for("home"))
            flash(msg, "error")
    return render_template("signup.html")


@app.route("/logout")
def logout():
    u = current_user()
    if u:
        auth.log("logout", email=u["email"], ip=request.remote_addr)
    session.clear()
    return redirect(url_for("login"))


# ---- dashboard -----------------------------------------------------------
@app.route("/")
@login_required
def home():
    return render_template("dashboard.html", data=load_data())


@app.route("/api/data")
@login_required
def api_data():
    return jsonify(load_data())


# the 12 reports the SRS asks for (step 49) + the two audit artefacts.
# key -> (filename, human title)
REPORTS = {
    "menu_performance":        ("menu_performance.csv",        "Menu performance"),
    "profitability":           ("profitability.csv",           "Profitability"),
    "customer_segments":       ("customer_segments.csv",       "Customer segmentation"),
    "market_basket_rules":     ("market_basket_rules.csv",     "Market-basket analysis"),
    "demand_forecast":         ("demand_forecast.csv",         "Demand forecast"),
    "wastage_by_item":         ("wastage_by_item.csv",         "Wastage"),
    "promotion_effectiveness": ("promotion_effectiveness.csv", "Promotions"),
    "price_sensitivity":       ("price_sensitivity.csv",       "Pricing"),
    "location_performance":    ("location_performance.csv",    "Location performance"),
    "anomalies":               ("anomalies.csv",               "Anomalies"),
    "recommendations":         ("recommendations.csv",         "Recommendations"),
    "model_comparison":        ("model_comparison.csv",        "Spark vs Python model comparison"),
    "data_quality_report":     ("data_quality_report.csv",     "Data-quality report"),
    "cleaning_log":            ("cleaning_log.csv",            "Cleaning log"),
}


def _csv_to_xlsx(path, sheet_name):
    """render a processed CSV into a lightly-styled .xlsx workbook in memory."""
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    df = pd.read_csv(path)
    wb = Workbook()
    ws = wb.active
    ws.title = (sheet_name or "Report")[:31]
    header_fill = PatternFill("solid", fgColor="0EA5A4")
    header_font = Font(bold=True, color="FFFFFF")
    ws.append(list(df.columns))
    for j, _ in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=j)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    for row in df.itertuples(index=False):
        ws.append(list(row))
    # freeze header + rough column autosize
    ws.freeze_panes = "A2"
    for j, col in enumerate(df.columns, 1):
        width = min(48, max(12, int(df[col].astype(str).str.len().head(200).max() or 12) + 2,
                            len(str(col)) + 2))
        ws.column_dimensions[get_column_letter(j)].width = width
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@app.route("/download/<report>")
@permission_required("export")
def download(report):
    entry = REPORTS.get(report)
    if not entry:
        abort(404)
    fname, title = entry
    path = PROCESSED / fname
    if not path.exists():
        abort(404)
    fmt = (request.args.get("fmt") or "csv").lower()
    u = current_user()
    auth.log("export", f"{report}.{fmt}", email=u["email"], ip=request.remote_addr)
    if fmt in ("xlsx", "excel"):
        buf = _csv_to_xlsx(path, title)
        return send_file(buf, as_attachment=True, download_name=f"{report}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument."
                                  "spreadsheetml.sheet")
    return send_file(path, as_attachment=True, download_name=fname)


# ---- live filtering (SRS step 48) ----------------------------------------
@app.route("/api/filter/options")
@login_required
def filter_options():
    from src import live
    return jsonify(live.options())


@app.route("/api/filter", methods=["POST"])
@login_required
def api_filter():
    from src import live
    params = request.get_json(silent=True) or {}
    return jsonify(live.apply_filters(params))


@app.route("/api/reports")
@login_required
def api_reports():
    """the report catalogue the dashboard's Reports view renders."""
    out = []
    for key, (fname, title) in REPORTS.items():
        out.append({"key": key, "title": title,
                    "available": (PROCESSED / fname).exists()})
    return jsonify(out)


@app.route("/api/report/<report>")
@login_required
def api_report_view(report):
    """return a processed CSV as JSON rows so ANY logged-in user (Analyst too)
    can read the data in an Excel-like table on the dashboard, even without the
    export permission. we cap the row count so the browser stays snappy."""
    import csv
    entry = REPORTS.get(report)
    if not entry:
        abort(404)
    fname, title = entry
    path = PROCESSED / fname
    if not path.exists():
        abort(404)
    cap = 2000
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    columns = rows[0] if rows else []
    body = rows[1:]
    total = len(body)
    truncated = total > cap
    u = current_user()
    auth.log("view_report", report, email=u["email"], ip=request.remote_addr)
    return jsonify({"key": report, "title": title, "columns": columns,
                    "rows": body[:cap], "total": total, "truncated": truncated})


# ---- chatbot -------------------------------------------------------------
def _chat_answer(question, data):
    """a small, fully-functional data assistant. no external LLM — it reads the
    computed dashboard numbers and answers the common owner questions with real
    figures. keyword/intent matching, deliberately simple and transparent."""
    q = (question or "").lower().strip()
    k = data.get("kpis", {}) or {}
    menu = data.get("menu", []) or []
    locs = data.get("locations_table", []) or []
    segs = data.get("segments", []) or []
    recs = data.get("recommendations", []) or []
    anoms = data.get("anomalies", []) or []
    promos = data.get("promotions", []) or []

    def money(n):
        try:
            n = float(n)
        except Exception:
            return str(n)
        if n >= 1e6:
            return "$%.2fM" % (n / 1e6)
        if n >= 1e3:
            return "$%.1fk" % (n / 1e3)
        return "$%d" % round(n)

    # margin isn't stored — derive it from profit / revenue
    try:
        margin = round(float(k.get("total_profit", 0)) / float(k.get("total_revenue", 1)) * 100, 1)
    except Exception:
        margin = "—"

    if not q:
        return "Ask me about revenue, profit, orders, wastage, your best or worst items, locations, customer segments, the forecast or recommendations."

    # help / greeting
    if any(w in q for w in ["help", "what can you", "hi", "hello", "hey"]):
        return ("Hi! I read your live dashboard numbers. Try: \"total revenue\", "
                "\"top item\", \"worst item\", \"wastage\", \"best location\", "
                "\"customer segments\", \"forecast\", or \"recommendations\".")

    # revenue / profit / orders / aov
    if "profit" in q and "margin" not in q:
        return f"Total profit is {money(k.get('total_profit'))} — that's a {margin}% margin across the period."
    if "revenue" in q or "sales" in q or "turnover" in q:
        return f"Total revenue for the period is {money(k.get('total_revenue'))}, from {int(k.get('total_orders', 0)):,} orders."
    if "order" in q and "value" not in q:
        return f"You've had {int(k.get('total_orders', 0)):,} orders, with an average order value of {money(k.get('aov'))}."
    if "aov" in q or "average order" in q or "basket size" in q:
        return f"Average order value (AOV) is {money(k.get('aov'))}."
    if "margin" in q:
        return f"Overall profit margin is {margin}% (profit {money(k.get('total_profit'))} on revenue {money(k.get('total_revenue'))})."

    # customers
    if "repeat" in q or "loyal" in q or "retention" in q:
        return f"Repeat-customer rate is {k.get('repeat_rate', '—')}%. Active customers this period: {int(k.get('active_customers', 0)):,}."
    if "customer" in q or "segment" in q:
        if segs:
            top = max(segs, key=lambda s: s.get("count", 0))
            parts = ", ".join(f"{s.get('name')} ({int(s.get('count', 0)):,})" for s in segs[:5])
            return f"You have {len(segs)} customer segments. Biggest: {top.get('name')} with {int(top.get('count', 0)):,} customers. Breakdown: {parts}."
        return f"Active customers: {int(k.get('active_customers', 0)):,}, repeat rate {k.get('repeat_rate', '—')}%."

    # wastage
    if "wast" in q or "waste" in q or "spoil" in q:
        return f"Food wastage is {money(k.get('wastage_cost'))} ({k.get('wastage_rate', '—')}% of prepared quantity). Check the Wastage board for the worst items and next-week risk predictions."

    # forecast
    if "forecast" in q or "predict" in q or "next week" in q or "demand" in q:
        return f"The 14-day forecast projects about {int(k.get('forecast_orders_14d', 0)):,} orders. The Demand Forecast board shows the model beating a naive baseline on error."

    # best / worst item
    if ("top" in q or "best" in q or "highest" in q or "most" in q) and ("item" in q or "dish" in q or "seller" in q or "menu" in q or "sell" in q):
        if menu:
            t = max(menu, key=lambda m: m.get("revenue", 0))
            return f"Your top item by revenue is {t.get('name')} ({t.get('cat')}) at {money(t.get('revenue'))}, {int(t.get('qty', 0)):,} sold."
    if ("worst" in q or "lowest" in q or "bad" in q or "underperform" in q) and ("item" in q or "dish" in q or "menu" in q):
        if menu:
            w = min(menu, key=lambda m: m.get("revenue", 0))
            return f"The lowest-revenue item is {w.get('name')} ({w.get('cat')}) at {money(w.get('revenue'))}. See Menu Intelligence for its full profile."

    # locations
    if "location" in q or "branch" in q or "store" in q or "outlet" in q:
        if locs:
            best = max(locs, key=lambda l: l.get("rev", 0))
            worst = min(locs, key=lambda l: l.get("profit", 999))
            return (f"You run {len(locs)} locations. Top by revenue: {best.get('name')} "
                    f"({money(best.get('rev'))}). Lowest margin: {worst.get('name')} "
                    f"({worst.get('profit')}%). Full comparison is on the Multi-Location board.")

    # promotions
    if "promo" in q or "discount" in q or "offer" in q:
        traps = [p for p in promos if p.get("verdict") == "TRAP"]
        if promos:
            msg = f"You have {len(promos)} promotions tracked."
            if traps:
                msg += f" Watch out: {traps[0].get('name')} is a 'trap' — it lifts sales but hurts margin."
            return msg

    # recommendations
    if "recommend" in q or "advice" in q or "suggest" in q or "action" in q or "what should" in q:
        if recs:
            crit = [r for r in recs if r.get("priority") == "Critical"]
            head = crit[0] if crit else recs[0]
            return (f"There are {len(recs)} recommendations ({len(crit)} critical). "
                    f"Top one: {head.get('action')}. See the Recommendations board for the ranked list.")

    # anomalies
    if "anomal" in q or "unusual" in q or "outlier" in q or "problem" in q:
        return f"The engine flagged {len(anoms)} anomalies (sales, margin and rating outliers). They're explained on the Anomalies board."

    # fallback
    return ("I didn't quite catch that. I can answer questions about revenue, profit, "
            "orders, AOV, wastage, top/worst items, locations, customer segments, the "
            "forecast, promotions, anomalies and recommendations. Try one of those!")


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    payload = request.get_json(silent=True) or {}
    question = payload.get("message", "")
    answer = _chat_answer(question, load_data())
    return jsonify({"reply": answer})


# ---- forgot / reset password (all roles) ---------------------------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        pw = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not email or len(pw) < 6:
            flash("Enter your email and a new password of at least 6 characters.", "error")
        elif pw != confirm:
            flash("The two passwords don't match.", "error")
        elif not auth.email_exists(email):
            flash("No account is registered with that email.", "error")
        else:
            auth.set_password(email, pw)
            auth.log("password_reset", "self-service", email=email.lower(), ip=request.remote_addr)
            flash("Password updated — you can sign in with your new password.", "ok")
            return redirect(url_for("login"))
    return render_template("forgot.html")


# ---- about ---------------------------------------------------------------
@app.route("/about")
def about():
    return render_template("about.html")


# ---- admin: user management + audit --------------------------------------
@app.route("/admin")
@permission_required("admin")
def admin():
    return render_template("admin.html", users=auth.list_users(),
                           audit=auth.recent_audit(120), roles=auth.ROLES)


@app.route("/admin/role", methods=["POST"])
@permission_required("admin")
def admin_role():
    uid = int(request.form["uid"])
    role = request.form["role"]
    me = current_user()
    # don't let an admin lock themselves out of admin
    if uid == me["id"] and role != "Admin":
        flash("You can't remove your own Admin role.", "error")
    else:
        auth.set_role(uid, role)
        auth.log("role_change", f"user#{uid} -> {role}", email=me["email"], ip=request.remote_addr)
        flash("Role updated.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/active", methods=["POST"])
@permission_required("admin")
def admin_active():
    uid = int(request.form["uid"])
    active = request.form["active"] == "1"
    me = current_user()
    if uid == me["id"] and not active:
        flash("You can't deactivate your own account.", "error")
    else:
        auth.set_active(uid, active)
        auth.log("account_" + ("enabled" if active else "disabled"),
                 f"user#{uid}", email=me["email"], ip=request.remote_addr)
        flash("Account updated.", "ok")
    return redirect(url_for("admin"))


@app.route("/health")
def health():
    return {"status": "ok", "data_ready": DATA_FILE.exists(), "users": auth.count_users()}


# dev server: never let the browser cache HTML/JS/CSS, so a redeploy or restart
# is always picked up on the next load (no more "hard refresh" surprises).
@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
