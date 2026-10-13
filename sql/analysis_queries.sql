-- Run against data/olist.sqlite after scripts/prepare_data.py.
-- Tables: orders (one row per order), items (one row per order item).
-- "Valid" orders exclude canceled and unavailable ones.

-- 1. Headline KPIs
SELECT COUNT(*) AS orders,
       COUNT(DISTINCT customer_unique_id) AS customers,
       ROUND(SUM(item_revenue), 0) AS revenue,
       ROUND(SUM(item_revenue) / COUNT(*), 2) AS aov
FROM orders
WHERE order_status NOT IN ('canceled', 'unavailable');

-- 2. Monthly revenue with month-on-month growth
WITH monthly AS (
    SELECT order_month, ROUND(SUM(item_revenue), 0) AS revenue, COUNT(*) AS orders
    FROM orders
    WHERE order_status NOT IN ('canceled', 'unavailable')
    GROUP BY order_month
)
SELECT order_month, revenue, orders,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY order_month)) / LAG(revenue) OVER (ORDER BY order_month), 1) AS growth_pct
FROM monthly
ORDER BY order_month;

-- 3. Top 10 categories by revenue with share of total
SELECT category,
       ROUND(SUM(price), 0) AS revenue,
       ROUND(100.0 * SUM(price) / SUM(SUM(price)) OVER (), 1) AS share_pct,
       COUNT(*) AS items_sold
FROM items
WHERE order_status NOT IN ('canceled', 'unavailable')
GROUP BY category
ORDER BY revenue DESC
LIMIT 10;

-- 4. How many customers buy more than once
WITH per_customer AS (
    SELECT customer_unique_id, COUNT(*) AS orders
    FROM orders
    WHERE order_status NOT IN ('canceled', 'unavailable')
    GROUP BY customer_unique_id
)
SELECT CASE WHEN orders = 1 THEN '1 order' WHEN orders = 2 THEN '2 orders' ELSE '3+ orders' END AS bucket,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_customers
FROM per_customer
GROUP BY bucket
ORDER BY customers DESC;

-- 5. Late delivery rate and average review score, on time vs late
SELECT CASE WHEN is_late = 1 THEN 'late' ELSE 'on time' END AS delivery,
       COUNT(*) AS orders,
       ROUND(AVG(review_score), 2) AS avg_review,
       ROUND(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0 END), 1) AS low_score_pct
FROM orders
WHERE is_delivered = 1 AND review_score IS NOT NULL
GROUP BY is_late;

-- 6. Delivery performance by state (states with at least 500 orders)
SELECT customer_state,
       COUNT(*) AS orders,
       ROUND(SUM(item_revenue), 0) AS revenue,
       ROUND(AVG(delivery_days), 1) AS avg_delivery_days,
       ROUND(100.0 * AVG(is_late), 1) AS late_pct,
       ROUND(AVG(review_score), 2) AS avg_review
FROM orders
WHERE order_status NOT IN ('canceled', 'unavailable')
GROUP BY customer_state
HAVING COUNT(*) >= 500
ORDER BY revenue DESC;

-- 7. Payment methods: share of orders and average order value
SELECT payment_type,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(AVG(item_revenue), 2) AS aov
FROM orders
WHERE order_status NOT IN ('canceled', 'unavailable') AND payment_type IS NOT NULL
GROUP BY payment_type
ORDER BY orders DESC;

-- 8. Seller concentration: revenue share of the top 10 percent of sellers
WITH seller_rev AS (
    SELECT seller_id, SUM(price) AS revenue
    FROM items
    WHERE order_status NOT IN ('canceled', 'unavailable')
    GROUP BY seller_id
),
ranked AS (
    SELECT revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rnk, COUNT(*) OVER () AS total
    FROM seller_rev
)
SELECT ROUND(100.0 * SUM(CASE WHEN rnk <= total * 0.10 THEN revenue ELSE 0 END) / SUM(revenue), 1) AS top_10pct_sellers_revenue_share
FROM ranked;

-- 9. Categories where freight is a large part of the price (at least 500 orders)
SELECT category,
       COUNT(DISTINCT order_id) AS orders,
       ROUND(AVG(price), 1) AS avg_price,
       ROUND(AVG(freight_value), 1) AS avg_freight,
       ROUND(100.0 * AVG(freight_value) / AVG(price), 1) AS freight_pct_of_price
FROM items
WHERE order_status NOT IN ('canceled', 'unavailable')
GROUP BY category
HAVING COUNT(DISTINCT order_id) >= 500
ORDER BY freight_pct_of_price DESC
LIMIT 10;
