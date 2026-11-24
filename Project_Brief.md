CONTEXT
Act as a senior data engineer and BI developer helping me with this project.
I am a university student building a combined Data Warehousing & BI (DWBI)
and Data Analysis & Visualization (DAV) project. I am currently working solo
on the whole project, including the Power BI dashboard, but it may be handed
to another team member later, so everything must stay understandable to
someone who did not write it. Explain things clearly, since I must
understand and defend every step in a viva. Write complete, runnable code,
never placeholders, and explain briefly why each choice is made.

PROJECT
Title: University Dropout Early-Warning Warehouse (Student Retention Power BI Dashboard)
Dataset: Open University Learning Analytics Dataset (OULAD), Kaggle, 2013-2014
Files: studentInfo.csv, studentRegistration.csv, studentAssessment.csv,
       assessments.csv, courses.csv, vle.csv, studentVle.csv
Goal: Identify students at risk of dropping out (final_result = Withdrawn or
Fail) early enough for advisors to intervene, and show them in an interactive
Power BI dashboard by course and week.

TECH STACK (fixed)
- Database: MySQL 8 (schemas: staging, bronze, silver, gold, marts)
- Language: Python 3.10+ (pandas, numpy, SQLAlchemy + PyMySQL, scikit-learn,
  matplotlib, seaborn, plotly optional)
- Dashboard: Power BI Desktop (connected to MySQL)
- OS: Windows
- No Git. Versioning is done through folder snapshots and mysqldump backups
  (see BACKUP AND VERSIONING).
- Provide requirements.txt and keep DB credentials in a .env file, never
  hard-coded.

ARCHITECTURE (follow exactly)
Data Sources -> Staging Layer -> Lakehouse (Bronze -> Silver -> Gold)
-> Data Marts (Academic Mart, Early Warning Mart) -> Analytics & AI
(EDA in Python/Pandas, Expert System with Backward Chaining, Power BI)
-> Users (Student Advisors, Course Instructors, University Admin).
AI results are written back into the Early Warning Mart.

Staging tables: stg_students (studentInfo + studentRegistration),
stg_assessments (studentAssessment + assessments), stg_vle (studentVle + vle).
Lakehouse in MySQL: Bronze = raw copies of the CSVs exactly as loaded (also
keep the original CSVs as the raw file layer); Silver = cleaned and joined
student-course activity; Gold = weekly student engagement, analysis-ready.
Note: MySQL is not a true lakehouse, so Bronze/Silver/Gold are implemented as
separate schemas plus the raw CSV files. Say this explicitly in the report.

DELIVER IN THIS ORDER (finish and confirm each phase before the next)

PHASE 1 - Project setup
- Folder structure: data/raw, sql/, etl/, eda/, ai/, dashboard/, docs/, backups/
- requirements.txt, .env template, DB connection helper in Python
- SQL to create the schemas
- Create the starter files: README.md, PROJECT_STATUS.md,
  docs/data_dictionary.md, docs/decisions_log.md

PHASE 2 - Staging + Bronze (ETL step 1)
- CREATE TABLE statements with proper data types
- Python script to bulk-load each CSV into staging, then into Bronze
  (chunked loading for the large studentVle file, around 10M rows)
- Row-count reconciliation check between each CSV and its table

PHASE 3 - Cleaning and Silver layer (ETL step 2)
Handle explicitly and log how many rows each rule affects:
- Missing assessment scores (NULL score) -> decide and justify treatment
- Missing imd_band and date_registration values
- Date offsets: dates are days relative to presentation start and can be
  negative; keep as offsets and add week_number = FLOOR(date / 7)
- Duplicate registrations (same student, module, presentation) -> dedupe rule
- date_unregistration present = withdrawn; check consistency with final_result
- Join key: (id_student, code_module, code_presentation)
Output: silver tables for student-course info, weighted assessment
performance, and VLE activity. Produce a data quality log
(docs/data_quality_log.md).

