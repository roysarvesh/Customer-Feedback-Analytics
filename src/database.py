"""
src/database.py — SQLite database layer using SQLAlchemy.

Responsibilities:
- Define ORM models (Business, Review, City, Category, Keyword)
- Create schema / indexes
- Load cleaned DataFrame into SQLite
- Provide a session factory for query modules
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.utils import setup_logging, timer

logger = setup_logging(__name__)


# ─────────────────────────────────────────────
# BASE
# ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# ORM MODELS
# ─────────────────────────────────────────────

class City(Base):
    __tablename__ = "cities"

    city_id = Column(Integer, primary_key=True, autoincrement=True)
    city_name = Column(String(200), nullable=False, unique=True)
    state = Column(String(200), nullable=True)
    country = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    businesses = relationship("Business", back_populates="city", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<City id={self.city_id} name='{self.city_name}'>"


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(300), nullable=False, unique=True)

    businesses = relationship("Business", back_populates="category", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Category id={self.category_id} name='{self.category_name}'>"


class Business(Base):
    __tablename__ = "businesses"

    business_id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(500), nullable=True, index=True)  # e.g. gmap_id
    name = Column(String(500), nullable=False)
    city_id = Column(Integer, ForeignKey("cities.city_id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source = Column(String(100), nullable=False, default="google_maps")

    city = relationship("City", back_populates="businesses")
    category = relationship("Category", back_populates="businesses")
    reviews = relationship("Review", back_populates="business", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Business id={self.business_id} name='{self.name}'>"


class Review(Base):
    __tablename__ = "reviews"

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.business_id"), nullable=False, index=True)
    rating = Column(Float, nullable=False)
    review_text = Column(Text, nullable=True)
    review_date = Column(String(20), nullable=True, index=True)  # YYYY-MM-DD string
    review_year = Column(Integer, nullable=True)
    review_month = Column(Integer, nullable=True)
    source = Column(String(100), nullable=False, default="google_maps")
    # NLP columns — populated by sentiment.py
    sentiment_compound = Column(Float, nullable=True)
    sentiment_label = Column(String(20), nullable=True)  # Positive / Neutral / Negative
    sentiment_positive = Column(Float, nullable=True)
    sentiment_neutral = Column(Float, nullable=True)
    sentiment_negative = Column(Float, nullable=True)

    business = relationship("Business", back_populates="reviews")
    keywords = relationship("Keyword", back_populates="review", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Review id={self.review_id} rating={self.rating}>"


class Keyword(Base):
    __tablename__ = "keywords"

    keyword_id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, ForeignKey("reviews.review_id"), nullable=False, index=True)
    keyword = Column(String(200), nullable=False)
    complaint_category = Column(String(200), nullable=True)

    review = relationship("Review", back_populates="keywords")


# ─────────────────────────────────────────────
# ENGINE & SESSION
# ─────────────────────────────────────────────

def get_engine(db_url: Optional[str] = None, echo: bool = False):
    """
    Create and return a SQLAlchemy engine.

    Args:
        db_url: SQLAlchemy database URL. Defaults to config.DB_URL.
        echo:   If True, log all SQL statements.

    Returns:
        SQLAlchemy Engine.
    """
    url = db_url or cfg.DB_URL
    engine = create_engine(url, echo=echo, future=True)

    # Enable WAL mode for better concurrent read performance
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def get_session_factory(engine=None) -> sessionmaker:
    """
    Return a sessionmaker bound to the given (or default) engine.

    Args:
        engine: SQLAlchemy engine. Created from config if None.

    Returns:
        sessionmaker instance.
    """
    eng = engine or get_engine()
    return sessionmaker(bind=eng, autoflush=False, autocommit=False)


def get_session(engine=None) -> Session:
    """Return a new SQLAlchemy Session."""
    factory = get_session_factory(engine)
    return factory()


# ─────────────────────────────────────────────
# SCHEMA CREATION
# ─────────────────────────────────────────────

def create_schema(engine=None) -> None:
    """
    Create all tables and indexes. Safe to call multiple times (CREATE IF NOT EXISTS).

    Args:
        engine: SQLAlchemy engine.
    """
    eng = engine or get_engine()
    Base.metadata.create_all(eng)

    # Composite indexes for analytics queries
    with eng.connect() as conn:
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_reviews_date_rating ON reviews (review_date, rating)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_business_sentiment ON reviews (business_id, sentiment_label)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_year_month ON reviews (review_year, review_month)",
            "CREATE INDEX IF NOT EXISTS idx_businesses_city_category ON businesses (city_id, category_id)",
            "CREATE INDEX IF NOT EXISTS idx_keywords_category ON keywords (complaint_category)",
        ]
        for stmt in index_statements:
            conn.execute(text(stmt))
        conn.commit()

    logger.info("Schema created and indexes applied.")


# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────

def clear_reviews_and_keywords(engine=None) -> None:
    """
    Delete all rows from `reviews` and `keywords` (which references
    review_id via foreign key) before a fresh data load.

    Cities, Categories, and Businesses are safely upserted elsewhere (looked
    up by name before insert), but Reviews have no natural dedup key and
    were previously always freshly bulk-inserted with no cleanup step. That
    meant every re-run of `python src/database.py` silently *added* another
    ~200K rows on top of whatever was already there instead of replacing
    them — after a few runs the reviews table no longer matched the
    cleaned CSV row-for-row, which made write_sentiment_to_db()'s
    row-count safety check fail and skip writing sentiment scores entirely.

    Args:
        engine: SQLAlchemy engine.
    """
    eng = engine or get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM keywords"))
        conn.execute(text("DELETE FROM reviews"))
    logger.info("Cleared existing reviews and keywords before reload.")


@timer
def load_dataframe_to_db(
    df: pd.DataFrame,
    engine=None,
    source: str = "google_maps",
) -> None:
    """
    Load a cleaned DataFrame into the SQLite database.

    Strategy:
    - Upsert Cities from the city column.
    - Upsert Categories from the category column.
    - Upsert Businesses (deduplicated by name+city).
    - Clear existing Reviews/Keywords, then bulk-insert fresh Reviews.
      (Reviews are always a full reload, not an incremental upsert — see
      clear_reviews_and_keywords() for why this step is required.)

    Args:
        df:     Cleaned DataFrame (output of preprocessing.py).
        engine: SQLAlchemy engine.
        source: Platform source string (e.g. 'google_maps').
    """
    from src.utils import resolve_column_roles
    import config as cfg

    eng = engine or get_engine()
    create_schema(eng)
    clear_reviews_and_keywords(eng)

    platform_cfg = cfg.PLATFORM_SOURCES[cfg.ACTIVE_PLATFORM]["expected_columns"]
    roles = resolve_column_roles(df, platform_cfg)

    city_col = roles.get("city")
    cat_col = roles.get("category")
    name_col = roles.get("business_name")
    rating_col = roles.get("rating")
    text_col = roles.get("review_text")
    date_col = roles.get("date")
    lat_col = roles.get("latitude")
    lon_col = roles.get("longitude")
    ext_id_col = roles.get("business_id")

    logger.info("Loading %d rows into database...", len(df))

    with get_session(eng) as session:
        # --- Cities ---
        city_map: dict = {}  # city_name → city_id
        if city_col and city_col in df.columns:
            city_names = df[city_col].dropna().unique()
            for cname in city_names:
                existing = session.query(City).filter_by(city_name=str(cname)).first()
                if existing:
                    city_map[str(cname)] = existing.city_id
                else:
                    city = City(city_name=str(cname))
                    session.add(city)
                    session.flush()
                    city_map[str(cname)] = city.city_id
            logger.info("Loaded %d cities.", len(city_map))

        # --- Categories ---
        cat_map: dict = {}  # cat_name → category_id
        if cat_col and cat_col in df.columns:
            cat_names = df[cat_col].dropna().unique()
            for cname in cat_names:
                existing = session.query(Category).filter_by(category_name=str(cname)).first()
                if existing:
                    cat_map[str(cname)] = existing.category_id
                else:
                    cat = Category(category_name=str(cname))
                    session.add(cat)
                    session.flush()
                    cat_map[str(cname)] = cat.category_id
            logger.info("Loaded %d categories.", len(cat_map))

        # --- Businesses ---
        biz_map: dict = {}  # (name, city_id) → business_id
        if name_col and name_col in df.columns:
            biz_df = df[[name_col] + (
                [city_col] if city_col and city_col in df.columns else []
            ) + (
                [cat_col] if cat_col and cat_col in df.columns else []
            ) + (
                [lat_col] if lat_col and lat_col in df.columns else []
            ) + (
                [lon_col] if lon_col and lon_col in df.columns else []
            ) + (
                [ext_id_col] if ext_id_col and ext_id_col in df.columns else []
            )].drop_duplicates(subset=[name_col] + (
                [city_col] if city_col and city_col in df.columns else []
            ))

            for _, row in biz_df.iterrows():
                bname = str(row.get(name_col, "Unknown"))
                cid = city_map.get(str(row.get(city_col, ""))) if city_col else None
                catid = cat_map.get(str(row.get(cat_col, ""))) if cat_col else None
                key = (bname, cid)
                existing = session.query(Business).filter_by(
                    name=bname, city_id=cid
                ).first()
                if existing:
                    biz_map[key] = existing.business_id
                else:
                    biz = Business(
                        name=bname,
                        city_id=cid,
                        category_id=catid,
                        latitude=float(row[lat_col]) if lat_col and lat_col in row and pd.notna(row.get(lat_col)) else None,
                        longitude=float(row[lon_col]) if lon_col and lon_col in row and pd.notna(row.get(lon_col)) else None,
                        external_id=str(row[ext_id_col]) if ext_id_col and ext_id_col in row else None,
                        source=source,
                    )
                    session.add(biz)
                    session.flush()
                    biz_map[key] = biz.business_id
            logger.info("Loaded %d businesses.", len(biz_map))

        # --- Reviews (bulk insert) ---
        reviews_to_insert = []
        for _, row in df.iterrows():
            bname = str(row.get(name_col, "Unknown")) if name_col else "Unknown"
            cid = city_map.get(str(row.get(city_col, ""))) if city_col else None
            biz_id = biz_map.get((bname, cid))

            date_val = str(row.get(date_col, "")) if date_col and pd.notna(row.get(date_col, None)) else None
            year = None
            month = None
            if date_val and len(date_val) >= 7:
                try:
                    parts = date_val.split("-")
                    year = int(parts[0])
                    month = int(parts[1])
                except (ValueError, IndexError):
                    pass

            reviews_to_insert.append({
                "business_id": biz_id,
                "rating": float(row[rating_col]) if rating_col else None,
                "review_text": str(row[text_col]) if text_col else None,
                "review_date": date_val,
                "review_year": year,
                "review_month": month,
                "source": source,
            })

        # Batch insert
        BATCH = 5000
        for i in range(0, len(reviews_to_insert), BATCH):
            session.bulk_insert_mappings(Review, reviews_to_insert[i:i + BATCH])
            session.flush()
            logger.debug("Inserted review batch %d/%d", i // BATCH + 1, (len(reviews_to_insert) // BATCH) + 1)

        session.commit()
        logger.info("All %d reviews committed to database.", len(reviews_to_insert))


if __name__ == "__main__":
    from src.utils import load_csv
    df = load_csv(cfg.CLEANED_CSV_PATH)
    load_dataframe_to_db(df)
