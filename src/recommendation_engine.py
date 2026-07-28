"""
src/recommendation_engine.py — Automated business insight and recommendation generator.

Produces a structured list of natural-language insights derived from analytics:
- Businesses below rating threshold
- Cities above/below national average
- Most common complaint category
- Category performance comparison
- Trend direction (improving / declining)
- High negative-sentiment businesses

Insights are returned as a list of dicts:
  [{"type": "warning", "title": "...", "detail": "...", "action": "..."}, ...]

Types: "warning" | "success" | "info" | "critical"
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.utils import setup_logging

logger = setup_logging(__name__)

Insight = Dict[str, str]


# ─────────────────────────────────────────────
# INDIVIDUAL INSIGHT GENERATORS
# ─────────────────────────────────────────────

def _insight_businesses_needing_attention(
    bottom_df: pd.DataFrame,
    threshold: float = cfg.RATING_ALERT_THRESHOLD,
) -> List[Insight]:
    """Flag businesses below the rating alert threshold."""
    insights = []
    if bottom_df.empty:
        return insights

    count = len(bottom_df)
    worst = bottom_df.iloc[0]
    insights.append({
        "type": "critical" if count > 5 else "warning",
        "title": f"{count} Business{'es' if count > 1 else ''} Need Attention",
        "detail": (
            f"{count} businesses have an average rating below {threshold}★. "
            f"The lowest-rated is '{worst.get('business_name', 'Unknown')}' "
            f"({worst.get('avg_rating', 0):.1f}★ across {int(worst.get('review_count', 0))} reviews)."
        ),
        "action": (
            "Conduct service quality audits for these locations. "
            "Review negative feedback themes to identify root causes."
        ),
    })
    return insights


def _insight_city_vs_national(
    city_df: pd.DataFrame,
    national_avg: float,
) -> List[Insight]:
    """Flag cities significantly above or below national average."""
    insights = []
    if city_df.empty or national_avg == 0:
        return insights

    LOW_THRESHOLD = -0.3
    HIGH_THRESHOLD = 0.3

    low_cities = city_df[city_df["avg_rating"] < national_avg + LOW_THRESHOLD].head(3)
    high_cities = city_df[city_df["avg_rating"] > national_avg + HIGH_THRESHOLD].head(3)

    if not low_cities.empty:
        names = ", ".join(low_cities["city_name"].tolist())
        avg = low_cities["avg_rating"].mean()
        insights.append({
            "type": "warning",
            "title": "Cities Below National Average",
            "detail": (
                f"{names} {'have' if len(low_cities) > 1 else 'has'} average ratings "
                f"({avg:.2f}★) significantly below the national average of {national_avg:.2f}★."
            ),
            "action": (
                "Investigate location-specific factors such as local competition, "
                "staffing issues, or regional customer expectations."
            ),
        })

    if not high_cities.empty:
        names = ", ".join(high_cities["city_name"].tolist())
        avg = high_cities["avg_rating"].mean()
        insights.append({
            "type": "success",
            "title": "Top Performing Cities",
            "detail": (
                f"{names} {'are' if len(high_cities) > 1 else 'is'} performing "
                f"above the national average with ratings of {avg:.2f}★."
            ),
            "action": (
                "Study best practices from these locations and replicate "
                "successful approaches in underperforming cities."
            ),
        })
    return insights


def _insight_top_complaint(complaint_df: pd.DataFrame) -> List[Insight]:
    """Identify the #1 complaint category."""
    if complaint_df.empty:
        return []

    top = complaint_df.iloc[0]
    cat = top.get("category", "Unknown")
    pct = top.get("pct", 0)

    return [{
        "type": "warning",
        "title": f"Top Complaint: {cat}",
        "detail": (
            f"'{cat}' accounts for {pct:.1f}% of all negative feedback — "
            "the most frequently mentioned issue in customer reviews."
        ),
        "action": (
            f"Prioritise improvements to {cat.lower()} experience. "
            "Set measurable targets and monitor weekly."
        ),
    }]


def _insight_category_comparison(cat_df: pd.DataFrame) -> List[Insight]:
    """Compare business categories by average rating."""
    if cat_df.empty or len(cat_df) < 2:
        return []

    best = cat_df.iloc[0]
    worst = cat_df.iloc[-1]
    gap = float(best.get("avg_rating", 0)) - float(worst.get("avg_rating", 0))

    return [{
        "type": "info",
        "title": f"{best.get('category_name', 'Top Category')} Outperforms Others",
        "detail": (
            f"'{best.get('category_name', 'Top')}' category leads with "
            f"{best.get('avg_rating', 0):.2f}★, while "
            f"'{worst.get('category_name', 'Bottom')}' lags at "
            f"{worst.get('avg_rating', 0):.2f}★ — a gap of {gap:.2f} stars."
        ),
        "action": (
            f"Investigate what '{best.get('category_name', '')}' businesses do differently. "
            "Consider cross-category training and process sharing."
        ),
    }]


