# Data Dictionary: University Dropout Early-Warning Warehouse
**Dataset:** Open University Learning Analytics Dataset (OULAD)  
**Target:** MySQL 8.0 Database Schemas (`staging`, `bronze`, `silver`, `gold`, `marts`)  
**Status:** Initial Draft (Phase 1)

---

## 1. Overview of Architecture Schemas

| Schema | Purpose | Primary Consumer |
|:---|:---|:---|
| `staging` | Ephemeral ingestion landing zone for type-casting and load validation | ETL scripts |
| `bronze` | Immutable, 1:1 raw copies of source CSV files | Data engineering & lineage audit |
| `silver` | Cleaned, deduplicated, enriched entities with relative week numbers | Analytics & Gold Feature Engineering |
| `gold` | Student-course-week engagement feature store (strictly zero leakage) | AI Expert System & EDA |
| `marts` | Dimensional Star Schemas (`academic_mart`, `early_warning_mart`) | Power BI Desktop & End-user reporting |

---

## 2. Raw Source Files (OULAD) Catalog (`data/raw/`)

### 2.1 `courses.csv`
- **Description:** Contains list of modules and their presentations.
- **Grain:** 1 row per module presentation.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module code (e.g., 'AAA', 'BBB').
  - `code_presentation` (VARCHAR(10)): Semester code (e.g., '2013J', '2014B'). 'B' denotes February start; 'J' denotes October start.
  - `module_presentation_length` (INT): Duration of the module in days.

### 2.2 `assessments.csv`
- **Description:** Assessment metadata for each module presentation.
- **Grain:** 1 row per assessment.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `id_assessment` (INT): Unique assessment ID.
  - `assessment_type` (VARCHAR(10)): Assessment category: Tutor Marked Assessment (`TMA`), Computer Marked Assessment (`CMA`), Final Exam (`Exam`).
  - `date` (INT, Nullable): Final submission date relative to module start (day 0).
  - `weight` (DECIMAL(5,2)): Assessment weight percentage towards final grade (0–100%).

### 2.3 `vle.csv`
- **Description:** Metadata for materials hosted on the Virtual Learning Environment (VLE).
- **Grain:** 1 row per VLE resource.
- **Columns:**
  - `id_site` (INT): Unique VLE resource identifier.
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `activity_type` (VARCHAR(50)): Type of resource (e.g., 'forumng', 'resource', 'oucontent', 'url', 'quiz').
  - `week_from` (INT, Nullable): Intended week to start using resource.
  - `week_to` (INT, Nullable): Intended week to stop using resource.

### 2.4 `studentInfo.csv`
- **Description:** Demographic information and final course outcome per student registration.
- **Grain:** 1 row per student per module presentation.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `id_student` (INT): Unique student identifier.
  - `gender` (VARCHAR(5)): Gender ('M', 'F').
  - `region` (VARCHAR(50)): Geographic region of student.
  - `highest_education` (VARCHAR(50)): Prior education level.
  - `imd_band` (VARCHAR(20)): Index of Multiple Deprivation decile band (socioeconomic proxy).
  - `age_band` (VARCHAR(20)): Age bracket (e.g., '0-35', '35-55', '55<=').
  - `num_of_prev_attempts` (INT): Number of times student previously attempted this module.
  - `studied_credits` (INT): Number of credits currently enrolled in.
  - `disability` (VARCHAR(5)): Declared disability status ('Y', 'N').
  - `final_result` (VARCHAR(20)): Target label ('Pass', 'Fail', 'Distinction', 'Withdrawn').

### 2.5 `studentRegistration.csv`
- **Description:** Registration and unregistration timeline.
- **Grain:** 1 row per student registration.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `id_student` (INT): Student identifier.
  - `date_registration` (INT, Nullable): Day of registration relative to start (negative = registered early).
  - `date_unregistration` (INT, Nullable): Day of withdrawal/unregistration relative to start.

### 2.6 `studentAssessment.csv`
- **Description:** Student results for individual submitted assessments.
- **Grain:** 1 row per student per assessment submission.
- **Columns:**
  - `id_assessment` (INT): Assessment identifier.
  - `id_student` (INT): Student identifier.
  - `date_submitted` (INT): Submission date relative to start.
  - `is_banked` (TINYINT): 1 if assessment score transferred from previous attempt; 0 otherwise.
  - `score` (DECIMAL(5,2), Nullable): Score achieved (0–100). NULL if not scored or missing.

