-- One row per entity to score. Replace with the challenge query.
-- Keep only information known BEFORE the outcome happens.
SELECT
    c.customer_id,
    c.segment,
    c.state,
    c.plan,
    c.monthly_fee,
    c.tenure_months,
    COALESCE(o.orders_count, 0)        AS orders_count,
    COALESCE(o.orders_total, 0)        AS orders_total,
    COALESCE(o.late_payments, 0)       AS late_payments,
    o.days_since_last_order,
    COALESCE(t.tickets_count, 0)       AS tickets_count,
    COALESCE(t.unresolved_tickets, 0)  AS unresolved_tickets,
    c.churned
FROM customers c
LEFT JOIN (
    SELECT
        customer_id,
        COUNT(*)                                   AS orders_count,
        SUM(amount)                                AS orders_total,
        SUM(CASE WHEN paid_late THEN 1 ELSE 0 END) AS late_payments,
        (DATE '2026-11-01' - MAX(order_date))      AS days_since_last_order
    FROM orders
    GROUP BY customer_id
) o ON o.customer_id = c.customer_id
LEFT JOIN (
    SELECT
        customer_id,
        COUNT(*)                                      AS tickets_count,
        SUM(CASE WHEN NOT resolved THEN 1 ELSE 0 END) AS unresolved_tickets
    FROM support_tickets
    GROUP BY customer_id
) t ON t.customer_id = c.customer_id
