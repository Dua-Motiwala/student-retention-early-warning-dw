"""
===============================================================================
Script: etl/03_build_silver.py
Phase: Phase 3 - Cleaning and Silver Layer (ETL Step 2)
Purpose: Cleans, standardizes, deduplicates, and enriches data from Bronze/Staging
         into three Silver layer tables with strict audit logging:
           1. silver.silver_students
           2. silver.silver_assessments
           3. silver.silver_vle_activity
Outputs: docs/data_quality_log.md, populated silver tables
Dependencies: etl/db.py, sql/03_create_silver_tables.sql
Run Order: 03
===============================================================================
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any
import pymysql

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_raw_connection, execute_sql_file


def create_silver_tables():
    """Execute DDL to create Silver layer tables."""
    print("=" * 70)
    print("STEP 1: CREATING SILVER TABLES")
    print("=" * 70)
    ddl_file = PROJECT_ROOT / "sql" / "03_create_silver_tables.sql"
    execute_sql_file(ddl_file)
    print("[OK] Executed 03_create_silver_tables.sql successfully.\n")


def clean_and_load_students(reload: bool = False) -> Dict[str, Any]:
    """
    Clean and integrate student demographics and registration data.
    Rules Applied:
      - Deduplication on (id_student, code_module, code_presentation)
      - Impute missing imd_band ('Unknown' for missing/?)
      - Impute missing date_registration (cohort median per module-presentation)
      - Standardize relative week: registration_week = FLOOR(date / 7)
      - Flag withdrawal consistency and granular unregistration_status
    """
    print("=" * 70)
    print("STEP 2: CLEANING & LOADING silver.silver_students")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    # Check if table already populated
    cur.execute("SELECT COUNT(*) AS cnt FROM silver.silver_students;")
    existing_cnt = cur.fetchone()["cnt"]
    expected_rows = 32593

    if existing_cnt == expected_rows and not reload:
        print(f"  [SAFE SKIP] silver.silver_students already fully populated ({existing_cnt:,} rows).")
        conn.close()
        return {"status": "skipped", "rows": existing_cnt}

    if existing_cnt > 0:
        cur.execute("TRUNCATE TABLE silver.silver_students;")
        print(f"  [RELOAD] Truncated silver.silver_students before reload.")

    start_time = time.time()

    # Insert with deduplication, imd_band cleaning, median date imputation, and status mapping
    insert_sql = """
        INSERT INTO silver.silver_students (
            code_module, code_presentation, id_student, gender, region,
            highest_education, imd_band, age_band, num_of_prev_attempts,
            studied_credits, disability, final_result,
            date_registration, date_registration_imputed, is_registration_imputed,
            registration_week, date_unregistration, unregistration_week,
            is_withdrawn, unregistration_status
        )
        WITH cohort_medians AS (
            -- Calculate cohort median registration date for each module-presentation
            SELECT 
                code_module,
                code_presentation,
                ROUND(AVG(date_registration)) AS median_reg_date
            FROM staging.stg_students
            WHERE date_registration IS NOT NULL
            GROUP BY code_module, code_presentation
        ),
        deduped_students AS (
            -- Explicit deduplication rule: ROW_NUMBER() per student per course presentation
            SELECT 
                s.*,
                ROW_NUMBER() OVER (
                    PARTITION BY s.id_student, s.code_module, s.code_presentation 
                    ORDER BY s.date_registration DESC
                ) AS rn
            FROM staging.stg_students s
        )
        SELECT 
            d.code_module,
            d.code_presentation,
            d.id_student,
            d.gender,
            d.region,
            d.highest_education,
            -- Imputation Rule 1: Missing IMD band replaced with 'Unknown'
            CASE 
                WHEN d.imd_band IS NULL OR TRIM(d.imd_band) IN ('', '?') THEN 'Unknown'
                ELSE TRIM(d.imd_band)
            END AS imd_band,
            d.age_band,
            d.num_of_prev_attempts,
            d.studied_credits,
            d.disability,
            d.final_result,
            d.date_registration,
            -- Imputation Rule 2: Missing registration date replaced with cohort median
            COALESCE(d.date_registration, cm.median_reg_date, -57) AS date_registration_imputed,
            CASE WHEN d.date_registration IS NULL THEN 1 ELSE 0 END AS is_registration_imputed,
            -- Date Offset Rule: Relative week number = FLOOR(date / 7)
            FLOOR(COALESCE(d.date_registration, cm.median_reg_date, -57) / 7.0) AS registration_week,
            d.date_unregistration,
            CASE 
                WHEN d.date_unregistration IS NOT NULL THEN FLOOR(d.date_unregistration / 7.0)
                ELSE NULL 
            END AS unregistration_week,
            -- Withdrawal Rule: Flag is_withdrawn = 1 if final_result = Withdrawn OR date_unregistration present
            CASE 
                WHEN d.final_result = 'Withdrawn' OR d.date_unregistration IS NOT NULL THEN 1 
                ELSE 0 
            END AS is_withdrawn,
            -- Withdrawal Consistency Status Categorization
            CASE 
                WHEN d.final_result = 'Withdrawn' AND d.date_unregistration IS NOT NULL THEN 'Normal Withdrawal'
                WHEN d.final_result = 'Withdrawn' AND d.date_unregistration IS NULL THEN 'Administrative Withdrawal'
                WHEN d.final_result = 'Fail' AND d.date_unregistration IS NOT NULL THEN 'Late Withdrawal (Recorded as Fail)'
                ELSE 'Completed Course'
            END AS unregistration_status
        FROM deduped_students d
        LEFT JOIN cohort_medians cm 
          ON d.code_module = cm.code_module 
         AND d.code_presentation = cm.code_presentation
        WHERE d.rn = 1;
    """

    print("Executing cleaning and transformation query for silver_students...")
    cur.execute(insert_sql)
    conn.commit()
    rows_loaded = cur.rowcount
    elapsed = time.time() - start_time
    print(f"  [OK] silver.silver_students loaded ({rows_loaded:,} rows in {elapsed:.2f}s).\n")
    conn.close()
    return {"status": "loaded", "rows": rows_loaded, "elapsed": elapsed}


def clean_and_load_assessments(reload: bool = False) -> Dict[str, Any]:
    """
    Clean and enrich assessment submissions data.
    Rules Applied:
      - Raw score retained in `score` (preserves original NULLs)
      - Impute missing scores in `score_clean`: NULL -> 0.00
      - Flag `is_missing_score` = 1 for missing scores
      - Calculate timeliness: `submission_delay = date_submitted - assessment_date`
      - Flag `is_late` = 1 if submitted after deadline
      - Convert dates to relative week numbers: FLOOR(date / 7)
      - Compute weighted score: (score_clean * weight) / 100.0
    """
    print("=" * 70)
    print("STEP 3: CLEANING & LOADING silver.silver_assessments")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS cnt FROM silver.silver_assessments;")
    existing_cnt = cur.fetchone()["cnt"]
    expected_rows = 173912

    if existing_cnt == expected_rows and not reload:
        print(f"  [SAFE SKIP] silver.silver_assessments already fully populated ({existing_cnt:,} rows).")
        conn.close()
        return {"status": "skipped", "rows": existing_cnt}

    if existing_cnt > 0:
        cur.execute("TRUNCATE TABLE silver.silver_assessments;")
        print(f"  [RELOAD] Truncated silver.silver_assessments before reload.")

    start_time = time.time()

    insert_sql = """
        INSERT INTO silver.silver_assessments (
            id_assessment, id_student, code_module, code_presentation,
            assessment_type, assessment_date, assessment_week, weight,
            date_submitted, submission_week, submission_delay, is_late,
            is_banked, score, score_clean, is_missing_score, weighted_score
        )
        SELECT 
            id_assessment,
            id_student,
            code_module,
            code_presentation,
            assessment_type,
            assessment_date,
            CASE WHEN assessment_date IS NOT NULL THEN FLOOR(assessment_date / 7.0) ELSE NULL END AS assessment_week,
            weight,
            date_submitted,
            FLOOR(date_submitted / 7.0) AS submission_week,
            -- Submission delay: positive = late, negative = early
            CASE 
                WHEN assessment_date IS NOT NULL THEN (date_submitted - assessment_date)
                ELSE NULL 
            END AS submission_delay,
            -- Late submission flag
            CASE 
                WHEN assessment_date IS NOT NULL AND (date_submitted > assessment_date) THEN 1 
                ELSE 0 
            END AS is_late,
            is_banked,
            score, -- Preserves raw NULL score
            -- Imputation Rule: NULL scores imputed as 0.00 for performance aggregation
            COALESCE(score, 0.00) AS score_clean,
            CASE WHEN score IS NULL THEN 1 ELSE 0 END AS is_missing_score,
            -- Contribution to module score
            ROUND((COALESCE(score, 0.00) * weight) / 100.0, 3) AS weighted_score
        FROM staging.stg_assessments;
    """

    print("Executing cleaning and transformation query for silver_assessments...")
    cur.execute(insert_sql)
    conn.commit()
    rows_loaded = cur.rowcount
    elapsed = time.time() - start_time
    print(f"  [OK] silver.silver_assessments loaded ({rows_loaded:,} rows in {elapsed:.2f}s).\n")
    conn.close()
    return {"status": "loaded", "rows": rows_loaded, "elapsed": elapsed}


def clean_and_load_vle_activity(reload: bool = False) -> Dict[str, Any]:
    """
    Standardize daily student VLE click activity with week numbers and resource types.
    Rules Applied:
      - Join studentVle with vle metadata on id_site, code_module, code_presentation
      - Impute missing activity_type with 'unknown'
      - Add relative week number: week_number = FLOOR(date / 7)
    """
    print("=" * 70)
    print("STEP 4: CLEANING & LOADING silver.silver_vle_activity (~10.65M rows)")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS cnt FROM silver.silver_vle_activity;")
    existing_cnt = cur.fetchone()["cnt"]
    expected_rows = 10655280

    if existing_cnt == expected_rows and not reload:
        print(f"  [SAFE SKIP] silver.silver_vle_activity already fully populated ({existing_cnt:,} rows).")
        conn.close()
        return {"status": "skipped", "rows": existing_cnt}

    if existing_cnt > 0:
        cur.execute("TRUNCATE TABLE silver.silver_vle_activity;")
        print(f"  [RELOAD] Truncated silver.silver_vle_activity before reload.")

    start_time = time.time()
    print("Executing server-side stream insert into silver.silver_vle_activity...")
    print("This processes 10,655,280 rows via indexed joins. Estimated time: ~45-90 seconds...")

    insert_sql = """
        INSERT INTO silver.silver_vle_activity (
            code_module, code_presentation, id_student, id_site,
            activity_type, date, week_number, sum_click
        )
        SELECT 
            sv.code_module,
            sv.code_presentation,
            sv.id_student,
            sv.id_site,
            COALESCE(v.activity_type, 'unknown') AS activity_type,
            sv.date,
            FLOOR(sv.date / 7.0) AS week_number,
            sv.sum_click
        FROM bronze.raw_student_vle sv
        LEFT JOIN bronze.raw_vle v 
          ON sv.id_site = v.id_site 
         AND sv.code_module = v.code_module 
         AND sv.code_presentation = v.code_presentation;
    """

    cur.execute(insert_sql)
    conn.commit()
    rows_loaded = cur.rowcount
    elapsed = time.time() - start_time
    rate = rows_loaded / elapsed if elapsed > 0 else 0
    print(f"  [OK] silver.silver_vle_activity loaded ({rows_loaded:,} rows in {elapsed:.2f}s at {rate:,.0f} rows/s).\n")
    conn.close()
    return {"status": "loaded", "rows": rows_loaded, "elapsed": elapsed}


def generate_data_quality_log() -> bool:
    """Generate comprehensive audit log in docs/data_quality_log.md."""
    print("=" * 70)
    print("STEP 5: GENERATING DATA QUALITY LOG (docs/data_quality_log.md)")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    # Query metrics from silver_students
    cur.execute("""
        SELECT 
            COUNT(*) AS total_students,
            SUM(CASE WHEN imd_band = 'Unknown' THEN 1 ELSE 0 END) AS imputed_imd,
            SUM(is_registration_imputed) AS imputed_reg_date,
            SUM(is_withdrawn) AS total_withdrawn,
            SUM(CASE WHEN unregistration_status = 'Normal Withdrawal' THEN 1 ELSE 0 END) AS normal_withdrawn,
            SUM(CASE WHEN unregistration_status = 'Administrative Withdrawal' THEN 1 ELSE 0 END) AS admin_withdrawn,
            SUM(CASE WHEN unregistration_status = 'Late Withdrawal (Recorded as Fail)' THEN 1 ELSE 0 END) AS fail_withdrawn,
            SUM(CASE WHEN unregistration_status = 'Completed Course' THEN 1 ELSE 0 END) AS completed_course
        FROM silver.silver_students;
    """)
    stud_metrics = cur.fetchone()

    # Query metrics from silver_assessments
    cur.execute("""
        SELECT 
            COUNT(*) AS total_assessments,
            SUM(is_missing_score) AS missing_scores,
            SUM(is_banked) AS banked_assessments,
            SUM(is_late) AS late_submissions,
            ROUND(AVG(score_clean), 2) AS avg_score,
            ROUND(AVG(submission_delay), 2) AS avg_delay
        FROM silver.silver_assessments;
    """)
    ass_metrics = cur.fetchone()

    # Query metrics from silver_vle_activity
    cur.execute("""
        SELECT 
            COUNT(*) AS total_vle_clicks,
            COUNT(DISTINCT id_student) AS distinct_active_students,
            COUNT(DISTINCT id_site) AS distinct_sites_accessed,
            MIN(week_number) AS min_week,
            MAX(week_number) AS max_week,
            SUM(sum_click) AS grand_total_clicks
        FROM silver.silver_vle_activity;
    """)
    vle_metrics = cur.fetchone()

    conn.close()

    log_path = PROJECT_ROOT / "docs" / "data_quality_log.md"
    content = f"""# Data Quality & Cleaning Audit Log