### 2.7 `studentVle.csv`
- **Description:** Student interaction click logs with VLE resources (~10.65M rows).
- **Grain:** 1 row per student per resource per day.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `id_student` (INT): Student identifier.
  - `id_site` (INT): VLE resource identifier.
  - `date` (INT): Date of interaction relative to module start (day 0). Negative values = pre-course activity.
  - `sum_click` (INT): Total clicks recorded for this student on this resource on this day.

---

## 3. Bronze Layer Tables (`bronze` Schema)

| Table | Grain | Row Count | Primary Key | Foreign / Index Keys |
|:---|:---|:---:|:---|:---|
| `raw_courses` | 1 presentation | 22 | `(code_module, code_presentation)` | — |
| `raw_assessments` | 1 assessment | 206 | `id_assessment` | `idx_raw_ass_course (code_module, code_presentation)` |
| `raw_vle` | 1 VLE material | 6,364 | `id_site` | `idx_raw_vle_course (code_module, code_presentation)` |
| `raw_student_info` | 1 student reg | 32,593 | — | `idx_raw_info_student_course (id_student, code_module, code_presentation)` |
| `raw_student_registration` | 1 registration | 32,593 | — | `idx_raw_reg_student_course (id_student, code_module, code_presentation)` |
| `raw_student_assessment` | 1 submission | 173,912 | — | `idx_raw_sa_student (id_student)`, `idx_raw_sa_assessment (id_assessment)` |
| `raw_student_vle` | 1 click event | 10,655,280 | — | `idx_raw_sv_student_course (id_student, code_module, code_presentation)`, `idx_raw_sv_site (id_site)` |

---

## 4. Staging Layer Tables & Views (`staging` Schema)

| Object | Type | Grain | Row Count | Description / Underlying Tables |
|:---|:---:|:---|:---:|:---|
| `stg_courses` | Table | 1 presentation | 22 | Direct copy from `bronze.raw_courses` |
| `stg_students` | Table | 1 student reg | 32,593 | Joined entity of `bronze.raw_student_info` LEFT JOIN `bronze.raw_student_registration` |
| `stg_assessments` | Table | 1 submission | 173,912 | Joined entity of `bronze.raw_student_assessment` JOIN `bronze.raw_assessments` |
| `stg_vle` | View | 1 click event | 10,655,280 | Integrated view over `bronze.raw_student_vle` LEFT JOIN `bronze.raw_vle` (zero disk duplication) |

---

## 5. Silver Layer Tables (`silver` Schema)

### 5.1 `silver.silver_students`
- **Grain:** 1 row per student per module presentation (`id_student`, `code_module`, `code_presentation`).
- **Row Count:** 32,593 rows.
- **Primary Key:** `(id_student, code_module, code_presentation)`.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module code (e.g. 'AAA', 'BBB').
  - `code_presentation` (VARCHAR(10)): Semester code (e.g. '2013J', '2014B').
  - `id_student` (INT UNSIGNED): Unique student identifier.
  - `gender` (VARCHAR(5)): Gender ('M', 'F').
  - `region` (VARCHAR(50)): Geographic region.
  - `highest_education` (VARCHAR(50)): Prior education attainment level.
  - `imd_band` (VARCHAR(20)): Index of Multiple Deprivation band (missing values cleansed to `'Unknown'`).
  - `age_band` (VARCHAR(20)): Age bracket (e.g. '0-35', '35-55', '55<=').
  - `num_of_prev_attempts` (SMALLINT): Previous attempts on this module.
  - `studied_credits` (SMALLINT): Enrolled credits.
  - `disability` (VARCHAR(5)): Disability status ('Y', 'N').
  - `final_result` (VARCHAR(20)): Target outcome label ('Pass', 'Fail', 'Distinction', 'Withdrawn').
  - `date_registration` (SMALLINT, Nullable): Raw registration day offset.
  - `date_registration_imputed` (SMALLINT): Cleaned registration offset (cohort median imputed for 45 missing rows).
  - `is_registration_imputed` (TINYINT): 1 if registration date was imputed, 0 otherwise.
  - `registration_week` (SMALLINT): `FLOOR(date_registration_imputed / 7.0)`.
  - `date_unregistration` (SMALLINT, Nullable): Day of withdrawal relative to course start.
  - `unregistration_week` (SMALLINT, Nullable): `FLOOR(date_unregistration / 7.0)`.
  - `is_withdrawn` (TINYINT): 1 if `final_result = 'Withdrawn'` OR `date_unregistration IS NOT NULL`, 0 otherwise.
  - `unregistration_status` (VARCHAR(50)): Detailed withdrawal classification ('Normal Withdrawal', 'Administrative Withdrawal', 'Late Withdrawal (Recorded as Fail)', 'Completed Course').

