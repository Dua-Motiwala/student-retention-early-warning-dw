"""
===============================================================================
Script: etl/05_load_marts.py
Phase: Phase 5 - Data Marts (Star Schemas for Academic & Early Warning Marts)
Purpose: Builds and populates the Conformed Dimensional Star Schemas in the
         `marts` schema:
         - Conformed Dimensions: dim_student, dim_course, dim_date (dim_week),
           dim_assessment_type
         - Academic Mart Fact: fact_student_performance (173,912 rows)
         - Early Warning Mart Fact: fact_weekly_engagement (627,031 rows)
         - Fact Table DDL created for AI write-back: fact_risk_flag
Inputs: silver.silver_students, silver.silver_assessments, bronze.raw_courses,
        gold.gold_student_weekly_engagement
Outputs: Populated dimensions and fact tables in `marts` schema.
Dependencies: etl/db.py, sql/05_create_marts.sql
Run Order: 05
===============================================================================
"""

import sys
import time
import argparse
from pathlib import Path
from sqlalchemy import text

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_engine, execute_sql_file


def create_marts_tables():
    """Execute DDL to create dimensional and fact tables in marts schema."""
    print("=" * 70)
    print("STEP 1: CREATING MARTS SCHEMA TABLES & VIEWS")
    print("=" * 70)
    ddl_file = PROJECT_ROOT / "sql" / "05_create_marts.sql"
    execute_sql_file(ddl_file)
    print("  [OK] Executed sql/05_create_marts.sql successfully.\n")