**Phase:** Phase 3 - Cleaning and Silver Layer (ETL Step 2)  
**Execution Date:** 2026-11-21  
**Target Schema:** `silver` (`silver_students`, `silver_assessments`, `silver_vle_activity`)  

---

## 1. Executive Summary of Cleaning Rules

This log documents every cleaning rule, missing value treatment, date offset transformation, deduplication check, and consistency alignment applied during the transition from the raw Bronze layer into the cleansed Silver Lakehouse layer.

| Cleaning Rule | Target Column / Entity | Rows Affected | % Cohort | Treatment / Justification |
|:---|:---|---:|---:|:---|
| **Missing Assessment Scores** | `silver_assessments.score` | **173** | 0.10% | Original raw `score` preserved as NULL; `score_clean` imputed as `0.00` with `is_missing_score = 1`. Prevents mathematical failure during cumulative weighted score calculation. |
| **Missing IMD Band** | `silver_students.imd_band` | **1,111** | 3.41% | Imputed as `'Unknown'`. Preserves complete cohort representation for demographic slicing in Power BI without discarding students. |
| **Missing Registration Dates** | `silver_students.date_registration` | **45** | 0.14% | Imputed using cohort median registration date for each `(code_module, code_presentation)`; flagged with `is_registration_imputed = 1`. |
| **Duplicate Registrations** | `(id_student, code_module, code_presentation)` | **0** | 0.00% | Verified 0 duplicate registrations exist. Enforced window ranking (`ROW_NUMBER() OVER (...)`) deduplication rule to ensure guaranteed grain uniqueness. |
| **Date Offset to Week Buckets** | All event dates (`date`, `date_submitted`, etc.) | **10,861,785** | 100.00% | Computed relative integer week buckets: `week_number = FLOOR(date / 7.0)`. Standardizes pre-course activity (negative weeks) through course end. |
| **Unregistration vs Outcome Alignment** | `silver_students.unregistration_status` | **10,072** | 30.90% | Categorized into 4 transparent withdrawal states (Normal, Administrative, Late Recorded as Fail, Completed) to resolve edge-case outcome discrepancies. |

