# University Dropout Early-Warning Warehouse
## Student Retention Power BI Dashboard & AI Early-Warning System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Database MySQL 8.0](https://img.shields.io/badge/Database-MySQL%208.0-orange.svg)](https://www.mysql.com/)
[![Dashboard Power BI](https://img.shields.io/badge/BI-Power%20BI-yellow.svg)](https://powerbi.microsoft.com/)

---

## 1. Project Overview

This project implements an end-to-end **Data Warehousing & Business Intelligence (DWBI)** and **Data Analysis & Visualization (DAV)** solution using the **Open University Learning Analytics Dataset (OULAD)** (Kaggle, 2013–2014).

The primary objective is to **identify university students at risk of dropping out** (`final_result` = *Withdrawn* or *Fail*) early in the semester, allowing student advisors and course instructors to execute targeted, timely academic interventions.

Key deliverables include:
1. **Medallion Lakehouse Architecture in MySQL 8** (`staging` -> `bronze` -> `silver` -> `gold` -> `marts`).
2. **Feature Store with Strict Temporal Integrity** (Week $N$ features use strictly activity $\le N$ with zero target leakage).
3. **AI Expert System with Backward Chaining** that infers student risk hypotheses (`AT_RISK`) and provides transparent rule explanations.
4. **Interactive 5-Page Power BI Dashboard** connected directly to dimensional star schema marts.

---

## 2. Architecture & Layer Separation

Although MySQL is an RDBMS rather than a distributed object storage lakehouse, the pipeline emulates the **Lakehouse Medallion Architecture** using dedicated database schemas plus the raw file layer:

```
[Raw OULAD CSVs] (data/raw/)
       │
       ▼
 [staging] (Bulk chunked ingestion, type validation)
       │
       ▼
  [bronze] (Immutable 1:1 raw copies of source CSVs)
       │
       ▼
  [silver] (Cleaned, deduplicated, relative week offsets, unified join keys)
       │
       ▼
   [gold]  (Weekly student engagement features, cumulative clicks, zero leakage)
       │
       ├───────────────────────────────────────────┐
       ▼                                           ▼
 [Academic Mart] (marts)                 [Early Warning Mart] (marts)
 - dim_student                           - dim_student
 - dim_course                            - dim_course
 - dim_date (week)                       - dim_week
 - dim_assessment_type                   - fact_weekly_engagement
 - fact_student_performance              - fact_risk_flag (written back by AI)
       │                                           │
       └─────────────────────┬─────────────────────┘
                             ▼
     ┌───────────────────────────────────────────────┐
     │           Analytics & Presentation            │
     ├───────────────────────┬───────────────────────┤
     │  Python DAV / EDA     │  AI Expert System     │
     │  (eda/)               │  (Backward Chaining)  │
     └───────────────────────┴───────────────────────┘
                             │
                             ▼
            [Interactive Power BI Dashboard]
            - Page 1: Executive Overview
            - Page 2: At-Risk Students Matrix
            - Page 3: Engagement Analysis
            - Page 4: Performance & Assessments
            - Page 5: Demographics & Retention
```

---

## 3. Directory Structure

```text
DWBI Project/
├── data/
│   └── raw/                   # Original OULAD CSV files (source of truth)
│       ├── assessments.csv
│       ├── courses.csv
│       ├── studentAssessment.csv
│       ├── studentInfo.csv
│       ├── studentRegistration.csv
│       ├── studentVle.csv     (~10.6M rows, chunked ingestion)
│       └── vle.csv
├── sql/                       # Numbered SQL DDL and transformation scripts
│   └── 01_create_schemas.sql  # Creates: staging, bronze, silver, gold, marts
├── etl/                       # Python ETL modules and database connection helpers
│   └── db.py                  # Centralized SQLAlchemy / PyMySQL connection manager
├── eda/                       # Python exploratory data analysis and DAV scripts
├── ai/                        # Backward-chaining expert system and rule engine
├── dashboard/                 # Power BI templates, DAX measures, export CSVs
│   ├── figures/               # Saved charts and visualizations for reporting
│   └── export/                # CSV fallbacks for Power BI offline connection
├── docs/                      # Comprehensive technical documentation & viva defense
│   ├── data_dictionary.md     # Detailed dictionary of all schemas and tables
│   ├── decisions_log.md       # Architectural decisions, reasons, and rejected options
│   └── data_quality_log.md    # Data cleansing and validation audit log
├── backups/                   # Phase snapshots and mysqldump backups (no Git)
├── .env.example               # Template for database credentials
├── .env                       # Local database credentials (never shared)
├── requirements.txt           # Python library requirements
├── run_pipeline.py            # Single-command runner for the entire pipeline
├── PROJECT_BRIEF.md           # Master project brief and guidelines
└── PROJECT_STATUS.md          # Real-time tracking of phases, run orders, and metrics
```

---

## 4. Setup and Installation

### Step 1: Install Python Dependencies
Ensure Python 3.10+ is installed:
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and fill in your MySQL credentials:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_actual_password
DB_NAME=staging
MYSQL_BIN_DIR=C:\Program Files\MySQL\MySQL Server 8.0\bin
```

### Step 3: Verify MySQL Server
Ensure MySQL Server 8.0+ is running. Verify connectivity using:
```bash
python etl/db.py
```

### Step 4: Run the Pipeline
Execute phases sequentially or run the master script:
```bash
# Phase 1: Initialize Schemas
python run_pipeline.py --phase 1

# Phase 2: Ingest Raw CSVs into Bronze & Staging
python etl/02_load_staging_bronze.py
# (Or: python run_pipeline.py --phase 2)
```

#### Safe Execution & Ingestion Guardrails (`etl/02_load_staging_bronze.py`)
1. **Idempotent Safe-Skip (Default):**  
   If a table is already fully loaded and matches the source CSV row count with 100% parity (e.g. `raw_student_vle` = 10,655,280 rows), the script automatically logs `[SAFE SKIP]` and advances to the reconciliation audit in ~2 seconds without inserting duplicate rows.
2. **Auto-Repair on Partial/Mismatched Loads:**  
   If an earlier load was interrupted or left partial rows (e.g. 10,654,200 rows instead of 10,655,280), the script detects the discrepancy, automatically logs `[AUTO REPAIR]`, truncates the damaged table, and re-loads it from scratch to guarantee exact parity without duplicates.
3. **Manual Forced Reload (`--reload`):**  
   To wipe and reload all Bronze and Staging tables from scratch on demand:
   ```bash
   python etl/02_load_staging_bronze.py --reload
   ```
   This safely truncates the existing tables first and performs a fresh chunked ingestion of all raw files.

---

## 5. Master Pipeline Run Order

| Run Order | Script / File | Phase | Description |
|:---|:---|:---|:---|
| **01** | `sql/01_create_schemas.sql` | Phase 1 | Creates schemas (`staging`, `bronze`, `silver`, `gold`, `marts`) |
| **02** | `etl/02_load_staging_bronze.py` | Phase 2 | Loads raw CSVs into staging and bronze tables (chunked VLE load) |
| **03** | `etl/03_build_silver.py` | Phase 3 | Cleans data, deduplicates registrations, computes relative week offsets |
| **04** | `etl/04_build_gold.py` | Phase 4 | Computes weekly student engagement features with zero target leakage |
| **05** | `sql/05_create_marts.sql` & `etl/05_load_marts.py` | Phase 5 | Builds Star Schemas (Academic Mart & Early Warning Mart) |
| **06** | `eda/06_run_eda.py` | Phase 6 | Executes exploratory data analysis and exports visualizations |
| **07** | `ai/07_expert_system.py` | Phase 7 | Runs backward-chaining rule engine; writes flags to `fact_risk_flag` |
| **08** | Power BI Report Build | Phase 8 | Builds 5-page dashboard using DAX measures & Mart connections |
| **09** | Report & Viva Defense | Phase 9 | Finalizes documentation, viva scripts, and examiner Q&A |
