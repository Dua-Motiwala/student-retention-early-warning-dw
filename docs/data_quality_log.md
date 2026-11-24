# Data Quality & Cleaning Audit Log
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
- **Total Processed Records:** `32,593`
- **Deduplication Check:** 32,593 input rows -> 32,593 output rows (0 duplicates dropped).
- **Missing IMD Deciles:** `1,111` records categorized as `'Unknown'`.
- **Missing Registration Dates:** `45` records imputed with cohort median.
- **Withdrawal & Outcome Consistency Matrix:**
  - `Normal Withdrawal` (final_result = 'Withdrawn' AND date_unregistration present): **10,063**
  - `Administrative Withdrawal` (final_result = 'Withdrawn' BUT date_unregistration is NULL): **93**
  - `Late Withdrawal (Recorded as Fail)` (date_unregistration present BUT final_result = 'Fail'): **9**
  - `Completed Course` (Pass, Distinction, or Academic Fail without withdrawal): **22,428**
  - **Total Flagged At-Risk / Withdrawn:** **10,165**

### 2.2 `silver.silver_assessments` (Grain: 1 row per student submission)
- **Total Submissions Processed:** `173,912`
- **Missing Scores Imputed to 0.0:** `173` rows (flagged with `is_missing_score = 1`).
- **Banked Assessments Transferred:** `1,909` rows (from previous attempts).
- **Late Submissions Flagged:** `49,318` rows (submitted past deadline offset).
- **Cohort Mean Clean Score:** `75.72` / 100.
- **Cohort Mean Submission Delay:** `-16.66` days.

### 2.3 `silver.silver_vle_activity` (Grain: 1 row per student per site per day)
- **Total Interaction Logs Processed:** `10,655,280`
- **Distinct Active Students:** `26,074`
- **Distinct Learning Resources Accessed:** `6,268`
- **Relative Week Range:** Week `-4` (pre-course day -25) to Week `38` (day 269).
- **Cumulative Clicks Tracked:** `39,605,099` clicks.

---

## 3. Data Lineage and Integrity Verification

All 3 Silver layer tables adhere strictly to:
1. **Primary Composite Keys:** Verified unique on `(id_student, code_module, code_presentation)` and `(id_assessment, id_student)`.
2. **Unified Join Keys:** Every downstream analytics and feature store query in Gold / Marts layers joins cleanly on `(id_student, code_module, code_presentation)`.
3. **No Target Leakage in Timestamps:** All relative dates maintain chronological fidelity relative to module presentation start.