def _insight_sentiment_health(kpis: dict) -> List[Insight]:
    """Overall sentiment health insight."""
    insights = []
    pos_pct = kpis.get("positive_pct", 0) or 0
    neg_pct = kpis.get("negative_pct", 0) or 0
    avg = kpis.get("avg_rating", 0) or 0

    if pos_pct >= 70:
        insights.append({
            "type": "success",
            "title": "Strong Positive Sentiment",
            "detail": (
                f"{pos_pct:.1f}% of reviews are positive, indicating generally "
                f"satisfied customers with an average rating of {avg:.2f}★."
            ),
            "action": "Maintain quality standards and leverage positive reviews in marketing.",
        })
    elif neg_pct >= 30:
        insights.append({
            "type": "critical",
            "title": "High Negative Sentiment Alert",
            "detail": (
                f"{neg_pct:.1f}% of reviews are negative. This level of negative "
                "sentiment requires immediate management attention."
            ),
            "action": "Initiate customer recovery program. Respond to all negative reviews within 24 hours.",
        })
    elif neg_pct >= 20:
        insights.append({
            "type": "warning",
            "title": "Elevated Negative Feedback",
            "detail": (
                f"{neg_pct:.1f}% of all reviews are negative. "
                f"Overall average rating is {avg:.2f}★."
            ),
            "action": "Review complaint categories and develop targeted action plans.",
        })
    return insights


def _insight_review_trend(trend_df: pd.DataFrame) -> List[Insight]:
    """Check if review volume is growing or declining."""
    if trend_df.empty or len(trend_df) < 3:
        return []

    recent = trend_df.tail(3)["review_count"].mean()
    earlier = trend_df.head(3)["review_count"].mean()

    if earlier == 0:
        return []

    change_pct = (recent - earlier) / earlier * 100

    if change_pct > 20:
        return [{
            "type": "success",
            "title": "Growing Review Volume",
            "detail": f"Recent review volume is {change_pct:.0f}% higher than earlier periods, indicating increased customer engagement.",
            "action": "Capitalise on growth momentum. Encourage reviews through loyalty programs.",
        }]
    elif change_pct < -20:
        return [{
            "type": "warning",
            "title": "Declining Review Activity",
            "detail": f"Recent review volume has dropped by {abs(change_pct):.0f}% compared to earlier periods.",
            "action": "Investigate causes of reduced engagement. Consider review solicitation campaigns.",
        }]
    return []


# ─────────────────────────────────────────────
# MAIN INSIGHT GENERATOR
# ─────────────────────────────────────────────

def generate_insights(
    kpis: dict,
    bottom_df: pd.DataFrame,
    city_df: pd.DataFrame,
    national_avg: float,
    complaint_df: pd.DataFrame,
    category_df: pd.DataFrame,
    trend_df: pd.DataFrame,
) -> List[Insight]:
    """
    Orchestrate all insight generators and return a combined list.

    Args:
        kpis:          KPI summary dict from analytics.get_kpi_summary().
        bottom_df:     Lowest-rated businesses DataFrame.
        city_df:       City performance DataFrame.
        national_avg:  National average rating.
        complaint_df:  Complaint category frequencies DataFrame.
        category_df:   Category average ratings DataFrame.
        trend_df:      Monthly review volume DataFrame.

    Returns:
        List of insight dicts: [{type, title, detail, action}, ...]
    """
    insights: List[Insight] = []

    insights.extend(_insight_sentiment_health(kpis))
    insights.extend(_insight_businesses_needing_attention(bottom_df))
    insights.extend(_insight_city_vs_national(city_df, national_avg))
    insights.extend(_insight_top_complaint(complaint_df))
    insights.extend(_insight_category_comparison(category_df))
    insights.extend(_insight_review_trend(trend_df))

    logger.info("Generated %d business insights.", len(insights))
    return insights


def generate_recommendations(insights: List[Insight]) -> List[str]:
    """
    Distil insights into a plain-English recommendation list.

    Args:
        insights: List of insight dicts.

    Returns:
        List of recommendation strings.
    """
    return [ins["action"] for ins in insights if ins.get("action")]
