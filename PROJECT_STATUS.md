# Project Status & Handoff Tracking
**Project:** University Dropout Early-Warning Warehouse & Retention Dashboard  
**Dataset:** Open University Learning Analytics Dataset (OULAD)  
**Last Updated:** 2026-11-22  
**Database:** MySQL 8.0.46 Community Server (GPL) on `localhost:3306`

---

## 1. Phase Status Overview

| Phase | Description | Status | Completion Date | Gate Approval |
|:---|:---|:---:|:---:|:---|
| **Phase 1** | Project Setup, Schemas, & Starter Documentation | **COMPLETED** | 2026-11-20 | Schemas verified; backup created |
| **Phase 2** | Staging & Bronze Bulk Loading (ETL Step 1) | **COMPLETED** | 2026-11-21 | 100% row-count parity across 10.9M rows; mysqldump created |
| **Phase 3** | Cleaning, Deduplication, & Silver Layer (ETL Step 2) | **COMPLETED** | 2026-11-21 | Cleaned 3 Silver tables; data quality log generated |
| **Phase 4** | Gold Layer (Weekly Engagement & Zero Leakage) | **COMPLETED** | 2026-11-21 | 627,031 weekly features built with verified Zero Target Leakage |
| **Phase 5** | Dimensional Data Marts (Academic & Early Warning) | **COMPLETED** | 2026-11-22 | 7 mart objects built; 100% FK integrity; 0 orphan keys |
| **Phase 6** | Exploratory Data Analysis & DAV Visualizations | **COMPLETED** | 2026-11-22 | 17 charts + 11 summary CSVs generated with one-line insights |
| **Phase 7** | AI Expert System (Backward Chaining & Flag Writeback)| **COMPLETED** | 2026-11-22 | 198,493 risk flags written; 11-week median lead time; ML baseline compared |
| **Phase 8** | Power BI Dashboard Specification & DAX Measures | **COMPLETED** | 2026-11-22 | 5-page specification, 23 DAX measures, M scripts, 7 fallback CSVs |
| **Phase 9** | Documentation, Viva Defense Script, & Final Handoff | **NEXT** | — | Awaiting user "next" |

---

## 2. Exact Run Order to Rebuild State

Execute from the workspace root (`f:\Onedrive\Documents\DWBI Project`):

```bash
# Phase 1: Initialize Database Schemas (staging, bronze, silver, gold, marts)
python run_pipeline.py --phase 1

# Phase 2: Ingest Raw CSVs into Bronze & Populate Staging
python run_pipeline.py --phase 2

# Phase 3: Cleanse, Deduplicate, & Populate Silver Layer
python run_pipeline.py --phase 3

# Phase 4: Construct Gold Feature Store (Zero Target Leakage)
python run_pipeline.py --phase 4

# Phase 5: Build Dimensional Star Schemas (Academic & Early Warning Marts)
python run_pipeline.py --phase 5

# Phase 6: Run EDA & Generate DAV Visualizations
python run_pipeline.py --phase 6

# Phase 7: Run Backward-Chaining AI Expert System & Write Back Flags
python run_pipeline.py --phase 7

# Phase 8: Export Dimensional Marts to CSV for Power BI Desktop
python run_pipeline.py --phase 8
# (Or run etl/08_export_marts.py directly)

# Restore Database from Dump (if rebuilding from scratch without re-running ETL):
# mysql -u root -p < backups/phase8.sql
```

---

## 3. Database Objects Inventory

| Schema | Table / Object | Grain | Row Count | Purpose |
|:---|:---|:---|:---:|:---|
| `bronze` | `raw_courses` | 1 course presentation | 22 | Immutable 1:1 copy of courses.csv |
| `bronze` | `raw_assessments` | 1 assessment | 206 | Immutable 1:1 copy of assessments.csv |
| `bronze` | `raw_vle` | 1 VLE material | 6,364 | Immutable 1:1 copy of vle.csv |
| `bronze` | `raw_student_info` | 1 student registration | 32,593 | Immutable 1:1 copy of studentInfo.csv |
| `bronze` | `raw_student_registration` | 1 student course reg | 32,593 | Immutable 1:1 copy of studentRegistration.csv |
| `bronze` | `raw_student_assessment` | 1 student submission | 173,912 | Immutable 1:1 copy of studentAssessment.csv |
| `bronze` | `raw_student_vle` | 1 student interaction | 10,655,280 | Immutable 1:1 copy of studentVle.csv |
| `staging` | `stg_courses` | 1 course presentation | 22 | Staged courses metadata |
| `staging` | `stg_students` | 1 student registration | 32,593 | Integrated studentInfo + studentRegistration |
| `staging` | `stg_assessments` | 1 student submission | 173,912 | Integrated studentAssessment + assessments |
| `staging` | `stg_vle` | 1 student interaction | 10,655,280 | Integrated view over studentVle + vle |
| `silver` | `silver_students` | 1 student registration | 32,593 | Deduplicated, imputed IMD & reg dates, unreg status |
| `silver` | `silver_assessments` | 1 student submission | 173,912 | Cleaned scores (NULL→0.0), submission delay, relative weeks |
| `silver` | `silver_vle_activity` | 1 student resource day | 10,655,280 | Daily click logs enriched with relative week numbers |
| `gold` | `gold_student_weekly_engagement` | 1 student course week | 627,031 | Weekly engagement, velocity, cumulative assessment performance |
| `marts` | `dim_student` | 1 unique student | 28,785 | Conformed student demographics dimension |
| `marts` | `dim_course` | 1 module presentation | 22 | Conformed course & semester dimension |
| `marts` | `dim_date` | 1 academic week | 91 | Academic calendar week dimension (Week -4 to 86) |
| `marts` | `dim_week` (view) | 1 academic week | 91 | Alias view over `dim_date` for Early Warning naming |
| `marts` | `dim_assessment_type` | 1 assessment category | 3 | Assessment evaluation type dimension (TMA, CMA, Exam) |
| `marts` | `fact_student_performance` | 1 assessment submission | 173,912 | Academic Mart fact: scores, timeliness, pass flags |
| `marts` | `fact_weekly_engagement` | 1 student-course-week | 627,031 | Early Warning Mart fact: engagement velocity & academic progress |
| `marts` | `fact_risk_flag` | 1 student-course-week evaluation | 198,493 | AI write-back: risk level, calibrated score, auditable rules fired |

