"""Create the four analysis notebooks. Run once, then execute them with jupyter nbconvert."""

import nbformat as nbf

from common import ROOT

SETUP = '''from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
OUT = ROOT / "outputs"
sns.set_theme(style="whitegrid")
pd.options.display.float_format = "{:,.2f}".format'''


def notebook(name: str, cells: list[tuple[str, str]]) -> None:
    nb = nbf.v4.new_notebook()
    nb["cells"] = [nbf.v4.new_markdown_cell(c) if kind == "md" else nbf.v4.new_code_cell(c) for kind, c in cells]
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}
    nbf.write(nb, ROOT / "notebooks" / name)


notebook("01_data_cleaning.ipynb", [
    ("md", "# 1. Data cleaning and preparation\nLoad the raw Olist files, check their quality, and decide what to keep.\n\nSource: Brazilian E-Commerce Public Dataset by Olist (Kaggle). Real, anonymised orders from 2016 to 2018."),
    ("code", SETUP),
    ("code", '''raw = ROOT / "data" / "raw"
files = ["olist_orders_dataset", "olist_order_items_dataset", "olist_customers_dataset", "olist_order_payments_dataset",
         "olist_order_reviews_dataset", "olist_products_dataset", "olist_sellers_dataset", "product_category_name_translation"]
tables = {f: pd.read_csv(raw / f"{f}.csv") for f in files}
pd.DataFrame({"rows": {k: len(v) for k, v in tables.items()}, "columns": {k: v.shape[1] for k, v in tables.items()}})'''),
    ("md", "## Orders: status and date range\nOnly delivered orders have a delivery date, and a few statuses (canceled, unavailable) never turned into revenue."),
    ("code", '''orders = tables["olist_orders_dataset"]
orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"])
print(orders["order_status"].value_counts())
monthly = orders.groupby(orders["order_purchase_timestamp"].dt.to_period("M")).size()
monthly.plot(kind="bar", figsize=(12, 3.5), title="Orders per month (raw, all dates)");'''),
    ("md", "**Decision:** keep January 2017 to August 2018. Late 2016 has almost no orders and September to October 2018 is cut off, which would distort any trend."),
    ("md", "## Missing values and duplicates"),
    ("code", '''checks = []
for name, df in tables.items():
    checks.append({"table": name, "rows": len(df), "duplicate_rows": int(df.duplicated().sum()), "columns_with_nulls": int((df.isna().sum() > 0).sum())})
pd.DataFrame(checks)'''),
    ("code", '''reviews = tables["olist_order_reviews_dataset"]
print("orders with more than one review:", int((reviews.groupby("order_id").size() > 1).sum()))
cust = tables["olist_customers_dataset"]
print("customer_id rows:", len(cust), "| real unique customers (customer_unique_id):", cust["customer_unique_id"].nunique())'''),
    ("md", "**Key finding:** `customer_id` is created per order, so counting it would treat every order as a new customer. All customer analysis uses `customer_unique_id`. For orders with several reviews, the most recent review is kept."),
    ("md", "## Prepared tables\n`scripts/prepare_data.py` builds one row per order and one row per item, translates category names to English, and adds delivery days, late flag and review score."),
    ("code", '''prepared = pd.read_csv(ROOT / "data" / "processed" / "orders.csv")
print(prepared.shape)
prepared[["order_id", "order_month", "order_status", "item_revenue", "freight", "delivery_days", "is_late", "review_score", "payment_type"]].head()'''),
])

