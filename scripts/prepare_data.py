"""Clean the raw Olist files and build analysis-ready tables plus a SQLite database."""

import sqlite3

import pandas as pd

from common import DB_PATH, PROCESSED, RAW, WINDOW_END, WINDOW_START

DATE_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def load_raw() -> dict[str, pd.DataFrame]:
    return {
        "orders": pd.read_csv(RAW / "olist_orders_dataset.csv", parse_dates=DATE_COLS),
        "items": pd.read_csv(RAW / "olist_order_items_dataset.csv"),
        "customers": pd.read_csv(RAW / "olist_customers_dataset.csv"),
        "payments": pd.read_csv(RAW / "olist_order_payments_dataset.csv"),
        "reviews": pd.read_csv(RAW / "olist_order_reviews_dataset.csv"),
        "products": pd.read_csv(RAW / "olist_products_dataset.csv"),
        "sellers": pd.read_csv(RAW / "olist_sellers_dataset.csv"),
        "translation": pd.read_csv(RAW / "product_category_name_translation.csv"),
    }


def build_orders(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per order with revenue, delivery and review fields."""
    orders = t["orders"].merge(t["customers"], on="customer_id", how="left")

    totals = t["items"].groupby("order_id").agg(
        items=("order_item_id", "count"),
        item_revenue=("price", "sum"),
        freight=("freight_value", "sum"),
    )
    orders = orders.join(totals, on="order_id")
    orders["gmv"] = orders["item_revenue"] + orders["freight"]

    # Some orders have more than one review; keep the most recent one.
    reviews = (
        t["reviews"].sort_values("review_creation_date").drop_duplicates("order_id", keep="last")
    )[["order_id", "review_score"]]
    orders = orders.merge(reviews, on="order_id", how="left")

    pay = t["payments"].sort_values("payment_value", ascending=False).drop_duplicates("order_id")
    orders = orders.merge(pay[["order_id", "payment_type"]], on="order_id", how="left")

    orders["order_month"] = orders["order_purchase_timestamp"].dt.to_period("M").astype(str)
    orders["delivery_days"] = (
        orders["order_delivered_customer_date"] - orders["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400
    orders["estimated_days"] = (
        orders["order_estimated_delivery_date"] - orders["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400
    delivered = orders["order_status"].eq("delivered") & orders["order_delivered_customer_date"].notna()
    orders["is_delivered"] = delivered
    orders["is_late"] = delivered & (
        orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"]
    )

    in_window = orders["order_purchase_timestamp"].between(WINDOW_START, pd.Timestamp(WINDOW_END) + pd.Timedelta(days=1))
    return orders[in_window].reset_index(drop=True)


def build_items(t: dict[str, pd.DataFrame], orders: pd.DataFrame) -> pd.DataFrame:
    """One row per order item with English category names."""
    products = t["products"].merge(t["translation"], on="product_category_name", how="left")
    products["category"] = products["product_category_name_english"].fillna("unknown")
    items = t["items"].merge(products[["product_id", "category"]], on="product_id", how="left")
    items["category"] = items["category"].fillna("unknown")
    keep = orders[["order_id", "order_month", "order_status", "customer_unique_id", "customer_state"]]
    return items.merge(keep, on="order_id", how="inner")


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    tables = load_raw()
    orders = build_orders(tables)
    items = build_items(tables, orders)

    orders.to_csv(PROCESSED / "orders.csv", index=False)
    items.to_csv(PROCESSED / "items.csv", index=False)

    with sqlite3.connect(DB_PATH) as con:
        orders.to_sql("orders", con, if_exists="replace", index=False)
        items.to_sql("items", con, if_exists="replace", index=False)

    print(f"orders: {len(orders):,} | items: {len(items):,} | customers: {orders.customer_unique_id.nunique():,}")
    print(f"window: {orders.order_purchase_timestamp.min().date()} to {orders.order_purchase_timestamp.max().date()}")


if __name__ == "__main__":
    main()
