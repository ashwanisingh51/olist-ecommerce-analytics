"""Save the main charts as PNG files in outputs/charts."""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from common import CHARTS, OUTPUTS

BLUE = "#2563eb"
ORANGE = "#ea580c"
GREY = "#94a3b8"


def style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=130)
    plt.close(fig)


def monthly_revenue() -> None:
    m = pd.read_csv(OUTPUTS / "monthly_kpis.csv")
    fig, ax = plt.subplots(figsize=(11, 4.8))
    colors = [ORANGE if x == "2017-11" else BLUE for x in m["order_month"]]
    ax.bar(m["order_month"], m["revenue"] / 1e3, color=colors)
    ax.set_title("Monthly revenue (Nov 2017 peak highlighted)", loc="left", fontweight="bold")
    ax.set_ylabel("Revenue (BRL thousands)")
    ax.tick_params(axis="x", rotation=60)
    save(fig, "monthly_revenue.png")


def top_categories() -> None:
    c = pd.read_csv(OUTPUTS / "category_performance.csv").head(10).sort_values("revenue")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(c["category"].str.replace("_", " "), c["revenue"] / 1e3, color=BLUE)
    for y, (rev, share) in enumerate(zip(c["revenue"], c["revenue_share"])):
        ax.text(rev / 1e3, y, f"  {share:.1%}", va="center", fontsize=9)
    ax.set_title("Top 10 categories by revenue (share of total)", loc="left", fontweight="bold")
    ax.set_xlabel("Revenue (BRL thousands)")
    save(fig, "top_categories.png")


def delay_vs_review() -> None:
    d = pd.read_csv(OUTPUTS / "delay_bucket_vs_review.csv")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = [BLUE, BLUE, ORANGE, ORANGE, ORANGE]
    bars = ax.bar(d["delay_bucket"], d["avg_review"], color=colors)
    for bar, v, n in zip(bars, d["avg_review"], d["orders"]):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.05, f"{v:.2f}\n({n:,} orders)", ha="center", fontsize=9)
    ax.set_ylim(0, 5.2)
    ax.set_ylabel("Average review score (1 to 5)")
    ax.set_title("Late deliveries wreck review scores", loc="left", fontweight="bold")
    ax.tick_params(axis="x", rotation=15)
    save(fig, "delay_vs_review.png")


def state_delivery() -> None:
    s = pd.read_csv(OUTPUTS / "state_performance.csv").head(10).sort_values("avg_delivery_days")
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [ORANGE if v > 14 else BLUE for v in s["avg_delivery_days"]]
    ax.barh(s["customer_state"], s["avg_delivery_days"], color=colors)
    for y, (days, share) in enumerate(zip(s["avg_delivery_days"], s["revenue_share"])):
        ax.text(days, y, f"  {days:.1f} days ({share:.0%} of revenue)", va="center", fontsize=9)
    ax.set_xlim(0, s["avg_delivery_days"].max() * 1.5)
    ax.set_title("Average delivery time, 10 biggest states by revenue", loc="left", fontweight="bold")
    ax.set_xlabel("Days from purchase to delivery")
    save(fig, "state_delivery_days.png")


def segments() -> None:
    s = pd.read_csv(OUTPUTS / "customer_segments.csv").sort_values("revenue_share")
    fig, ax = plt.subplots(figsize=(10, 5))
    y = range(len(s))
    ax.barh([i + 0.2 for i in y], s["customer_share"] * 100, height=0.4, color=GREY, label="Share of customers")
    ax.barh([i - 0.2 for i in y], s["revenue_share"] * 100, height=0.4, color=BLUE, label="Share of revenue")
    ax.set_yticks(list(y))
    ax.set_yticklabels(s["segment"])
    ax.set_xlabel("Percent")
    ax.set_title("Customer segments: almost everyone buys once", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    save(fig, "customer_segments.png")


def cohort_heatmap() -> None:
    c = pd.read_csv(OUTPUTS / "cohort_retention.csv")
    c = c[(c["period"] <= 6) & (c["cohort"] >= "2017-01") & (c["cohort"] <= "2018-02")]
    matrix = c.pivot(index="cohort", columns="period", values="retention").drop(columns=0)
    fig, ax = plt.subplots(figsize=(9, 6.5))
    sns.heatmap(matrix * 100, annot=True, fmt=".1f", cmap="Blues", cbar=False, ax=ax)
    ax.set_title("Repeat purchase rate by cohort (% of cohort who bought again)", loc="left", fontweight="bold")
    ax.set_xlabel("Months after first purchase")
    ax.set_ylabel("First purchase month")
    save(fig, "cohort_repeat_rate.png")


def main() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    style()
    monthly_revenue()
    top_categories()
    delay_vs_review()
    state_delivery()
    segments()
    cohort_heatmap()
    print("charts saved:", sorted(p.name for p in CHARTS.glob("*.png")))


if __name__ == "__main__":
    main()