PHASE 4 - Gold layer
- Weekly engagement per student per course presentation: total clicks,
  active days, distinct VLE resources, clicks by activity_type, cumulative
  clicks, week-over-week change, assessments submitted so far, average score
  so far, weighted score so far, days submitted early/late
- IMPORTANT: every feature at week N must use only data available up to
  week N (no target leakage), so the early-warning logic is realistic.

PHASE 5 - Data marts (star schemas)
- Academic Mart: dim_student, dim_course (module + presentation), dim_date
  (week), dim_assessment_type, fact_student_performance
- Early Warning Mart: dim_student, dim_course, dim_week,
  fact_weekly_engagement, fact_risk_flag (student_id, course, week,
  risk_level, risk_score, rules_triggered, flagged_at)
- Give DDL, load SQL, primary/foreign keys, and sensible indexes
- Explain why each index is chosen (note that no R-Tree/spatial index is
  needed since there is no location data)
- Produce a complete data dictionary for both marts (table, column, type,
  meaning, example value) so the dashboard can be built, by me or anyone
  taking over, without needing to know how the data was prepared

PHASE 6 - EDA in Python (also feeds the DAV requirement)
Produce a clear, commented script or notebook with labelled charts and a
one-line insight under each:
- Pass / fail / distinction / withdrawn rates overall and by course,
  presentation, gender, age band, region, education level, IMD band
- Score distributions and assessment submission behaviour
- Click activity vs final result, engagement trend by week for each outcome
- When withdrawals happen (week distribution)
- Correlation heatmap of the engineered features
Save figures to dashboard/figures and key tables to CSV.

PHASE 7 - AI Expert System (Backward Chaining)
- Goal: prove the hypothesis AT_RISK(student, course, week)
- Knowledge base of IF-THEN rules derived from the EDA, for example:
  AT_RISK IF low_engagement AND missed_assessments;
  low_engagement IF clicks_last_2_weeks < threshold;
  missed_assessments IF submitted < expected;
  low_performance IF weighted_score < threshold; etc.
- Implement a real backward-chaining inference engine in Python (goal stack,
  rule lookup, sub-goal resolution against facts), not a disguised
  if/else block. Record the rules that fired as an explanation per student.
- Derive thresholds from the data (percentiles), not guesses, keep them in a
  config file, and document where each value came from
- Output risk_level (Low / Medium / High), risk_score and rules_triggered,
  then WRITE BACK to fact_risk_flag in the Early Warning Mart
- Validate against actual outcomes: precision, recall, F1, confusion matrix,
  and how many weeks early the system flags students who later withdraw
- Optional: compare with a simple scikit-learn baseline (logistic
  regression / decision tree) to justify the rule-based approach
- Make fact_risk_flag a clean, stable, documented table, since Power BI
  will connect to it. Update the data dictionary.

PHASE 8 - Power BI dashboard (main DAV deliverable)
Note: the agent cannot operate Power BI Desktop. Provide the Power Query (M)
code, DAX measures (saved in dashboard/dax_measures.md), the MySQL
connection steps, and a page-by-page build guide with exact visuals, fields
and slicers, so I can build the report manually. Give a CSV export of the
marts as a fallback in dashboard/export/.
Connect to MySQL (explain the MySQL connector setup). Do transformations in
Power Query where appropriate and write DAX measures for: Total Students,
Withdrawal Rate, Pass Rate, At-Risk Count, At-Risk %, Avg Engagement
(clicks), Avg Score, Early Detection Lead Time, and week-over-week change.
Design 5 pages:
1. Executive Overview - KPI cards, outcome distribution, trend by presentation
2. At-Risk Students - by course and week (heat-map matrix), risk level
   breakdown, filterable student table with rules triggered, drill-through
   to a student detail page
3. Engagement Analysis - weekly clicks by outcome, activity types, resource usage
4. Performance and Assessments - score distribution, submission timeliness,
   score vs engagement
5. Demographics and Retention - outcomes by age band, gender, region,
   education, IMD band
