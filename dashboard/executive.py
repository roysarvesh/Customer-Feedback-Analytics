import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.analytics import (
    get_kpi_summary,
    get_businesses_needing_attention,
    get_category_performance,
    get_rating_distribution,
    get_national_avg_rating,
    get_avg_rating_by_category,
    _sql,
)
from src.recommendation_engine import generate_insights, generate_recommendations
from src.charts import (
    rating_gauge,
    rating_distribution_bar,
    category_performance_treemap,
    category_volume_bar,
)
from src.database import get_engine


def render():
    st.header("Executive Dashboard")
    engine = get_engine()

    kpis = get_kpi_summary(engine)
    if not kpis or not kpis.get("total_reviews"):
        st.warning("No data available. Please run the data pipeline first "
                    "(preprocessing.py → database.py → sentiment.py → keyword_extraction.py).")
        return

    # ── Top KPIs ──────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Reviews", f"{kpis.get('total_reviews', 0):,}")
    col2.metric("Avg Rating", f"{kpis.get('avg_rating', 0):.2f}★")
    col3.metric("Positive Sentiment", f"{kpis.get('positive_pct', 0) or 0}%")
    col4.metric("Negative Sentiment", f"{kpis.get('negative_pct', 0) or 0}%")
    col5.metric("Total Businesses", f"{kpis.get('total_businesses', 0):,}")

    st.markdown("---")

    # ── Charts row ────────────────────────────────────────────────────
    # NOTE: the original "Review Volume Trend" line chart was removed here.
    # It grouped reviews by month, but review_date in this dataset is
    # relative text (e.g. "2 weeks ago"), not a real timestamp, so every
    # row failed date parsing and the chart was always empty. Review
    # volume by category is shown instead, since category data is real.
    cat_df = get_avg_rating_by_category(engine)

    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("Review Volume by Category")
        if not cat_df.empty:
            st.plotly_chart(category_volume_bar(cat_df), use_container_width=True)
        else:
            st.info("No category data available yet. Run the data pipeline first.")

    with c2:
        st.subheader("Overall Rating")
        st.plotly_chart(rating_gauge(kpis.get("avg_rating", 0)), use_container_width=True)
        dist_df = get_rating_distribution(engine)
        if not dist_df.empty:
            st.plotly_chart(rating_distribution_bar(dist_df), use_container_width=True)

    st.markdown("---")

    # ── Insights Engine ───────────────────────────────────────────────
    st.subheader("AI Business Insights")

    with st.spinner("Generating insights..."):
        bottom_df = get_businesses_needing_attention(engine)
        category_perf_df = get_category_performance(engine)
        nat_avg = get_national_avg_rating(engine)

        comp_df = _sql(
            "SELECT complaint_category as category, COUNT(*) as count "
            "FROM keywords GROUP BY complaint_category ORDER BY count DESC LIMIT 1",
            engine,
        )
        if not comp_df.empty:
            comp_df["pct"] = comp_df["count"] / max(comp_df["count"].sum(), 1) * 100

        # This dataset has no city or usable review-date data, so those two
        # insight generators are fed empty frames — they safely no-op.
        insights = generate_insights(
            kpis, bottom_df, pd.DataFrame(), nat_avg, comp_df, cat_df, pd.DataFrame()
        )
        recs = generate_recommendations(insights)

    if insights:
        for ins in insights:
            if ins["type"] == "critical":
                st.error(f"**{ins['title']}**\n\n{ins['detail']}")
            elif ins["type"] == "warning":
                st.warning(f"**{ins['title']}**\n\n{ins['detail']}")
            elif ins["type"] == "success":
                st.success(f"**{ins['title']}**\n\n{ins['detail']}")
            else:
                st.info(f"**{ins['title']}**\n\n{ins['detail']}")

        with st.expander("View Actionable Recommendations"):
            for r in recs:
                st.write(f"- {r}")
    else:
        st.info("No critical insights at this time.")

    st.markdown("---")
    st.subheader("Category Overview")
    if not category_perf_df.empty:
        st.plotly_chart(category_performance_treemap(category_perf_df), use_container_width=True)
    else:
        st.info("Not enough data to build a category overview yet.")
