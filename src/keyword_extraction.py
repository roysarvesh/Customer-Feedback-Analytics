"""
src/keyword_extraction.py — Complaint category detection and keyword extraction.

Methodology:
- Rule-based keyword matching against COMPLAINT_CATEGORIES in config.py
- TF-IDF top-N keyword extraction per business / overall
- Returns structured DataFrames for dashboard consumption
"""

import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.utils import setup_logging, timer

logger = setup_logging(__name__)


# ─────────────────────────────────────────────
# COMPLAINT CATEGORY DETECTION
# ─────────────────────────────────────────────

def detect_complaint_categories(
    text: str,
    categories: Optional[Dict[str, List[str]]] = None,
) -> List[str]:
    """
    Identify which complaint categories appear in a review text.

    Uses simple keyword-matching with word boundaries.

    Args:
        text:       Review text string.
        categories: Category → keywords map. Defaults to config.COMPLAINT_CATEGORIES.

    Returns:
        List of matched category names.
    """
    if not isinstance(text, str) or text.strip() == "":
        return []

    cats = categories or cfg.COMPLAINT_CATEGORIES
    lower_text = text.lower()
    matched = []

    for category, keywords in cats.items():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern, lower_text):
                matched.append(category)
                break  # One match per category is sufficient

    return matched


@timer
def score_complaint_categories(
    df: pd.DataFrame,
    text_col: str,
    sentiment_col: Optional[str] = "sentiment_label",
) -> pd.DataFrame:
    """
    Apply complaint category detection to every row and return category frequencies.

    Args:
        df:            DataFrame with review text.
        text_col:      Column containing review text.
        sentiment_col: Column containing sentiment label (to restrict to Negative).

    Returns:
        DataFrame with columns: [category, count, pct]
        sorted by count descending.
    """
    # Focus complaint detection on negative reviews if column available
    if sentiment_col and sentiment_col in df.columns:
        analysis_df = df[df[sentiment_col] == "Negative"].copy()
        logger.info(
            "Complaint analysis on %d Negative reviews (of %d total).",
            len(analysis_df), len(df),
        )
    else:
        analysis_df = df.copy()

    category_counts: Counter = Counter()
    for text in analysis_df[text_col].dropna():
        matched = detect_complaint_categories(str(text))
        category_counts.update(matched)

    total = sum(category_counts.values()) or 1
    results = [
        {
            "category": cat,
            "count": cnt,
            "pct": round(cnt / total * 100, 2),
        }
        for cat, cnt in category_counts.most_common()
    ]

    return pd.DataFrame(results)


def tag_review_categories(
    df: pd.DataFrame,
    text_col: str,
) -> pd.DataFrame:
    """
    Add a 'complaint_categories' list column to the DataFrame.

    Args:
        df:       Review DataFrame.
        text_col: Review text column name.

    Returns:
        DataFrame with new 'complaint_categories' column.
    """
    df = df.copy()
    df["complaint_categories"] = df[text_col].apply(
        lambda t: detect_complaint_categories(str(t))
    )
    return df


# ─────────────────────────────────────────────
# TF-IDF KEYWORD EXTRACTION
# ─────────────────────────────────────────────

def extract_tfidf_keywords(
    texts: pd.Series,
    top_n: int = 20,
    max_features: int = 5000,
    ngram_range: Tuple[int, int] = (1, 2),
) -> pd.DataFrame:
    """
    Extract top-N keywords from a collection of texts using TF-IDF.

    Args:
        texts:        Series of text strings.
        top_n:        Number of top keywords to return.
        max_features: Maximum vocabulary size for TfidfVectorizer.
        ngram_range:  N-gram range (e.g. (1, 2) for unigrams + bigrams).

    Returns:
        DataFrame with columns: [keyword, tfidf_score].
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from src.sentiment import get_stopwords

    clean_texts = texts.dropna().astype(str).tolist()
    if len(clean_texts) < 2:
        logger.warning("Not enough texts for TF-IDF extraction.")
        return pd.DataFrame(columns=["keyword", "tfidf_score"])

    stops = list(get_stopwords())
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        stop_words=stops,
        ngram_range=ngram_range,
        min_df=2,
    )
    tfidf_matrix = vectorizer.fit_transform(clean_texts)
    feature_names = vectorizer.get_feature_names_out()

    # Mean TF-IDF score across all documents
    mean_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
    top_indices = mean_scores.argsort()[::-1][:top_n]

    results = [
        {"keyword": feature_names[i], "tfidf_score": round(float(mean_scores[i]), 6)}
        for i in top_indices
    ]
    return pd.DataFrame(results)


def extract_positive_negative_themes(
    df: pd.DataFrame,
    text_col: str,
    sentiment_col: str = "sentiment_label",
    top_n: int = 20,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extract top keywords separately for Positive and Negative reviews.

    Args:
        df:            DataFrame with review text and sentiment labels.
        text_col:      Review text column name.
        sentiment_col: Sentiment label column name.
        top_n:         Top N keywords to extract per sentiment.

    Returns:
        Tuple of (positive_keywords_df, negative_keywords_df).
    """
    pos_texts = df.loc[df[sentiment_col] == "Positive", text_col]
    neg_texts = df.loc[df[sentiment_col] == "Negative", text_col]

    logger.info(
        "Extracting themes: %d positive reviews, %d negative reviews.",
        len(pos_texts), len(neg_texts),
    )

    pos_kw = extract_tfidf_keywords(pos_texts, top_n=top_n)
    neg_kw = extract_tfidf_keywords(neg_texts, top_n=top_n)

    pos_kw["sentiment"] = "Positive"
    neg_kw["sentiment"] = "Negative"

    return pos_kw, neg_kw


