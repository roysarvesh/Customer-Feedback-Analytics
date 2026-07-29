"""
config.py — Central configuration for the Multi-Platform Customer Feedback Analytics Platform.

All paths are derived from ROOT_DIR so the project is fully portable.
Modify PLATFORM_SOURCES to add new review sources without touching other modules.
"""

from pathlib import Path
from typing import Dict, List, Any

# ─────────────────────────────────────────────
# ROOT & DIRECTORY STRUCTURE
# ─────────────────────────────────────────────
import os
ROOT_DIR: Path = Path(__file__).parent.resolve()
HOME_DIR: Path = Path(os.path.expanduser("~"))

# Writable directories (Database, Processed) are placed in the user's home directory 
# to bypass Windows Controlled Folder Access which blocks Python from writing in Documents.
APP_DATA_DIR: Path = HOME_DIR / ".customer_feedback_analytics"
PROCESSED_DIR: Path = APP_DATA_DIR / "processed"
DATABASE_DIR: Path = APP_DATA_DIR / "database"

# Read-only or project-local directories
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = ROOT_DIR
ASSETS_DIR: Path = ROOT_DIR / "assets"
SQL_DIR: Path = ROOT_DIR / "sql"
SRC_DIR: Path = ROOT_DIR / "src"
DASHBOARD_DIR: Path = ROOT_DIR / "dashboard"
NOTEBOOKS_DIR: Path = ROOT_DIR / "notebooks"