Requirements: slicers (course, presentation, week, risk level, demographics),
cross-filtering, drill-through, tooltips, bookmarks or navigation buttons,
consistent colour palette and fonts, and a justification for every chart
type chosen (right chart for the data, avoid clutter). Add a short
"insights and recommendations" section for advisors, instructors and admin,
and state what each user group should do with each page.

PHASE 9 - Documentation and report
- ER/star-schema description, ETL flow, data quality log, rule base table,
  evaluation results, dashboard screenshot checklist, limitations and
  future work
- A short viva/demo script and likely examiner questions with answers,
  covering the whole pipeline, not just one part

HANDOFF REQUIREMENTS (important)
I am working solo for now, but the project may be passed to someone else at
any point, so keep these habits throughout.

At the end of EVERY phase, provide:
1. A "Phase summary" of 5-8 lines: what was built, which tables/files were
   created, and why the key decisions were made.
2. An update to PROJECT_STATUS.md with these sections:
   - Completed phases and current phase (with date)
   - Exact run order (scripts/SQL files in sequence, with commands)
   - Tables created (schema.table, row count, grain, purpose)
   - Decisions and assumptions (e.g. how NULL scores were treated, and why)
   - Known issues / open questions
   - Next step (and, if stopped mid-phase, exactly where work paused)
3. Row-count and sanity checks to confirm the phase worked.
4. Updates to docs/data_dictionary.md and docs/decisions_log.md (date,
   decision, reason, alternatives rejected). If an earlier-phase script is
   changed, log it and flag which downstream outputs must be re-run.

Code standards for readability:
- Every script starts with a header comment: purpose, inputs, outputs,
  dependencies, and which phase it belongs to.
- Number files in run order (01_create_schemas.sql, 02_load_staging.py, ...).
- README.md at the root: project overview, architecture description, setup
  steps (install, .env, MySQL), and the full run order.
- No magic numbers: thresholds and settings go in a config file with comments.
- Plain, descriptive names; avoid clever one-liners.
- Provide a single run_pipeline.py (or run_all.sql plus a Python runner) that
  executes all completed phases in order, so everything can be rebuilt with
  one command.

HANDOFF CHECK (run once after Phase 8, and again before any handoff)
Confirm a person who has never seen the project could: read README.md and
PROJECT_STATUS.md, restore the database from the latest dump, run the
pipeline, understand every table from the data dictionary, and connect
Power BI to the marts. List anything that would block them.

BACKUP AND VERSIONING (no Git)
At the end of every phase:
- Copy the project folder into backups/ named like
  phase3_silver_done_YYYY-MM-DD
- Run mysqldump, e.g.
  mysqldump -u root -p --databases staging bronze silver gold marts > backups/phase3.sql
  so the long studentVle load never needs repeating, and tell me the file names
- Keep the .env file out of any shared folders since it contains credentials;
  share the Kaggle link in the README instead of the large CSVs
- Update PROJECT_STATUS.md at the end of every working session, not only at
  phase boundaries

OUTPUT RULES (agent mode)
- Work one phase at a time. At the end of each phase, stop and wait for me to
  say "next". Do not start the next phase on your own.
- Create files directly in the workspace using the numbered names and folder
  structure above. In chat, only summarise what you created and why.
- Before running anything that changes or deletes data (DROP, TRUNCATE,
  overwriting tables or files, restoring dumps), tell me and wait for
  confirmation. Never drop a schema that already holds loaded data.
- Run the row-count and sanity checks yourself after each step and show me
  the results. If something fails, diagnose it, fix it, and tell me what
  you changed.
- Never print or log passwords. Read DB credentials only from .env.
- Do not download the dataset yourself. I will place the CSVs in data/raw.
  If a file is missing, tell me exactly which one.
- Keep code commented and beginner-readable. State assumptions and flag any
  decision I should confirm.
- Mention expected runtimes and memory issues for the large studentVle file
  (load it in chunks; do not read it fully into memory).
- Start by confirming the plan in 5 lines and asking for my MySQL version,
  host/port, and whether the CSVs are in data/raw.
