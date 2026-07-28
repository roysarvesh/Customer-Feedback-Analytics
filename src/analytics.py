"""
src/analytics.py — SQL-backed analytics engine.

All analytical queries run against the SQLite database via raw SQL
(using pandas read_sql for DataFrame output). This keeps analytics
separate from ORM models and makes queries easy to debug and extend.

Every function returns a pandas DataFrame ready for Plotly charts.
"""

import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd
from sqlalchemy import create_engine, text

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.utils import setup_logging

logger = setup_logging(__name__)


# ─────────────────────────────────────────────
# CONNECTION HELPER
# ─────────────────────────────────────────────

def _get_engine(engine=None):
    """Return engine from argument or create from config."""
    if engine is not None:
        return engine
    return create_engine(cfg.DB_URL, future=True)


def _sql(query: str, engine=None, params: Optional[dict] = None) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a DataFrame.

    Args:
        query:  SQL query string.
        engine: SQLAlchemy engine (created from config if None).
        params: Optional named parameters dict for parameterised queries.

    Returns:
        pandas DataFrame of query results.
    """
    eng = _get_engine(engine)
    with eng.connect() as conn:
        result = conn.execute(text(query), params or {})
        rows = result.fetchall()
        cols = list(result.keys())
    return pd.DataFrame(rows, columns=cols)


# ─────────────────────────────────────────────
# EXECUTIVE KPIs
# ─────────────────────────────────────────────

def get_kpi_summary(engine=None) -> dict:
    """
    Return top-level KPIs for the executive dashboard.

    Returns:
        Dict with keys: total_reviews, avg_rating, positive_pct,
                        negative_pct, neutral_pct, total_businesses,
                        total_cities.
    """
    df = _sql(
        """
        SELECT
            COUNT(r.review_id)                                        AS total_reviews,
            ROUND(AVG(r.rating), 2)                                   AS avg_rating,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(*), 1) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS negative_pct,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Neutral'  THEN 1 ELSE 0 END) / COUNT(*), 1) AS neutral_pct
        FROM reviews r
        """,
        engine,
    )
    biz_df = _sql("SELECT COUNT(*) AS total_businesses FROM businesses", engine)
    city_df = _sql("SELECT COUNT(*) AS total_cities FROM cities", engine)

    result = df.iloc[0].to_dict() if not df.empty else {}
    result["total_businesses"] = int(biz_df.iloc[0, 0]) if not biz_df.empty else 0
    result["total_cities"] = int(city_df.iloc[0, 0]) if not city_df.empty else 0
    return result


# ─────────────────────────────────────────────
# RATINGS ANALYTICS
# ─────────────────────────────────────────────

def get_rating_distribution(engine=None) -> pd.DataFrame:
    """Rating value distribution (1–5 stars)."""
    return _sql(
        """
        SELECT
            CAST(rating AS INTEGER) AS rating,
            COUNT(*)                AS review_count,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM reviews), 2) AS pct
        FROM reviews
        WHERE rating BETWEEN 1 AND 5
        GROUP BY CAST(rating AS INTEGER)
        ORDER BY rating
        """,
        engine,
    )


def get_avg_rating_by_city(
    engine=None,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
    limit: int = 30,
) -> pd.DataFrame:
    """Average rating per city, filtered by minimum review count."""
    return _sql(
        f"""
        SELECT
            c.city_name,
            ROUND(AVG(r.rating), 2)  AS avg_rating,
            COUNT(r.review_id)       AS review_count
        FROM reviews r
        JOIN businesses b ON r.business_id = b.business_id
        JOIN cities c     ON b.city_id = c.city_id
        GROUP BY c.city_name
        HAVING COUNT(r.review_id) >= {min_reviews}
        ORDER BY avg_rating DESC
        LIMIT {limit}
        """,
        engine,
    )


def get_avg_rating_by_category(
    engine=None,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """Average rating per business category."""
    return _sql(
        f"""
        SELECT
            cat.category_name,
            ROUND(AVG(r.rating), 2)  AS avg_rating,
            COUNT(r.review_id)       AS review_count
        FROM reviews r
        JOIN businesses b ON r.business_id = b.business_id
        JOIN categories cat ON b.category_id = cat.category_id
        GROUP BY cat.category_name
        HAVING COUNT(r.review_id) >= {min_reviews}
        ORDER BY avg_rating DESC
        """,
        engine,
    )


def get_top_businesses(
    engine=None,
    n: int = 10,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """Top N highest-rated businesses."""
    return _sql(
        f"""
        SELECT
            b.name                       AS business_name,
            c.city_name,
            cat.category_name,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            COUNT(r.review_id)           AS review_count,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(*), 1) AS positive_pct
        FROM reviews r
        JOIN businesses b  ON r.business_id = b.business_id
        LEFT JOIN cities c     ON b.city_id = c.city_id
        LEFT JOIN categories cat ON b.category_id = cat.category_id
        GROUP BY b.business_id
        HAVING COUNT(r.review_id) >= {min_reviews}
        ORDER BY avg_rating DESC, review_count DESC
        LIMIT {n}
        """,
        engine,
    )


def get_bottom_businesses(
    engine=None,
    n: int = 10,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """Bottom N lowest-rated businesses (needing attention)."""
    return _sql(
        f"""
        SELECT
            b.name                       AS business_name,
            c.city_name,
            cat.category_name,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            COUNT(r.review_id)           AS review_count,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS negative_pct
        FROM reviews r
        JOIN businesses b  ON r.business_id = b.business_id
        LEFT JOIN cities c     ON b.city_id = c.city_id
        LEFT JOIN categories cat ON b.category_id = cat.category_id
        GROUP BY b.business_id
        HAVING COUNT(r.review_id) >= {min_reviews}
        ORDER BY avg_rating ASC, negative_pct DESC
        LIMIT {n}
        """,
        engine,
    )


def get_businesses_needing_attention(
    engine=None,
    threshold: float = cfg.RATING_ALERT_THRESHOLD,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """Businesses with average rating below alert threshold."""
    return _sql(
        f"""
        SELECT
            b.name                       AS business_name,
            c.city_name,
            cat.category_name,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            COUNT(r.review_id)           AS review_count,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS negative_pct
        FROM reviews r
        JOIN businesses b  ON r.business_id = b.business_id
        LEFT JOIN cities c     ON b.city_id = c.city_id
        LEFT JOIN categories cat ON b.category_id = cat.category_id
        GROUP BY b.business_id
        HAVING avg_rating < {threshold} AND COUNT(r.review_id) >= {min_reviews}
        ORDER BY avg_rating ASC
        """,
        engine,
    )


# ─────────────────────────────────────────────
# TREND ANALYTICS
# ─────────────────────────────────────────────

def get_monthly_review_volume(engine=None) -> pd.DataFrame:
    """Monthly review count over time."""
    return _sql(
        """
        SELECT
            review_year                  AS year,
            review_month                 AS month,
            PRINTF('%04d-%02d', review_year, review_month) AS year_month,
            COUNT(review_id)             AS review_count
        FROM reviews
        WHERE review_year IS NOT NULL AND review_month IS NOT NULL
        GROUP BY review_year, review_month
        ORDER BY review_year, review_month
        """,
        engine,
    )


def get_monthly_avg_rating(engine=None) -> pd.DataFrame:
    """Monthly average rating trend."""
    return _sql(
        """
        SELECT
            review_year                  AS year,
            review_month                 AS month,
            PRINTF('%04d-%02d', review_year, review_month) AS year_month,
            ROUND(AVG(rating), 3)        AS avg_rating,
            COUNT(review_id)             AS review_count
        FROM reviews
        WHERE review_year IS NOT NULL AND review_month IS NOT NULL
        GROUP BY review_year, review_month
        ORDER BY review_year, review_month
        """,
        engine,
    )


def get_monthly_sentiment_trend(engine=None) -> pd.DataFrame:
    """Monthly positive and negative review percentage trend."""
    return _sql(
        """
        SELECT
            review_year,
            review_month,
            PRINTF('%04d-%02d', review_year, review_month) AS year_month,
            COUNT(*)                                        AS total,
            ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(*), 2) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 2) AS negative_pct,
            ROUND(100.0 * SUM(CASE WHEN sentiment_label = 'Neutral'  THEN 1 ELSE 0 END) / COUNT(*), 2) AS neutral_pct
        FROM reviews
        WHERE review_year IS NOT NULL AND review_month IS NOT NULL
        GROUP BY review_year, review_month
        ORDER BY review_year, review_month
        """,
        engine,
    )


def get_review_growth_rate(engine=None) -> pd.DataFrame:
    """Month-over-month review growth using LAG window function."""
    return _sql(
        """
        WITH monthly AS (
            SELECT
                PRINTF('%04d-%02d', review_year, review_month) AS year_month,
                COUNT(*) AS review_count
            FROM reviews
            WHERE review_year IS NOT NULL
            GROUP BY review_year, review_month
            ORDER BY review_year, review_month
        )
        SELECT
            year_month,
            review_count,
            LAG(review_count) OVER (ORDER BY year_month) AS prev_month_count,
            ROUND(
                100.0 * (review_count - LAG(review_count) OVER (ORDER BY year_month))
                / NULLIF(LAG(review_count) OVER (ORDER BY year_month), 0),
                2
            ) AS growth_pct
        FROM monthly
        """,
        engine,
    )


def get_rating_trend_with_running_avg(engine=None, window: int = 3) -> pd.DataFrame:
    """Monthly average rating with 3-month running average."""
    return _sql(
        f"""
        WITH monthly AS (
            SELECT
                PRINTF('%04d-%02d', review_year, review_month) AS year_month,
                ROUND(AVG(rating), 3) AS avg_rating
            FROM reviews
            WHERE review_year IS NOT NULL
            GROUP BY review_year, review_month
            ORDER BY review_year, review_month
        )
        SELECT
            year_month,
            avg_rating,
            ROUND(AVG(avg_rating) OVER (
                ORDER BY year_month
                ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW
            ), 3) AS running_avg_{window}m
        FROM monthly
        """,
        engine,
    )


# ─────────────────────────────────────────────
# GEOGRAPHIC ANALYTICS
# ─────────────────────────────────────────────

def get_city_performance(
    engine=None,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """City-level aggregate: rating, review count, sentiment distribution."""
    return _sql(
        f"""
        SELECT
            c.city_name,
            COUNT(r.review_id)           AS review_count,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(*), 1) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS negative_pct,
            COUNT(DISTINCT b.business_id) AS business_count
        FROM reviews r
        JOIN businesses b ON r.business_id = b.business_id
        JOIN cities c     ON b.city_id = c.city_id
        GROUP BY c.city_name
        HAVING COUNT(r.review_id) >= {min_reviews}
        ORDER BY review_count DESC
        """,
        engine,
    )


def get_category_performance(
    engine=None,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """
    Category-level aggregate: rating, review count, sentiment distribution.

    Used in place of get_city_performance() for datasets (like this one)
    that have no city / location columns but do have business categories.
    """
    return _sql(
        f"""
        SELECT
            cat.category_name,
            COUNT(r.review_id)           AS review_count,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(*), 1) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS negative_pct,
            COUNT(DISTINCT b.business_id) AS business_count
        FROM reviews r
        JOIN businesses b   ON r.business_id = b.business_id
        JOIN categories cat ON b.category_id = cat.category_id
        GROUP BY cat.category_name
        HAVING COUNT(r.review_id) >= {min_reviews}
        ORDER BY review_count DESC
        """,
        engine,
    )


def get_national_avg_rating(engine=None) -> float:
    """Overall average rating across all reviews."""
    df = _sql("SELECT ROUND(AVG(rating), 3) AS national_avg FROM reviews", engine)
    return float(df.iloc[0, 0]) if not df.empty else 0.0


# ─────────────────────────────────────────────
# BUSINESS COMPARISON
# ─────────────────────────────────────────────

def get_business_profile(
    business_name: str,
    engine=None,
) -> dict:
    """
    Full analytics profile for a single business.

    Args:
        business_name: Exact business name string.
        engine:        SQLAlchemy engine.

    Returns:
        Dict with avg_rating, review_count, sentiment breakdown,
        monthly trend DataFrame.
    """
    df = _sql(
        """
        SELECT
            b.name,
            ROUND(AVG(r.rating), 2)      AS avg_rating,
            COUNT(r.review_id)           AS review_count,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Positive' THEN 1 ELSE 0 END) / COUNT(*), 1) AS positive_pct,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Negative' THEN 1 ELSE 0 END) / COUNT(*), 1) AS negative_pct,
            ROUND(100.0 * SUM(CASE WHEN r.sentiment_label = 'Neutral'  THEN 1 ELSE 0 END) / COUNT(*), 1) AS neutral_pct
        FROM reviews r
        JOIN businesses b ON r.business_id = b.business_id
        WHERE b.name = :name
        GROUP BY b.name
        """,
        engine,
        params={"name": business_name},
    )

    trend_df = _sql(
        """
        SELECT
            PRINTF('%04d-%02d', r.review_year, r.review_month) AS year_month,
            ROUND(AVG(r.rating), 2)  AS avg_rating,
            COUNT(r.review_id)       AS review_count
        FROM reviews r
        JOIN businesses b ON r.business_id = b.business_id
        WHERE b.name = :name
          AND r.review_year IS NOT NULL
        GROUP BY r.review_year, r.review_month
        ORDER BY r.review_year, r.review_month
        """,
        engine,
        params={"name": business_name},
    )

    result = df.iloc[0].to_dict() if not df.empty else {}
    result["monthly_trend"] = trend_df
    return result


def get_business_names(engine=None) -> List[str]:
    """Return sorted list of all business names in the database."""
    df = _sql("SELECT DISTINCT name FROM businesses ORDER BY name", engine)
    return df["name"].tolist() if not df.empty else []


def get_city_names(engine=None) -> List[str]:
    """Return sorted list of all city names in the database."""
    df = _sql("SELECT city_name FROM cities ORDER BY city_name", engine)
    return df["city_name"].tolist() if not df.empty else []


def get_category_names(engine=None) -> List[str]:
    """Return sorted list of all category names in the database."""
    df = _sql("SELECT category_name FROM categories ORDER BY category_name", engine)
    return df["category_name"].tolist() if not df.empty else []


# ─────────────────────────────────────────────
# ADVANCED WINDOW FUNCTION QUERIES
# ─────────────────────────────────────────────

def get_business_rating_rank(
    engine=None,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """Rank all businesses by average rating using DENSE_RANK."""
    return _sql(
        f"""
        WITH biz_stats AS (
            SELECT
                b.name                       AS business_name,
                c.city_name,
                ROUND(AVG(r.rating), 2)      AS avg_rating,
                COUNT(r.review_id)           AS review_count
            FROM reviews r
            JOIN businesses b  ON r.business_id = b.business_id
            LEFT JOIN cities c ON b.city_id = c.city_id
            GROUP BY b.business_id
            HAVING COUNT(r.review_id) >= {min_reviews}
        )
        SELECT
            business_name,
            city_name,
            avg_rating,
            review_count,
            DENSE_RANK() OVER (ORDER BY avg_rating DESC) AS rating_rank
        FROM biz_stats
        ORDER BY rating_rank
        """,
        engine,
    )


def get_businesses_with_declining_ratings(
    engine=None,
    min_reviews: int = cfg.MIN_REVIEW_COUNT,
) -> pd.DataFrame:
    """
    Identify businesses whose recent average rating is lower than their overall average.
    Uses a 6-month recent window vs all-time average.
    """
    return _sql(
        f"""
        WITH all_time AS (
            SELECT
                b.business_id,
                b.name,
                ROUND(AVG(r.rating), 2) AS all_time_avg,
                COUNT(r.review_id)      AS total_reviews
            FROM reviews r
            JOIN businesses b ON r.business_id = b.business_id
            GROUP BY b.business_id
            HAVING COUNT(r.review_id) >= {min_reviews}
        ),
        recent AS (
            SELECT
                b.business_id,
                ROUND(AVG(r.rating), 2) AS recent_avg
            FROM reviews r
            JOIN businesses b ON r.business_id = b.business_id
            WHERE r.review_date >= DATE('now', '-6 months')
            GROUP BY b.business_id
        )
        SELECT
            a.name           AS business_name,
            a.all_time_avg,
            r.recent_avg,
            ROUND(r.recent_avg - a.all_time_avg, 2) AS rating_change,
            a.total_reviews
        FROM all_time a
        JOIN recent r ON a.business_id = r.business_id
        WHERE r.recent_avg < a.all_time_avg
        ORDER BY rating_change ASC
        LIMIT 20
        """,
        engine,
    )


def get_review_percentile_by_city(engine=None) -> pd.DataFrame:
    """City review count with NTILE percentile ranking."""
    return _sql(
        """
        WITH city_counts AS (
            SELECT
                c.city_name,
                COUNT(r.review_id) AS review_count
            FROM reviews r
            JOIN businesses b ON r.business_id = b.business_id
            JOIN cities c     ON b.city_id = c.city_id
            GROUP BY c.city_name
        )
        SELECT
            city_name,
            review_count,
            NTILE(4) OVER (ORDER BY review_count) AS quartile
        FROM city_counts
        ORDER BY review_count DESC
        """,
        engine,
    )


def get_top_cities_per_category(engine=None) -> pd.DataFrame:
    """Best city per category using RANK() window function."""
    return _sql(
        """
        WITH city_cat AS (
            SELECT
                cat.category_name,
                c.city_name,
                ROUND(AVG(r.rating), 2) AS avg_rating,
                COUNT(r.review_id)      AS review_count
            FROM reviews r
            JOIN businesses b   ON r.business_id = b.business_id
            JOIN categories cat ON b.category_id = cat.category_id
            JOIN cities c       ON b.city_id = c.city_id
            GROUP BY cat.category_name, c.city_name
            HAVING COUNT(r.review_id) >= 5
        ),
        ranked AS (
            SELECT *,
                RANK() OVER (PARTITION BY category_name ORDER BY avg_rating DESC) AS rnk
            FROM city_cat
        )
        SELECT category_name, city_name, avg_rating, review_count, rnk
        FROM ranked
        WHERE rnk = 1
        ORDER BY avg_rating DESC
        """,
        engine,
    )


def get_sample_reviews(
    engine=None,
    sentiment: Optional[str] = None,
    business_name: Optional[str] = None,
    city_name: Optional[str] = None,
    limit: int = 20,
) -> pd.DataFrame:
    """
    Fetch sample reviews with optional filters.

    Args:
        sentiment:     Filter by 'Positive', 'Negative', or 'Neutral'. None = all.
        business_name: Filter by exact business name.
        city_name:     Filter by city name.
        limit:         Max rows to return.
    """
    where_clauses = ["1=1"]
    params: dict = {}

    if sentiment:
        where_clauses.append("r.sentiment_label = :sentiment")
        params["sentiment"] = sentiment
    if business_name:
        where_clauses.append("b.name = :biz")
        params["biz"] = business_name
    if city_name:
        where_clauses.append("c.city_name = :city")
        params["city"] = city_name

    where_str = " AND ".join(where_clauses)

    return _sql(
        f"""
        SELECT
            b.name              AS business_name,
            c.city_name,
            r.rating,
            r.sentiment_label,
            r.review_text,
            r.review_date
        FROM reviews r
        JOIN businesses b  ON r.business_id = b.business_id
        LEFT JOIN cities c ON b.city_id = c.city_id
        WHERE {where_str}
        ORDER BY RANDOM()
        LIMIT {limit}
        """,
        engine,
        params=params,
    )