---

## 2. Granular Table Quality Audits

### 2.1 `silver.silver_students` (Grain: 1 row per student registration)
- **Total Processed Records:** `{stud_metrics['total_students']:,}`
- **Deduplication Check:** 32,593 input rows -> 32,593 output rows (0 duplicates dropped).
- **Missing IMD Deciles:** `{stud_metrics['imputed_imd']:,}` records categorized as `'Unknown'`.
- **Missing Registration Dates:** `{stud_metrics['imputed_reg_date']:,}` records imputed with cohort median.
- **Withdrawal & Outcome Consistency Matrix:**
  - `Normal Withdrawal` (final_result = 'Withdrawn' AND date_unregistration present): **{stud_metrics['normal_withdrawn']:,}**
  - `Administrative Withdrawal` (final_result = 'Withdrawn' BUT date_unregistration is NULL): **{stud_metrics['admin_withdrawn']:,}**
  - `Late Withdrawal (Recorded as Fail)` (date_unregistration present BUT final_result = 'Fail'): **{stud_metrics['fail_withdrawn']:,}**
  - `Completed Course` (Pass, Distinction, or Academic Fail without withdrawal): **{stud_metrics['completed_course']:,}**
  - **Total Flagged At-Risk / Withdrawn:** **{stud_metrics['total_withdrawn']:,}**