notebook("02_sales_and_categories.ipynb", [
    ("md", "# 2. Sales and category performance\nWhere does the revenue come from, and when?\n\nRevenue here means item price on valid orders (canceled and unavailable orders excluded). Freight is tracked separately."),
    ("code", SETUP),
    ("code", '''import json
summary = json.loads((OUT / "summary.json").read_text())
pd.Series({
    "Valid orders": f"{summary['valid_orders']:,}",
    "Unique customers": f"{summary['customers']:,}",
    "Revenue (BRL)": f"{summary['revenue']:,.0f}",
    "Average order value (BRL)": f"{summary['aov']:,.2f}",
    "Peak month": summary["peak_month"],
})'''),
    ("md", "## Monthly revenue"),
    ("code", '''m = pd.read_csv(OUT / "monthly_kpis.csv")
fig, ax = plt.subplots(figsize=(11, 4.5))
ax.bar(m["order_month"], m["revenue"] / 1e3, color=["#ea580c" if x == "2017-11" else "#2563eb" for x in m["order_month"]])
ax.set_ylabel("Revenue (BRL thousands)"); ax.tick_params(axis="x", rotation=60)
ax.set_title("Monthly revenue")
m[["order_month", "orders", "revenue", "aov", "revenue_growth"]].tail(10)'''),
    ("md", "Revenue grew steadily through 2017 and spiked in **November 2017** (Black Friday), about 52% above October. It then fell back in December, so the spike was a one-off and not a new baseline. 2018 settled between roughly BRL 0.84M and 0.99M per month."),
    ("md", "## Categories"),
    ("code", '''c = pd.read_csv(OUT / "category_performance.csv")
c.head(10)[["category", "revenue", "revenue_share", "items_sold", "avg_price", "avg_review"]]'''),
    ("code", '''top = c.head(10).sort_values("revenue")
plt.figure(figsize=(9, 5)); plt.barh(top["category"], top["revenue"] / 1e3, color="#2563eb")
plt.title("Top 10 categories by revenue"); plt.xlabel("Revenue (BRL thousands)");
print(f"Top 5 categories = {c.head(5)['revenue_share'].sum():.1%} of revenue")'''),
    ("md", "No single category dominates. The top five make up about 40% of revenue, which is a healthy spread. Health and beauty, watches and gifts, and bed, bath and table lead."),
    ("md", "## Freight cost by category\nHigh freight relative to price can put customers off. Electronics and furniture have the heaviest shipping burden."),
    ("code", '''f = c[c["orders"] >= 500].sort_values("freight_to_price", ascending=False).head(8)
f[["category", "avg_price", "avg_freight", "freight_to_price", "avg_review"]]'''),
    ("md", "## Payment methods"),
    ("code", '''pd.read_csv(OUT / "payment_summary.csv")'''),
    ("md", "Credit card is about three quarters of orders. Boleto (a Brazilian bank slip) is the second largest at about 20%, so supporting it matters in this market."),
])

notebook("03_customers_and_retention.ipynb", [
    ("md", "# 3. Customers, segments and retention\nDo customers come back?"),
    ("code", SETUP),
    ("code", '''import json
s = json.loads((OUT / "summary.json").read_text())
print(f"Customers who bought more than once: {s['repeat_customer_rate']:.1%}")
print(f"Share of revenue from repeat buyers: {s['repeat_revenue_share']:.1%}")'''),
    ("md", "**Only about 3% of customers ever buy a second time.** This is the single biggest feature of the business: it is almost entirely a one-time-purchase marketplace, so growth depends on constantly finding new customers."),
    ("md", "## Customer segments\nBecause nearly everyone has one order, classic RFM scoring is not useful. Segments are based on order count, recency (days since last purchase at the end of the data) and spend instead:\n\n- **Repeat buyer** (2+ orders), active if the last order was within 180 days\n- **One-timers** split by recency: recent (0 to 180 days), cooling (181 to 365), lost (over 365)\n- **High-value recent one-timer**: recent and in the top quarter of one-time spenders"),
    ("code", '''seg = pd.read_csv(OUT / "customer_segments.csv")
seg'''),
    ("code", '''seg2 = seg.sort_values("revenue_share")
y = range(len(seg2))
plt.figure(figsize=(10, 4.8))
plt.barh([i + 0.2 for i in y], seg2["customer_share"] * 100, height=0.4, color="#94a3b8", label="Share of customers")
plt.barh([i - 0.2 for i in y], seg2["revenue_share"] * 100, height=0.4, color="#2563eb", label="Share of revenue")
plt.yticks(list(y), seg2["segment"]); plt.legend(frameon=False); plt.xlabel("Percent");'''),
    ("md", "The **high-value recent one-timers** are about 10% of customers but 25% of revenue, with an average spend of BRL 343 versus about BRL 69 for other recent buyers. They are the best target for a second-purchase campaign."),
    ("md", "## Cohort repeat-purchase rate\nFor each month of first purchase, what share of that cohort buys again in each later month?"),
    ("code", '''c = pd.read_csv(OUT / "cohort_retention.csv")
c = c[(c["period"].between(1, 6)) & (c["cohort"] >= "2017-01") & (c["cohort"] <= "2018-02")]
matrix = c.pivot(index="cohort", columns="period", values="retention") * 100
plt.figure(figsize=(9, 6)); sns.heatmap(matrix, annot=True, fmt=".1f", cmap="Blues", cbar=False)
plt.title("% of cohort buying again, by months after first purchase");'''),
    ("code", '''print(f"Average share of a cohort that buys again in month 3: {s['month3_retention']:.2%}")'''),
    ("md", "In any single month after the first purchase, only 0.1% to 0.7% of a cohort returns. There is no sign of a loyal group building up over time."),
])