### 5.2 `silver.silver_assessments`
- **Grain:** 1 row per student assessment submission.
- **Row Count:** 173,912 rows.
- **Primary Key:** `(id_assessment`, `id_student)`.
- **Columns:**
  - `id_assessment` (INT UNSIGNED): Assessment identifier.
  - `id_student` (INT UNSIGNED): Student identifier.
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `assessment_type` (VARCHAR(10)): Assessment category ('TMA', 'CMA', 'Exam').
  - `assessment_date` (SMALLINT, Nullable): Official submission deadline day offset.
  - `assessment_week` (SMALLINT, Nullable): `FLOOR(assessment_date / 7.0)`.
  - `weight` (DECIMAL(5,2)): Assessment weight percentage towards final course grade (0–100%).
  - `date_submitted` (SMALLINT): Actual submission day offset.
  - `submission_week` (SMALLINT): `FLOOR(date_submitted / 7.0)`.
  - `submission_delay` (SMALLINT, Nullable): `date_submitted - assessment_date` (positive = late, negative = early).
  - `is_late` (TINYINT): 1 if submitted past deadline, 0 otherwise.
  - `is_banked` (TINYINT): 1 if score transferred from previous enrollment attempt.
  - `score` (DECIMAL(5,2), Nullable): Raw score achieved (preserves NULL for 173 rows).
  - `score_clean` (DECIMAL(5,2)): Cleaned score (missing scores imputed to 0.00).
  - `is_missing_score` (TINYINT): 1 if raw score was missing, 0 otherwise.
  - `weighted_score` (DECIMAL(7,3)): `(score_clean * weight) / 100.0`.

### 5.3 `silver.silver_vle_activity`
- **Grain:** 1 row per student per VLE resource per day interaction.
- **Row Count:** 10,655,280 rows.
- **Columns:**
  - `code_module` (VARCHAR(10)): Module identifier.
  - `code_presentation` (VARCHAR(10)): Presentation identifier.
  - `id_student` (INT UNSIGNED): Student identifier.
  - `id_site` (INT UNSIGNED): VLE resource site identifier.
  - `activity_type` (VARCHAR(50)): Resource category (e.g. 'forumng', 'resource', 'oucontent', 'quiz', 'url').
  - `date` (SMALLINT): Day of interaction relative to course start (range: -25 to 269).
  - `week_number` (SMALLINT): `FLOOR(date / 7.0)` (range: -4 to 38).
  - `sum_click` (INT UNSIGNED): Total clicks recorded for this student on this resource on this day.

---

## 6. Gold Layer Tables (`gold` Schema)

