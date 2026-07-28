"""
notebooks/01_data_profiling.py

Generates a Data Profiling Report for the raw dataset.
Can be run as a standalone script.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from src.utils import find_raw_csv, memory_usage_mb, describe_nulls, setup_logging

logger = setup_logging(__name__)

def generate_report(raw_csv_path: Path, output_md_path: Path):
    logger.info(f"Generating profiling report for {raw_csv_path}")
    df = pd.read_csv(raw_csv_path)

    report = []
    report.append(f"# Data Profiling Report: {raw_csv_path.name}\n")

    report.append("## 1. General Overview\n")
    report.append(f"- **Total Rows:** {len(df):,}")
    report.append(f"- **Total Columns:** {len(df.columns)}")
    report.append(f"- **Memory Usage:** {memory_usage_mb(df):.2f} MB")
    report.append(f"- **Duplicate Rows:** {df.duplicated().sum():,}\n")

    report.append("## 2. Column Information\n")
    report.append("| Column | Type | Null Count | Null % |")
    report.append("|--------|------|------------|--------|")
    null_summary = describe_nulls(df)
    for _, row in null_summary.iterrows():
        report.append(f"| {row['column']} | {row['dtype']} | {row['null_count']:,} | {row['null_pct']}% |")
    report.append("\n")

    report.append("## 3. Sample Data\n")
    report.append(df.head(5).to_markdown(index=False))
    report.append("\n")

    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    logger.info(f"Profiling report written to {output_md_path}")

if __name__ == "__main__":
    try:
        raw_csv = find_raw_csv(cfg.RAW_DIR, cfg.RAW_CSV_FILENAME)
        generate_report(raw_csv, cfg.PROFILING_REPORT_PATH)
    except FileNotFoundError as e:
        logger.error(e)