notebook("04_delivery_and_satisfaction.ipynb", [
    ("md", "# 4. Delivery performance and customer satisfaction\nDoes shipping speed change how customers rate their order?"),
    ("code", SETUP),
    ("code", '''import json
s = json.loads((OUT / "summary.json").read_text())
print(f"Average delivery time: {s['avg_delivery_days']:.1f} days")
print(f"Delivered late (after the estimated date): {s['late_rate']:.1%}")'''),
    ("md", "## Late vs on-time deliveries"),
    ("code", '''d = pd.read_csv(OUT / "delivery_vs_review.csv")
d["delivery"] = d["is_late"].map({False: "On time", True: "Late"})
d[["delivery", "orders", "avg_review", "low_score_share"]]'''),
    ("md", "On-time orders average **4.28** stars with 9% rating 1 or 2. Late orders average **2.55** stars with 55% rating 1 or 2. Being late is the strongest driver of a bad review in this data."),
    ("code", '''b = pd.read_csv(OUT / "delay_bucket_vs_review.csv")
plt.figure(figsize=(9, 4.5))
bars = plt.bar(b["delay_bucket"], b["avg_review"], color=["#2563eb", "#2563eb", "#ea580c", "#ea580c", "#ea580c"])
for bar, v in zip(bars, b["avg_review"]): plt.text(bar.get_x() + bar.get_width() / 2, v + 0.05, f"{v:.2f}", ha="center")
plt.ylim(0, 5); plt.ylabel("Average review score"); plt.xticks(rotation=15);
b'''),
    ("md", "Even 0 to 3 days late costs half a star, and more than a week late drops the score to 1.7. Delivering early barely helps (4.31 vs 4.23), so the goal is to avoid lateness, not to be as fast as possible."),
    ("md", "## Geography\nSão Paulo (SP) is 38% of revenue and delivers fastest. Other regions wait much longer."),
    ("code", '''st = pd.read_csv(OUT / "state_performance.csv")
st[st["orders"] >= 500].head(12)[["customer_state", "orders", "revenue_share", "avg_delivery_days", "late_rate", "avg_review"]]'''),
    ("code", '''top = st.head(10).sort_values("avg_delivery_days")
plt.figure(figsize=(9, 4.8)); plt.barh(top["customer_state"], top["avg_delivery_days"], color=["#ea580c" if v > 14 else "#2563eb" for v in top["avg_delivery_days"]])
plt.xlabel("Days from purchase to delivery"); plt.title("Average delivery time, 10 biggest states by revenue");'''),
    ("md", "Rio de Janeiro is the second biggest market (13% of revenue) but takes about 15 days versus under 9 in São Paulo, and 13% of its orders arrive late, more than double São Paulo's rate. Bahia and Ceará are worse still, with 19 to 21 day averages."),
    ("md", "## Recommendations\n1. Put realistic delivery estimates in front of customers in slow regions, so fewer orders count as late.\n2. Prioritise carrier and fulfilment fixes for Rio de Janeiro first, because of its size.\n3. Flag orders that are about to miss their date and contact the customer before the review is written.\n4. Run a second-purchase offer for high-value one-time buyers, since almost nobody returns on their own."),
])
print("notebooks written")
