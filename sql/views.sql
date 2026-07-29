-- sql/views.sql
-- Useful SQL Views for the Dashboard

-- View 1: Business Performance Summary
CREATE VIEW IF NOT EXISTS vw_business_summary AS
SELECT
    b.business_id,
    b.name,
    c.city_name,
    cat.category_name,
    COUNT(r.review_id) as total_reviews,
    ROUND(AVG(r.rating), 2) as average_rating,
    SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) as positive_reviews,
    SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) as negative_reviews,
    ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(r.review_id), 2) as positive_pct
FROM businesses b
LEFT JOIN reviews r ON b.business_id = r.business_id
LEFT JOIN cities c ON b.city_id = c.city_id
LEFT JOIN categories cat ON b.category_id = cat.category_id
GROUP BY b.business_id;

-- View 2: City Performance Summary
CREATE VIEW IF NOT EXISTS vw_city_summary AS
SELECT
    c.city_name,
    COUNT(DISTINCT b.business_id) as total_businesses,
    COUNT(r.review_id) as total_reviews,
    ROUND(AVG(r.rating), 2) as average_rating,
    ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(r.review_id), 2) as positive_pct
FROM cities c
LEFT JOIN businesses b ON c.city_id = b.city_id
LEFT JOIN reviews r ON b.business_id = r.business_id
GROUP BY c.city_id;

-- View 3: Monthly Trends
CREATE VIEW IF NOT EXISTS vw_monthly_trends AS
SELECT
    review_year,
    review_month,
    PRINTF('%04d-%02d', review_year, review_month) as year_month,
    COUNT(review_id) as total_reviews,
    ROUND(AVG(rating), 2) as average_rating,
    ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(review_id), 2) as positive_pct,
    ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(review_id), 2) as negative_pct
FROM reviews
WHERE review_year IS NOT NULL AND review_month IS NOT NULL
GROUP BY review_year, review_month;
