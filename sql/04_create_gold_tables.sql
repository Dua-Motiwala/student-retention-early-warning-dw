-- ==============================================================================
-- Script: sql/04_create_gold_tables.sql
-- Phase: Phase 4 - Gold Layer (Weekly Engagement & Zero Target Leakage)
-- Purpose: Define DDL for the analysis-ready Gold Layer weekly feature store.
-- Inputs: Aggregated from Silver Layer tables
-- Outputs: Table `gold.gold_student_weekly_engagement`
-- Dependencies: silver.silver_students, silver.silver_assessments, silver.silver_vle_activity
-- Run Order: 04
-- ==============================================================================

CREATE TABLE IF NOT EXISTS gold.gold_student_weekly_engagement (
    code_module VARCHAR(10) NOT NULL,
    code_presentation VARCHAR(10) NOT NULL,
    id_student INT UNSIGNED NOT NULL,
    week_number SMALLINT NOT NULL,

    -- 1. Weekly VLE Interaction Activity (Week N)
    weekly_clicks INT UNSIGNED NOT NULL DEFAULT 0,
    active_days TINYINT UNSIGNED NOT NULL DEFAULT 0,
    distinct_resources SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    clicks_oucontent INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_forumng INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_quiz INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_homepage INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_subpage INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_resource INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_url INT UNSIGNED NOT NULL DEFAULT 0,
    clicks_other INT UNSIGNED NOT NULL DEFAULT 0,

    -- 2. Longitudinal Velocity & Engagement Velocity (<= Week N, Zero Leakage)
    cumulative_clicks INT UNSIGNED NOT NULL DEFAULT 0,
    cumulative_active_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    prev_week_clicks INT UNSIGNED NOT NULL DEFAULT 0,
    wow_click_change INT NOT NULL DEFAULT 0,
    clicks_last_2_weeks INT UNSIGNED NOT NULL DEFAULT 0,

    -- 3. Academic Assessment Milestones (<= Week N, Zero Leakage)
    assessments_submitted_so_far SMALLINT NOT NULL DEFAULT 0,
    avg_score_so_far DECIMAL(5,2) NULL,
    weighted_score_so_far DECIMAL(7,3) NOT NULL DEFAULT 0.000,
    late_submissions_so_far SMALLINT NOT NULL DEFAULT 0,
    avg_submission_delay_so_far DECIMAL(5,2) NULL,

    -- 4. Status Flags & Ground Truth Reference
    is_registered_by_week TINYINT NOT NULL DEFAULT 1,
    is_withdrawn_by_week TINYINT NOT NULL DEFAULT 0,
    final_result VARCHAR(20) NOT NULL,

    PRIMARY KEY (id_student, code_module, code_presentation, week_number),
    KEY idx_gold_course_week (code_module, code_presentation, week_number),
    KEY idx_gold_student_course (id_student, code_module, code_presentation),
    KEY idx_gold_week (week_number),
    KEY idx_gold_result (final_result)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
