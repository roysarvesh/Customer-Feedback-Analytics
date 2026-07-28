"""
Multi-Platform Customer Feedback Analytics Platform - Main Streamlit Entrypoint
"""

import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import config as cfg

# NOTE: Geographic Analysis and Time-Series Trends were removed. This dataset
# (public_dataset.csv) has no city/latitude/longitude columns and its
# review_date values are relative text (e.g. "2 hafta önce") rather than
# real dates, so neither page could ever show real data.
from dashboard import executive, ratings, feedback, comparison

st.set_page_config(
    page_title=cfg.APP_TITLE,
    page_icon=cfg.APP_ICON,
    layout=cfg.APP_LAYOUT,
    initial_sidebar_state="expanded",
)

C = cfg.COLORS

# ── Global theme ─────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    /* App background */
    .stApp {{
        background-color: {C['background']};
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {C['surface']};
        border-right: 1px solid {C['border']};
    }}
    [data-testid="stSidebar"] .block-container {{
        padding-top: 1.5rem;
    }}

    /* Sidebar nav (radio) styled as a clean vertical menu */
    [data-testid="stSidebar"] div[role="radiogroup"] label {{
        padding: 0.5rem 0.75rem;
        border-radius: 8px;
        margin-bottom: 2px;
        transition: background-color 0.15s ease;
    }}
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background-color: {C['surface2']};
    }}

    /* Headers */
    h1, h2, h3 {{
        font-family: 'Inter', sans-serif;
        letter-spacing: -0.01em;
    }}
    h1 {{
        font-weight: 700;
        border-bottom: 2px solid {C['primary']};
        padding-bottom: 0.5rem;
        margin-bottom: 1.5rem !important;
    }}
    h3 {{
        color: {C['text_muted']};
        font-size: 1.05rem !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        margin-top: 0.5rem;
    }}

    /* Metric cards */
    div[data-testid="stMetric"] {{
        background-color: {C['surface']};
        padding: 18px 20px;
        border-radius: 12px;
        border: 1px solid {C['border']};
        box-shadow: 0 1px 3px rgba(0,0,0,0.25);
    }}
    div[data-testid="stMetricLabel"] {{
        color: {C['text_muted']};
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}
    div[data-testid="stMetricValue"] {{
        color: {C['text']};
        font-weight: 700;
    }}

    /* Chart / content containers */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {C['surface']};
        border-radius: 12px;
        border: 1px solid {C['border']};
    }}

    /* Dataframes and selects */
    div[data-testid="stDataFrame"] {{
        border-radius: 8px;
        overflow: hidden;
    }}

    /* Divider */
    hr {{
        border-color: {C['border']};
        margin: 1.75rem 0;
    }}

    /* Sidebar info/footer box */
    [data-testid="stSidebar"] .stAlert {{
        background-color: {C['surface2']};
        border: 1px solid {C['border']};
        border-radius: 10px;
    }}

    /* Hide default Streamlit chrome for a cleaner, more "product" feel */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────
st.sidebar.markdown(
    f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem;">
        <span style="font-size:1.6rem;">{cfg.APP_ICON}</span>
        <div>
            <div style="font-weight:700;font-size:1.05rem;color:{C['text']};line-height:1.2;">
                Feedback Analytics
            </div>
            <div style="font-size:0.75rem;color:{C['text_muted']};">
                Customer Insights Platform
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

pages = {
    "Executive Dashboard": executive.render,
    "Ratings Analytics": ratings.render,
    "Customer Feedback": feedback.render,
    "Business Comparison": comparison.render,
}

selection = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Powered by **Streamlit** & **Plotly**  \n"
    "Modular multi-platform architecture · Google Maps reviews dataset"
)

# Render selected page
pages[selection]()
