import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.analytics import _sql, get_sample_reviews
from src.charts import complaint_category_bar, sentiment_donut
from src.database import get_engine
import config as cfg


def render():
    st.header("Customer Feedback & NLP")
    engine = get_engine()

    c1, c2 = st.columns([1, 2])

    with c1:
        st.subheader("Sentiment Summary")
        sent_df = _sql(
            "SELECT sentiment_label, COUNT(*) as count FROM reviews "
            "WHERE sentiment_label IS NOT NULL GROUP BY sentiment_label",
            engine,
        )
        if not sent_df.empty:
            total = sent_df["count"].sum()
            pos = sent_df[sent_df["sentiment_label"] == "Positive"]["count"].sum() / total * 100
            neu = sent_df[sent_df["sentiment_label"] == "Neutral"]["count"].sum() / total * 100
            neg = sent_df[sent_df["sentiment_label"] == "Negative"]["count"].sum() / total * 100
            st.plotly_chart(sentiment_donut(pos, neu, neg), use_container_width=True)
        else:
            st.info("No sentiment data yet. Run src/sentiment.py to score reviews.")

    with c2:
        st.subheader("Top Complaints (Negative Reviews)")
        comp_df = _sql("""
            SELECT complaint_category as category, COUNT(*) as count
            FROM keywords
            WHERE complaint_category IS NOT NULL
            GROUP BY complaint_category
            ORDER BY count DESC
        """, engine)

        if not comp_df.empty:
            comp_df["pct"] = comp_df["count"] / comp_df["count"].sum() * 100
            st.plotly_chart(complaint_category_bar(comp_df), use_container_width=True)
        else:
            st.info("No complaint data yet. Run src/keyword_extraction.py after sentiment scoring.")

    st.markdown("---")
    st.subheader("Sample Reviews")

    f_sent = st.selectbox("Filter by Sentiment", ["All", "Positive", "Negative", "Neutral"])

    samples = get_sample_reviews(engine, sentiment=None if f_sent == "All" else f_sent, limit=10)

    if not samples.empty:
        for _, row in samples.iterrows():
            sentiment = (row["sentiment_label"] or "neutral").lower()
            with st.chat_message(sentiment):
                st.markdown(f"**{row['business_name']}** — {row['rating']}★")
                st.write(row["review_text"] or "_(no review text)_")
                if row["review_date"]:
                    st.caption(f"Date: {row['review_date']}")
    else:
        st.info("No reviews match this filter yet.")
