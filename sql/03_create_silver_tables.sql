-- ==============================================================================
-- Script: sql/03_create_silver_tables.sql
-- Phase: Phase 3 - Cleaning and Silver Layer (ETL Step 2)
-- Purpose: Define DDL for the cleansed and integrated Silver Layer tables.
-- Inputs: Data from `bronze` and `staging` schemas
-- Outputs: Tables in `silver` schema (silver_students, silver_assessments, silver_vle_activity)
-- Dependencies: Schemas created in 01, tables loaded in 02
-- Run Order: 03
-- ==============================================================================

-- 1. silver_students
-- Cleaned demographics, registration timeline, imputed values, and withdrawal status
CREATE TABLE IF NOT EXISTS silver.silver_students (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    gender VARCHAR(5) NOT NULL,
    region VARCHAR(50) NOT NULL,
    highest_education VARCHAR(50) NOT NULL,
    imd_band VARCHAR(20) NOT NULL,               -- Cleansed: 'Unknown' for 1,111 missing rows
    age_band VARCHAR(20) NOT NULL,
    num_of_prev_attempts SMALLINT NOT NULL,
    studied_credits SMALLINT NOT NULL,
    disability VARCHAR(5) NOT NULL,
    final_result VARCHAR(20) NOT NULL,
    date_registration SMALLINT NULL,              -- Original registration day offset
    date_registration_imputed SMALLINT NOT NULL,  -- Cohort median imputed for 45 missing rows
    is_registration_imputed TINYINT NOT NULL,     -- 1 if imputed, 0 otherwise
    registration_week SMALLINT NOT NULL,          -- FLOOR(date_registration_imputed / 7)
    date_unregistration SMALLINT NULL,            -- Day of withdrawal/unregistration
    unregistration_week SMALLINT NULL,            -- FLOOR(date_unregistration / 7)
    is_withdrawn TINYINT NOT NULL,                -- 1 if final_result = 'Withdrawn' or date_unreg IS NOT NULL
    unregistration_status VARCHAR(50) NOT NULL,   -- Granular status category
    PRIMARY KEY (id_student, code_module, code_presentation),
    KEY idx_silver_stud_course (code_module, code_presentation),
    KEY idx_silver_stud_result (final_result),
    KEY idx_silver_stud_withdrawn (is_withdrawn)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. silver_assessments
-- Cleaned assessment submissions with weights, timeliness, and imputed missing scores
CREATE TABLE IF NOT EXISTS silver.silver_assessments (
    id_assessment INT UNSIGNED NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    assessment_type VARCHAR(10) NOT NULL,
    assessment_date SMALLINT NULL,                -- Due date relative to course start
    assessment_week SMALLINT NULL,                -- FLOOR(assessment_date / 7)
    weight DECIMAL(5,2) NOT NULL,
    date_submitted SMALLINT NOT NULL,             -- Actual submission date
    submission_week SMALLINT NOT NULL,            -- FLOOR(date_submitted / 7)
    submission_delay SMALLINT NULL,               -- date_submitted - assessment_date (positive = late)
    is_late TINYINT NOT NULL,                     -- 1 if submitted after due date, 0 otherwise
    is_banked TINYINT NOT NULL,                   -- Transferred from previous attempt
    score DECIMAL(5,2) NULL,                      -- Original raw score (preserves NULL)
    score_clean DECIMAL(5,2) NOT NULL,            -- Imputed as 0.0 for missing scores
    is_missing_score TINYINT NOT NULL,            -- 1 if score was missing, 0 otherwise
    weighted_score DECIMAL(7,3) NOT NULL,         -- (score_clean * weight) / 100.0
    PRIMARY KEY (id_assessment, id_student),
    KEY idx_silver_ass_student_course (id_student, code_module, code_presentation),
    KEY idx_silver_ass_week (submission_week),
    KEY idx_silver_ass_type (assessment_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. silver_vle_activity
-- Standardized daily click activity with relative week numbers and activity types
CREATE TABLE IF NOT EXISTS silver.silver_vle_activity (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    id_site INT UNSIGNED NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    date SMALLINT NOT NULL,                       -- Relative day offset (-25 to 269)
    week_number SMALLINT NOT NULL,                -- FLOOR(date / 7) (-4 to 38)
    sum_click INT UNSIGNED NOT NULL,
    KEY idx_silver_vle_student_week (id_student, code_module, code_presentation, week_number),
    KEY idx_silver_vle_activity (activity_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