### 6.1 `gold.gold_student_weekly_engagement`
- **Grain:** 1 row per student per module presentation per week (`id_student`, `code_module`, `code_presentation`, `week_number`).
- **Row Count:** 627,031 rows.
- **Primary Key:** `(id_student, code_module, code_presentation, week_number)`.
- **Purpose:** Central feature store for longitudinal student engagement velocity and cumulative academic performance, engineered strictly with **Zero Target Leakage** (features at week $N$ only utilize data $\le N$).
- **Columns:**
  - `code_module` (VARCHAR(10)): Module identifier (e.g. 'AAA', 'BBB').
  - `code_presentation` (VARCHAR(10)): Presentation identifier (e.g. '2013J', '2014B').
  - `id_student` (INT UNSIGNED): Unique student identifier.
  - `week_number` (SMALLINT): Relative academic week offset (-4 to 38).
  - `weekly_clicks` (INT UNSIGNED): Total clicks recorded for this student in this specific week.
  - `active_days` (TINYINT UNSIGNED): Count of distinct active days in this week (0 to 7).
  - `distinct_resources` (SMALLINT UNSIGNED): Count of distinct VLE materials accessed in this week.
  - `clicks_oucontent` (INT UNSIGNED): Weekly clicks on interactive course materials.
  - `clicks_forumng` (INT UNSIGNED): Weekly clicks on discussion forums.
  - `clicks_quiz` (INT UNSIGNED): Weekly clicks on online quizzes.
  - `clicks_homepage` (INT UNSIGNED): Weekly clicks on course landing page.
  - `clicks_subpage` (INT UNSIGNED): Weekly clicks on module subpages.
  - `clicks_resource` (INT UNSIGNED): Weekly clicks on downloadable documents/resources.
  - `clicks_url` (INT UNSIGNED): Weekly clicks on external web links.
  - `clicks_other` (INT UNSIGNED): Weekly clicks on other learning activities.
  - `cumulative_clicks` (INT UNSIGNED): Running cumulative sum of all clicks up to week $N$.
  - `cumulative_active_days` (SMALLINT UNSIGNED): Running cumulative sum of active interaction days up to week $N$.
  - `prev_week_clicks` (INT UNSIGNED): Total clicks recorded in previous week ($N-1$).
  - `wow_click_change` (INT): Week-over-week change in clicks (`weekly_clicks - prev_week_clicks`).
  - `clicks_last_2_weeks` (INT UNSIGNED): Sum of clicks across the last two weeks (`weekly_clicks + prev_week_clicks`).
  - `assessments_submitted_so_far` (SMALLINT): Running count of assessments submitted on or before week $N$.
  - `avg_score_so_far` (DECIMAL(5,2), Nullable): Running average score of submitted assessments up to week $N$. NULL if none submitted yet.
  - `weighted_score_so_far` (DECIMAL(7,3)): Running cumulative weighted marks earned up to week $N$ (0–100 scale).
  - `late_submissions_so_far` (SMALLINT): Count of overdue assessments submitted up to week $N$.
  - `avg_submission_delay_so_far` (DECIMAL(5,2), Nullable): Mean submission delay in days up to week $N$ (negative = early, positive = late).
  - `is_registered_by_week` (TINYINT): 1 if student was enrolled by week $N$, 0 otherwise.
  - `is_withdrawn_by_week` (TINYINT): 1 if student withdrew on or before week $N$, 0 otherwise.
  - `final_result` (VARCHAR(20)): Final outcome ('Pass', 'Fail', 'Distinction', 'Withdrawn') preserved for validation and BI reporting.

---

## 7. Dimensional Data Marts (`marts` Schema)

The `marts` schema implements two conformed star schemas optimized for Power BI Desktop reporting and the AI Expert System:
1. **Academic Mart:** Centered on assessment submission events (`fact_student_performance`).
2. **Early Warning Mart:** Centered on longitudinal weekly engagement velocity (`fact_weekly_engagement`) and predictive risk flags (`fact_risk_flag`).

Both marts share conformed dimensions (`dim_student`, `dim_course`, `dim_date` / `dim_week`, `dim_assessment_type`), enabling seamless cross-filtering and drill-through across report pages.

---

### 7.1 Conformed Dimensions

#### 7.1.1 `marts.dim_student`
- **Description:** Conformed student profile dimension holding demographic attributes and historical enrollment counts.
- **Grain:** 1 row per unique student (`id_student`).
- **Row Count:** 28,785 rows.
- **Keys:** Primary Key: `student_key` (surrogate INT UNSIGNED); Business Key: `id_student` (UNIQUE).
- **Index Justifications:**
  - `PRIMARY KEY (student_key)`: Clustered index for fast 1:N star schema joins with fact tables.
  - `UNIQUE KEY uk_dim_student_id (id_student)`: Guarantees 1:1 business key integrity and accelerates ETL lookups.
  - `KEY idx_dim_student_region (region)`: B-Tree index accelerating Power BI demographic region slicers.
  - `KEY idx_dim_student_imd (imd_band)`: B-Tree index optimizing deprivation decile filtering.
  - `KEY idx_dim_student_edu (highest_education)`: B-Tree index supporting educational attainment drill-downs.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `student_key` | INT UNSIGNED | No | Surrogate primary key for dimension | `1042` |
