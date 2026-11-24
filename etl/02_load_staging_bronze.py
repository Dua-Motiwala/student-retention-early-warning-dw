"""
===============================================================================
Script: etl/02_load_staging_bronze.py
Phase: Phase 2 - Staging + Bronze Bulk Loading (ETL Step 1)
Purpose: Ingests all 7 OULAD CSV files into the Bronze layer, generates 
         integrated Staging tables, and executes strict row-count reconciliation.
Inputs: CSV files in data/raw/
Outputs: Populated tables in `bronze` and `staging` schemas
Dependencies: etl/db.py, sql/02_create_staging_bronze_tables.sql
Run Order: 02
===============================================================================
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
from tqdm import tqdm

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_raw_connection, execute_sql_file


def count_csv_lines(csv_path: Path) -> int:
    """Count data rows in a CSV file excluding header line."""
    with open(csv_path, "rb") as f:
        # Subtract 1 for header
        return max(0, sum(1 for _ in f) - 1)


def create_schema_tables():
    """Execute DDL to create bronze and staging tables."""
    print("=" * 70)
    print("STEP 1: CREATING BRONZE AND STAGING TABLES")
    print("=" * 70)
    ddl_file = PROJECT_ROOT / "sql" / "02_create_staging_bronze_tables.sql"
    execute_sql_file(ddl_file)
    print("[OK] Executed 02_create_staging_bronze_tables.sql successfully.\n")


def load_file_chunked(csv_path: Path, table_name: str, schema: str, columns: List[str], chunk_size: int = 100000, reload: bool = False):
    """
    Stream a CSV file into MySQL using chunked batch insertions to prevent 
    memory saturation and database timeouts.
    """
    print(f"Loading {csv_path.name} -> {schema}.{table_name} (chunk size: {chunk_size:,})...")
    total_rows = count_csv_lines(csv_path)
    
    col_str = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {schema}.{table_name} ({col_str}) VALUES ({placeholders})"
    
    conn = get_raw_connection(schema=schema)
    cur = conn.cursor()
    
    if reload:
        cur.execute(f"TRUNCATE TABLE {schema}.{table_name};")
        print(f"  [RELOAD] Truncated {schema}.{table_name} before reloading.")
    else:
        # Check if table is already fully loaded with exact row parity
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {schema}.{table_name};")
        existing_cnt = cur.fetchone()["cnt"]
        if existing_cnt == total_rows:
            print(f"  [SAFE SKIP] Table {schema}.{table_name} already fully loaded ({existing_cnt:,} / {total_rows:,} rows). Skipping.")
            conn.close()
            return
        elif existing_cnt > 0:
            print(f"  [AUTO REPAIR] Discrepancy detected in {schema}.{table_name} ({existing_cnt:,} existing vs {total_rows:,} expected).")
            print(f"  Cleaning partial/mismatched data and reloading to guarantee exact parity...")
            cur.execute(f"TRUNCATE TABLE {schema}.{table_name};")

    start_time = time.time()
    rows_inserted = 0

    with tqdm(total=total_rows, unit="rows", desc=f"  {table_name}") as pbar:
        for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
            # Convert DataFrame to object array and replace NaN with None for SQL NULL
            clean_chunk = chunk.astype(object).where(pd.notnull(chunk), None)
            records = clean_chunk.values.tolist()
            cur.executemany(insert_sql, records)
            conn.commit()
            rows_inserted += len(records)
            pbar.update(len(records))

    elapsed = time.time() - start_time
    rate = rows_inserted / elapsed if elapsed > 0 else 0
    print(f"  [OK] Ingested {rows_inserted:,} rows in {elapsed:.2f}s ({rate:,.0f} rows/s)\n")
    conn.close()


def load_all_bronze(reload: bool = False):
    """Ingest all 7 raw CSV files into bronze schema tables."""
    print("=" * 70)
    print("STEP 2: INGESTING RAW CSVs INTO BRONZE SCHEMA")
    print("=" * 70)
    raw_dir = PROJECT_ROOT / "data" / "raw"

    configs = [
        {
            "csv": raw_dir / "courses.csv",
            "table": "raw_courses",
            "cols": ["code_module", "code_presentation", "module_presentation_length"],
            "chunk_size": 10000
        },
        {
            "csv": raw_dir / "assessments.csv",
            "table": "raw_assessments",
            "cols": ["code_module", "code_presentation", "id_assessment", "assessment_type", "date", "weight"],
            "chunk_size": 10000
        },
        {
            "csv": raw_dir / "vle.csv",
            "table": "raw_vle",
            "cols": ["id_site", "code_module", "code_presentation", "activity_type", "week_from", "week_to"],
            "chunk_size": 10000
        },
        {
            "csv": raw_dir / "studentInfo.csv",
            "table": "raw_student_info",
            "cols": [
                "code_module", "code_presentation", "id_student", "gender", "region",
                "highest_education", "imd_band", "age_band", "num_of_prev_attempts",
                "studied_credits", "disability", "final_result"
            ],
            "chunk_size": 50000
        },
        {
            "csv": raw_dir / "studentRegistration.csv",
            "table": "raw_student_registration",
            "cols": ["code_module", "code_presentation", "id_student", "date_registration", "date_unregistration"],
            "chunk_size": 50000
        },
        {
            "csv": raw_dir / "studentAssessment.csv",
            "table": "raw_student_assessment",
            "cols": ["id_assessment", "id_student", "date_submitted", "is_banked", "score"],
            "chunk_size": 50000
        },
        {
            "csv": raw_dir / "studentVle.csv",
            "table": "raw_student_vle",
            "cols": ["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"],
            "chunk_size": 100000
        }
    ]

    for cfg in configs:
        load_file_chunked(
            csv_path=cfg["csv"],
            table_name=cfg["table"],
            schema="bronze",
            columns=cfg["cols"],
            chunk_size=cfg["chunk_size"],
            reload=reload
        )


def populate_staging_tables(reload: bool = False):
    """Populate staging schema tables by integrating bronze tables."""
    print("=" * 70)
    print("STEP 3: POPULATING INTEGRATED STAGING TABLES")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    if reload:
        cur.execute("TRUNCATE TABLE staging.stg_courses;")
        cur.execute("TRUNCATE TABLE staging.stg_students;")
        cur.execute("TRUNCATE TABLE staging.stg_assessments;")
        print("  [RELOAD] Truncated staging tables before reloading.")

    # 1. Populate staging.stg_courses
    print("Populating staging.stg_courses...")
    cur.execute("SELECT COUNT(*) AS cnt FROM bronze.raw_courses;")
    expected_courses = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM staging.stg_courses;")
    existing_courses = cur.fetchone()["cnt"]

    if existing_courses == expected_courses and not reload:
        print(f"  [SAFE SKIP] staging.stg_courses already populated ({existing_courses:,} rows).")
    else:
        if existing_courses > 0:
            cur.execute("TRUNCATE TABLE staging.stg_courses;")
        cur.execute("""
            INSERT INTO staging.stg_courses (code_module, code_presentation, module_presentation_length)
            SELECT code_module, code_presentation, module_presentation_length
            FROM bronze.raw_courses;
        """)
        conn.commit()
        print(f"  [OK] staging.stg_courses loaded ({cur.rowcount} rows).")

    # 2. Populate staging.stg_students (studentInfo + studentRegistration)
    print("Populating staging.stg_students (joining studentInfo + studentRegistration)...")
    cur.execute("SELECT COUNT(*) AS cnt FROM bronze.raw_student_info;")
    expected_students = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM staging.stg_students;")
    existing_students = cur.fetchone()["cnt"]

    if existing_students == expected_students and not reload:
        print(f"  [SAFE SKIP] staging.stg_students already populated ({existing_students:,} rows).")
    else:
        if existing_students > 0:
            cur.execute("TRUNCATE TABLE staging.stg_students;")
        cur.execute("""
            INSERT INTO staging.stg_students (
                code_module, code_presentation, id_student, gender, region,
                highest_education, imd_band, age_band, num_of_prev_attempts,
                studied_credits, disability, final_result, date_registration, date_unregistration
            )
            SELECT 
                i.code_module, i.code_presentation, i.id_student, i.gender, i.region,
                i.highest_education, i.imd_band, i.age_band, i.num_of_prev_attempts,
                i.studied_credits, i.disability, i.final_result,
                r.date_registration, r.date_unregistration
            FROM bronze.raw_student_info i
            LEFT JOIN bronze.raw_student_registration r
              ON i.id_student = r.id_student
             AND i.code_module = r.code_module
             AND i.code_presentation = r.code_presentation;
        """)
        conn.commit()
        print(f"  [OK] staging.stg_students loaded ({cur.rowcount} rows).")

    # 3. Populate staging.stg_assessments (studentAssessment + assessments)
    print("Populating staging.stg_assessments (joining studentAssessment + assessments)...")
    cur.execute("SELECT COUNT(*) AS cnt FROM bronze.raw_student_assessment;")
    expected_ass = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM staging.stg_assessments;")
    existing_ass = cur.fetchone()["cnt"]

    if existing_ass == expected_ass and not reload:
        print(f"  [SAFE SKIP] staging.stg_assessments already populated ({existing_ass:,} rows).")
    else:
        if existing_ass > 0:
            cur.execute("TRUNCATE TABLE staging.stg_assessments;")
        cur.execute("""
            INSERT INTO staging.stg_assessments (
                id_assessment, id_student, code_module, code_presentation,
                assessment_type, assessment_date, weight, date_submitted, is_banked, score
            )
            SELECT 
                sa.id_assessment, sa.id_student, a.code_module, a.code_presentation,
                a.assessment_type, a.date, a.weight, sa.date_submitted, sa.is_banked, sa.score
            FROM bronze.raw_student_assessment sa
            JOIN bronze.raw_assessments a
              ON sa.id_assessment = a.id_assessment;
        """)
        conn.commit()
        print(f"  [OK] staging.stg_assessments loaded ({cur.rowcount} rows).")

    conn.close()
    print("[OK] Integrated staging tables populated.\n")


def reconcile_row_counts() -> bool:
    """Perform rigorous row-count reconciliation between CSV files and database tables."""
    print("=" * 70)
    print("STEP 4: ROW-COUNT RECONCILIATION AUDIT")
    print("=" * 70)
    raw_dir = PROJECT_ROOT / "data" / "raw"
    conn = get_raw_connection()
    cur = conn.cursor()

    checks = [
        {"file": "courses.csv", "table": "bronze.raw_courses"},
        {"file": "assessments.csv", "table": "bronze.raw_assessments"},
        {"file": "vle.csv", "table": "bronze.raw_vle"},
        {"file": "studentInfo.csv", "table": "bronze.raw_student_info"},
        {"file": "studentRegistration.csv", "table": "bronze.raw_student_registration"},
        {"file": "studentAssessment.csv", "table": "bronze.raw_student_assessment"},
        {"file": "studentVle.csv", "table": "bronze.raw_student_vle"},
        {"file": "courses.csv", "table": "staging.stg_courses"},
        {"file": "studentAssessment.csv", "table": "staging.stg_assessments"},
        {"file": "studentVle.csv", "table": "staging.stg_vle"}
    ]

    all_matched = True
    print(f"{'Source CSV':<23} | {'Target DB Table':<26} | {'CSV Rows':>10} | {'DB Rows':>10} | {'Status':<5}")
    print("-" * 80)

    for chk in checks:
        csv_file = raw_dir / chk["file"]
        csv_cnt = count_csv_lines(csv_file)
        
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {chk['table']};")
        db_cnt = cur.fetchone()["cnt"]
        
        match = (csv_cnt == db_cnt)
        status = "MATCH" if match else "DIFF"
        if not match:
            all_matched = False
            
        print(f"{chk['file']:<23} | {chk['table']:<26} | {csv_cnt:>10,} | {db_cnt:>10,} | {status:<5}")

    # Special check for staging.stg_students
    cur.execute("SELECT COUNT(*) AS cnt FROM staging.stg_students;")
    stg_stud_cnt = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM bronze.raw_student_info;")
    raw_info_cnt = cur.fetchone()["cnt"]
    stg_match = (stg_stud_cnt == raw_info_cnt)
    print(f"{'studentInfo.csv':<23} | {'staging.stg_students':<26} | {raw_info_cnt:>10,} | {stg_stud_cnt:>10,} | {'MATCH' if stg_match else 'DIFF':<5}")

    conn.close()
    print("-" * 80)
    if all_matched and stg_match:
        print("[SUCCESS] All row counts reconciled with 100% parity across CSVs and Database tables.\n")
        return True
    else:
        print("[FAIL] Row count discrepancy detected!\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Ingest Raw CSVs into Bronze and Staging")
    parser.add_argument("--reload", action="store_true", help="Force truncate existing tables and reload from scratch")
    args = parser.parse_args()

    start_total = time.time()
    create_schema_tables()
    load_all_bronze(reload=args.reload)
    populate_staging_tables(reload=args.reload)
    success = reconcile_row_counts()
    
    elapsed_total = time.time() - start_total
    print(f"Total Phase 2 execution time: {elapsed_total:.2f} seconds ({elapsed_total/60:.2f} minutes).")
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
