"""
src/sentiment.py — VADER-based sentiment analysis pipeline.

Responsibilities:
- Download NLTK VADER lexicon on first run
- Score every review with VADER compound, positive, neutral, negative scores
- Assign sentiment label: Positive / Neutral / Negative
- Write sentiment scores back to the SQLite reviews table
- Generate word-frequency data for word clouds
"""

import logging
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
# NLTK / VADER SETUP
# ─────────────────────────────────────────────

def _ensure_vader_lexicon() -> None:
    """Download VADER lexicon if not already present."""
    import nltk
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        logger.info("Downloading VADER lexicon...")
        nltk.download("vader_lexicon", quiet=True)

    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)

    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)


def get_vader_analyzer():
    """Return a SentimentIntensityAnalyzer instance (initialises VADER lexicon)."""
    _ensure_vader_lexicon()
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    return SentimentIntensityAnalyzer()


# ─────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────

def score_text(text: str, analyzer) -> Dict[str, float]:
    """
    Score a single review text using VADER.

    Args:
        text:     Review text string.
        analyzer: SentimentIntensityAnalyzer instance.

    Returns:
        Dict with keys: compound, pos, neu, neg.
    """
    if not isinstance(text, str) or text.strip() == "":
        return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}
    scores = analyzer.polarity_scores(text)
    return {
        "compound": round(scores["compound"], 4),
        "pos": round(scores["pos"], 4),
        "neu": round(scores["neu"], 4),
        "neg": round(scores["neg"], 4),
    }


def assign_sentiment_label(compound: float) -> str:
    """
    Map a VADER compound score to a sentiment label.

    Args:
        compound: VADER compound score in [-1, 1].

    Returns:
        'Positive', 'Neutral', or 'Negative'.
    """
    if compound >= cfg.VADER_POSITIVE_THRESHOLD:
        return "Positive"
    elif compound <= cfg.VADER_NEGATIVE_THRESHOLD:
        return "Negative"
    return "Neutral"


@timer
def score_dataframe(
    df: pd.DataFrame,
    text_col: str,
    batch_size: int = cfg.NLP_BATCH_SIZE,
) -> pd.DataFrame:
    """
    Apply VADER sentiment scoring to an entire DataFrame.

    Processes in batches to manage memory on large datasets.

    Args:
        df:         DataFrame containing review text.
        text_col:   Name of the review text column.
        batch_size: Rows per processing batch.

    Returns:
        DataFrame with added columns:
          sentiment_compound, sentiment_positive, sentiment_neutral,
          sentiment_negative, sentiment_label
    """
    analyzer = get_vader_analyzer()
    df = df.copy()

    compounds, positives, neutrals, negatives = [], [], [], []

    total = len(df)
    for start in range(0, total, batch_size):
        batch = df[text_col].iloc[start:start + batch_size]
        for text in batch:
            scores = score_text(str(text), analyzer)
            compounds.append(scores["compound"])
            positives.append(scores["pos"])
            neutrals.append(scores["neu"])
            negatives.append(scores["neg"])

        pct = min((start + batch_size) / total * 100, 100)
        logger.debug("Sentiment scoring: %.0f%% complete", pct)

    df["sentiment_compound"] = compounds
    df["sentiment_positive"] = positives
    df["sentiment_neutral"] = neutrals
    df["sentiment_negative"] = negatives
    df["sentiment_label"] = df["sentiment_compound"].apply(assign_sentiment_label)

    pos_pct = (df["sentiment_label"] == "Positive").mean() * 100
    neg_pct = (df["sentiment_label"] == "Negative").mean() * 100
    neu_pct = (df["sentiment_label"] == "Neutral").mean() * 100

    logger.info(
        "Sentiment distribution — Positive: %.1f%% | Neutral: %.1f%% | Negative: %.1f%%",
        pos_pct, neu_pct, neg_pct,
    )
    return df


# ─────────────────────────────────────────────
# UPDATE DATABASE
# ─────────────────────────────────────────────

@timer
def write_sentiment_to_db(
    df: pd.DataFrame,
    engine=None,
) -> None:
    """
    Write computed sentiment scores back to the SQLite reviews table.

    Assumes reviews were inserted in the same order as df rows.
    Uses bulk UPDATE via pandas to_sql + temp table approach for speed.

    Args:
        df:     DataFrame with sentiment columns added by score_dataframe.
        engine: SQLAlchemy engine.
    """
    from sqlalchemy import text as sql_text
    import config as cfg

    if engine is None:
        from src.database import get_engine
        engine = get_engine()

    required = ["sentiment_compound", "sentiment_label", "sentiment_positive",
                "sentiment_neutral", "sentiment_negative"]
    present = [c for c in required if c in df.columns]
    if not present:
        logger.warning("No sentiment columns found in DataFrame. Run score_dataframe first.")
        return

    # Write to a temp table then batch-update main table
    with engine.connect() as conn:
        # Get review IDs in order
        result = conn.execute(sql_text("SELECT review_id FROM reviews ORDER BY review_id"))
        review_ids = [row[0] for row in result]

    if len(review_ids) != len(df):
        logger.warning(
            "Review count mismatch: DB has %d rows, DataFrame has %d rows. "
            "Skipping DB sentiment update. This usually means the reviews table "
            "is out of sync with reviews_cleaned.csv — re-run 'python src/database.py' "
            "(which now clears old reviews before reloading) and then re-run this script.",
            len(review_ids), len(df),
        )
        return

    df_update = df[required].copy()
    df_update["review_id"] = review_ids

    BATCH = 5000
    with engine.connect() as conn:
        for start in range(0, len(df_update), BATCH):
            batch = df_update.iloc[start:start + BATCH]
            for _, row in batch.iterrows():
                conn.execute(
                    sql_text(
                        "UPDATE reviews SET "
                        "sentiment_compound = :compound, "
                        "sentiment_label = :label, "
                        "sentiment_positive = :pos, "
                        "sentiment_neutral = :neu, "
                        "sentiment_negative = :neg "
                        "WHERE review_id = :rid"
                    ),
                    {
                        "compound": row["sentiment_compound"],
                        "label": row["sentiment_label"],
                        "pos": row["sentiment_positive"],
                        "neu": row["sentiment_neutral"],
                        "neg": row["sentiment_negative"],
                        "rid": int(row["review_id"]),
                    },
                )
        conn.commit()
    logger.info("Sentiment scores written to DB for %d reviews.", len(df_update))


