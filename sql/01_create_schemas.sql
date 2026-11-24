-- ==============================================================================
-- Script: sql/01_create_schemas.sql
-- Phase: Phase 1 - Project Setup & Architecture Initialization
-- Purpose: Create all database schemas required for the Lakehouse and Marts layers.
-- Inputs: None
-- Outputs: Schemas: staging, bronze, silver, gold, marts
-- Dependencies: MySQL 8.0+ running instance
-- Run Order: 01
-- ==============================================================================

-- 1. STAGING LAYER
-- Used for initial bulk CSV ingestion and schema-casting checks.
CREATE SCHEMA IF NOT EXISTS staging
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 2. BRONZE LAYER (Raw Data Lakehouse Layer)
-- Holds raw, unmodified table copies matching the original CSV structures 1:1.
-- Serves as the immutable source of truth in the database.
CREATE SCHEMA IF NOT EXISTS bronze
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 3. SILVER LAYER (Cleansed & Integrated Layer)
-- Holds cleaned, deduplicated, and integrated data with standardized keys and date offsets.
CREATE SCHEMA IF NOT EXISTS silver
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 4. GOLD LAYER (Feature Store / Aggregated Analytics Layer)
-- Holds weekly student engagement aggregations, cumulative metrics, and velocity indicators.
-- Guaranteed zero target leakage (features at week N use strictly data <= week N).
CREATE SCHEMA IF NOT EXISTS gold
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 5. MARTS LAYER (Dimensional Data Marts for BI & Analytics)
-- Contains Star Schemas for:
--   a) Academic Mart (dim_student, dim_course, dim_date, dim_assessment_type, fact_student_performance)
--   b) Early Warning Mart (dim_student, dim_course, dim_week, fact_weekly_engagement, fact_risk_flag)
CREATE SCHEMA IF NOT EXISTS marts
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
