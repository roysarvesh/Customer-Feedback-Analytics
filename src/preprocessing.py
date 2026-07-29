"""
src/preprocessing.py — Professional data cleaning pipeline.

Transformations applied (in order):
  1. Load raw CSV (auto-detect filename)
  2. Resolve column roles via config
  3. Remove exact duplicate rows
  4. Remove rows with null/invalid ratings (outside [1, 5])
  5. Remove blank / null review text
  6. Normalize review text (HTML strip, encoding fix, whitespace)
  7. Standardize city names (title-case, known abbreviations)
  8. Parse date column → ISO format (YYYY-MM-DD)
  9. Fill remaining nulls with 'Unknown'
 10. Export cleaned CSV + cleaning log JSON

Every step logs row counts before/after for full auditability.
"""

import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.utils import (
    load_csv,
    save_csv,
    save_json,
    find_raw_csv,
    resolve_column_roles,
    safe_datetime,
    clamp_rating,
    describe_nulls,
    timer,
    setup_logging,
)

logger = setup_logging(__name__)

# ─────────────────────────────────────────────
# CITY NAME STANDARDISATION MAP
# Common abbreviations and misspellings → canonical names
# ─────────────────────────────────────────────
CITY_ALIASES: Dict[str, str] = {
    "nyc": "New York City",
    "new york": "New York City",
    "la": "Los Angeles",
    "sf": "San Francisco",
    "dc": "Washington D.C.",
    "washington dc": "Washington D.C.",
    "chicago il": "Chicago",
    "delhi": "New Delhi",
    "new delhi": "New Delhi",
    "bengaluru": "Bangalore",
    "kolkata": "Kolkata",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "pune": "Pune",
    "hyderabad": "Hyderabad",
    "ahmedabad": "Ahmedabad",
}


# ─────────────────────────────────────────────
# TEXT NORMALISATION
# ─────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", text)


