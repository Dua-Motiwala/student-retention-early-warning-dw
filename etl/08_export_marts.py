"""
===============================================================================
Script: etl/08_export_marts.py
Phase: Phase 8 - Power BI Dashboard & Fallback Mart Exports
Purpose: Exports all dimensional mart tables and views from MySQL `marts`
         schema into CSV format inside `dashboard/export/` as a portable
         offline fallback for Power BI Desktop.
Inputs: marts.dim_student, marts.dim_course, marts.dim_date,
        marts.dim_assessment_type, marts.fact_student_performance,
        marts.fact_weekly_engagement, marts.fact_risk_flag
Outputs: CSV files in dashboard/export/
Dependencies: etl/db.py, pandas
Run Order: 08
===============================================================================
"""

import sys
import time
import argparse
from pathlib import Path
import pandas as pd
from sqlalchemy import text

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_engine

EXPORT_DIR = PROJECT_ROOT / "dashboard" / "export"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def export_marts(engine, reload: bool = False) -> bool:
    """Exports all marts tables to CSV files using chunked streaming."""
    print("=" * 70)
    print("EXPORTING DIMENSIONAL MARTS TO CSV (DASHBOARD FALLBACK)")
    print("=" * 70)

    tables = [
        ("dim_assessment_type", "marts.dim_assessment_type", 3),
        ("dim_course", "marts.dim_course", 22),
        ("dim_date", "marts.dim_date", 91),
        ("dim_student", "marts.dim_student", 28785),
        ("fact_student_performance", "marts.fact_student_performance", 173912),
        ("fact_weekly_engagement", "marts.fact_weekly_engagement", 627031),
        ("fact_risk_flag", "marts.fact_risk_flag", 198493),
    ]

    all_passed = True
    total_start = time.time()

    with engine.connect() as conn:
        for filename, sql_table, expected_rows in tables:
            out_file = EXPORT_DIR / f"{filename}.csv"
            if out_file.exists() and not reload:
                file_size_mb = out_file.stat().st_size / (1024 * 1024)
                print(f"  [SAFE SKIP] {out_file.name} already exists ({file_size_mb:.2f} MB).")
                continue

            print(f"  Exporting {sql_table} -> {out_file.name}...")
            t0 = time.time()
            
            # Stream in chunks for large fact tables to conserve memory
            chunk_size = 100000
            first_chunk = True
            row_count = 0

            for chunk in pd.read_sql(f"SELECT * FROM {sql_table}", conn, chunksize=chunk_size):
                chunk.to_csv(out_file, mode="w" if first_chunk else "a", index=False, header=first_chunk)
                first_chunk = False
                row_count += len(chunk)

            file_size_mb = out_file.stat().st_size / (1024 * 1024)
            elapsed = time.time() - t0
            print(f"  [OK] Exported {row_count:,} rows to {out_file.name} ({file_size_mb:.2f} MB) in {elapsed:.1f}s")

            if expected_rows > 0 and row_count != expected_rows:
                print(f"  [WARN] Row count mismatch on {filename}: expected {expected_rows:,}, exported {row_count:,}")
                all_passed = False

    print("\n" + "=" * 70)
    print(f"[SUCCESS] All dimensional marts exported to CSV in {time.time() - total_start:.1f}s")
    print(f"          Target directory: {EXPORT_DIR}")
    print("=" * 70)
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Phase 8: Export Dimensional Marts to CSV")
    parser.add_argument("--reload", action="store_true", help="Force overwrite existing CSV exports")
    args = parser.parse_args()

    engine = get_engine()
    success = export_marts(engine, reload=args.reload)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
