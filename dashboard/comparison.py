import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.analytics import get_business_profile, get_business_names
from src.charts import business_radar_comparison, business_sentiment_comparison_bar
from src.database import get_engine


def render():
    st.header("Business Comparison")
    engine = get_engine()

    names = get_business_names(engine)
    if not names:
        st.warning("No businesses found.")
        return

    c1, c2 = st.columns(2)
    with c1:
        biz1 = st.selectbox("Select Business A", options=names, index=0)
    with c2:
        biz2 = st.selectbox("Select Business B", options=names, index=min(1, len(names) - 1))

    if biz1 and biz2:
        prof1 = get_business_profile(biz1, engine)
        prof2 = get_business_profile(biz2, engine)

        if not prof1 or not prof2:
            st.info("Not enough review data for one of these businesses yet.")
            return

        st.markdown("---")

        # KPI Comparison
        k1, k2, k3 = st.columns(3)

        diff_rating = prof1.get("avg_rating", 0) - prof2.get("avg_rating", 0)
        k1.metric("Rating Gap", f"{diff_rating:+.2f}★")
        k2.metric(biz1, f"{prof1.get('avg_rating', 0):.2f}★", f"{prof1.get('review_count', 0)} reviews", delta_color="off")
        k3.metric(biz2, f"{prof2.get('avg_rating', 0):.2f}★", f"{prof2.get('review_count', 0)} reviews", delta_color="off")

        st.markdown("---")

        # NOTE: the original "Trend Comparison" chart was removed — it
        # relied on review dates this dataset doesn't have. Sentiment
        # breakdown comparison is shown instead, using data that's real.
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Performance Radar")
            st.plotly_chart(business_radar_comparison(prof1, prof2, biz1, biz2), width='stretch')

        with c4:
            st.subheader("Sentiment Breakdown")
            st.plotly_chart(business_sentiment_comparison_bar(prof1, prof2, biz1, biz2), width='stretch')
