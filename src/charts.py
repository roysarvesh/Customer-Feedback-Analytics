"""
src/charts.py — Reusable Plotly chart factory.

All charts use the dark theme and brand colour palette from config.py.
Every function returns a go.Figure ready to be passed to st.plotly_chart().

Design principles:
- Consistent dark theme + brand colours across all charts
- Hover templates with rich contextual information
- Accessible colour choices (colourblind-friendly palettes)
- Responsive layout (autosize=True)
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

COLORS = cfg.COLORS
TEMPLATE = cfg.PLOTLY_TEMPLATE
CHART_COLORS = cfg.COLORS["chart"]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a '#RRGGBB' hex string to a valid 'rgba(r,g,b,a)' string."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _base_layout(title: str = "", height: int = 400) -> dict:
    """Return a standard dark-theme layout dict."""
    return dict(
        title=dict(text=title, font=dict(size=16, color=COLORS["text"]), x=0.01),
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface2"],
        font=dict(color=COLORS["text"], family="Inter, sans-serif"),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(
            bgcolor=COLORS["surface"],
            bordercolor=COLORS["border"],
            borderwidth=1,
        ),
        xaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
        yaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
    )


# ─────────────────────────────────────────────
# RATINGS CHARTS
# ─────────────────────────────────────────────

def rating_distribution_bar(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart of rating distribution (1–5 stars).

    Args:
        df: DataFrame with columns [rating, review_count, pct].
    """
    fig = go.Figure(
        go.Bar(
            x=df["review_count"],
            y=df["rating"].astype(str) + " ★",
            orientation="h",
            marker_color=[
                COLORS["negative"],
                "#FF9F43",
                COLORS["neutral"],
                "#A8E063",
                COLORS["positive"],
            ],
            text=df["pct"].apply(lambda p: f"{p:.1f}%"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Reviews: %{x:,}<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout("Rating Distribution", height=320))
    fig.update_yaxes(categoryorder="array", categoryarray=["1 ★", "2 ★", "3 ★", "4 ★", "5 ★"])
    return fig


def category_volume_bar(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """
    Horizontal bar chart: review volume per business category.

    Used on the Executive Dashboard in place of a review-volume-over-time
    chart, since this dataset has no usable review dates (review_date is
    relative text like "2 weeks ago", not a real timestamp).

    Args:
        df:    DataFrame with columns [category_name, review_count, avg_rating].
        top_n: Number of categories to display.
    """
    plot_df = df.sort_values("review_count", ascending=False).head(top_n).sort_values("review_count")
    fig = go.Figure(
        go.Bar(
            x=plot_df["review_count"],
            y=plot_df["category_name"],
            orientation="h",
            marker=dict(
                color=plot_df["avg_rating"],
                colorscale=[[0, COLORS["negative"]], [0.5, COLORS["neutral"]], [1, COLORS["positive"]]],
                cmin=1, cmax=5,
                colorbar=dict(title="Avg ★", thickness=12),
            ),
            text=plot_df["review_count"].apply(lambda c: f"{c:,}"),
            textposition="outside",
            customdata=plot_df["avg_rating"],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Reviews: %{x:,}<br>"
                "Avg Rating: %{customdata:.2f}★<extra></extra>"
            ),
        )
    )
    fig.update_layout(**_base_layout("Review Volume by Category", height=max(380, top_n * 24)))
    return fig


def avg_rating_by_category_bar(df: pd.DataFrame) -> go.Figure:
    """Bar chart: average rating per category."""
    df_sorted = df.sort_values("avg_rating", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df_sorted["avg_rating"],
            y=df_sorted["category_name"],
            orientation="h",
            marker_color=COLORS["primary"],
            text=df_sorted["avg_rating"].apply(lambda r: f"{r:.2f}★"),
            textposition="outside",
            customdata=df_sorted["review_count"],
            hovertemplate=(
                "<b>%{y}</b><br>Avg Rating: %{x:.2f}★<br>"
                "Reviews: %{customdata:,}<extra></extra>"
            ),
        )
    )
    fig.update_layout(**_base_layout("Average Rating by Category", height=max(350, len(df_sorted) * 28)))
    fig.update_xaxes(range=[0, 5.5])
    return fig


def top_businesses_chart(df: pd.DataFrame, title: str = "Top Rated Businesses") -> go.Figure:
    """Horizontal bar: top/bottom businesses."""
    df_sorted = df.sort_values("avg_rating", ascending=True)
    color = COLORS["positive"] if "Top" in title else COLORS["negative"]
    fig = go.Figure(
        go.Bar(
            x=df_sorted["avg_rating"],
            y=df_sorted["business_name"],
            orientation="h",
            marker_color=color,
            text=df_sorted["avg_rating"].apply(lambda r: f"{r:.2f}★"),
            textposition="outside",
            customdata=df_sorted["review_count"],
            hovertemplate="<b>%{y}</b><br>Rating: %{x:.2f}★<br>Reviews: %{customdata:,}<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout(title, height=max(350, len(df_sorted) * 30)))
    fig.update_xaxes(range=[0, 5.5])
    return fig


# ─────────────────────────────────────────────
# SENTIMENT CHARTS
# ─────────────────────────────────────────────

def sentiment_donut(positive_pct: float, neutral_pct: float, negative_pct: float) -> go.Figure:
    """Donut chart of sentiment distribution."""
    fig = go.Figure(
        go.Pie(
            labels=["Positive", "Neutral", "Negative"],
            values=[positive_pct, neutral_pct, negative_pct],
            hole=0.6,
            marker_colors=[COLORS["positive"], COLORS["neutral"], COLORS["negative"]],
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b>: %{value:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout("Sentiment Distribution", height=320))
    fig.update_layout(showlegend=True)
    return fig


def complaint_category_bar(df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: complaint category frequencies."""
    df_sorted = df.sort_values("count", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df_sorted["count"],
            y=df_sorted["category"],
            orientation="h",
            marker_color=COLORS["negative"],
            text=df_sorted["pct"].apply(lambda p: f"{p:.1f}%"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Mentions: %{x:,} (%{text})<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout("Complaint Categories", height=max(320, len(df_sorted) * 30)))
    return fig


def keyword_bar(df: pd.DataFrame, title: str = "Top Keywords", color: str = "") -> go.Figure:
    """Bar chart for TF-IDF keywords."""
    col = color or COLORS["primary"]
    df_sorted = df.head(15).sort_values("tfidf_score", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=df_sorted["tfidf_score"],
            y=df_sorted["keyword"],
            orientation="h",
            marker_color=col,
            hovertemplate="<b>%{y}</b><br>TF-IDF Score: %{x:.4f}<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout(title, height=380))
    return fig


# ─────────────────────────────────────────────
# CATEGORY OVERVIEW CHART
# ─────────────────────────────────────────────
# (This dataset has no city/lat/long columns and no parseable review dates,
# so the original time-trend and geographic-map charts were removed. This
# treemap — grouped by business category instead of city — replaces the
# old "City Performance Overview" chart on the Executive Dashboard.)

def category_performance_treemap(df: pd.DataFrame) -> go.Figure:
    """Treemap: categories sized by review count, coloured by avg rating."""
    fig = px.treemap(
        df,
        path=["category_name"],
        values="review_count",
        color="avg_rating",
        color_continuous_scale=["#FF6B6B", "#FFC857", "#00C896"],
        range_color=[1, 5],
        custom_data=["avg_rating", "positive_pct"],
        template=TEMPLATE,
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Reviews: %{value:,}<br>"
            "Avg Rating: %{customdata[0]:.2f}★<br>"
            "Positive: %{customdata[1]:.1f}%<extra></extra>"
        )
    )
    fig.update_layout(**_base_layout("Category Performance Overview", height=480))
    return fig


# ─────────────────────────────────────────────
# BUSINESS COMPARISON CHARTS
# ─────────────────────────────────────────────

def business_radar_comparison(
    biz_a: dict,
    biz_b: dict,
    name_a: str,
    name_b: str,
) -> go.Figure:
    """
    Radar chart comparing two businesses across 5 dimensions.

    Dimensions: Rating, Positive%, Review Volume (normalised), Engagement, Recency.
    """
    def safe(d: dict, key: str, default: float = 0.0) -> float:
        return float(d.get(key, default) or default)

    categories = ["Avg Rating", "Positive %", "Reviews (norm)", "Neg-Free %", "Engagement"]

    max_reviews = max(safe(biz_a, "review_count", 1), safe(biz_b, "review_count", 1), 1)

    vals_a = [
        safe(biz_a, "avg_rating") / 5 * 100,
        safe(biz_a, "positive_pct"),
        safe(biz_a, "review_count") / max_reviews * 100,
        100 - safe(biz_a, "negative_pct"),
        min(safe(biz_a, "review_count") / 50, 100),
    ]
    vals_b = [
        safe(biz_b, "avg_rating") / 5 * 100,
        safe(biz_b, "positive_pct"),
        safe(biz_b, "review_count") / max_reviews * 100,
        100 - safe(biz_b, "negative_pct"),
        min(safe(biz_b, "review_count") / 50, 100),
    ]

    fig = go.Figure()
    for vals, name, color in [
        (vals_a, name_a, COLORS["primary"]),
        (vals_b, name_b, COLORS["secondary"]),
    ]:
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=name,
            line=dict(color=color, width=2),
            fillcolor=_hex_to_rgba(color, 0.15),
        ))

    fig.update_layout(
        **_base_layout("Business Comparison", height=420),
        polar=dict(
            bgcolor=COLORS["surface2"],
            radialaxis=dict(visible=True, range=[0, 100], gridcolor=COLORS["border"]),
            angularaxis=dict(gridcolor=COLORS["border"]),
        ),
    )
    return fig


def business_sentiment_comparison_bar(
    profile_a: dict,
    profile_b: dict,
    name_a: str,
    name_b: str,
) -> go.Figure:
    """
    Grouped bar chart comparing sentiment breakdown (%) of two businesses.

    Replaces the original rating-trend-over-time comparison, which relied
    on review dates this dataset doesn't have (review_date is relative
    text like "2 weeks ago", not a real timestamp).
    """
    categories = ["Positive", "Neutral", "Negative"]
    vals_a = [
        profile_a.get("positive_pct", 0) or 0,
        profile_a.get("neutral_pct", 0) or 0,
        profile_a.get("negative_pct", 0) or 0,
    ]
    vals_b = [
        profile_b.get("positive_pct", 0) or 0,
        profile_b.get("neutral_pct", 0) or 0,
        profile_b.get("negative_pct", 0) or 0,
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=categories, y=vals_a, name=name_a,
        marker_color=COLORS["primary"],
        hovertemplate=f"<b>{name_a}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=categories, y=vals_b, name=name_b,
        marker_color=COLORS["secondary"],
        hovertemplate=f"<b>{name_b}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout("Sentiment Breakdown Comparison", height=400))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="% of reviews", range=[0, 100])
    return fig


# ─────────────────────────────────────────────
# KPI GAUGE
# ─────────────────────────────────────────────

def rating_gauge(value: float, title: str = "Avg Rating") -> go.Figure:
    """Gauge chart for a single rating value."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"color": COLORS["text"], "size": 14}},
        number={"suffix": "★", "font": {"color": COLORS["text"], "size": 28}},
        gauge={
            "axis": {"range": [0, 5], "tickcolor": COLORS["text"]},
            "bar": {"color": COLORS["primary"]},
            "bgcolor": COLORS["surface2"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, 2], "color": COLORS["negative"]},
                {"range": [2, 3.5], "color": COLORS["neutral"]},
                {"range": [3.5, 5], "color": COLORS["positive"]},
            ],
            "threshold": {
                "line": {"color": "white", "width": 2},
                "thickness": 0.75,
                "value": value,
            },
        },
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["surface"],
        font=dict(color=COLORS["text"]),
        height=220,
        margin=dict(l=20, r=20, t=40, b=10),
    )
    return fig