---

## 4. Key Architectural Decisions & Assumptions

1. **Multi-Schema Medallion Architecture on MySQL 8 (DEC-001):**
   - 5 dedicated schemas (`staging`, `bronze`, `silver`, `gold`, `marts`) provide clean layer separation and auditable data lineage.
2. **Strict Credential Isolation (DEC-002):**
   - Credentials stored exclusively in `.env` and accessed via `python-dotenv`.
3. **Chunked Streaming Ingestion (DEC-004, DEC-008):**
   - Ingested 10.65M VLE records in 100k-row chunks, object-casting NaN to None to prevent PyMySQL conversion crashes.
4. **Staging VLE Storage Optimization (DEC-009):**
   - `staging.stg_vle` implemented as an integrated view to avoid duplicating 10.65M rows on host drive.
5. **Missing Value Imputation Strategy (DEC-011, DEC-012, DEC-013):**
   - Assessment scores (173 rows): raw NULL preserved, `score_clean = 0.00`, flagged with `is_missing_score = 1`.
   - IMD Band (1,111 rows): categorized as `'Unknown'` to retain 100% cohort representation.
   - Registration dates (45 rows): imputed with cohort presentation median.
6. **Zero Target Leakage Enforcement (DEC-006, DEC-017):**
   - Every metric at week $N$ strictly uses data $\le N$. Assessment performance is aligned using backward directional merging (`pd.merge_asof`).
7. **Vectorized In-Memory Gold Aggregation (DEC-016):**
   - Performed weekly click and velocity aggregations via pandas in RAM (25s) to eliminate on-disk MySQL temporary file bloat in `C:\Windows\Temp`.
8. **Conformed Dimensional Model with Surrogate Keys (DEC-019, DEC-020):**
   - Dual star schemas (Academic Mart & Early Warning Mart) share conformed dimensions with integer surrogate keys for optimal BI join performance.
9. **Extended Week Coverage (DEC-021):**
   - `dim_date` spans Week -4 to 86 (91 rows) to accommodate 72 legitimate late/deferred assessment submissions, preventing FK violations.
10. **EDA Memory Efficiency via Pre-Aggregated Gold Layer (DEC-024):**
    - Reading pre-aggregated 627k Gold weekly rows rather than 10.65M raw VLE records kept RAM < 1 GB while generating 17 publication-quality charts.
11. **True Backward-Chaining Inference Engine (DEC-026):**
    - Evaluated top-level goal `AT_RISK` via a goal stack and sub-goal resolution over student fact rows, guaranteeing full explainability for academic advisors.
12. **Empirical Percentile-Based Rule Thresholds (DEC-027):**
    - Grounded sub-goal thresholds in cohort P25/P15 distributions stored in `ai/rules_config.json`, adapting to natural engagement drop-off across weeks.
13. **Multi-Week Risk Flag Write-Back (DEC-028):**
    - Evaluated weeks 1-10 (198,493 rows), providing an average 12.3 weeks (median 11.0 weeks) detection lead time before student withdrawal.
14. **Dedicated `_Measures` DAX Calculation Table (DEC-029):**
    - Centralized 23 DAX measures cleanly decoupled from physical columns.
15. **Portable Dimensional Mart CSV Fallback Layer (DEC-030):**
    - Exported all 7 mart tables (~115 MB total) to `dashboard/export/` for offline Power BI development without live MySQL requirements.
16. **5-Page Role-Based Visual Architecture (DEC-031):**
    - Tailored specific pages and workflows for Student Advisors, Course Instructors, and University Leadership.

---

## 5. Known Issues & Open Questions

- **None.** All 8 completed phases have passed 100% sanity checks, row parity audits, FK integrity checks, and Zero Target Leakage validation.
- Database backups exist for every completed phase in `backups/` (`phase1.sql` through `phase8.sql`).

---

## 6. Next Steps

1. **Phase 9 (Final Documentation, Viva Defense Script, & Final Handoff) — NEXT:**
   - Author comprehensive final report (`docs/final_report.md`): complete architecture descriptions, star-schema ER diagrams, ETL pipeline summary, data quality log, evaluation results, dashboard screenshots guide, limitations, and future work.
   - Author comprehensive viva defense script (`docs/viva_defense_script.md`): examiner Q&A covering the entire pipeline from raw CSVs to backward chaining and Power BI.
   - Perform the **Handoff Check** validating that an independent developer can rebuild the entire system from `README.md`, `PROJECT_STATUS.md`, `run_pipeline.py`, and database dump `backups/phase8.sql`.
   - Create final backup (`backups/phase9.sql`).