# ─────────────────────────────────────────────
# WORD CLOUD DATA
# ─────────────────────────────────────────────

def get_stopwords() -> set:
    """Return a comprehensive set of English stopwords."""
    _ensure_vader_lexicon()
    from nltk.corpus import stopwords
    base = set(stopwords.words("english"))
    extra = {
        "place", "go", "went", "come", "came", "one", "two", "three",
        "also", "really", "very", "much", "many", "got", "get", "would",
        "could", "will", "think", "know", "say", "like", "just", "even",
        "na", "naan", "it's", "i've", "i'm", "don't", "didn't", "doesn't",
    }
    return base | extra


def build_word_frequency(
    texts: pd.Series,
    stopwords_set: Optional[set] = None,
    max_words: int = cfg.WORDCLOUD_MAX_WORDS,
) -> Dict[str, int]:
    """
    Build a word-frequency dictionary from a Series of text strings.

    Args:
        texts:         Series of review texts.
        stopwords_set: Words to exclude (auto-loaded if None).
        max_words:     Maximum number of words to return.

    Returns:
        Dict mapping word → frequency, sorted descending.
    """
    import re
    stops = stopwords_set or get_stopwords()
    freq: Dict[str, int] = {}

    for text in texts.dropna():
        words = re.findall(r"\b[a-zA-Z]{3,}\b", str(text).lower())
        for word in words:
            if word not in stops:
                freq[word] = freq.get(word, 0) + 1

    # Sort and limit
    sorted_freq = dict(
        sorted(freq.items(), key=lambda x: x[1], reverse=True)[:max_words]
    )
    return sorted_freq


def generate_wordcloud_image(
    word_freq: Dict[str, int],
    colormap: str = "Greens",
    background_color: str = "white",
    max_words: int = cfg.WORDCLOUD_MAX_WORDS,
    width: int = 800,
    height: int = 400,
) -> Optional[object]:
    """
    Generate a WordCloud image object from a word-frequency dict.

    Args:
        word_freq:        Dict of word → frequency.
        colormap:         Matplotlib colormap name.
        background_color: Background colour string.
        max_words:        Max words to render.
        width:            Image width in pixels.
        height:           Image height in pixels.

    Returns:
        WordCloud image object, or None if wordcloud package unavailable.
    """
    try:
        from wordcloud import WordCloud
    except ImportError:
        logger.warning("wordcloud package not installed. Skipping WordCloud generation.")
        return None

    if not word_freq:
        logger.warning("Empty word frequency dict. Returning None.")
        return None

    wc = WordCloud(
        width=width,
        height=height,
        max_words=max_words,
        background_color=background_color,
        colormap=colormap,
        prefer_horizontal=0.85,
        collocations=False,
    ).generate_from_frequencies(word_freq)
    return wc


def get_sentiment_word_clouds(
    df: pd.DataFrame,
    text_col: str,
    sentiment_col: str = "sentiment_label",
) -> Tuple[Optional[object], Optional[object]]:
    """
    Generate positive and negative WordCloud objects from a rated DataFrame.

    Args:
        df:            DataFrame with review text and sentiment label.
        text_col:      Name of the review text column.
        sentiment_col: Name of the sentiment label column.

    Returns:
        Tuple of (positive_wc, negative_wc). Either may be None.
    """
    stops = get_stopwords()

    pos_texts = df.loc[df[sentiment_col] == "Positive", text_col]
    neg_texts = df.loc[df[sentiment_col] == "Negative", text_col]

    pos_freq = build_word_frequency(pos_texts, stops)
    neg_freq = build_word_frequency(neg_texts, stops)

    positive_wc = generate_wordcloud_image(
        pos_freq, colormap=cfg.WORDCLOUD_POSITIVE_COLORMAP
    )
    negative_wc = generate_wordcloud_image(
        neg_freq, colormap=cfg.WORDCLOUD_NEGATIVE_COLORMAP
    )

    return positive_wc, negative_wc


if __name__ == "__main__":
    from src.utils import load_csv
    from src.utils import resolve_column_roles
    from src.database import get_engine

    df = load_csv(cfg.CLEANED_CSV_PATH)
    roles = resolve_column_roles(
        df, cfg.PLATFORM_SOURCES[cfg.ACTIVE_PLATFORM]["expected_columns"]
    )
    text_col = roles.get("review_text", "text")
    df = score_dataframe(df, text_col)
    logger.info("Sentiment scoring complete. Sample:\n%s", df[["sentiment_compound", "sentiment_label"]].head())

    # Persist scores back to the reviews table (this step was previously missing,
    # which left sentiment_label NULL for every row in the database).
    engine = get_engine()
    write_sentiment_to_db(df, engine)
