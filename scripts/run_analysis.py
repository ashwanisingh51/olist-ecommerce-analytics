"""Build the KPI tables used by the charts, notebooks and README."""

import json

import pandas as pd

from common import OUTPUTS, PROCESSED, WINDOW_END

INVALID_STATUSES = ["canceled", "unavailable"]


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    orders = pd.read_csv(PROCESSED / "orders.csv", parse_dates=["order_purchase_timestamp"])
    items = pd.read_csv(PROCESSED / "items.csv")
    return orders, items


def monthly_kpis(valid: pd.DataFrame) -> pd.DataFrame:
    first_month = valid.groupby("customer_unique_id")["order_month"].min().rename("first_month")
    v = valid.join(first_month, on="customer_unique_id")
    v["is_new"] = v["order_month"] == v["first_month"]
    m = v.groupby("order_month").agg(
        orders=("order_id", "nunique"),
        customers=("customer_unique_id", "nunique"),
        revenue=("item_revenue", "sum"),
        freight=("freight", "sum"),
        new_customer_orders=("is_new", "sum"),
    ).reset_index()
    m["aov"] = m["revenue"] / m["orders"]
    m["revenue_growth"] = m["revenue"].pct_change()
    return m


def category_performance(items: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    valid_items = items[~items["order_status"].isin(INVALID_STATUSES)]
    scores = orders[["order_id", "review_score"]]
    d = valid_items.merge(scores, on="order_id", how="left")
    c = d.groupby("category").agg(
        revenue=("price", "sum"),
        items_sold=("order_id", "count"),
        orders=("order_id", "nunique"),
        avg_price=("price", "mean"),
        avg_freight=("freight_value", "mean"),
        avg_review=("review_score", "mean"),
    ).reset_index()
    c["freight_to_price"] = c["avg_freight"] / c["avg_price"]
    c["revenue_share"] = c["revenue"] / c["revenue"].sum()
    return c.sort_values("revenue", ascending=False)


def state_performance(valid: pd.DataFrame) -> pd.DataFrame:
    s = valid.groupby("customer_state").agg(
        orders=("order_id", "nunique"),
        customers=("customer_unique_id", "nunique"),
        revenue=("item_revenue", "sum"),
        avg_delivery_days=("delivery_days", "mean"),
        late_rate=("is_late", "mean"),
        avg_review=("review_score", "mean"),
        avg_freight=("freight", "mean"),
    ).reset_index()
    s["revenue_share"] = s["revenue"] / s["revenue"].sum()
    return s.sort_values("revenue", ascending=False)


def customer_table(valid: pd.DataFrame) -> pd.DataFrame:
    end = pd.Timestamp(WINDOW_END) + pd.Timedelta(days=1)
    c = valid.groupby("customer_unique_id").agg(
        orders=("order_id", "nunique"),
        revenue=("item_revenue", "sum"),
        last_order=("order_purchase_timestamp", "max"),
        first_order=("order_purchase_timestamp", "min"),
    ).reset_index()
    c["recency_days"] = (end - c["last_order"]).dt.days
    one_time_cutoff = c.loc[c["orders"] == 1, "revenue"].quantile(0.75)

    def segment(row: pd.Series) -> str:
        if row.orders >= 2:
            return "Repeat buyer (active)" if row.recency_days <= 180 else "Repeat buyer (lapsed)"
        if row.recency_days <= 180:
            return "High-value recent one-timer" if row.revenue >= one_time_cutoff else "Recent one-timer"
        if row.recency_days <= 365:
            return "Cooling one-timer"
        return "Lost one-timer"

    c["segment"] = c.apply(segment, axis=1)
    return c


def segment_summary(c: pd.DataFrame) -> pd.DataFrame:
    s = c.groupby("segment").agg(customers=("customer_unique_id", "count"), revenue=("revenue", "sum"), avg_revenue=("revenue", "mean")).reset_index()
    s["customer_share"] = s["customers"] / s["customers"].sum()
    s["revenue_share"] = s["revenue"] / s["revenue"].sum()
    return s.sort_values("revenue", ascending=False)


def cohort_retention(valid: pd.DataFrame) -> pd.DataFrame:
    first = valid.groupby("customer_unique_id")["order_purchase_timestamp"].min().dt.to_period("M").rename("cohort")
    d = valid.join(first, on="customer_unique_id")
    d["period"] = (d["order_purchase_timestamp"].dt.to_period("M") - d["cohort"]).apply(lambda x: x.n)
    size = d.groupby("cohort")["customer_unique_id"].nunique().rename("cohort_size")
    active = d.groupby(["cohort", "period"])["customer_unique_id"].nunique().rename("active").reset_index()
    out = active.merge(size, on="cohort")
    out["retention"] = out["active"] / out["cohort_size"]
    out["cohort"] = out["cohort"].astype(str)
    return out


def payment_summary(valid: pd.DataFrame) -> pd.DataFrame:
    p = valid.dropna(subset=["payment_type"]).groupby("payment_type").agg(orders=("order_id", "count"), aov=("item_revenue", "mean")).reset_index()
    p["order_share"] = p["orders"] / p["orders"].sum()
    return p.sort_values("orders", ascending=False)


def seller_concentration(items: pd.DataFrame) -> dict:
    valid_items = items[~items["order_status"].isin(INVALID_STATUSES)]
    s = valid_items.groupby("seller_id")["price"].sum().sort_values(ascending=False)
    top10 = s.head(max(1, int(len(s) * 0.10))).sum() / s.sum()
    return {"sellers": int(len(s)), "top_10pct_revenue_share": float(top10)}


def main() -> None:
    OUTPUTS.mkdir(exist_ok=True)
    orders, items = load()
    valid = orders[~orders["order_status"].isin(INVALID_STATUSES)].copy()
    # order_delivered_customer_date was not kept in the orders table, so rebuild delay from days
    valid["delay_days"] = valid["delivery_days"] - valid["estimated_days"]

    monthly = monthly_kpis(valid)
    category = category_performance(items, orders)
    state = state_performance(valid)
    customers = customer_table(valid)
    segments = segment_summary(customers)
    cohort = cohort_retention(valid)
    payments = payment_summary(valid)
    sellers = seller_concentration(items)

    deliv = valid[valid["is_delivered"] & valid["review_score"].notna()].copy()
    by_late = deliv.groupby("is_late").agg(orders=("order_id", "count"), avg_review=("review_score", "mean"), low_score_share=("review_score", lambda s: (s <= 2).mean())).reset_index()
    bins = [-100, -10, 0, 3, 7, 1000]
    labels = ["10+ days early", "0 to 10 days early", "0 to 3 days late", "3 to 7 days late", "7+ days late"]
    deliv["delay_bucket"] = pd.cut(deliv["delay_days"], bins=bins, labels=labels)
    by_bucket = deliv.groupby("delay_bucket", observed=True).agg(orders=("order_id", "count"), avg_review=("review_score", "mean")).reset_index()

    monthly.to_csv(OUTPUTS / "monthly_kpis.csv", index=False)
    category.to_csv(OUTPUTS / "category_performance.csv", index=False)
    state.to_csv(OUTPUTS / "state_performance.csv", index=False)
    segments.to_csv(OUTPUTS / "customer_segments.csv", index=False)
    cohort.to_csv(OUTPUTS / "cohort_retention.csv", index=False)
    payments.to_csv(OUTPUTS / "payment_summary.csv", index=False)
    by_late.to_csv(OUTPUTS / "delivery_vs_review.csv", index=False)
    by_bucket.to_csv(OUTPUTS / "delay_bucket_vs_review.csv", index=False)

    peak = monthly.loc[monthly["revenue"].idxmax()]
    total_customers = customers["customer_unique_id"].nunique()
    repeat_rate = (customers["orders"] >= 2).mean()
    repeat_revenue_share = customers.loc[customers["orders"] >= 2, "revenue"].sum() / customers["revenue"].sum()
    late = by_late.set_index("is_late")
    top_cat = category.iloc[0]
    top5_share = category.head(5)["revenue_share"].sum()
    sp = state.set_index("customer_state")
    slow = state[state["orders"] >= 500].sort_values("avg_delivery_days", ascending=False).iloc[0]
    freight_heavy = category[category["orders"] >= 500].sort_values("freight_to_price", ascending=False).iloc[0]
    m3 = cohort[(cohort["period"] == 3)]["retention"].mean()

    summary = {
        "window": f"2017-01 to 2018-08",
        "valid_orders": int(valid["order_id"].nunique()),
        "customers": int(total_customers),
        "revenue": float(valid["item_revenue"].sum()),
        "freight": float(valid["freight"].sum()),
        "aov": float(valid["item_revenue"].sum() / valid["order_id"].nunique()),
        "peak_month": peak["order_month"],
        "peak_month_revenue": float(peak["revenue"]),
        "repeat_customer_rate": float(repeat_rate),
        "repeat_revenue_share": float(repeat_revenue_share),
        "late_rate": float(valid.loc[valid["is_delivered"], "is_late"].mean()),
        "avg_delivery_days": float(valid["delivery_days"].mean()),
        "review_on_time": float(late.loc[False, "avg_review"]),
        "review_late": float(late.loc[True, "avg_review"]),
        "low_score_on_time": float(late.loc[False, "low_score_share"]),
        "low_score_late": float(late.loc[True, "low_score_share"]),
        "top_category": top_cat["category"],
        "top_category_share": float(top_cat["revenue_share"]),
        "top5_category_share": float(top5_share),
        "sp_revenue_share": float(sp.loc["SP", "revenue_share"]),
        "slowest_state": slow["customer_state"],
        "slowest_state_days": float(slow["avg_delivery_days"]),
        "fastest_state_days": float(sp.loc["SP", "avg_delivery_days"]),
        "freight_heavy_category": freight_heavy["category"],
        "freight_heavy_ratio": float(freight_heavy["freight_to_price"]),
        "month3_retention": float(m3),
        "seller_top10_share": sellers["top_10pct_revenue_share"],
        "sellers": sellers["sellers"],
        "credit_card_share": float(payments.set_index("payment_type").loc["credit_card", "order_share"]),
    }
    (OUTPUTS / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=float))
    print(segments.to_string())
    print(by_bucket.to_string())
    print(category.head(8)[["category", "revenue", "revenue_share", "avg_review"]].to_string())
    print(state.head(6)[["customer_state", "revenue_share", "avg_delivery_days", "late_rate", "avg_review"]].to_string())


if __name__ == "__main__":
    main()
