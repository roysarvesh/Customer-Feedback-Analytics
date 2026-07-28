import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.analytics import get_city_performance, _sql
from src.charts import city_scatter_map
from src.database import get_engine

def render():
    st.header("Geographic Analysis")
    engine = get_engine()

    st.subheader("Interactive Map")
    
    # Needs lat/long
    df = _sql("SELECT c.city_name, c.latitude, c.longitude, ROUND(AVG(r.rating),2) as avg_rating, COUNT(r.review_id) as review_count FROM reviews r JOIN businesses b ON r.business_id = b.business_id JOIN cities c ON c.city_id = b.city_id WHERE c.latitude IS NOT NULL GROUP BY c.city_name", engine)
    
    if df.empty or df['latitude'].isnull().all():
        st.info("Latitude/Longitude data not available for cities in this dataset.")
    else:
        fig = city_scatter_map(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Map generation failed.")
            
    st.markdown("---")
    st.subheader("City Performance Table")
    city_df = get_city_performance(engine)
    if not city_df.empty:
        st.dataframe(city_df, use_container_width=True)
