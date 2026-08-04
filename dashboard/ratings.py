import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.analytics import get_rating_distribution, get_avg_rating_by_category, get_top_businesses, get_bottom_businesses
from src.charts import rating_distribution_bar, avg_rating_by_category_bar, top_businesses_chart
from src.database import get_engine


def render():
    st.header("Ratings Analytics")
    engine = get_engine()

    # NOTE: the original "Average Rating by City" panel was removed — this
    # dataset has no city column, so it could never show data. The overall
    # rating distribution is shown alongside category ratings instead.
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Overall Rating Distribution")
        dist_df = get_rating_distribution(engine)
        if not dist_df.empty:
            st.plotly_chart(rating_distribution_bar(dist_df), width='stretch')
        else:
            st.info("No rating data available yet.")

    with c2:
        st.subheader("Average Rating by Category")
        cat_df = get_avg_rating_by_category(engine)
        if not cat_df.empty:
            st.plotly_chart(avg_rating_by_category_bar(cat_df), width='stretch')
        else:
            st.info("No category data available yet.")

    st.markdown("---")
    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Top Performers")
        top_df = get_top_businesses(engine)
        if not top_df.empty:
            st.plotly_chart(top_businesses_chart(top_df, "Highest Rated"), width='stretch')
        else:
            st.info("Not enough reviewed businesses yet.")

    with c4:
        st.subheader("Needs Attention")
        bot_df = get_bottom_businesses(engine)
        if not bot_df.empty:
            st.plotly_chart(top_businesses_chart(bot_df, "Lowest Rated"), width='stretch')
        else:
            st.info("Not enough reviewed businesses yet.")