def _fix_encoding(text: str) -> str:
    """Normalize unicode (NFC) and replace common mojibake patterns."""
    text = unicodedata.normalize("NFC", text)
    # Replace common mis-encoded apostrophes and quotes
    text = text.replace("\u2019", "'")
    text = text.replace("\u2018", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    return text


def _clean_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(series: pd.Series) -> pd.Series:
    """
    Apply full text normalisation pipeline to a string Series:
      HTML strip → encoding fix → whitespace collapse.

    Args:
        series: Raw review text Series.

    Returns:
        Cleaned text Series.
    """
    return (
        series.astype(str)
        .apply(_strip_html)
        .apply(_fix_encoding)
        .apply(_clean_whitespace)
    )


# ─────────────────────────────────────────────
# CITY STANDARDISATION
# ─────────────────────────────────────────────

def standardize_city(city: str) -> str:
    """
    Standardise a single city name.
    1. Lowercase for lookup.
    2. Apply CITY_ALIASES map.
    3. Return title-cased result.

    Args:
        city: Raw city name string.

    Returns:
        Standardised city name.
    """
    if not isinstance(city, str) or city.strip() == "":
        return "Unknown"
    cleaned = city.strip().lower()
    if cleaned in CITY_ALIASES:
        return CITY_ALIASES[cleaned]
    return city.strip().title()


def standardize_cities(series: pd.Series) -> pd.Series:
    """Vectorised city standardisation over a Series."""
    return series.apply(standardize_city)


# ─────────────────────────────────────────────
# CLEANING STEPS
# ─────────────────────────────────────────────

def _step_remove_duplicates(
    df: pd.DataFrame, log: Dict
) -> pd.DataFrame:
    """Remove exact duplicate rows."""
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    log["step_01_remove_duplicates"] = {
        "rows_before": before,
        "rows_after": len(df),
        "rows_removed": removed,
    }
    logger.info("[Step 1] Removed %d duplicate rows.", removed)
    return df


def _step_clean_ratings(
    df: pd.DataFrame, rating_col: str, log: Dict
) -> pd.DataFrame:
    """Coerce ratings to numeric; drop rows outside [RATING_MIN, RATING_MAX]."""
    before = len(df)
    cleaned_series, n_invalid = clamp_rating(
        df[rating_col], cfg.RATING_MIN, cfg.RATING_MAX
    )
    df = df.copy()
    df[rating_col] = cleaned_series
    df = df.dropna(subset=[rating_col])
    log["step_02_clean_ratings"] = {
        "rows_before": before,
        "rows_after": len(df),
        "rows_removed": n_invalid,
        "rating_range": [cfg.RATING_MIN, cfg.RATING_MAX],
    }
    logger.info("[Step 2] Removed %d rows with invalid ratings.", n_invalid)
    return df


def _step_remove_blank_reviews(
    df: pd.DataFrame, text_col: str, log: Dict
) -> pd.DataFrame:
    """Drop rows where review text is null or whitespace-only."""
    before = len(df)
    # Replace whitespace-only strings with NaN, then drop
    df = df.copy()
    df[text_col] = df[text_col].apply(
        lambda x: None if (pd.isna(x) or str(x).strip() == "") else x
    )
    df = df.dropna(subset=[text_col])
    removed = before - len(df)
    log["step_03_remove_blank_reviews"] = {
        "rows_before": before,
        "rows_after": len(df),
        "rows_removed": removed,
    }
    logger.info("[Step 3] Removed %d rows with blank/null reviews.", removed)
    return df


def _step_normalize_text(
    df: pd.DataFrame, text_col: str, log: Dict
) -> pd.DataFrame:
    """Normalize review text in-place."""
    df = df.copy()
    df[text_col] = normalize_text(df[text_col])
    log["step_04_normalize_text"] = {
        "column": text_col,
        "operations": ["html_strip", "encoding_fix", "whitespace_collapse"],
    }
    logger.info("[Step 4] Review text normalized.")
    return df


def _step_standardize_cities(
    df: pd.DataFrame, city_col: Optional[str], log: Dict
) -> pd.DataFrame:
    """Standardise city names if city column exists."""
    if city_col is None or city_col not in df.columns:
        log["step_05_standardize_cities"] = {"status": "skipped", "reason": "no city column"}
        logger.warning("[Step 5] City column not found — skipping.")
        return df
    df = df.copy()
    before_unique = df[city_col].nunique()
    df[city_col] = standardize_cities(df[city_col])
    after_unique = df[city_col].nunique()
    log["step_05_standardize_cities"] = {
        "column": city_col,
        "unique_cities_before": int(before_unique),
        "unique_cities_after": int(after_unique),
    }
    logger.info(
        "[Step 5] City standardisation: %d → %d unique cities.",
        before_unique,
        after_unique,
    )
    return df


def _step_parse_dates(
    df: pd.DataFrame, date_col: Optional[str], log: Dict
) -> pd.DataFrame:
    """Parse date column to YYYY-MM-DD string."""
    if date_col is None or date_col not in df.columns:
        log["step_06_parse_dates"] = {"status": "skipped", "reason": "no date column"}
        logger.warning("[Step 6] Date column not found — skipping.")
        return df
    df = df.copy()
    parsed = safe_datetime(df[date_col])
    before_null = parsed.isna().sum()
    df[date_col] = parsed.dt.strftime("%Y-%m-%d")
    log["step_06_parse_dates"] = {
        "column": date_col,
        "null_dates_after_parse": int(before_null),
        "sample_values": df[date_col].dropna().head(3).tolist(),
    }
    logger.info(
        "[Step 6] Dates parsed. %d rows had unparseable dates.", before_null
    )
    return df


def _step_fill_nulls(
    df: pd.DataFrame, log: Dict
) -> pd.DataFrame:
    """Fill remaining object-column nulls with 'Unknown'."""
    df = df.copy()
    object_cols = df.select_dtypes(include="object").columns
    fill_counts = {}
    for col in object_cols:
        n = df[col].isna().sum()
        if n > 0:
            df[col] = df[col].fillna("Unknown")
            fill_counts[col] = int(n)
    log["step_07_fill_nulls"] = {"columns_filled": fill_counts}
    logger.info("[Step 7] Null fill complete: %d columns affected.", len(fill_counts))
    return df


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

@timer
def run_cleaning_pipeline(
    raw_csv: Optional[Path] = None,
    output_csv: Optional[Path] = None,
    log_path: Optional[Path] = None,
    sample_size: Optional[int] = None,
) -> pd.DataFrame:
    """
    Execute the full data cleaning pipeline.

    Args:
        raw_csv:     Path to raw CSV. Auto-detected if None.
        output_csv:  Destination for cleaned CSV. Defaults to config.
        log_path:    Destination for cleaning log JSON.
        sample_size: If set, randomly sample this many rows from raw data.

    Returns:
        Cleaned DataFrame.
    """
    raw_csv = raw_csv or find_raw_csv(cfg.RAW_DIR, cfg.RAW_CSV_FILENAME)
    output_csv = output_csv or cfg.CLEANED_CSV_PATH
    log_path = log_path or cfg.CLEANING_LOG_PATH

    logger.info("=" * 60)
    logger.info("Starting data cleaning pipeline")
    logger.info("Source: %s", raw_csv)
    logger.info("=" * 60)

    # --- Load ---
    df = load_csv(raw_csv)
    if sample_size and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)
        logger.info("Sampled %d rows from dataset.", sample_size)

    initial_rows = len(df)
    cleaning_log: Dict = {
        "source_file": str(raw_csv),
        "initial_rows": initial_rows,
        "initial_columns": list(df.columns),
        "sample_size": sample_size,
    }

    # --- Resolve column roles ---
    platform_cfg = cfg.PLATFORM_SOURCES[cfg.ACTIVE_PLATFORM]["expected_columns"]
    roles = resolve_column_roles(df, platform_cfg)
    cleaning_log["column_roles"] = roles

    rating_col = roles.get("rating")
    text_col = roles.get("review_text")
    city_col = roles.get("city")
    date_col = roles.get("date")

    if not rating_col:
        raise ValueError(
            "Could not detect a rating column. "
            f"Expected one of: {platform_cfg['rating']}"
        )
    if not text_col:
        raise ValueError(
            "Could not detect a review text column. "
            f"Expected one of: {platform_cfg['review_text']}"
        )

    # --- Execute cleaning steps ---
    df = _step_remove_duplicates(df, cleaning_log)
    df = _step_clean_ratings(df, rating_col, cleaning_log)
    df = _step_remove_blank_reviews(df, text_col, cleaning_log)
    df = _step_normalize_text(df, text_col, cleaning_log)
    df = _step_standardize_cities(df, city_col, cleaning_log)
    df = _step_parse_dates(df, date_col, cleaning_log)
    df = _step_fill_nulls(df, cleaning_log)

    final_rows = len(df)
    cleaning_log["final_rows"] = final_rows
    cleaning_log["total_rows_removed"] = initial_rows - final_rows
    cleaning_log["retention_pct"] = round(final_rows / initial_rows * 100, 2)

    # --- Save outputs ---
    save_csv(df, output_csv)
    save_json(cleaning_log, log_path)

    logger.info("=" * 60)
    logger.info(
        "Cleaning complete: %d → %d rows (%.1f%% retained).",
        initial_rows, final_rows, cleaning_log["retention_pct"],
    )
    logger.info("Cleaned CSV → %s", output_csv)
    logger.info("Cleaning log → %s", log_path)
    logger.info("=" * 60)

    return df


if __name__ == "__main__":
    run_cleaning_pipeline(sample_size=cfg.SAMPLE_SIZE)