| `id_student` | INT UNSIGNED | No | Unique natural student ID | `28400` |
| `gender` | VARCHAR(5) | No | Gender of the student ('M', 'F') | `'F'` |
| `region` | VARCHAR(50) | No | UK geographic region of residence | `'Scotland'` |
| `highest_education` | VARCHAR(50) | No | Highest qualification achieved on entry | `'HE Qualification'` |
| `imd_band` | VARCHAR(20) | No | Index of Multiple Deprivation decile band | `'20-30%'` |
| `age_band` | VARCHAR(20) | No | Student age bracket ('0-35', '35-55', '55<=') | `'0-35'` |
| `disability` | VARCHAR(5) | No | Declared disability status ('Y', 'N') | `'N'` |
| `total_courses_enrolled` | SMALLINT UNSIGNED | No | Lifetime module presentation enrollments | `2` |
| `created_at` | TIMESTAMP | No | Timestamp of dimension record creation | `2026-11-21 23:45:00` |

#### 7.1.2 `marts.dim_course`
- **Description:** Conformed course and presentation dimension.
- **Grain:** 1 row per module presentation (`code_module`, `code_presentation`).
- **Row Count:** 22 rows.
- **Keys:** Primary Key: `course_key` (surrogate INT UNSIGNED); Business Key: `(code_module, code_presentation)`.
- **Index Justifications:**
  - `PRIMARY KEY (course_key)`: Clustered index for star join relationships.
  - `UNIQUE KEY uk_dim_course (code_module, code_presentation)`: Prevents duplicate course offerings.
  - `KEY idx_dim_course_year (presentation_year)`: B-Tree index supporting temporal cohort comparisons.
  - `KEY idx_dim_course_season (semester_season)`: B-Tree index enabling Spring vs Autumn term slicers.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `course_key` | INT UNSIGNED | No | Surrogate primary key for course presentation | `3` |
| `code_module` | VARCHAR(10) | No | Module code abbreviation | `'BBB'` |
| `code_presentation` | VARCHAR(10) | No | Presentation semester code | `'2013B'` |
| `module_presentation_length` | INT | No | Official presentation duration in days | `240` |
| `semester_season` | VARCHAR(15) | No | Semester delivery season ('Spring (Feb)', 'Autumn (Oct)') | `'Spring (Feb)'` |
| `presentation_year` | SMALLINT | No | Calendar delivery year | `2013` |
| `academic_year` | VARCHAR(15) | No | Academic cycle year designation | `'2012/2013'` |
| `course_full_name` | VARCHAR(50) | No | Formatted human-readable course label | `'Module BBB (2013B)'` |

#### 7.1.3 `marts.dim_date`
- **Description:** Academic calendar week dimension covering the entire longitudinal timeline from pre-course preparation through extended post-term marking.
- **Grain:** 1 row per relative academic week (`week_number`).
- **Row Count:** 91 rows (Week -4 through Week 86).
- **Keys:** Primary Key: `week_key` (surrogate INT UNSIGNED); Business Key: `week_number` (UNIQUE).
- **Index Justifications:**
  - `PRIMARY KEY (week_key)`: Clustered index for temporal fact joins.
  - `UNIQUE KEY uk_dim_date_week (week_number)`: Enforces strict temporal ordering without duplication.
  - `KEY idx_dim_date_phase (academic_phase)`: B-Tree index optimizing phase-based slice filtering.
  - `KEY idx_dim_date_warning_win (is_early_warning_window)`: B-Tree index accelerating Early Warning dashboard queries.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `week_key` | INT UNSIGNED | No | Surrogate primary key for academic week | `5` |
| `week_number` | SMALLINT | No | Relative week number (-4 to 86) | `0` |
| `week_label` | VARCHAR(30) | No | Human-readable week label | `'Week 0'` |
| `academic_phase` | VARCHAR(40) | No | Educational milestone stage category | `'Early Course & Onboarding'` |
| `is_early_warning_window` | TINYINT | No | 1 if within early detection window (Weeks 0–5); 0 otherwise | `1` |
| `start_day_offset` | SMALLINT | No | Starting day offset relative to course launch | `0` |
| `end_day_offset` | SMALLINT | No | Ending day offset relative to course launch | `6` |

#### 7.1.4 `marts.dim_week` (View)
- **Description:** Conformed view alias directly exposing `marts.dim_date` to provide intuitive naming inside the Early Warning Mart.
- **Definition:** `CREATE OR REPLACE VIEW marts.dim_week AS SELECT * FROM marts.dim_date;`