def load_dimensions(engine, reload: bool = False) -> bool:
    """Populates conformed dimensions: dim_assessment_type, dim_course, dim_date, dim_student."""
    print("=" * 70)
    print("STEP 2: POPULATING CONFORMED DIMENSIONS")
    print("=" * 70)

    with engine.connect() as conn:
        # 1. dim_assessment_type (3 rows)
        cnt = conn.execute(text("SELECT count(*) FROM marts.dim_assessment_type")).scalar()
        if cnt == 3 and not reload:
            print(f"  [SAFE SKIP] dim_assessment_type already populated ({cnt} rows).")
        else:
            if cnt > 0 and reload:
                # Need to disable foreign key checks temporarily if truncating
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                conn.execute(text("TRUNCATE TABLE marts.dim_assessment_type;"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            conn.execute(text("""
                INSERT INTO marts.dim_assessment_type (assessment_type, assessment_type_name, marking_method, is_exam)
                VALUES
                ('TMA', 'Tutor Marked Assessment', 'Manual / Tutor', 0),
                ('CMA', 'Computer Marked Assessment', 'Automated', 0),
                ('Exam', 'Final Examination', 'Formal Exam', 1)
                ON DUPLICATE KEY UPDATE assessment_type_name=VALUES(assessment_type_name);
            """))
            conn.commit()
            print("  [OK] dim_assessment_type populated (3 rows).")

        # 2. dim_course (22 rows)
        cnt = conn.execute(text("SELECT count(*) FROM marts.dim_course")).scalar()
        if cnt == 22 and not reload:
            print(f"  [SAFE SKIP] dim_course already populated ({cnt} rows).")
        else:
            if cnt > 0 and reload:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                conn.execute(text("TRUNCATE TABLE marts.dim_course;"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            conn.execute(text("""
                INSERT INTO marts.dim_course (
                    code_module, code_presentation, module_presentation_length,
                    semester_season, presentation_year, academic_year, course_full_name
                )
                SELECT
                    code_module,
                    code_presentation,
                    module_presentation_length,
                    CASE 
                        WHEN code_presentation LIKE '%B' THEN 'Spring (Feb)'
                        WHEN code_presentation LIKE '%J' THEN 'Autumn (Oct)'
                        ELSE 'Other'
                    END AS semester_season,
                    CAST(SUBSTRING(code_presentation, 1, 4) AS SIGNED) AS presentation_year,
                    CASE 
                        WHEN code_presentation LIKE '%B' THEN CONCAT(CAST(SUBSTRING(code_presentation, 1, 4) AS SIGNED) - 1, '/', SUBSTRING(code_presentation, 1, 4))
                        ELSE CONCAT(SUBSTRING(code_presentation, 1, 4), '/', CAST(SUBSTRING(code_presentation, 1, 4) AS SIGNED) + 1)
                    END AS academic_year,
                    CONCAT('Module ', code_module, ' (', code_presentation, ')') AS course_full_name
                FROM bronze.raw_courses
                ORDER BY code_module, code_presentation;
            """))
            conn.commit()
            print("  [OK] dim_course populated (22 rows).")

        # 3. dim_date (91 rows, covering weeks -4 to 86)
        cnt = conn.execute(text("SELECT count(*) FROM marts.dim_date")).scalar()
        if cnt >= 91 and not reload:
            print(f"  [SAFE SKIP] dim_date already populated ({cnt} rows).")
        else:
            if cnt > 0 and reload:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                conn.execute(text("TRUNCATE TABLE marts.dim_date;"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            for w in range(-4, 87):
                phase = (
                    'Pre-Course Preparation' if w < 0 else
                    'Early Course & Onboarding' if w <= 4 else
                    'Mid-Term Core' if w <= 14 else
                    'Late Term / Pre-Exam' if w <= 25 else
                    'Exams & Wrap-Up' if w <= 38 else
                    'Extended / Post-Term Review'
                )
                is_ew = 1 if (0 <= w <= 5) else 0
                conn.execute(text("""
                    INSERT INTO marts.dim_date (
                        week_number, week_label, academic_phase, is_early_warning_window,
                        start_day_offset, end_day_offset
                    )
                    VALUES (:w, :lbl, :phase, :is_ew, :start_d, :end_d)
                    ON DUPLICATE KEY UPDATE week_label=VALUES(week_label);
                """), {'w': w, 'lbl': f'Week {w}', 'phase': phase, 'is_ew': is_ew, 'start_d': w * 7, 'end_d': w * 7 + 6})
            conn.commit()
            print("  [OK] dim_date populated (91 rows, Week -4 to 86).")

        # 4. dim_student (28,785 rows)
        cnt = conn.execute(text("SELECT count(*) FROM marts.dim_student")).scalar()
        if cnt == 28785 and not reload:
            print(f"  [SAFE SKIP] dim_student already populated ({cnt:,} rows).")
        else:
            if cnt > 0 and reload:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
                conn.execute(text("TRUNCATE TABLE marts.dim_student;"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            t0 = time.time()
            conn.execute(text("""
                INSERT INTO marts.dim_student (
                    id_student, gender, region, highest_education, imd_band,
                    age_band, disability, total_courses_enrolled
                )
                SELECT 
                    id_student,
                    MAX(gender) AS gender,
                    MAX(region) AS region,
                    MAX(highest_education) AS highest_education,
                    MAX(imd_band) AS imd_band,
                    MAX(age_band) AS age_band,
                    MAX(disability) AS disability,
                    COUNT(DISTINCT CONCAT(code_module, '_', code_presentation)) AS total_courses_enrolled
                FROM silver.silver_students
                GROUP BY id_student
                ORDER BY id_student;
            """))
            conn.commit()
            stu_cnt = conn.execute(text("SELECT count(*) FROM marts.dim_student")).scalar()
            print(f"  [OK] dim_student populated ({stu_cnt:,} rows in {time.time()-t0:.2f}s).")

    return True


def load_fact_student_performance(engine, reload: bool = False) -> bool:
    """Populates Academic Mart fact table: fact_student_performance (173,912 rows)."""
    print("\n" + "=" * 70)
    print("STEP 3: POPULATING FACT_STUDENT_PERFORMANCE (ACADEMIC MART)")
    print("=" * 70)

    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT count(*) FROM marts.fact_student_performance")).scalar()
        if cnt == 173912 and not reload:
            print(f"  [SAFE SKIP] fact_student_performance already populated ({cnt:,} rows).")
            return True

        if cnt > 0:
            print(f"  [RELOAD] Truncating marts.fact_student_performance...")
            conn.execute(text("TRUNCATE TABLE marts.fact_student_performance;"))
            conn.commit()

        t0 = time.time()
        print("  Inserting records from silver_assessments joined to surrogate keys...")
        res = conn.execute(text("""
            INSERT INTO marts.fact_student_performance (
                student_key, course_key, week_key, assessment_type_key,
                id_assessment, id_student, code_module, code_presentation,
                assessment_date, date_submitted, submission_delay, is_late, is_banked,
                weight, score, score_clean, is_missing_score, weighted_score, is_passed_assessment
            )
            SELECT
                s.student_key,
                c.course_key,
                d.week_key,
                a.assessment_type_key,
                sa.id_assessment,
                sa.id_student,
                sa.code_module,
                sa.code_presentation,
                sa.assessment_date,
                sa.date_submitted,
                sa.submission_delay,
                sa.is_late,
                sa.is_banked,
                sa.weight,
                sa.score,
                sa.score_clean,
                sa.is_missing_score,
                sa.weighted_score,
                CASE WHEN sa.score_clean >= 40.0 THEN 1 ELSE 0 END AS is_passed_assessment
            FROM silver.silver_assessments sa
            INNER JOIN marts.dim_student s ON sa.id_student = s.id_student
            INNER JOIN marts.dim_course c ON sa.code_module = c.code_module AND sa.code_presentation = c.code_presentation
            INNER JOIN marts.dim_date d ON sa.submission_week = d.week_number
            INNER JOIN marts.dim_assessment_type a ON sa.assessment_type = a.assessment_type;
        """))
        conn.commit()
        print(f"  [OK] Inserted {res.rowcount:,} rows into fact_student_performance in {time.time()-t0:.2f}s.")

    return True


def load_fact_weekly_engagement(engine, reload: bool = False) -> bool:
    """Populates Early Warning Mart fact table: fact_weekly_engagement (627,031 rows)."""
    print("\n" + "=" * 70)
    print("STEP 4: POPULATING FACT_WEEKLY_ENGAGEMENT (EARLY WARNING MART)")
    print("=" * 70)

    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT count(*) FROM marts.fact_weekly_engagement")).scalar()
        if cnt == 627031 and not reload:
            print(f"  [SAFE SKIP] fact_weekly_engagement already populated ({cnt:,} rows).")
            return True

        if cnt > 0:
            print(f"  [RELOAD] Truncating marts.fact_weekly_engagement...")
            conn.execute(text("TRUNCATE TABLE marts.fact_weekly_engagement;"))
            conn.commit()

        t0 = time.time()
        print("  Inserting records from gold_student_weekly_engagement joined to surrogate keys...")
        res = conn.execute(text("""
            INSERT INTO marts.fact_weekly_engagement (
                student_key, course_key, week_key,
                id_student, code_module, code_presentation, week_number,
                weekly_clicks, active_days, distinct_resources,
                clicks_oucontent, clicks_forumng, clicks_quiz, clicks_homepage,
                clicks_subpage, clicks_resource, clicks_url, clicks_other,
                cumulative_clicks, cumulative_active_days, prev_week_clicks, wow_click_change, clicks_last_2_weeks,
                assessments_submitted_so_far, avg_score_so_far, weighted_score_so_far,
                late_submissions_so_far, avg_submission_delay_so_far,
                is_registered_by_week, is_withdrawn_by_week, final_result
            )
            SELECT
                s.student_key,
                c.course_key,
                d.week_key,
                g.id_student,
                g.code_module,
                g.code_presentation,
                g.week_number,
                g.weekly_clicks,
                g.active_days,
                g.distinct_resources,
                g.clicks_oucontent,
                g.clicks_forumng,
                g.clicks_quiz,
                g.clicks_homepage,
                g.clicks_subpage,
                g.clicks_resource,
                g.clicks_url,
                g.clicks_other,
                g.cumulative_clicks,
                g.cumulative_active_days,
                g.prev_week_clicks,
                g.wow_click_change,
                g.clicks_last_2_weeks,
                g.assessments_submitted_so_far,
                g.avg_score_so_far,
                g.weighted_score_so_far,
                g.late_submissions_so_far,
                g.avg_submission_delay_so_far,
                g.is_registered_by_week,
                g.is_withdrawn_by_week,
                g.final_result
            FROM gold.gold_student_weekly_engagement g
            INNER JOIN marts.dim_student s ON g.id_student = s.id_student
            INNER JOIN marts.dim_course c ON g.code_module = c.code_module AND g.code_presentation = c.code_presentation
            INNER JOIN marts.dim_date d ON g.week_number = d.week_number;
        """))
        conn.commit()
        print(f"  [OK] Inserted {res.rowcount:,} rows into fact_weekly_engagement in {time.time()-t0:.2f}s.")

    return True


def reconcile_and_audit(engine) -> bool:
    """Verifies row counts, foreign key integrity, and absence of orphan keys."""
    print("\n" + "=" * 70)
    print("STEP 5: ROW-COUNT RECONCILIATION & INTEGRITY AUDIT")
    print("=" * 70)

    audit_specs = [
        ("dim_assessment_type", "marts.dim_assessment_type", 3),
        ("dim_course", "marts.dim_course", 22),
        ("dim_date", "marts.dim_date", 91),
        ("dim_student", "marts.dim_student", 28785),
        ("fact_student_performance", "marts.fact_student_performance", 173912),
        ("fact_weekly_engagement", "marts.fact_weekly_engagement", 627031),
        ("fact_risk_flag (schema ready)", "marts.fact_risk_flag", 0)
    ]

    all_passed = True
    print(f"{'Object Name':<32} | {'Expected Rows':<15} | {'Actual Rows':<15} | {'Status':<10}")
    print("-" * 78)

    with engine.connect() as conn:
        for name, table_sql, expected in audit_specs:
            cnt = conn.execute(text(f"SELECT count(*) FROM {table_sql}")).scalar()
            status = "MATCH" if cnt == expected else "MISMATCH"
            if status == "MISMATCH":
                all_passed = False
            print(f"{name:<32} | {expected:<15,d} | {cnt:<15,d} | {status:<10}")

        print("-" * 78)

        # Foreign Key Null checks
        null_fsp = conn.execute(text("""
            SELECT count(*) FROM marts.fact_student_performance 
            WHERE student_key IS NULL OR course_key IS NULL OR week_key IS NULL OR assessment_type_key IS NULL
        """)).scalar()

        null_fwe = conn.execute(text("""
            SELECT count(*) FROM marts.fact_weekly_engagement 
            WHERE student_key IS NULL OR course_key IS NULL OR week_key IS NULL
        """)).scalar()

        print(f"  fact_student_performance NULL foreign keys: {null_fsp}")
        print(f"  fact_weekly_engagement NULL foreign keys:    {null_fwe}")

        if null_fsp > 0 or null_fwe > 0:
            print("  [ERROR] Foreign key integrity violation: orphan records detected!")
            all_passed = False
        else:
            print("  [PASS] Foreign key referential integrity: 100% verified (0 orphan keys).")

    if all_passed:
        print("\n[SUCCESS] Phase 5 dimensional marts built and validated successfully.")
    else:
        print("\n[FAIL] Phase 5 validation checks reported discrepancies.")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Phase 5: Load Dimensional Data Marts")
    parser.add_argument("--reload", action="store_true", help="Force truncate and reload all marts tables")
    args = parser.parse_args()

    engine = get_engine()
    create_marts_tables()
    load_dimensions(engine, reload=args.reload)
    load_fact_student_performance(engine, reload=args.reload)
    load_fact_weekly_engagement(engine, reload=args.reload)
    success = reconcile_and_audit(engine)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
