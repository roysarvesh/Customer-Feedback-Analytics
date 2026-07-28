import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.analytics import get_monthly_review_volume, get_rating_trend_with_running_avg, get_monthly_sentiment_trend, get_review_growth_rate
from src.charts import monthly_review_volume_line, avg_rating_trend_line, sentiment_trend_area, review_growth_bar
from src.database import get_engine

def render():
    st.header("Time-Series Trends")
    engine = get_engine()

    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Average Rating Trend")
        trend_df = get_rating_trend_with_running_avg(engine)
        if not trend_df.empty:
            st.plotly_chart(avg_rating_trend_line(trend_df), use_container_width=True)

    with c2:
        st.subheader("Review Volume Growth")
        growth_df = get_review_growth_rate(engine)
        if not growth_df.empty:
            st.plotly_chart(review_growth_bar(growth_df), use_container_width=True)

    st.markdown("---")
    
    st.subheader("Sentiment Shift Over Time")
    sent_trend = get_monthly_sentiment_trend(engine)
    if not sent_trend.empty:
        st.plotly_chart(sentiment_trend_area(sent_trend), use_container_width=True)
