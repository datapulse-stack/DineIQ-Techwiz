"""
Generates the report diagrams (DFD, Use-Case, Activity, Sequence) as PNGs.
Pure-matplotlib so there are no graphviz/system dependencies.

    python docs/make_diagrams.py   ->   docs/diagrams/*.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, FancyArrowPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagrams")
os.makedirs(OUT, exist_ok=True)

TEAL = "#0E6E63"
TEAL_D = "#0A4A43"
LIGHT = "#EAF4F2"
INK = "#1B2A28"
GREY = "#5A6A67"


def _box(ax, x, y, w, h, text, fc=LIGHT, ec=TEAL, tc=INK, fs=9, bold=False, round_=True):
    style = "round,pad=0.02,rounding_size=0.08" if round_ else "square,pad=0.02"
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style,
                                fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, weight="bold" if bold else "normal", wrap=True)


def _arrow(ax, p1, p2, text="", color=TEAL_D, fs=7.5, style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=12,
                                 color=color, lw=1.3, shrinkA=2, shrinkB=2))
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.12, text, ha="center", va="bottom", fontsize=fs, color=GREY)


def _fig(w=11, h=7):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    return fig, ax


def _title(ax, t):
    ax.text(6, 7.7, t, ha="center", va="top", fontsize=13, weight="bold", color=TEAL_D)


# --------------------------------------------------------------------------
def dfd():
    fig, ax = _fig()
    _title(ax, "Figure A — Data-Flow Diagram (Level 1)")
    # external entities (double-box look via square boxes)
    _box(ax, 0.3, 5.6, 2.2, 0.9, "Synthetic Data\nGenerator", fc="#fff", ec=GREY, round_=False)
    _box(ax, 0.3, 1.3, 2.2, 0.9, "Users\n(Admin/Mgr/Analyst)", fc="#fff", ec=GREY, round_=False)
    # processes
    _box(ax, 3.4, 5.6, 2.3, 0.9, "1.0 Ingest &\nData Quality", fc=LIGHT)
    _box(ax, 6.4, 5.6, 2.3, 0.9, "2.0 Clean &\nIntegrate", fc=LIGHT)
    _box(ax, 9.3, 5.6, 2.3, 0.9, "3.0 Feature\nEngineering", fc=LIGHT)
    _box(ax, 6.4, 3.6, 2.3, 0.9, "4.0 Analytics &\nML Models", fc=LIGHT)
    _box(ax, 3.4, 1.3, 2.3, 0.9, "5.0 Web Dashboard\n(Flask)", fc=LIGHT)
    # data stores (open-ended)
    _box(ax, 9.3, 3.5, 2.3, 0.8, "D1  raw_data/*.csv", fc="#FDF6E3", ec=GREY)
    _box(ax, 9.3, 2.4, 2.3, 0.8, "D2  processed/*.csv\n+ Parquet", fc="#FDF6E3", ec=GREY)
    _box(ax, 6.4, 2.3, 2.3, 0.8, "D3  dashboard_data.json", fc="#FDF6E3", ec=GREY)
    # arrows
    _arrow(ax, (2.5, 6.05), (3.4, 6.05), "raw records")
    _arrow(ax, (5.7, 6.05), (6.4, 6.05))
    _arrow(ax, (8.7, 6.05), (9.3, 6.05))
    _arrow(ax, (10.45, 5.6), (10.45, 4.3), "features")
    _arrow(ax, (9.3, 3.9), (8.7, 4.0), "read")
    _arrow(ax, (9.3, 2.8), (8.7, 3.9), "read")
    _arrow(ax, (7.55, 3.6), (7.55, 3.1), "write")
    _arrow(ax, (6.4, 2.7), (5.7, 2.0), "serve")
    _arrow(ax, (4.55, 1.3), (2.5, 1.75), "views / exports")
    _arrow(ax, (2.5, 1.75), (4.55, 1.3), color=GREY, style="-")
    fig.savefig(os.path.join(OUT, "dfd.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)


def usecase():
    fig, ax = _fig()
    _title(ax, "Figure B — Use-Case Diagram")
    # system boundary
    ax.add_patch(Rectangle((3.4, 0.6), 5.2, 6.6, fill=False, ec=TEAL, lw=1.4))
    ax.text(6.0, 7.0, "DineIQ Analytics", ha="center", fontsize=10, color=TEAL_D, weight="bold")

    def actor(x, y, name):
        ax.plot([x], [y + 0.35], marker="o", ms=8, color=INK)
        ax.plot([x, x], [y + 0.28, y - 0.05], color=INK, lw=1.5)
        ax.plot([x - 0.25, x + 0.25], [y + 0.15, y + 0.15], color=INK, lw=1.5)
        ax.plot([x, x - 0.2], [y - 0.05, y - 0.35], color=INK, lw=1.5)
        ax.plot([x, x + 0.2], [y - 0.05, y - 0.35], color=INK, lw=1.5)
        ax.text(x, y - 0.65, name, ha="center", fontsize=9, weight="bold", color=INK)

    actor(1.4, 5.6, "Analyst")
    actor(1.4, 3.6, "Manager")
    actor(1.4, 1.6, "Admin")

    ucs = [
        (6.0, 6.6, "Log in / Reset password"),
        (6.0, 5.8, "View dashboards"),
        (6.0, 5.0, "Use assistant (chat)"),
        (6.0, 4.2, "View report tables"),
        (6.0, 3.4, "Export CSV / Excel"),
        (6.0, 2.6, "Run what-if simulation"),
        (6.0, 1.8, "Manage users & roles"),
        (6.0, 1.1, "View audit trail"),
    ]
    for x, y, t in ucs:
        ax.add_patch(Ellipse((x, y), 3.6, 0.62, fc=LIGHT, ec=TEAL, lw=1.2))
        ax.text(x, y, t, ha="center", va="center", fontsize=8.3, color=INK)

    # connections (analyst -> view things; manager adds export/whatif; admin all)
    for y in [6.6, 5.8, 5.0, 4.2]:
        ax.plot([1.7, 4.2], [5.6, y], color=GREY, lw=0.8)
    for y in [3.4, 2.6]:
        ax.plot([1.7, 4.2], [3.6, y], color=GREY, lw=0.8)
    for y in [1.8, 1.1]:
        ax.plot([1.7, 4.2], [1.6, y], color=GREY, lw=0.8)
    fig.savefig(os.path.join(OUT, "usecase.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)


def activity():
    fig, ax = _fig(9, 11)
    ax.set_ylim(0, 12)
    ax.text(6, 11.6, "Figure C — Activity Diagram (analytics pipeline)",
            ha="center", fontsize=13, weight="bold", color=TEAL_D)
    # start
    ax.add_patch(Ellipse((6, 11.0), 0.5, 0.35, fc=INK, ec=INK))
    steps = [
        "Generate / load raw CSV data",
        "Data-quality assessment",
        "Clean & quarantine bad records",
        "Integrate -> order-line fact table",
        "Feature engineering (RFM, margin, trend)",
        "Classify menu (4 quadrants)  ·  Segment customers",
        "Market-basket  ·  Forecast  ·  Pricing  ·  Wastage",
        "Dual ML: Spark MLlib  ||  Python DS  -> compare",
        "Churn model  ·  Anomalies  ·  Recommendations",
        "Assemble dashboard_data.json + reports",
    ]
    y = 10.2
    prev = (6, 10.82)
    for i, s in enumerate(steps):
        _box(ax, 3.0, y - 0.35, 6.0, 0.62, s, fc=LIGHT, fs=8.6)
        _arrow(ax, prev, (6, y + 0.27))
        prev = (6, y - 0.35)
        y -= 0.95
    # decision diamond for spark availability
    _arrow(ax, prev, (6, y + 0.3))
    ax.add_patch(plt.Polygon([(6, y + 0.3), (7.0, y - 0.1), (6, y - 0.5), (5.0, y - 0.1)],
                             fc="#FDF6E3", ec=TEAL, lw=1.2))
    ax.text(6, y - 0.1, "Spark\navailable?", ha="center", va="center", fontsize=7.5)
    ax.text(7.2, y - 0.1, "yes -> real Spark preds", fontsize=7, color=GREY, va="center")
    ax.text(4.8, y - 0.75, "no -> documented stand-in", fontsize=7, color=GREY, ha="center")
    # end
    _arrow(ax, (6, y - 0.5), (6, y - 1.0))
    ax.add_patch(Ellipse((6, y - 1.2), 0.5, 0.35, fc="#fff", ec=INK, lw=2))
    ax.add_patch(Ellipse((6, y - 1.2), 0.3, 0.2, fc=INK, ec=INK))
    fig.savefig(os.path.join(OUT, "activity.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)


def sequence():
    fig, ax = _fig(11, 7.5)
    _title(ax, "Figure D — Sequence Diagram (view a report)")
    actors = [("Analyst", 1.4), ("Browser", 3.8), ("Flask app.py", 6.2),
              ("auth.py", 8.4), ("data files", 10.6)]
    for name, x in actors:
        _box(ax, x - 0.9, 6.6, 1.8, 0.55, name, fc=TEAL, tc="#fff", ec=TEAL_D, fs=8.5, bold=True)
        ax.plot([x, x], [0.6, 6.6], color=GREY, lw=1, ls="--")

    def msg(y, x1, x2, text, ret=False):
        _arrow(ax, (x1, y), (x2, y), color=(GREY if ret else TEAL_D),
               style=("-|>" if not ret else "-|>"))
        ax.text((x1 + x2) / 2, y + 0.1, text, ha="center", fontsize=7.6,
                color=INK, style=("italic" if ret else "normal"))

    xs = {n: x for n, x in actors}
    msg(6.1, xs["Analyst"], xs["Browser"], "click 'View report'")
    msg(5.5, xs["Browser"], xs["Flask app.py"], "GET /api/report/<key>")
    msg(4.9, xs["Flask app.py"], xs["auth.py"], "current_user() / permission check")
    msg(4.3, xs["auth.py"], xs["Flask app.py"], "role OK (view)", ret=True)
    msg(3.7, xs["Flask app.py"], xs["data files"], "read processed_data/<key>.csv")
    msg(3.1, xs["data files"], xs["Flask app.py"], "rows + columns", ret=True)
    msg(2.5, xs["Flask app.py"], xs["Browser"], "JSON {columns, rows}", ret=True)
    msg(1.9, xs["Browser"], xs["Analyst"], "render Excel-like table", ret=True)
    ax.text(6, 0.8, "If the session is stale, auth.py clears it and returns 302 -> /login",
            ha="center", fontsize=7.5, color=GREY, style="italic")
    fig.savefig(os.path.join(OUT, "sequence.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    dfd(); usecase(); activity(); sequence()
    print("wrote diagrams to", OUT)
