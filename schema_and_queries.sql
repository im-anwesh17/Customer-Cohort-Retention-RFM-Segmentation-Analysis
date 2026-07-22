-- ============================================================
-- Customer Cohort Retention & RFM Segmentation Analysis
-- Database Schema (PostgreSQL Syntax) & Analytical Queries
-- ============================================================

-- 1. DATABASE SCHEMA (DDL)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT PRIMARY KEY,
    signup_date DATE NOT NULL,
    country VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(customer_id),
    order_date TIMESTAMP NOT NULL,
    order_value DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL
);

-- ------------------------------------------------------------
-- 2. COHORT RETENTION ANALYSIS QUERY
-- Demonstrating: CTEs, Window Functions (MIN() OVER), Date Functions
-- ------------------------------------------------------------
WITH first_purchases AS (
    -- Step 1: Identify initial purchase date and cohort month for each customer
    SELECT 
        customer_id,
        MIN(order_date) AS first_order_date,
        DATE_TRUNC('month', MIN(order_date))::DATE AS cohort_month
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
),
cohort_sizes AS (
    -- Step 2: Calculate total unique customers in each acquisition cohort
    SELECT 
        cohort_month,
        COUNT(DISTINCT customer_id) AS total_cohort_customers
    FROM first_purchases
    GROUP BY cohort_month
),
monthly_activities AS (
    -- Step 3: Map all completed transactions to cohort month and calculate month offset
    SELECT 
        fp.cohort_month,
        fp.customer_id,
        DATE_TRUNC('month', o.order_date)::DATE AS activity_month,
        (EXTRACT(YEAR FROM DATE_TRUNC('month', o.order_date)) - EXTRACT(YEAR FROM fp.cohort_month)) * 12 +
        (EXTRACT(MONTH FROM DATE_TRUNC('month', o.order_date)) - EXTRACT(MONTH FROM fp.cohort_month)) AS month_index
    FROM orders o
    JOIN first_purchases fp ON o.customer_id = fp.customer_id
    WHERE o.status = 'Completed'
),
cohort_matrix AS (
    -- Step 4: Count active customers per cohort and month index
    SELECT 
        ma.cohort_month,
        cs.total_cohort_customers,
        ma.month_index,
        COUNT(DISTINCT ma.customer_id) AS active_customers
    FROM monthly_activities ma
    JOIN cohort_sizes cs ON ma.cohort_month = cs.cohort_month
    GROUP BY ma.cohort_month, cs.total_cohort_customers, ma.month_index
)
-- Step 5: Final output with calculated retention percentages
SELECT 
    cohort_month,
    total_cohort_customers,
    month_index,
    active_customers,
    ROUND((active_customers::NUMERIC / total_cohort_customers::NUMERIC) * 100, 2) AS retention_rate_pct
FROM cohort_matrix
ORDER BY cohort_month, month_index;


-- ------------------------------------------------------------
-- 3. RFM SEGMENTATION QUERY
-- Demonstrating: NTILE() Window Function, Aggregations, CASE Statements
-- ------------------------------------------------------------
WITH rfm_raw AS (
    -- Step 1: Calculate raw Recency, Frequency, and Monetary values
    SELECT 
        customer_id,
        DATE '2026-01-01' - MAX(order_date)::DATE AS recency_days,
        COUNT(DISTINCT order_id) AS frequency,
        SUM(order_value) AS monetary_value
    FROM orders
    WHERE status = 'Completed'
    GROUP BY customer_id
),
rfm_scores AS (
    -- Step 2: Divide metrics into quintiles (1-5 scale) using NTILE()
    SELECT 
        customer_id,
        recency_days,
        frequency,
        monetary_value,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,   -- Lower recency = Higher score
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,      -- Higher frequency = Higher score
        NTILE(5) OVER (ORDER BY monetary_value ASC) AS m_score   -- Higher spend = Higher score
    FROM rfm_raw
),
rfm_segmented AS (
    -- Step 3: Classify customers into strategic business segments based on scores
    SELECT 
        customer_id,
        recency_days,
        frequency,
        monetary_value,
        r_score, f_score, m_score,
        CASE 
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'Promising / New'
            WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Lost / Churned'
            ELSE 'Need Attention'
        END AS customer_segment
    FROM rfm_scores
)
-- Step 4: Aggregate metrics by customer segment for executive reporting
SELECT 
    customer_segment,
    COUNT(customer_id) AS customer_count,
    ROUND((COUNT(customer_id)::NUMERIC / (SELECT COUNT(*) FROM rfm_segmented)::NUMERIC) * 100, 2) AS segment_pct,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency), 1) AS avg_orders_per_customer,
    ROUND(AVG(monetary_value), 2) AS avg_total_spend,
    ROUND(SUM(monetary_value), 2) AS total_revenue
FROM rfm_segmented
GROUP BY customer_segment
ORDER BY total_revenue DESC;