#### 7.1.5 `marts.dim_assessment_type`
- **Description:** Assessment evaluation category and marking methodology dimension.
- **Grain:** 1 row per assessment category.
- **Row Count:** 3 rows ('TMA', 'CMA', 'Exam').
- **Keys:** Primary Key: `assessment_type_key` (surrogate INT UNSIGNED); Business Key: `assessment_type` (UNIQUE).
- **Index Justifications:**
  - `PRIMARY KEY (assessment_type_key)`: Clustered index for star schema joins.
  - `UNIQUE KEY uk_dim_assessment_type (assessment_type)`: Enforces unique category codes.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `assessment_type_key` | INT UNSIGNED | No | Surrogate primary key for assessment type | `1` |
| `assessment_type` | VARCHAR(10) | No | Assessment category code ('TMA', 'CMA', 'Exam') | `'TMA'` |
| `assessment_type_name` | VARCHAR(50) | No | Full human-readable category title | `'Tutor Marked Assessment'` |
| `marking_method` | VARCHAR(40) | No | Grading method ('Manual / Tutor', 'Automated', 'Formal Exam') | `'Manual / Tutor'` |
| `is_exam` | TINYINT | No | Flag indicating final course examination (1 = Exam, 0 = Continuous) | `0` |

---

### 7.2 Fact Tables

#### 7.2.1 `marts.fact_student_performance` (Academic Mart)
- **Description:** Granular assessment performance and timeliness fact table.
- **Grain:** 1 row per individual assessment submission.
- **Row Count:** 173,912 rows.
- **Keys:** Primary Key: `performance_key` (surrogate BIGINT UNSIGNED AUTO_INCREMENT).
- **Foreign Keys:**
  - `student_key` REFERENCES `marts.dim_student (student_key)`
  - `course_key` REFERENCES `marts.dim_course (course_key)`
  - `week_key` REFERENCES `marts.dim_date (week_key)`
  - `assessment_type_key` REFERENCES `marts.dim_assessment_type (assessment_type_key)`
- **Index Justifications:**
  - `KEY idx_fsp_student (student_key)`: Enables student-level longitudinal performance drill-downs.
  - `KEY idx_fsp_course (course_key)`: Accelerates course-level grade distributions and pass-rate KPIs.
  - `KEY idx_fsp_week (week_key)`: Optimizes submission timeline visual filtering.
  - `KEY idx_fsp_type (assessment_type_key)`: Accelerates TMA vs CMA vs Exam slicing.
  - `KEY idx_fsp_course_week (course_key, week_key)`: Compound index optimizing course-by-week grade matrices.
  - `KEY idx_fsp_assessment (id_assessment)`: Optimizes assessment item difficulty analysis.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `performance_key` | BIGINT UNSIGNED | No | Surrogate primary key for fact record | `1` |
| `student_key` | INT UNSIGNED | No | Foreign key referencing `dim_student` | `412` |
| `course_key` | INT UNSIGNED | No | Foreign key referencing `dim_course` | `1` |
| `week_key` | INT UNSIGNED | No | Foreign key referencing `dim_date` (submission week) | `6` |
| `assessment_type_key` | INT UNSIGNED | No | Foreign key referencing `dim_assessment_type` | `1` |
| `id_assessment` | INT UNSIGNED | No | Natural assessment ID | `1752` |
| `id_student` | INT UNSIGNED | No | Natural student ID | `11391` |
| `code_module` | VARCHAR(10) | No | Module code abbreviation | `'AAA'` |
| `code_presentation` | VARCHAR(10) | No | Presentation semester code | `'2013J'` |
| `assessment_date` | SMALLINT | Yes | Official scheduled deadline day offset | `19` |
| `date_submitted` | SMALLINT | No | Actual day offset of submission | `18` |
| `submission_delay` | SMALLINT | Yes | Days submitted past deadline (negative = early, positive = late) | `-1` |
| `is_late` | TINYINT | No | Flag indicating overdue submission (`date_submitted > assessment_date`) | `0` |
| `is_banked` | TINYINT | No | Flag indicating mark transferred from prior registration | `0` |
| `weight` | DECIMAL(5,2) | No | Assessment weight percentage (0.00–100.00) | `10.00` |
| `score` | DECIMAL(5,2) | Yes | Raw recorded score (0.00–100.00; NULL if missing) | `78.00` |
| `score_clean` | DECIMAL(5,2) | No | Imputed score for analytics (missing scores assigned 0.00) | `78.00` |
| `is_missing_score` | TINYINT | No | Audit flag (1 if original score was NULL; 0 otherwise) | `0` |
| `weighted_score` | DECIMAL(7,3) | No | Contribution to final score (`score_clean * weight / 100.0`) | `7.800` |
| `is_passed_assessment` | TINYINT | No | Flag indicating passing score (`score_clean >= 40.0`) | `1` |

