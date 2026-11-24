-- ==============================================================================
-- Script: sql/02_create_staging_bronze_tables.sql
-- Phase: Phase 2 - Staging + Bronze Bulk Loading (ETL Step 1)
-- Purpose: Define DDL for Bronze (immutable 1:1 raw CSV copies) and Staging tables.
-- Inputs: None
-- Outputs: Tables in `bronze` and `staging` schemas
-- Dependencies: Schemas created in 01_create_schemas.sql
-- Run Order: 02
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. BRONZE LAYER (1:1 Raw Copies of Source OULAD CSV Files)
-- ------------------------------------------------------------------------------

-- courses.csv
CREATE TABLE IF NOT EXISTS bronze.raw_courses (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    module_presentation_length INT NOT NULL,
    PRIMARY KEY (code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- assessments.csv
CREATE TABLE IF NOT EXISTS bronze.raw_assessments (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_assessment INT UNSIGNED NOT NULL,
    assessment_type VARCHAR(10) NOT NULL,
    date SMALLINT NULL,
    weight DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (id_assessment),
    KEY idx_raw_ass_course (code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- vle.csv
CREATE TABLE IF NOT EXISTS bronze.raw_vle (
    id_site INT UNSIGNED NOT NULL,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    week_from SMALLINT NULL,
    week_to SMALLINT NULL,
    PRIMARY KEY (id_site),
    KEY idx_raw_vle_course (code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- studentInfo.csv
CREATE TABLE IF NOT EXISTS bronze.raw_student_info (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    gender VARCHAR(5) NOT NULL,
    region VARCHAR(50) NOT NULL,
    highest_education VARCHAR(50) NOT NULL,
    imd_band VARCHAR(20) NULL,
    age_band VARCHAR(20) NOT NULL,
    num_of_prev_attempts SMALLINT NOT NULL,
    studied_credits SMALLINT NOT NULL,
    disability VARCHAR(5) NOT NULL,
    final_result VARCHAR(20) NOT NULL,
    KEY idx_raw_info_student (id_student),
    KEY idx_raw_info_course (code_module, code_presentation),
    KEY idx_raw_info_student_course (id_student, code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- studentRegistration.csv
CREATE TABLE IF NOT EXISTS bronze.raw_student_registration (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    date_registration SMALLINT NULL,
    date_unregistration SMALLINT NULL,
    KEY idx_raw_reg_student (id_student),
    KEY idx_raw_reg_course (code_module, code_presentation),
    KEY idx_raw_reg_student_course (id_student, code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- studentAssessment.csv
CREATE TABLE IF NOT EXISTS bronze.raw_student_assessment (
    id_assessment INT UNSIGNED NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    date_submitted SMALLINT NOT NULL,
    is_banked TINYINT NOT NULL,
    score DECIMAL(5,2) NULL,
    KEY idx_raw_sa_student (id_student),
    KEY idx_raw_sa_assessment (id_assessment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- studentVle.csv (~10.65M rows)
CREATE TABLE IF NOT EXISTS bronze.raw_student_vle (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    id_site INT UNSIGNED NOT NULL,
    date SMALLINT NOT NULL,
    sum_click INT UNSIGNED NOT NULL,
    KEY idx_raw_sv_student_course (id_student, code_module, code_presentation),
    KEY idx_raw_sv_site (id_site)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- 2. STAGING LAYER (Integrated Ingestion Tables & Views per Architecture)
-- ------------------------------------------------------------------------------

-- stg_courses
CREATE TABLE IF NOT EXISTS staging.stg_courses (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    module_presentation_length INT NOT NULL,
    PRIMARY KEY (code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- stg_students (studentInfo + studentRegistration)
CREATE TABLE IF NOT EXISTS staging.stg_students (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    gender VARCHAR(5) NOT NULL,
    region VARCHAR(50) NOT NULL,
    highest_education VARCHAR(50) NOT NULL,
    imd_band VARCHAR(20) NULL,
    age_band VARCHAR(20) NOT NULL,
    num_of_prev_attempts SMALLINT NOT NULL,
    studied_credits SMALLINT NOT NULL,
    disability VARCHAR(5) NOT NULL,
    final_result VARCHAR(20) NOT NULL,
    date_registration SMALLINT NULL,
    date_unregistration SMALLINT NULL,
    KEY idx_stg_student_course (id_student, code_module, code_presentation)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- stg_assessments (studentAssessment + assessments)
CREATE TABLE IF NOT EXISTS staging.stg_assessments (
    id_assessment INT UNSIGNED NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    assessment_type VARCHAR(10) NOT NULL,
    assessment_date SMALLINT NULL,
    weight DECIMAL(5,2) NOT NULL,
    date_submitted SMALLINT NOT NULL,
    is_banked TINYINT NOT NULL,
    score DECIMAL(5,2) NULL,
    KEY idx_stg_ass_student (id_student, code_module, code_presentation),
    KEY idx_stg_ass_id (id_assessment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- stg_vle (studentVle + vle) - Integrated View to prevent disk duplication of 10.65M rows
CREATE OR REPLACE VIEW staging.stg_vle AS
SELECT 
    sv.code_module,
    sv.code_presentation,
    sv.id_student,
    sv.id_site,
    v.activity_type,
    v.week_from,
    v.week_to,
    sv.date,
    sv.sum_click
FROM bronze.raw_student_vle sv
LEFT JOIN bronze.raw_vle v 
  ON sv.id_site = v.id_site 
 AND sv.code_module = v.code_module 
 AND sv.code_presentation = v.code_presentation;