# Ensure critical directories exist at import time
for _dir in [RAW_DIR, PROCESSED_DIR, DATABASE_DIR, ASSETS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
DB_PATH: Path = DATABASE_DIR / "feedback_analytics.db"
DB_URL: str = f"sqlite:///{DB_PATH}"
DB_ECHO: bool = False  # Set True to see SQLAlchemy SQL logs

# ─────────────────────────────────────────────
# DATA FILES
# ─────────────────────────────────────────────
# The profiler auto-detects CSV files in RAW_DIR.
# Primary expected filename (Kaggle download):
RAW_CSV_FILENAME: str = "public_dataset.csv"
RAW_CSV_PATH: Path = RAW_DIR / RAW_CSV_FILENAME

CLEANED_CSV_PATH: Path = PROCESSED_DIR / "reviews_cleaned.csv"
CLEANING_LOG_PATH: Path = PROCESSED_DIR / "cleaning_log.json"
PROFILING_REPORT_PATH: Path = PROCESSED_DIR / "profiling_report.md"

# ─────────────────────────────────────────────
# PLATFORM / SOURCE REGISTRY
# Each entry defines how to map raw columns for that source.
# Add a new dict here to support a new platform — no other changes needed.
# ─────────────────────────────────────────────
PLATFORM_SOURCES: Dict[str, Dict[str, Any]] = {
    "google_maps": {
        "display_name": "Google Maps",
        "icon": "🗺️",
        "expected_columns": {
            "rating": ["rating", "stars", "score", "note", "review_rating"],
            "review_text": ["text", "review", "review_text", "content", "comment"],
            "business_name": ["name", "business_name", "place_name", "gmap_name"],
            "city": ["city", "City", "location", "city_name"],
            "category": ["category", "categories", "type", "business_type", "place_category"],
            "date": ["time", "date", "review_date", "created_at", "timestamp"],
            "latitude": ["latitude", "lat"],
            "longitude": ["longitude", "lng", "lon"],
            "business_id": ["gmap_id", "place_id", "business_id", "id"],
            "state": ["state", "State", "province"],
        },
    },
    "tripadvisor": {
        "display_name": "TripAdvisor",
        "icon": "✈️",
        "expected_columns": {
            "rating": ["rating", "bubble_rating"],
            "review_text": ["review_body", "text", "content"],
            "business_name": ["hotel_name", "restaurant_name", "attraction_name"],
            "city": ["location_city"],
            "category": ["category"],
            "date": ["review_date", "date_of_stay"],
            "latitude": ["latitude"],
            "longitude": ["longitude"],
            "business_id": ["trip_id", "location_id"],
            "state": ["location_state"],
        },
    },
    "yelp": {
        "display_name": "Yelp",
        "icon": "⭐",
        "expected_columns": {
            "rating": ["stars"],
            "review_text": ["text"],
            "business_name": ["name"],
            "city": ["city"],
            "category": ["categories"],
            "date": ["date"],
            "latitude": ["latitude"],
            "longitude": ["longitude"],
            "business_id": ["business_id"],
            "state": ["state"],
        },
    },
}

# Active platform for this run
ACTIVE_PLATFORM: str = "google_maps"

# ─────────────────────────────────────────────
# RATING CONFIGURATION
# ─────────────────────────────────────────────
RATING_MIN: float = 1.0
RATING_MAX: float = 5.0
RATING_ALERT_THRESHOLD: float = 3.5   # Businesses below this need attention
RATING_GOOD_THRESHOLD: float = 4.0   # Businesses above this are performing well

# ─────────────────────────────────────────────
# NLP / SENTIMENT CONFIGURATION
# ─────────────────────────────────────────────
VADER_POSITIVE_THRESHOLD: float = 0.05   # compound score >= this → Positive
VADER_NEGATIVE_THRESHOLD: float = -0.05  # compound score <= this → Negative
# Between thresholds → Neutral

# Complaint categories with associated keyword signals.
# NOTE: this dataset's reviews are primarily in Turkish, so Turkish keyword
# equivalents are included alongside the English ones for each category —
# English-only matching would find almost nothing in this dataset.
COMPLAINT_CATEGORIES: Dict[str, List[str]] = {
    "Waiting Time": [
        "wait", "waiting", "slow", "long queue", "queue", "delay",
        "took forever", "hours", "time", "late", "slow service",
        "bekle", "bekledik", "bekliyoruz", "bekleme", "sıra", "geç kaldı",
        "yavaş", "uzun süre", "gecikme",
    ],
    "Price / Value": [
        "expensive", "overpriced", "price", "costly", "value",
        "cheap", "affordable", "worth", "pricey", "budget",
        "pahalı", "fiyat", "fiyatlar", "ucuz", "değer", "uygun fiyat",
    ],
    "Food Quality": [
        "food", "taste", "flavour", "flavor", "stale", "cold",
        "undercooked", "overcooked", "bland", "delicious", "fresh",
        "quality", "portion", "menu",
        "yemek", "lezzet", "lezzetli", "taze", "soğuk", "kalite",
        "menü", "porsiyon", "tat",
    ],
    "Service": [
        "service", "staff", "rude", "unfriendly", "helpful",
        "attentive", "ignoring", "ignored", "server", "waiter",
        "cashier", "employee", "attitude",
        "hizmet", "personel", "kaba", "ilgisiz", "yardımsever",
        "garson", "kasiyer", "çalışan", "tutum", "güler yüzlü",
    ],
    "Cleanliness": [
        "dirty", "clean", "hygiene", "hygienic", "filthy",
        "unclean", "messy", "tidy", "smell", "odour", "odor",
        "kirli", "temiz", "hijyen", "pis", "koku", "temizlik",
    ],
    "Parking": [
        "parking", "park", "parked", "no parking", "valet",
        "parking lot", "parking space",
        "otopark", "park yeri",
    ],
    "Ambience": [
        "ambience", "ambiance", "atmosphere", "noise", "noisy",
        "loud", "music", "decor", "cozy", "comfortable", "crowded",
        "busy", "vibe", "setting",
        "atmosfer", "gürültü", "gürültülü", "müzik", "dekor",
        "rahat", "kalabalık", "ortam",
    ],
    "Location / Access": [
        "location", "far", "accessible", "accessible", "directions",
        "map", "navigation", "distance", "inconvenient", "hard to find",
        "konum", "uzak", "ulaşım", "yol tarifi", "mesafe", "erişim",
    ],
}

POSITIVE_THEME_KEYWORDS: List[str] = [
    "great", "amazing", "excellent", "fantastic", "wonderful", "love",
    "best", "friendly", "recommend", "perfect", "outstanding", "superb",
    "delicious", "fresh", "good", "nice", "clean", "helpful", "fast",
    "efficient", "cozy", "beautiful", "stunning", "awesome", "brilliant",
]

NEGATIVE_THEME_KEYWORDS: List[str] = [
    "bad", "terrible", "awful", "horrible", "worst", "poor",
    "disappointing", "disgusting", "rude", "dirty", "slow", "overpriced",
    "cold", "stale", "unfriendly", "ignored", "never", "avoid",
    "waste", "pathetic", "mediocre", "unacceptable", "filthy",
]

# WordCloud config
WORDCLOUD_MAX_WORDS: int = 150
WORDCLOUD_BACKGROUND: str = "white"
WORDCLOUD_POSITIVE_COLORMAP: str = "Greens"
WORDCLOUD_NEGATIVE_COLORMAP: str = "Reds"

# Min reviews required for a business to appear in analytics
MIN_REVIEW_COUNT: int = 5

# ─────────────────────────────────────────────
# STREAMLIT / UI CONFIGURATION
# ─────────────────────────────────────────────
APP_TITLE: str = "Customer Feedback Analytics Platform"
APP_ICON: str = "📊"
APP_LAYOUT: str = "wide"

# Brand colour palette (dark-theme, Plotly-compatible)
COLORS = {
    "primary": "#6C63FF",       # Purple
    "secondary": "#00D4AA",     # Teal
    "positive": "#00C896",      # Green
    "negative": "#FF6B6B",      # Red-coral
    "neutral": "#FFC857",       # Amber
    "background": "#0E1117",    # Dark bg
    "surface": "#1A1D2E",       # Card bg
    "surface2": "#252840",      # Elevated card bg
    "text": "#EAEAEA",          # Primary text
    "text_muted": "#9CA3AF",    # Muted text
    "border": "#2D3150",        # Border
    "chart": [
        "#6C63FF", "#00D4AA", "#FFC857", "#FF6B6B",
        "#4CC9F0", "#F72585", "#7209B7", "#3A0CA3",
    ],
}

PLOTLY_TEMPLATE: str = "plotly_dark"

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ─────────────────────────────────────────────
# SAMPLING (for large datasets)
# Set SAMPLE_SIZE = None to process all rows.
# ─────────────────────────────────────────────
SAMPLE_SIZE: int | None = 200_000  # Use None in production after first test run

# ─────────────────────────────────────────────
# BATCH PROCESSING (NLP)
# ─────────────────────────────────────────────
NLP_BATCH_SIZE: int = 5_000  # Rows per VADER batch to avoid memory spikes
