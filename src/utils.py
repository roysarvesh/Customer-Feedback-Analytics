"""
src/utils.py — Shared utilities for the Customer Feedback Analytics Platform.

Provides:
- Logging setup (call once at app entry-point)
- Timer decorator for performance tracking
- File I/O helpers
- Column-role auto-detection (rating, date, text, location, ID)
- Safe DataFrame operations
"""

import json
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

import pandas as pd

# Import config lazily to avoid circular imports in tests
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import config as cfg
    _LOG_LEVEL = cfg.LOG_LEVEL
    _LOG_FORMAT = cfg.LOG_FORMAT
    _LOG_DATE_FORMAT = cfg.LOG_DATE_FORMAT
except ImportError:
    _LOG_LEVEL = "INFO"
    _LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    _LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

F = TypeVar("F", bound=Callable[..., Any])

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

def setup_logging(name: str = "cfap", level: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a named logger.
    Call once at the application entry-point; subsequent calls return
    the same logger instance.

    Args:
        name:  Logger name (usually the module's __name__).
        level: Override log level (defaults to config.LOG_LEVEL).

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    level_str = level or _LOG_LEVEL
    numeric_level = getattr(logging, level_str.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    handler = logging.StreamHandler()
    handler.setLevel(numeric_level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# Module-level logger
logger = setup_logging(__name__)


# ─────────────────────────────────────────────
# TIMER DECORATOR
# ─────────────────────────────────────────────

def timer(func: F) -> F:
    """
    Decorator that logs the execution time of any function.

    Usage:
        @timer
        def my_function(): ...
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("⏱  %s finished in %.2fs", func.__qualname__, elapsed)
        return result
    return wrapper  # type: ignore[return-value]


# ─────────────────────────────────────────────
# FILE I/O HELPERS
# ─────────────────────────────────────────────

def load_json(path: Path) -> Any:
    """Load a JSON file and return its content."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path, indent: int = 2) -> None:
    """Serialize *data* to JSON and write to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    logger.debug("JSON written → %s", path)


def load_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    """
    Load a CSV file with sensible defaults.

    Args:
        path:    Absolute path to the CSV file.
        **kwargs: Forwarded to pd.read_csv.

    Returns:
        DataFrame.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If the resulting DataFrame is empty.
    """
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("low_memory", False)
    df = pd.read_csv(path, **kwargs)

    if df.empty:
        raise ValueError(f"CSV is empty: {path}")

    logger.info("Loaded %s rows × %s cols from %s", *df.shape, path.name)
    return df


def save_csv(df: pd.DataFrame, path: Path, **kwargs: Any) -> None:
    """Write a DataFrame to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs.setdefault("index", False)
    kwargs.setdefault("encoding", "utf-8")
    df.to_csv(path, **kwargs)
    logger.info("CSV written → %s (%s rows)", path.name, len(df))


def find_raw_csv(raw_dir: Path, preferred_name: str) -> Path:
    """
    Locate a CSV in *raw_dir*.  Returns the *preferred_name* if it exists,
    otherwise returns the first CSV found, otherwise raises FileNotFoundError.

    Args:
        raw_dir:        Directory containing raw data files.
        preferred_name: Expected filename (e.g. 'google_maps_reviews.csv').

    Returns:
        Path to the located CSV.
    """
    preferred = raw_dir / preferred_name
    if preferred.exists():
        logger.info("Found preferred dataset: %s", preferred.name)
        return preferred

    csvs = list(raw_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(
            f"No CSV files found in {raw_dir}. "
            "Please place the Kaggle dataset there and try again."
        )

    found = csvs[0]
    logger.warning(
        "Preferred file '%s' not found. Using '%s' instead.",
        preferred_name,
        found.name,
    )
    return found


# ─────────────────────────────────────────────
# COLUMN-ROLE AUTO-DETECTION
# ─────────────────────────────────────────────

def detect_column_role(
    df: pd.DataFrame,
    candidates: List[str],
    sample_rows: int = 1000,
) -> Optional[str]:
    """
    Return the first column in *candidates* that actually exists in *df*.

    Args:
        df:          Source DataFrame.
        candidates:  Ordered list of possible column names.
        sample_rows: Unused (reserved for future fuzzy matching).

    Returns:
        Matched column name, or None if no candidate found.
    """
    existing = set(df.columns)
    for col in candidates:
        if col in existing:
            return col
    return None


def resolve_column_roles(
    df: pd.DataFrame,
    source_config: Dict[str, List[str]],
) -> Dict[str, Optional[str]]:
    """
    Resolve all column roles for a given platform source config.

    Args:
        df:            DataFrame to inspect.
        source_config: Dict mapping role → list of candidate column names.
                       (Comes from config.PLATFORM_SOURCES[platform]["expected_columns"])

    Returns:
        Dict mapping role name → actual column name (or None if not found).
    """
    resolved: Dict[str, Optional[str]] = {}
    for role, candidates in source_config.items():
        resolved[role] = detect_column_role(df, candidates)
        if resolved[role]:
            logger.debug("Column role '%s' → '%s'", role, resolved[role])
        else:
            logger.warning("Column role '%s' could not be resolved. Candidates: %s", role, candidates)
    return resolved


# ─────────────────────────────────────────────
# SAFE DATAFRAME HELPERS
# ─────────────────────────────────────────────

def safe_numeric(series: pd.Series, errors: str = "coerce") -> pd.Series:
    """Convert a series to numeric, coercing errors to NaN."""
    return pd.to_numeric(series, errors=errors)


def safe_datetime(series: pd.Series, errors: str = "coerce") -> pd.Series:
    """
    Parse a series as datetime.
    Handles Unix timestamps (int/float) and string dates automatically.
    """
    # If the series looks like Unix timestamps (large integers), convert accordingly
    sample = series.dropna().head(100)
    if pd.api.types.is_numeric_dtype(sample):
        numeric_sample = pd.to_numeric(sample, errors="coerce").dropna()
        if len(numeric_sample) > 0:
            median_val = numeric_sample.median()
            # Unix ms if > 1e10, Unix seconds otherwise
            if median_val > 1e10:
                logger.debug("Detected Unix millisecond timestamps.")
                return pd.to_datetime(
                    pd.to_numeric(series, errors="coerce"), unit="ms", errors=errors
                )
            elif median_val > 1e8:
                logger.debug("Detected Unix second timestamps.")
                return pd.to_datetime(
                    pd.to_numeric(series, errors="coerce"), unit="s", errors=errors
                )
    # `infer_datetime_format` was deprecated in pandas 2.x and has been
    # removed entirely in newer pandas releases (this is why the app worked
    # locally with a warning but crashed with a hard TypeError on Streamlit
    # Cloud, which installs a newer pandas since requirements.txt had no
    # upper version bound). Modern pandas infers the format automatically
    # without needing this argument at all.
    return pd.to_datetime(series, errors=errors)


def memory_usage_mb(df: pd.DataFrame) -> float:
    """Return total memory usage of a DataFrame in megabytes."""
    return df.memory_usage(deep=True).sum() / 1024 ** 2


def describe_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame summarising null counts and percentages per column.

    Returns:
        DataFrame with columns: ['column', 'null_count', 'null_pct', 'dtype']
    """
    null_counts = df.isnull().sum()
    null_pct = (null_counts / len(df) * 100).round(2)
    summary = pd.DataFrame({
        "column": null_counts.index,
        "null_count": null_counts.values,
        "null_pct": null_pct.values,
        "dtype": [str(df[c].dtype) for c in null_counts.index],
    })
    return summary.sort_values("null_count", ascending=False).reset_index(drop=True)


def top_n_values(series: pd.Series, n: int = 10) -> pd.DataFrame:
    """
    Return the top *n* value counts for a Series as a DataFrame.

    Returns:
        DataFrame with columns: ['value', 'count', 'pct']
    """
    counts = series.value_counts(dropna=False).head(n)
    total = len(series)
    return pd.DataFrame({
        "value": counts.index.astype(str),
        "count": counts.values,
        "pct": (counts.values / total * 100).round(2),
    })


def clamp_rating(
    series: pd.Series, rating_min: float, rating_max: float
) -> Tuple[pd.Series, int]:
    """
    Coerce to numeric and mask values outside [rating_min, rating_max].

    Returns:
        Tuple of (cleaned_series, number_of_invalid_rows_removed).
    """
    numeric = pd.to_numeric(series, errors="coerce")
    invalid_mask = (numeric < rating_min) | (numeric > rating_max) | numeric.isna()
    n_invalid = int(invalid_mask.sum())
    return numeric.where(~invalid_mask), n_invalid