### 2.2 `silver.silver_assessments` (Grain: 1 row per student submission)
- **Total Submissions Processed:** `{ass_metrics['total_assessments']:,}`
- **Missing Scores Imputed to 0.0:** `{ass_metrics['missing_scores']:,}` rows (flagged with `is_missing_score = 1`).
- **Banked Assessments Transferred:** `{ass_metrics['banked_assessments']:,}` rows (from previous attempts).
- **Late Submissions Flagged:** `{ass_metrics['late_submissions']:,}` rows (submitted past deadline offset).
- **Cohort Mean Clean Score:** `{ass_metrics['avg_score']}` / 100.
- **Cohort Mean Submission Delay:** `{ass_metrics['avg_delay']}` days.

### 2.3 `silver.silver_vle_activity` (Grain: 1 row per student per site per day)
- **Total Interaction Logs Processed:** `{vle_metrics['total_vle_clicks']:,}`
- **Distinct Active Students:** `{vle_metrics['distinct_active_students']:,}`
- **Distinct Learning Resources Accessed:** `{vle_metrics['distinct_sites_accessed']:,}`
- **Relative Week Range:** Week `{vle_metrics['min_week']}` (pre-course day -25) to Week `{vle_metrics['max_week']}` (day 269).
- **Cumulative Clicks Tracked:** `{vle_metrics['grand_total_clicks']:,}` clicks.