# ─────────────────────────────────────────────
# BUSINESS-LEVEL COMPLAINT ANALYSIS
# ─────────────────────────────────────────────

def business_complaint_profile(
    df: pd.DataFrame,
    text_col: str,
    business_col: str,
    sentiment_col: Optional[str] = "sentiment_label",
    top_n_businesses: int = 20,
) -> pd.DataFrame:
    """
    For each business, compute which complaint categories appear most often.

    Args:
        df:                 Full reviews DataFrame.
        text_col:           Review text column.
        business_col:       Business name column.
        sentiment_col:      Sentiment label column (filter to Negative).
        top_n_businesses:   Number of most-reviewed businesses to analyse.

    Returns:
        DataFrame with columns: [business, category, count]
    """
    if sentiment_col and sentiment_col in df.columns:
        analysis_df = df[df[sentiment_col] == "Negative"].copy()
    else:
        analysis_df = df.copy()

    top_businesses = (
        analysis_df[business_col]
        .value_counts()
        .head(top_n_businesses)
        .index.tolist()
    )

    rows = []
    for biz in top_businesses:
        biz_texts = analysis_df.loc[analysis_df[business_col] == biz, text_col]
        cat_counts: Counter = Counter()
        for text in biz_texts.dropna():
            matched = detect_complaint_categories(str(text))
            cat_counts.update(matched)

        for cat, cnt in cat_counts.items():
            rows.append({"business": biz, "category": cat, "count": cnt})

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# PERSIST TO DATABASE
# ─────────────────────────────────────────────

@timer
def write_keywords_to_db(engine=None, batch_size: int = 5000) -> int:
    """
    Detect complaint categories for every Negative review already scored
    in the database, and persist the matches to the `keywords` table.

    This reads directly from the reviews table (not the CSV) so it always
    aligns with the correct review_id, and only runs after sentiment.py
    has populated sentiment_label.

    Args:
        engine:     SQLAlchemy engine.
        batch_size: Rows per INSERT batch.

    Returns:
        Number of (review, category) rows inserted.
    """
    from sqlalchemy import text as sql_text
    if engine is None:
        from src.database import get_engine
        engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(sql_text(
            "SELECT review_id, review_text FROM reviews WHERE sentiment_label = 'Negative'"
        ))
        rows = result.fetchall()

    if not rows:
        logger.warning(
            "No Negative reviews found in the database. "
            "Run src/sentiment.py before src/keyword_extraction.py."
        )
        return 0

    # Clear any previous run so this script is safely re-runnable
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM keywords"))

    inserts = []
    for review_id, review_text in rows:
        for category in detect_complaint_categories(str(review_text)):
            inserts.append({
                "review_id": review_id,
                "keyword": category,
                "complaint_category": category,
            })

    with engine.begin() as conn:
        for start in range(0, len(inserts), batch_size):
            batch = inserts[start:start + batch_size]
            if batch:
                conn.execute(
                    sql_text(
                        "INSERT INTO keywords (review_id, keyword, complaint_category) "
                        "VALUES (:review_id, :keyword, :complaint_category)"
                    ),
                    batch,
                )

    logger.info(
        "Tagged %d complaint-category mentions across %d negative reviews.",
        len(inserts), len(rows),
    )
    return len(inserts)


if __name__ == "__main__":
    from src.utils import load_csv, resolve_column_roles
    from src.database import get_engine

    df = load_csv(cfg.CLEANED_CSV_PATH)
    roles = resolve_column_roles(
        df, cfg.PLATFORM_SOURCES[cfg.ACTIVE_PLATFORM]["expected_columns"]
    )
    text_col = roles.get("review_text", "text")
    cat_df = score_complaint_categories(df, text_col)
    logger.info("Complaint categories:\n%s", cat_df.to_string(index=False))

    # Persist to the keywords table (this step previously did not exist,
    # which is why "Top Complaints" always showed as unavailable).
    engine = get_engine()
    write_keywords_to_db(engine)
