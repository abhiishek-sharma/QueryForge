# QueryForge evaluation results

- Model: `qwen2.5-coder:7b` via Ollama (ollama version is 0.40.15), temperature 0, seed 0
- Date: 2026-11-17, machine: Darwin arm64
- Dataset: `samples/shop.db` (synthetic), cases: `eval/cases.json`
- **Answer correctness: 16/16** (result compared with a reference query's result, not just SQL validity)
- Generation latency (warm model): median 4672 ms, p95 14953 ms

| Category | Correct |
|---|---|
| filter | 4/4 |
| aggregation | 4/4 |
| join | 4/4 |
| ambiguous | 2/2 |
| unanswerable | 2/2 |

| Case | Question | Result | Why | Generated SQL |
|---|---|---|---|---|
| filter-1 | List the names of customers who live in Germany. | ✅ | matches reference | `SELECT name FROM customers WHERE country = 'Germany'` |
| filter-2 | Which products cost more than 100? | ✅ | matches reference | `SELECT name FROM products WHERE price > 100` |
| filter-3 | How many orders were cancelled? | ✅ | matches reference | `SELECT COUNT(*) FROM orders WHERE status = 'cancelled'` |
| filter-4 | Which customers signed up in March 2024? | ✅ | matches reference | `SELECT name FROM customers WHERE signup_date LIKE '2024-03-%'` |
| agg-1 | How many products are in each category? | ✅ | matches reference | `SELECT category, COUNT(*) AS product_count FROM products GROUP BY category` |
| agg-2 | What is the average product price? | ✅ | matches reference | `SELECT AVG(price) AS average_price FROM products` |
| agg-3 | How many customers are there in each country? | ✅ | matches reference | `SELECT country, COUNT(id) AS customer_count FROM customers GROUP BY country` |
| agg-4 | How many orders were placed in each month of 2025? | ✅ | matches reference 2 | `SELECT   strftime('%Y-%m', order_date) AS month,   COUNT(id) AS order_count FROM   orders WHERE   strftime('%Y', order_date) = '2025' GROUP BY   month ORDER BY   month` |
| join-1 | What is the total revenue from completed orders for each product category? | ✅ | matches reference | `SELECT p.category, SUM(oi.quantity * oi.unit_price) AS total_revenue FROM order_items oi JOIN orders o ON oi.order_id = o.id JOIN products p ON oi.product_id = p.id WHERE o.status = 'completed' GROUP BY p.category` |
| join-2 | Which 3 customers spent the most on completed orders? Show name and amount. | ✅ | matches reference | `SELECT c.name, SUM(oi.quantity * oi.unit_price) AS total_spent FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id WHERE o.status = 'completed' GROUP BY c.id ORDER BY total_spent DESC LIMIT 3` |
| join-3 | How many orders has each customer from Spain placed? Show customer name and order count. | ✅ | matches reference 1 | `SELECT c.name, COUNT(o.id) AS order_count FROM customers c JOIN orders o ON c.id = o.customer_id WHERE c.country = 'Spain' GROUP BY c.name` |
| join-4 | Which product was sold in the largest total quantity? | ✅ | matches reference 1 | `SELECT p.name, SUM(oi.quantity) AS total_quantity FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY p.name ORDER BY total_quantity DESC LIMIT 1` |
| ambig-1 | What is our total revenue? | ✅ | matches reference 1 | `SELECT SUM(order_items.quantity * order_items.unit_price) AS total_revenue FROM order_items` |
| ambig-2 | Who is our best customer? | ✅ | matches reference 1 (assumption stated: The best customer is the one with the highest total order value.) | `SELECT c.name, SUM(oi.quantity * oi.unit_price) AS total_order_value FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id GROUP BY c.id ORDER BY total_order_value DESC LIMIT 1` |
| unans-1 | What is the email address of each customer? | ✅ | refused | `CANNOT_ANSWER: Email addresses are not present in the provided schema.` |
| unans-2 | Which marketing campaign brought in the most orders? | ✅ | refused | `CANNOT_ANSWER: The schema does not contain information about marketing campaigns or their impact on orders.` |

Small, hand-written set on one synthetic schema. It shows how the demo behaves; it is not a benchmark.