#### 7.2.2 `marts.fact_weekly_engagement` (Early Warning Mart)
- **Description:** Weekly longitudinal feature and velocity fact table engineered with strict zero target leakage for early warning risk detection.
- **Grain:** 1 row per student per course presentation per week.
- **Row Count:** 627,031 rows.
- **Keys:** Primary Key: `engagement_key` (surrogate BIGINT UNSIGNED AUTO_INCREMENT).
- **Foreign Keys:**
  - `student_key` REFERENCES `marts.dim_student (student_key)`
  - `course_key` REFERENCES `marts.dim_course (course_key)`
  - `week_key` REFERENCES `marts.dim_date (week_key)`
- **Index Justifications:**
  - `KEY idx_fwe_student (student_key)`: Supports student profile drill-through and timeline tracing.
  - `KEY idx_fwe_course (course_key)`: Accelerates course-level cohort attrition KPIs.
  - `KEY idx_fwe_week (week_key)`: Supports weekly trend analysis and timeline animations.
  - `KEY idx_fwe_course_week (course_key, week_key)`: Compound index optimizing the Page 2 At-Risk Heatmap matrix.
  - `KEY idx_fwe_student_course (student_key, course_key)`: Optimizes multi-week student trajectory queries.
  - `KEY idx_fwe_result (final_result)`: Accelerates cross-filtering by actual student outcome.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `engagement_key` | BIGINT UNSIGNED | No | Surrogate primary key for fact record | `1` |
| `student_key` | INT UNSIGNED | No | Foreign key referencing `dim_student` | `1042` |
| `course_key` | INT UNSIGNED | No | Foreign key referencing `dim_course` | `2` |
| `week_key` | INT UNSIGNED | No | Foreign key referencing `dim_date` (`week_number`) | `5` |
| `id_student` | INT UNSIGNED | No | Natural student ID | `28400` |
| `code_module` | VARCHAR(10) | No | Module code abbreviation | `'AAA'` |
| `code_presentation` | VARCHAR(10) | No | Presentation semester code | `'2013J'` |
| `week_number` | SMALLINT | No | Relative academic week number (-4 to 38) | `0` |
| `weekly_clicks` | INT UNSIGNED | No | Total clicks recorded during this specific week | `82` |
| `active_days` | TINYINT UNSIGNED | No | Count of distinct active days in this week (0 to 7) | `4` |
| `distinct_resources` | SMALLINT UNSIGNED | No | Count of distinct VLE materials accessed in this week | `12` |
| `clicks_oucontent` | INT UNSIGNED | No | Weekly clicks on interactive learning texts | `45` |
| `clicks_forumng` | INT UNSIGNED | No | Weekly clicks on discussion forums | `18` |
| `clicks_quiz` | INT UNSIGNED | No | Weekly clicks on self-assessment quizzes | `0` |
| `clicks_homepage` | INT UNSIGNED | No | Weekly clicks on course landing page | `15` |
| `clicks_subpage` | INT UNSIGNED | No | Weekly clicks on navigation subpages | `4` |
| `clicks_resource` | INT UNSIGNED | No | Weekly clicks on static documents/PDFs | `0` |
| `clicks_url` | INT UNSIGNED | No | Weekly clicks on external hyperlinks | `0` |
| `clicks_other` | INT UNSIGNED | No | Weekly clicks on all other VLE activity types | `0` |
| `cumulative_clicks` | INT UNSIGNED | No | Cumulative clicks up to week $N$ | `120` |
| `cumulative_active_days` | SMALLINT UNSIGNED | No | Cumulative active interaction days up to week $N$ | `7` |
| `prev_week_clicks` | INT UNSIGNED | No | Total clicks recorded in previous week ($N-1$) | `38` |
| `wow_click_change` | INT | No | Week-over-week click velocity (`weekly_clicks - prev_week_clicks`) | `44` |
| `clicks_last_2_weeks` | INT UNSIGNED | No | Two-week rolling click activity (`weekly_clicks + prev_week_clicks`) | `120` |
| `assessments_submitted_so_far` | SMALLINT | No | Count of assessments submitted on or before week $N$ | `0` |
| `avg_score_so_far` | DECIMAL(5,2) | Yes | Average score of submitted assessments up to week $N$ | `NULL` |
| `weighted_score_so_far` | DECIMAL(7,3) | No | Cumulative weighted marks earned up to week $N$ (0–100) | `0.000` |
| `late_submissions_so_far` | SMALLINT | No | Count of overdue assessments submitted up to week $N$ | `0` |
| `avg_submission_delay_so_far` | DECIMAL(5,2) | Yes | Mean submission delay in days up to week $N$ | `NULL` |
| `is_registered_by_week` | TINYINT | No | 1 if enrolled by week $N$; 0 otherwise | `1` |
| `is_withdrawn_by_week` | TINYINT | No | 1 if student withdrew on or before week $N$; 0 otherwise | `0` |
| `final_result` | VARCHAR(20) | No | Ground truth course outcome ('Pass', 'Fail', 'Distinction', 'Withdrawn') | `'Pass'` |

