-- ==============================================================================
-- Script: sql/05_create_marts.sql
-- Phase: Phase 5 - Data Marts (Star Schemas for Academic & Early Warning Marts)
-- Purpose: Define DDL for Star Schema Dimensions and Fact tables in `marts` schema.
-- Inputs: Data from `silver` and `gold` schemas
-- Outputs: Dimensions (dim_student, dim_course, dim_date, dim_week, dim_assessment_type)
--          Fact Tables (fact_student_performance, fact_weekly_engagement, fact_risk_flag)
-- Dependencies: silver and gold schemas populated
-- Run Order: 05
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. CONFORMED DIMENSIONS
-- ------------------------------------------------------------------------------

-- dim_student: Unique student profile dimension (28,785 rows)
-- Primary Key: student_key (surrogate key)
-- Business Key: id_student
-- Index Justification: B-Tree index on id_student for join lookup; B-Tree on region,
-- imd_band, and highest_education for Power BI demographic slicers and cross-filtering.
CREATE TABLE IF NOT EXISTS marts.dim_student (
    student_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_student INT UNSIGNED NOT NULL,
    gender VARCHAR(5) NOT NULL,
    region VARCHAR(50) NOT NULL,
    highest_education VARCHAR(50) NOT NULL,
    imd_band VARCHAR(20) NOT NULL,
    age_band VARCHAR(20) NOT NULL,
    disability VARCHAR(5) NOT NULL,
    total_courses_enrolled SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_dim_student_id (id_student),
    KEY idx_dim_student_region (region),
    KEY idx_dim_student_imd (imd_band),
    KEY idx_dim_student_edu (highest_education)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_course: Course and presentation dimension (22 rows)
-- Primary Key: course_key
-- Business Key: (code_module, code_presentation)
-- Index Justification: Unique compound B-Tree on (code_module, code_presentation) prevents
-- duplicates; B-Tree on semester_season and presentation_year enables fast time-slicing.
CREATE TABLE IF NOT EXISTS marts.dim_course (
    course_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    module_presentation_length INT NOT NULL,
    semester_season VARCHAR(15) NOT NULL,
    presentation_year SMALLINT NOT NULL,
    academic_year VARCHAR(15) NOT NULL,
    course_full_name VARCHAR(50) NOT NULL,
    UNIQUE KEY uk_dim_course (code_module, code_presentation),
    KEY idx_dim_course_year (presentation_year),
    KEY idx_dim_course_season (semester_season)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_date: Academic week dimension (43 rows, weeks -4 to 38)
-- Primary Key: week_key
-- Business Key: week_number
-- Index Justification: Unique B-Tree on week_number guarantees temporal ordering;
-- B-Tree on academic_phase and is_early_warning_window accelerates dashboard phase filters.
CREATE TABLE IF NOT EXISTS marts.dim_date (
    week_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    week_number SMALLINT NOT NULL,
    week_label VARCHAR(30) NOT NULL,
    academic_phase VARCHAR(40) NOT NULL,
    is_early_warning_window TINYINT NOT NULL,
    start_day_offset SMALLINT NOT NULL,
    end_day_offset SMALLINT NOT NULL,
    UNIQUE KEY uk_dim_date_week (week_number),
    KEY idx_dim_date_phase (academic_phase),
    KEY idx_dim_date_warning_win (is_early_warning_window)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_week: View alias over dim_date for Early Warning Mart conformed naming
CREATE OR REPLACE VIEW marts.dim_week AS 
SELECT * FROM marts.dim_date;

-- dim_assessment_type: Assessment category dimension (3 rows)
-- Primary Key: assessment_type_key
-- Business Key: assessment_type
-- Index Justification: Unique B-Tree on assessment_type code ('TMA', 'CMA', 'Exam').
CREATE TABLE IF NOT EXISTS marts.dim_assessment_type (
    assessment_type_key INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    assessment_type VARCHAR(10) NOT NULL,
    assessment_type_name VARCHAR(50) NOT NULL,
    marking_method VARCHAR(40) NOT NULL,
    is_exam TINYINT NOT NULL,
    UNIQUE KEY uk_dim_assessment_type (assessment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 2. ACADEMIC MART (Star Schema)
-- ------------------------------------------------------------------------------

-- fact_student_performance: Assessment submission facts (173,912 rows)
-- Grain: 1 row per student assessment submission
-- Index Justification: Foreign key B-Tree indexes on student_key, course_key, week_key,
-- and assessment_type_key prevent table scans during dimensional star joins. Compound
-- B-Tree on (course_key, week_key) accelerates course-level performance matrices.
CREATE TABLE IF NOT EXISTS marts.fact_student_performance (
    performance_key BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_key INT UNSIGNED NOT NULL,
    course_key INT UNSIGNED NOT NULL,
    week_key INT UNSIGNED NOT NULL,
    assessment_type_key INT UNSIGNED NOT NULL,

    -- Business Keys
    id_assessment INT UNSIGNED NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,

    -- Submission Timeline & Timeliness
    assessment_date SMALLINT NULL,
    date_submitted SMALLINT NOT NULL,
    submission_delay SMALLINT NULL,
    is_late TINYINT NOT NULL,
    is_banked TINYINT NOT NULL,

    -- Scores & Measures
    weight DECIMAL(5,2) NOT NULL,
    score DECIMAL(5,2) NULL,
    score_clean DECIMAL(5,2) NOT NULL,
    is_missing_score TINYINT NOT NULL,
    weighted_score DECIMAL(7,3) NOT NULL,
    is_passed_assessment TINYINT NOT NULL,

    CONSTRAINT fk_fsp_student FOREIGN KEY (student_key) REFERENCES marts.dim_student (student_key),
    CONSTRAINT fk_fsp_course FOREIGN KEY (course_key) REFERENCES marts.dim_course (course_key),
    CONSTRAINT fk_fsp_week FOREIGN KEY (week_key) REFERENCES marts.dim_date (week_key),
    CONSTRAINT fk_fsp_type FOREIGN KEY (assessment_type_key) REFERENCES marts.dim_assessment_type (assessment_type_key),

    KEY idx_fsp_student (student_key),
    KEY idx_fsp_course (course_key),
    KEY idx_fsp_week (week_key),
    KEY idx_fsp_type (assessment_type_key),
    KEY idx_fsp_course_week (course_key, week_key),
    KEY idx_fsp_assessment (id_assessment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 3. EARLY WARNING MART (Star Schema)
-- ------------------------------------------------------------------------------

-- fact_weekly_engagement: Student weekly engagement and velocity facts (627,031 rows)
-- Grain: 1 row per student per course presentation per week
-- Index Justification: Compound B-Tree on (course_key, week_key) is the primary index for
-- Power BI heat-map matrices. B-Tree on (student_key, course_key) supports student drill-through.
CREATE TABLE IF NOT EXISTS marts.fact_weekly_engagement (
    engagement_key BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_key INT UNSIGNED NOT NULL,
    course_key INT UNSIGNED NOT NULL,
    week_key INT UNSIGNED NOT NULL,

    -- Business Keys
    id_student INT UNSIGNED NOT NULL,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    week_number SMALLINT NOT NULL,

    -- Weekly VLE Activity Measures
    weekly_clicks INT UNSIGNED NOT NULL,
    active_days TINYINT UNSIGNED NOT NULL,
    distinct_resources SMALLINT UNSIGNED NOT NULL,
    clicks_oucontent INT UNSIGNED NOT NULL,
    clicks_forumng INT UNSIGNED NOT NULL,
    clicks_quiz INT UNSIGNED NOT NULL,
    clicks_homepage INT UNSIGNED NOT NULL,
    clicks_subpage INT UNSIGNED NOT NULL,
    clicks_resource INT UNSIGNED NOT NULL,
    clicks_url INT UNSIGNED NOT NULL,
    clicks_other INT UNSIGNED NOT NULL,

    -- Velocity Indicators (Zero Target Leakage)
    cumulative_clicks INT UNSIGNED NOT NULL,
    cumulative_active_days SMALLINT UNSIGNED NOT NULL,
    prev_week_clicks INT UNSIGNED NOT NULL,
    wow_click_change INT NOT NULL,
    clicks_last_2_weeks INT UNSIGNED NOT NULL,

    -- Academic Progress Measures (Zero Target Leakage)
    assessments_submitted_so_far SMALLINT NOT NULL,
    avg_score_so_far DECIMAL(5,2) NULL,
    weighted_score_so_far DECIMAL(7,3) NOT NULL,
    late_submissions_so_far SMALLINT NOT NULL,
    avg_submission_delay_so_far DECIMAL(5,2) NULL,

    -- Status & Ground Truth Reference
    is_registered_by_week TINYINT NOT NULL,
    is_withdrawn_by_week TINYINT NOT NULL,
    final_result VARCHAR(20) NOT NULL,

    CONSTRAINT fk_fwe_student FOREIGN KEY (student_key) REFERENCES marts.dim_student (student_key),
    CONSTRAINT fk_fwe_course FOREIGN KEY (course_key) REFERENCES marts.dim_course (course_key),
    CONSTRAINT fk_fwe_week FOREIGN KEY (week_key) REFERENCES marts.dim_date (week_key),

    KEY idx_fwe_student (student_key),
    KEY idx_fwe_course (course_key),
    KEY idx_fwe_week (week_key),
    KEY idx_fwe_course_week (course_key, week_key),
    KEY idx_fwe_student_course (student_key, course_key),
    KEY idx_fwe_result (final_result)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- fact_risk_flag: AI Early Warning risk classifications and rule traces
-- Grain: 1 row per student per course per week risk evaluation (populated in Phase 7)
-- Index Justification: B-Tree on risk_level supports high-risk filtering. Compound B-Tree
-- on (course_key, week_key, risk_level) optimizes Power BI advisor alert queues.
CREATE TABLE IF NOT EXISTS marts.fact_risk_flag (
    risk_flag_key BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_key INT UNSIGNED NOT NULL,
    course_key INT UNSIGNED NOT NULL,
    week_key INT UNSIGNED NOT NULL,

    -- Business Keys
    student_id INT UNSIGNED NOT NULL,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    week_number SMALLINT NOT NULL,

    -- AI Predictions & Rule Explanations
    risk_level VARCHAR(20) NOT NULL,             -- 'Low', 'Medium', 'High'
    risk_score DECIMAL(5,2) NOT NULL,            -- 0.00 to 100.00
    rules_triggered TEXT NOT NULL,               -- Auditable fired rule names / sub-goals
    flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_frf_student FOREIGN KEY (student_key) REFERENCES marts.dim_student (student_key),
    CONSTRAINT fk_frf_course FOREIGN KEY (course_key) REFERENCES marts.dim_course (course_key),
    CONSTRAINT fk_frf_week FOREIGN KEY (week_key) REFERENCES marts.dim_date (week_key),

    KEY idx_frf_student (student_key),
    KEY idx_frf_course (course_key),
    KEY idx_frf_week (week_key),
    KEY idx_frf_level (risk_level),
    KEY idx_frf_course_week_level (course_key, week_key, risk_level),
    KEY idx_frf_student_id (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Note on Spatial Indexes:
-- R-Tree / Spatial indexes are strictly omitted because OULAD contains no coordinate/GIS
-- geometry data. Regions are alphanumeric categorical strings (e.g., 'East Anglian Region').
