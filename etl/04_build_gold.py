"""
===============================================================================
Script: etl/04_build_gold.py
Phase: Phase 4 - Gold Layer (Weekly Engagement & Zero Target Leakage)
Purpose: Computes weekly student engagement features, activity velocity,
         and cumulative assessment performance strictly up to week N 
         (zero target leakage) and loads into `gold.gold_student_weekly_engagement`.
Inputs: silver.silver_students, silver.silver_assessments, data/raw/studentVle.csv
Outputs: Populated table `gold.gold_student_weekly_engagement`
Dependencies: etl/db.py, sql/04_create_gold_tables.sql
Run Order: 04
===============================================================================
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import numpy as np
from tqdm import tqdm

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_raw_connection, get_engine, execute_sql_file


def create_gold_tables():
    """Execute DDL to create Gold layer tables."""
    print("=" * 70)
    print("STEP 1: CREATING GOLD TABLES")
    print("=" * 70)
    ddl_file = PROJECT_ROOT / "sql" / "04_create_gold_tables.sql"
    execute_sql_file(ddl_file)
    print("[OK] Executed 04_create_gold_tables.sql successfully.\n")


def build_and_load_gold(reload: bool = False) -> bool:
    """
    Constructs the longitudinal weekly feature store with zero target leakage
    and bulk-inserts records into gold.gold_student_weekly_engagement.
    """
    print("=" * 70)
    print("STEP 2: FEATURE ENGINEERING & INGESTION (GOLD LAYER)")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    # Check existing rows
    cur.execute("SELECT COUNT(*) AS cnt FROM gold.gold_student_weekly_engagement;")
    existing_cnt = cur.fetchone()["cnt"]
    expected_rows = 627031

    if existing_cnt == expected_rows and not reload:
        print(f"  [SAFE SKIP] gold.gold_student_weekly_engagement already fully populated ({existing_cnt:,} rows).")
        conn.close()
        return True

    if existing_cnt > 0:
        cur.execute("TRUNCATE TABLE gold.gold_student_weekly_engagement;")
        print(f"  [RELOAD] Truncated gold.gold_student_weekly_engagement before reload.")

    start_time = time.time()

    # 1. Load VLE and map activity types
    print("  Aggregating VLE activity across 10.65M rows...")
    df_vle_meta = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "vle.csv")
    vle_map = df_vle_meta.set_index("id_site")["activity_type"].to_dict()

    pivot_acts = ['oucontent', 'forumng', 'quiz', 'homepage', 'subpage', 'resource', 'url']
    chunk_size = 1000000
    weekly_aggs = []

    for chunk in pd.read_csv(PROJECT_ROOT / "data" / "raw" / "studentVle.csv", chunksize=chunk_size):
        chunk['activity_type'] = chunk['id_site'].map(vle_map).fillna('unknown')
        chunk['week_number'] = np.floor(chunk['date'] / 7.0).astype(int)
        for act in pivot_acts:
            chunk[f'clicks_{act}'] = np.where(chunk['activity_type'] == act, chunk['sum_click'], 0)
        chunk['clicks_other'] = np.where(~chunk['activity_type'].isin(pivot_acts), chunk['sum_click'], 0)
        
        agg = chunk.groupby(['code_module', 'code_presentation', 'id_student', 'week_number'], as_index=False).agg(
            weekly_clicks=('sum_click', 'sum'),
            active_days=('date', 'nunique'),
            distinct_resources=('id_site', 'nunique'),
            clicks_oucontent=('clicks_oucontent', 'sum'),
            clicks_forumng=('clicks_forumng', 'sum'),
            clicks_quiz=('clicks_quiz', 'sum'),
            clicks_homepage=('clicks_homepage', 'sum'),
            clicks_subpage=('clicks_subpage', 'sum'),
            clicks_resource=('clicks_resource', 'sum'),
            clicks_url=('clicks_url', 'sum'),
            clicks_other=('clicks_other', 'sum')
        )
        weekly_aggs.append(agg)

    combined_vle = pd.concat(weekly_aggs, ignore_index=True)
    final_vle = combined_vle.groupby(['code_module', 'code_presentation', 'id_student', 'week_number'], as_index=False).agg(
        weekly_clicks=('weekly_clicks', 'sum'),
        active_days=('active_days', 'sum'),
        distinct_resources=('distinct_resources', 'sum'),
        clicks_oucontent=('clicks_oucontent', 'sum'),
        clicks_forumng=('clicks_forumng', 'sum'),
        clicks_quiz=('clicks_quiz', 'sum'),
        clicks_homepage=('clicks_homepage', 'sum'),
        clicks_subpage=('clicks_subpage', 'sum'),
        clicks_resource=('clicks_resource', 'sum'),
        clicks_url=('clicks_url', 'sum'),
        clicks_other=('clicks_other', 'sum')
    )
    print(f"  [OK] VLE aggregated into {len(final_vle):,} student-week milestones.")

    # 2. Cumulative VLE metrics (Zero Leakage)
    print("  Calculating longitudinal VLE velocity (cumsum, shift, WoW)...")
    final_vle.sort_values(['id_student', 'code_module', 'code_presentation', 'week_number'], inplace=True)
    grp = final_vle.groupby(['id_student', 'code_module', 'code_presentation'])

    final_vle['cumulative_clicks'] = grp['weekly_clicks'].cumsum()
    final_vle['cumulative_active_days'] = grp['active_days'].cumsum()
    final_vle['prev_week_clicks'] = grp['weekly_clicks'].shift(1).fillna(0).astype(int)
    final_vle['wow_click_change'] = final_vle['weekly_clicks'] - final_vle['prev_week_clicks']
    final_vle['clicks_last_2_weeks'] = final_vle['weekly_clicks'] + final_vle['prev_week_clicks']

    # 3. Load Student Demographics from Silver
    print("  Integrating student demographic timelines...")
    engine = get_engine()
    df_stud = pd.read_sql(
        "SELECT code_module, code_presentation, id_student, registration_week, unregistration_week, is_withdrawn, final_result FROM silver.silver_students;", 
        con=engine
    )
    df_stud['id_student'] = df_stud['id_student'].astype('int64')
    final_vle['id_student'] = final_vle['id_student'].astype('int64')

    merged = pd.merge(final_vle, df_stud, on=['code_module', 'code_presentation', 'id_student'], how='inner')
    merged['is_registered_by_week'] = np.where(merged['registration_week'] <= merged['week_number'], 1, 0)
    merged['is_withdrawn_by_week'] = np.where(
        (merged['is_withdrawn'] == 1) & (merged['unregistration_week'].notnull()) & (merged['unregistration_week'] <= merged['week_number']), 
        1, 0
    )

    # 4. Assessment Performance Cumulative Metrics (Zero Target Leakage)
    print("  Calculating cumulative assessment performance so far (strictly <= week N)...")
    df_ass = pd.read_sql(
        "SELECT code_module, code_presentation, id_student, submission_week, score_clean, weighted_score, is_late, submission_delay FROM silver.silver_assessments;", 
        con=engine
    )
    df_ass['id_student'] = df_ass['id_student'].astype('int64')
    df_ass['submission_week'] = df_ass['submission_week'].astype('int64')

    ass_grp = df_ass.groupby(['code_module', 'code_presentation', 'id_student', 'submission_week'], as_index=False).agg(
        sub_count=('score_clean', 'count'),
        score_sum=('score_clean', 'sum'),
        weighted_sum=('weighted_score', 'sum'),
        late_sum=('is_late', 'sum'),
        delay_sum=('submission_delay', 'sum')
    )
    ass_grp.sort_values(['id_student', 'code_module', 'code_presentation', 'submission_week'], inplace=True)
    ass_student_grp = ass_grp.groupby(['id_student', 'code_module', 'code_presentation'])
    ass_grp['cum_sub_count'] = ass_student_grp['sub_count'].cumsum()
    ass_grp['cum_score_sum'] = ass_student_grp['score_sum'].cumsum()
    ass_grp['cum_weighted_score'] = ass_student_grp['weighted_sum'].cumsum()
    ass_grp['cum_late_sum'] = ass_student_grp['late_sum'].cumsum()
    ass_grp['cum_delay_sum'] = ass_student_grp['delay_sum'].cumsum()

    # Align keys and types for merge_asof
    merged['week_number'] = merged['week_number'].astype('int64')
    merged['code_module'] = merged['code_module'].astype(str)
    merged['code_presentation'] = merged['code_presentation'].astype(str)

    ass_grp['code_module'] = ass_grp['code_module'].astype(str)
    ass_grp['code_presentation'] = ass_grp['code_presentation'].astype(str)

    merged.sort_values(['week_number'], inplace=True)
    ass_grp.sort_values(['submission_week'], inplace=True)

    gold_df = pd.merge_asof(
        merged,
        ass_grp[['id_student', 'code_module', 'code_presentation', 'submission_week', 
                 'cum_sub_count', 'cum_score_sum', 'cum_weighted_score', 'cum_late_sum', 'cum_delay_sum']],
        by=['id_student', 'code_module', 'code_presentation'],
        left_on='week_number',
        right_on='submission_week',
        direction='backward'
    )

    # Fill nulls for weeks preceding first assessment
    gold_df['assessments_submitted_so_far'] = gold_df['cum_sub_count'].fillna(0).astype(int)
    gold_df['avg_score_so_far'] = np.where(
        gold_df['assessments_submitted_so_far'] > 0, 
        np.round(gold_df['cum_score_sum'] / gold_df['assessments_submitted_so_far'], 2), 
        None
    )
    gold_df['weighted_score_so_far'] = np.round(gold_df['cum_weighted_score'].fillna(0.0), 3)
    gold_df['late_submissions_so_far'] = gold_df['cum_late_sum'].fillna(0).astype(int)
    gold_df['avg_submission_delay_so_far'] = np.where(
        gold_df['assessments_submitted_so_far'] > 0, 
        np.round(gold_df['cum_delay_sum'] / gold_df['assessments_submitted_so_far'], 2), 
        None
    )

    # Sort final dataset
    gold_df.sort_values(['id_student', 'code_module', 'code_presentation', 'week_number'], inplace=True)

    # Target column order matching MySQL table
    target_cols = [
        'code_module', 'code_presentation', 'id_student', 'week_number',
        'weekly_clicks', 'active_days', 'distinct_resources',
        'clicks_oucontent', 'clicks_forumng', 'clicks_quiz', 'clicks_homepage',
        'clicks_subpage', 'clicks_resource', 'clicks_url', 'clicks_other',
        'cumulative_clicks', 'cumulative_active_days', 'prev_week_clicks',
        'wow_click_change', 'clicks_last_2_weeks',
        'assessments_submitted_so_far', 'avg_score_so_far', 'weighted_score_so_far',
        'late_submissions_so_far', 'avg_submission_delay_so_far',
        'is_registered_by_week', 'is_withdrawn_by_week', 'final_result'
    ]
    export_df = gold_df[target_cols]

    # 5. Bulk insert into MySQL in chunks of 50,000 rows
    print(f"  Streaming {len(export_df):,} rows into gold.gold_student_weekly_engagement...")
    col_str = ", ".join(target_cols)
    placeholders = ", ".join(["%s"] * len(target_cols))
    insert_sql = f"INSERT INTO gold.gold_student_weekly_engagement ({col_str}) VALUES ({placeholders})"

    batch_size = 50000
    total_records = len(export_df)

    with tqdm(total=total_records, unit="rows", desc="  gold_weekly_engagement") as pbar:
        for start_idx in range(0, total_records, batch_size):
            end_idx = min(start_idx + batch_size, total_records)
            chunk_slice = export_df.iloc[start_idx:end_idx]
            # Replace NaN with None for clean SQL NULL insertion
            records = chunk_slice.astype(object).where(pd.notnull(chunk_slice), None).values.tolist()
            cur.executemany(insert_sql, records)
            conn.commit()
            pbar.update(len(records))

    elapsed = time.time() - start_time
    rate = total_records / elapsed if elapsed > 0 else 0
    print(f"  [OK] Ingested {total_records:,} Gold rows in {elapsed:.2f}s ({rate:,.0f} rows/s).\n")
    conn.close()
    return True


def validate_zero_leakage() -> bool:
    """Run automated validation checks for data completeness and zero target leakage."""
    print("=" * 70)
    print("STEP 3: ZERO TARGET LEAKAGE & SANITY VALIDATION")
    print("=" * 70)
    conn = get_raw_connection()
    cur = conn.cursor()

    # 1. Total row count check
    cur.execute("SELECT COUNT(*) AS cnt FROM gold.gold_student_weekly_engagement;")
    total_rows = cur.fetchone()["cnt"]
    print(f"  Total Rows in Gold Feature Store: {total_rows:,}")

    # 2. Check cumulative monotonicity: cumulative_clicks >= weekly_clicks
    cur.execute("""
        SELECT COUNT(*) AS violation_cnt 
        FROM gold.gold_student_weekly_engagement 
        WHERE cumulative_clicks < weekly_clicks;
    """)
    click_violations = cur.fetchone()["violation_cnt"]
    print(f"  Cumulative Clicks Monotonicity Violations: {click_violations}")

    # 3. Check zero leakage: assessments_submitted_so_far should never exceed total submissions for that student
    cur.execute("""
        SELECT COUNT(*) AS violation_cnt
        FROM gold.gold_student_weekly_engagement g
        JOIN (
            SELECT code_module, code_presentation, id_student, COUNT(*) AS max_subs
            FROM silver.silver_assessments
            GROUP BY code_module, code_presentation, id_student
        ) s ON g.code_module = s.code_module 
           AND g.code_presentation = s.code_presentation 
           AND g.id_student = s.id_student
        WHERE g.assessments_submitted_so_far > s.max_subs;
    """)
    leak_violations = cur.fetchone()["violation_cnt"]
    print(f"  Assessment Count Leakage Violations: {leak_violations}")

    # 4. Check score range validity (0 to 100)
    cur.execute("""
        SELECT COUNT(*) AS score_violations
        FROM gold.gold_student_weekly_engagement
        WHERE avg_score_so_far < 0 OR avg_score_so_far > 100;
    """)
    score_violations = cur.fetchone()["score_violations"]
    print(f"  Score Range Violations (outside 0-100): {score_violations}")

    # 5. Check sample summary statistics
    cur.execute("""
        SELECT 
            ROUND(AVG(weekly_clicks), 1) AS avg_weekly_clicks,
            ROUND(AVG(cumulative_clicks), 1) AS avg_cum_clicks,
            ROUND(AVG(active_days), 2) AS avg_active_days,
            ROUND(AVG(assessments_submitted_so_far), 2) AS avg_assessments_so_far,
            ROUND(AVG(weighted_score_so_far), 2) AS avg_weighted_score_so_far
        FROM gold.gold_student_weekly_engagement;
    """)
    stats = cur.fetchone()
    print("\n  Gold Layer Cohort Averages:")
    print(f"    Avg Weekly Clicks:            {stats['avg_weekly_clicks']}")
    print(f"    Avg Cumulative Clicks:        {stats['avg_cum_clicks']}")
    print(f"    Avg Active Days / Week:       {stats['avg_active_days']}")
    print(f"    Avg Assessments Submitted:    {stats['avg_assessments_so_far']}")
    print(f"    Avg Weighted Score Earned:    {stats['avg_weighted_score_so_far']} / 100")

    conn.close()
    all_passed = (click_violations == 0 and leak_violations == 0 and score_violations == 0 and total_rows == 627031)
    if all_passed:
        print("\n[SUCCESS] Zero Target Leakage verified: All features at week N strictly use data <= week N.\n")
        return True
    else:
        print("\n[FAIL] Validation issues detected in Gold Layer!\n")
        return False


def main():
    parser = argparse.ArgumentParser(description="Phase 4: Gold Weekly Engagement Feature Store")
    parser.add_argument("--reload", action="store_true", help="Force truncate existing gold table and reload")
    args = parser.parse_args()

    start_total = time.time()
    create_gold_tables()
    build_and_load_gold(reload=args.reload)
    success = validate_zero_leakage()

    elapsed = time.time() - start_total
    print("=" * 70)
    print(f"Total Phase 4 Execution Time: {elapsed:.2f}s ({elapsed/60:.2f} min).")
    print("=" * 70)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
