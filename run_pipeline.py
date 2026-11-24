"""
===============================================================================
Script: run_pipeline.py
Phase: Master Orchestration Runner
Purpose: Provides a single, unified entry point to run all completed phases 
         in sequence or execute an individual phase cleanly.
Usage:
    python run_pipeline.py            # Run all completed phases
    python run_pipeline.py --phase 1  # Run only Phase 1
===============================================================================
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import test_connection, execute_sql_file, get_raw_connection


def check_prerequisites() -> bool:
    """Check required folders, raw data files, and database connectivity."""
    print("=" * 70)
    print("CHECKING PREREQUISITES...")
    print("=" * 70)
    
    # 1. Check raw CSVs
    required_files = [
        "courses.csv",
        "assessments.csv",
        "vle.csv",
        "studentInfo.csv",
        "studentRegistration.csv",
        "studentAssessment.csv",
        "studentVle.csv"
    ]
    raw_dir = PROJECT_ROOT / "data" / "raw"
    missing = [f for f in required_files if not (raw_dir / f).exists()]
    
    if missing:
        print(f"[ERROR] Missing raw data files in {raw_dir}:")
        for m in missing:
            print(f"  - {m}")
        return False
    else:
        print(f"[OK] All 7 source CSV files present in {raw_dir}")

    # 2. Test DB Connection
    db_test = test_connection()
    if not db_test["success"]:
        print(f"[ERROR] Database connection failed: {db_test.get('error')}")
        print("Please ensure MySQL is running and your password in .env is correct.")
        return False
    else:
        print(f"[OK] MySQL Connected ({db_test['version']}) as {db_test['current_user']}")

    return True


def run_phase_1() -> bool:
    """Execute Phase 1: Database Schemas Creation and Verification."""
    print("\n" + "=" * 70)
    print("PHASE 1: INITIALIZING DATABASE SCHEMAS")
    print("=" * 70)
    
    sql_file = PROJECT_ROOT / "sql" / "01_create_schemas.sql"
    print(f"Executing: {sql_file}")
    
    try:
        execute_sql_file(sql_file)
        print("[OK] Executed 01_create_schemas.sql successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to execute schema script: {e}")
        return False

    # Verify schemas exist
    expected_schemas = ["staging", "bronze", "silver", "gold", "marts"]
    conn = get_raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA;")
            found = {row["SCHEMA_NAME"].lower() for row in cur.fetchall()}
            
        print("\nVerifying Created Schemas:")
        all_ok = True
        for s in expected_schemas:
            if s in found:
                print(f"  [OK] Schema '{s}' exists.")
            else:
                print(f"  [FAIL] Schema '{s}' NOT found!")
                all_ok = False
        return all_ok
    finally:
        conn.close()


def run_phase_2(reload: bool = False) -> bool:
    """Execute Phase 2: Staging and Bronze Bulk Ingestion."""
    print("\n" + "=" * 70)
    print("PHASE 2: INGESTING DATA INTO BRONZE & STAGING LAYERS")
    print("=" * 70)
    import importlib
    mod = importlib.import_module("etl.02_load_staging_bronze")
    
    mod.create_schema_tables()
    mod.load_all_bronze(reload=reload)
    mod.populate_staging_tables(reload=reload)
    return mod.reconcile_row_counts()


def run_phase_3(reload: bool = False) -> bool:
    """Execute Phase 3: Cleaning, Deduplication, & Silver Layer Ingestion."""
    print("\n" + "=" * 70)
    print("PHASE 3: CLEANING & BUILDING SILVER LAYER TABLES")
    print("=" * 70)
    import importlib
    mod = importlib.import_module("etl.03_build_silver")
    
    mod.create_silver_tables()
    mod.clean_and_load_students(reload=reload)
    mod.clean_and_load_assessments(reload=reload)
    mod.clean_and_load_vle_activity(reload=reload)
    mod.generate_data_quality_log()
    return True


def run_phase_4(reload: bool = False) -> bool:
    """Execute Phase 4: Gold Layer Weekly Engagement Feature Store."""
    print("\n" + "=" * 70)
    print("PHASE 4: BUILDING GOLD FEATURE STORE (ZERO TARGET LEAKAGE)")
    print("=" * 70)
    import importlib
    mod = importlib.import_module("etl.04_build_gold")
    
    mod.create_gold_tables()
    mod.build_and_load_gold(reload=reload)
    return mod.validate_zero_leakage()


def run_phase_5(reload: bool = False) -> bool:
    """Execute Phase 5: Dimensional Star Schemas (Academic & Early Warning Marts)."""
    print("\n" + "=" * 70)
    print("PHASE 5: BUILDING DIMENSIONAL STAR SCHEMAS (DATA MARTS)")
    print("=" * 70)
    import importlib
    mod = importlib.import_module("etl.05_load_marts")
    
    mod.create_marts_tables()
    engine = mod.get_engine()
    mod.load_dimensions(engine, reload=reload)
    mod.load_fact_student_performance(engine, reload=reload)
    mod.load_fact_weekly_engagement(engine, reload=reload)
    return mod.reconcile_and_audit(engine)


def run_phase_6() -> bool:
    """Execute Phase 6: EDA & DAV Visualizations."""
    print("\n" + "=" * 70)
    print("PHASE 6: EXPLORATORY DATA ANALYSIS & DAV VISUALIZATIONS")
    print("=" * 70)
    import importlib
    mod = importlib.import_module("eda.06_run_eda")
    mod.main()
    return True


def run_phase_7(reload: bool = False) -> bool:
    """Execute Phase 7: AI Expert System (Backward Chaining & Risk Flag Writeback)."""
    print("\n" + "=" * 70)
    print("PHASE 7: AI EXPERT SYSTEM (BACKWARD CHAINING)")
    print("=" * 70)
    import importlib
    import json
    mod = importlib.import_module("ai.07_expert_system")
    
    config_path = Path(__file__).resolve().parent / "ai" / "rules_config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    
    bc_engine = mod.BackwardChainingEngine(config)
    db_engine = mod.get_engine()
    eval_weeks = list(range(1, 11))
    
    df_results = mod.run_inference(db_engine, bc_engine, eval_weeks, reload=reload)
    mod.validate_predictions(df_results)
    mod.analyze_early_detection(df_results, db_engine)
    mod.run_baseline_comparison(df_results, db_engine)
    return mod.reconcile(db_engine)


def run_phase_8(reload: bool = False) -> bool:
    """Execute Phase 8: Export Dimensional Marts to CSV for Power BI Desktop."""
    print("\n" + "=" * 70)
    print("PHASE 8: POWER BI DASHBOARD SPECIFICATIONS & MARTS CSV EXPORT")
    print("=" * 70)
    import importlib
    mod = importlib.import_module("etl.08_export_marts")
    db_engine = mod.get_engine()
    return mod.export_marts(db_engine, reload=reload)


def main():
    parser = argparse.ArgumentParser(description="Master DWBI Pipeline Runner")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5, 6, 7, 8, 9],
                        help="Specific phase number to execute")
    parser.add_argument("--reload", action="store_true",
                        help="Force truncate existing tables and reload from scratch")
    args = parser.parse_args()

    if not check_prerequisites():
        sys.exit(1)

    phase_target = args.phase

    if phase_target is None or phase_target == 1:
        success = run_phase_1()
        if not success:
            print("\n[FAILED] Phase 1 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 1 completed successfully.")

    if phase_target is None or phase_target == 2:
        success = run_phase_2(reload=args.reload)
        if not success:
            print("\n[FAILED] Phase 2 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 2 completed successfully.")

    if phase_target is None or phase_target == 3:
        success = run_phase_3(reload=args.reload)
        if not success:
            print("\n[FAILED] Phase 3 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 3 completed successfully.")

    if phase_target is None or phase_target == 4:
        success = run_phase_4(reload=args.reload)
        if not success:
            print("\n[FAILED] Phase 4 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 4 completed successfully.")

    if phase_target is None or phase_target == 5:
        success = run_phase_5(reload=args.reload)
        if not success:
            print("\n[FAILED] Phase 5 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 5 completed successfully.")

    if phase_target is None or phase_target == 6:
        success = run_phase_6()
        if not success:
            print("\n[FAILED] Phase 6 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 6 completed successfully.")

    if phase_target is None or phase_target == 7:
        success = run_phase_7(reload=args.reload)
        if not success:
            print("\n[FAILED] Phase 7 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 7 completed successfully.")

    if phase_target is None or phase_target == 8:
        success = run_phase_8(reload=args.reload)
        if not success:
            print("\n[FAILED] Phase 8 did not complete successfully.")
            sys.exit(1)
        print("\n[SUCCESS] Phase 8 completed successfully.")

    if phase_target and phase_target > 8:
        print(f"\n[INFO] Phase {phase_target} is not yet implemented or unlocked.")


if __name__ == "__main__":
    main()
