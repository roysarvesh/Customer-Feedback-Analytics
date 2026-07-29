-- sql/schema.sql
-- 3NF Normalized Database Schema for Customer Feedback Analytics Platform

-- Enable Foreign Keys (SQLite specific)
PRAGMA foreign_keys = ON;

-- 1. Cities Table
CREATE TABLE IF NOT EXISTS cities (
    city_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name VARCHAR(200) NOT NULL UNIQUE,
    state VARCHAR(200),
    country VARCHAR(200),
    latitude REAL,
    longitude REAL
);

-- 2. Categories Table
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name VARCHAR(300) NOT NULL UNIQUE
);

-- 3. Businesses Table
CREATE TABLE IF NOT EXISTS businesses (
    business_id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id VARCHAR(500),
    name VARCHAR(500) NOT NULL,
    city_id INTEGER,
    category_id INTEGER,
    address TEXT,
    latitude REAL,
    longitude REAL,
    source VARCHAR(100) NOT NULL DEFAULT 'google_maps',
    FOREIGN KEY(city_id) REFERENCES cities(city_id),
    FOREIGN KEY(category_id) REFERENCES categories(category_id),
    UNIQUE(name, city_id) -- Prevent exact duplicates for the same city
);

-- 4. Reviews Table
CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    rating REAL NOT NULL,
    review_text TEXT,
    review_date VARCHAR(20),
    review_year INTEGER,
    review_month INTEGER,
    source VARCHAR(100) NOT NULL DEFAULT 'google_maps',
    sentiment_compound REAL,
    sentiment_label VARCHAR(20),
    sentiment_positive REAL,
    sentiment_neutral REAL,
    sentiment_negative REAL,
    FOREIGN KEY(business_id) REFERENCES businesses(business_id)
);

-- 5. Keywords Table (Populated later by NLP pipeline)
CREATE TABLE IF NOT EXISTS keywords (
    keyword_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    keyword VARCHAR(200) NOT NULL,
    complaint_category VARCHAR(200),
    FOREIGN KEY(review_id) REFERENCES reviews(review_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_businesses_ext_id ON businesses(external_id);
CREATE INDEX IF NOT EXISTS idx_reviews_business_id ON reviews(business_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_reviews_year_month ON reviews(review_year, review_month);
CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_keywords_review_id ON keywords(review_id);
CREATE INDEX IF NOT EXISTS idx_keywords_category ON keywords(complaint_category);
