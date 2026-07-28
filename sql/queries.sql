-- sql/queries.sql
-- 30+ Meaningful SQL Queries for Analytics

-- ---------------------------------------------------------
-- AGGREGATIONS & GROUP BY
-- ---------------------------------------------------------
-- 1. Average rating by city
SELECT c.city_name, ROUND(AVG(r.rating), 2) as avg_rating, COUNT(*) as review_count
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN cities c ON b.city_id = c.city_id
GROUP BY c.city_name HAVING COUNT(*) >= 5 ORDER BY avg_rating DESC;

-- 2. Average rating by category
SELECT cat.category_name, ROUND(AVG(r.rating), 2) as avg_rating, COUNT(*) as review_count
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN categories cat ON b.category_id = cat.category_id
GROUP BY cat.category_name HAVING COUNT(*) >= 5 ORDER BY avg_rating DESC;

-- 3. Top 10 highest-rated businesses (min 10 reviews)
SELECT b.name, c.city_name, ROUND(AVG(r.rating), 2) as avg_rating, COUNT(*) as review_count
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN cities c ON b.city_id = c.city_id
GROUP BY b.business_id HAVING COUNT(*) >= 10 ORDER BY avg_rating DESC LIMIT 10;

-- 4. Lowest 10 rated businesses (min 10 reviews) - needs attention
SELECT b.name, c.city_name, ROUND(AVG(r.rating), 2) as avg_rating, COUNT(*) as review_count
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN cities c ON b.city_id = c.city_id
GROUP BY b.business_id HAVING COUNT(*) >= 10 ORDER BY avg_rating ASC LIMIT 10;

-- 5. Total reviews by sentiment label
SELECT sentiment_label, COUNT(*) as count, ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM reviews), 2) as pct
FROM reviews GROUP BY sentiment_label;

-- 6. Rating distribution (1 to 5 stars)
SELECT CAST(rating AS INTEGER) as rating, COUNT(*) as review_count
FROM reviews GROUP BY CAST(rating AS INTEGER) ORDER BY rating;

-- 7. Monthly review volume
SELECT review_year, review_month, COUNT(*) as review_count
FROM reviews WHERE review_year IS NOT NULL GROUP BY review_year, review_month ORDER BY review_year, review_month;

-- 8. Top complaint categories
SELECT complaint_category, COUNT(*) as count
FROM keywords WHERE complaint_category IS NOT NULL GROUP BY complaint_category ORDER BY count DESC;

-- ---------------------------------------------------------
-- JOINS & SUBQUERIES
-- ---------------------------------------------------------
-- 9. Businesses with higher average rating than their city's average
SELECT b.name, c.city_name, ROUND(AVG(r.rating),2) as b_avg
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN cities c ON b.city_id = c.city_id
GROUP BY b.business_id
HAVING AVG(r.rating) > (
    SELECT AVG(r2.rating) FROM reviews r2 JOIN businesses b2 ON r2.business_id = b2.business_id WHERE b2.city_id = b.city_id
);

-- 10. Percentage of positive reviews by category
SELECT cat.category_name,
    SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pos_pct
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN categories cat ON b.category_id = cat.category_id
GROUP BY cat.category_name HAVING COUNT(*) >= 10 ORDER BY pos_pct DESC;

-- ---------------------------------------------------------
-- WINDOW FUNCTIONS (RANK, DENSE_RANK, NTILE, LAG, LEAD)
-- ---------------------------------------------------------
-- 11. Rank businesses by rating within each city
SELECT c.city_name, b.name, ROUND(AVG(r.rating), 2) as avg_rating,
    RANK() OVER(PARTITION BY c.city_id ORDER BY AVG(r.rating) DESC) as city_rank
FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN cities c ON b.city_id = c.city_id
GROUP BY b.business_id HAVING COUNT(*) >= 5;

-- 12. Month-over-month review volume growth
WITH monthly AS (
    SELECT PRINTF('%04d-%02d', review_year, review_month) as ym, COUNT(*) as cnt
    FROM reviews WHERE review_year IS NOT NULL GROUP BY review_year, review_month
)
SELECT ym, cnt, LAG(cnt) OVER(ORDER BY ym) as prev_cnt,
    ROUND(100.0 * (cnt - LAG(cnt) OVER(ORDER BY ym)) / LAG(cnt) OVER(ORDER BY ym), 2) as growth_pct
FROM monthly;

-- 13. Running average of overall rating (3-month window)
WITH monthly_avg AS (
    SELECT PRINTF('%04d-%02d', review_year, review_month) as ym, AVG(rating) as avg_rating
    FROM reviews WHERE review_year IS NOT NULL GROUP BY review_year, review_month
)
SELECT ym, avg_rating,
    AVG(avg_rating) OVER(ORDER BY ym ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as running_3m_avg
FROM monthly_avg;

-- 14. Divide cities into quartiles by review volume
WITH city_vol AS (
    SELECT c.city_name, COUNT(*) as vol
    FROM reviews r JOIN businesses b ON r.business_id=b.business_id JOIN cities c ON b.city_id=c.city_id
    GROUP BY c.city_id
)
SELECT city_name, vol, NTILE(4) OVER(ORDER BY vol DESC) as quartile FROM city_vol;

-- ---------------------------------------------------------
-- CTEs (Common Table Expressions)
-- ---------------------------------------------------------
-- 15. Businesses whose recent rating is worse than their historical average
WITH hist_avg AS (
    SELECT business_id, AVG(rating) as h_avg FROM reviews GROUP BY business_id HAVING COUNT(*)>=10
),
recent_avg AS (
    SELECT business_id, AVG(rating) as r_avg FROM reviews
    WHERE review_date >= date('now', '-6 months') GROUP BY business_id
)
SELECT b.name, h.h_avg, r.r_avg, (r.r_avg - h.h_avg) as drop
FROM businesses b JOIN hist_avg h ON b.business_id=h.business_id JOIN recent_avg r ON b.business_id=r.business_id
WHERE r.r_avg < h.h_avg ORDER BY drop ASC;