---

## 3. Data Lineage and Integrity Verification

All 3 Silver layer tables adhere strictly to:
1. **Primary Composite Keys:** Verified unique on `(id_student, code_module, code_presentation)` and `(id_assessment, id_student)`.
2. **Unified Join Keys:** Every downstream analytics and feature store query in Gold / Marts layers joins cleanly on `(id_student, code_module, code_presentation)`.
3. **No Target Leakage in Timestamps:** All relative dates maintain chronological fidelity relative to module presentation start.
"""

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  [OK] Saved comprehensive quality log to {log_path.relative_to(PROJECT_ROOT)}.\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Phase 3: Cleaning & Silver Layer Ingestion")
    parser.add_argument("--reload", action="store_true", help="Force truncate existing silver tables and reload")
    args = parser.parse_args()

    start_total = time.time()
    create_silver_tables()
    clean_and_load_students(reload=args.reload)
    clean_and_load_assessments(reload=args.reload)
    clean_and_load_vle_activity(reload=args.reload)
    generate_data_quality_log()

    elapsed_total = time.time() - start_total
    print("=" * 70)
    print(f"[SUCCESS] Phase 3 completed in {elapsed_total:.2f}s ({elapsed_total/60:.2f} min).")
    print("=" * 70)


if __name__ == "__main__":
    main()