#### 7.2.3 `marts.fact_risk_flag` (Early Warning Mart - AI Write-Back)
- **Description:** Predictive student risk status generated by the AI Expert System (backward-chaining inference engine) in Phase 7 and written back for Power BI reporting.
- **Grain:** 1 row per student per course presentation per evaluation week.
- **Row Count:** 198,493 rows (evaluated across longitudinal early warning Weeks 1 to 10).
- **Keys:** Primary Key: `risk_flag_key` (surrogate BIGINT UNSIGNED AUTO_INCREMENT).
- **Foreign Keys:**
  - `student_key` REFERENCES `marts.dim_student (student_key)`
  - `course_key` REFERENCES `marts.dim_course (course_key)`
  - `week_key` REFERENCES `marts.dim_date (week_key)`
- **Index Justifications:**
  - `KEY idx_frf_student (student_key)`: Supports student advisor drill-down.
  - `KEY idx_frf_course (course_key)`: Accelerates course-level risk queue summaries.
  - `KEY idx_frf_week (week_key)`: Accelerates temporal risk trajectory filtering.
  - `KEY idx_frf_level (risk_level)`: Optimizes advisor alert filtering for 'High' risk cases.
  - `KEY idx_frf_course_week_level (course_key, week_key, risk_level)`: Compound index optimizing the Power BI At-Risk heat map matrix.
  - `KEY idx_frf_student_id (student_id)`: Accelerates direct natural student ID lookups.
- **Columns:**

| Column Name | Data Type | Nullable | Meaning / Description | Example Value |
|:---|:---|:---:|:---|:---|
| `risk_flag_key` | BIGINT UNSIGNED | No | Surrogate primary key for risk flag fact | `1` |
| `student_key` | INT UNSIGNED | No | Foreign key referencing `dim_student` | `1042` |
| `course_key` | INT UNSIGNED | No | Foreign key referencing `dim_course` | `1` |
| `week_key` | INT UNSIGNED | No | Foreign key referencing `dim_date` | `8` |
| `student_id` | INT UNSIGNED | No | Natural student ID for advisor reference | `28400` |
| `code_module` | VARCHAR(10) | No | Module code abbreviation | `'AAA'` |
| `code_presentation` | VARCHAR(10) | No | Presentation semester code | `'2013J'` |
| `week_number` | SMALLINT | No | Academic week number when risk was evaluated | `3` |
| `risk_level` | VARCHAR(20) | No | AI classification: 'Low', 'Medium', 'High' | `'High'` |
| `risk_score` | DECIMAL(5,2) | No | Calibrated risk probability score (0.00 to 100.00) | `84.50` |
| `rules_triggered` | TEXT | No | Semicolon-delimited chain of fired inference rules | `'R1: Zero clicks in last 2 weeks; R4: Missed TMA1'` |
| `flagged_at` | TIMESTAMP | No | Timestamp when the inference engine wrote back the flag | `2026-11-21 14:00:00` |

---

### 7.3 Note on Spatial Indexes
- **Spatial / R-Tree Index Exclusion Justification:**
  - Standard relational B-Tree indexes are utilized exclusively across all dimensional tables.
  - Spatial indexes (such as MySQL R-Tree indexes) are **strictly omitted** because the OULAD dataset contains no GIS coordinate geometries, polygons, or bounding boxes.
  - Student geographic locations are provided exclusively as nominal administrative region names (e.g., `'East Anglian Region'`, `'Scotland'`, `'South Region'`), which are optimally indexed via standard B-Tree indexes (`KEY idx_dim_student_region`).



