# Power BI Dashboard Specification & Visual Build Guide
**Project:** University Dropout Early-Warning Warehouse & Retention Dashboard  
**Dataset:** Open University Learning Analytics Dataset (OULAD)  
**Database:** MySQL 8.0 Community Server (`localhost:3306`, schema: `marts`)  
**Deliverable:** 5-Page Interactive Business Intelligence Report  

---

## 1. MySQL Connector & Ingestion Setup

### 1.1 Prerequisites
1. **MySQL Connector / NET:** Install **Oracle MySQL Connector/NET** (version 8.0.33 or later) or **MySQL Connector/ODBC** on the Windows machine running Power BI Desktop.
2. **Network Connectivity:** Ensure MySQL service is running locally on port 3306.

### 1.2 Connection Protocol
1. Open Power BI Desktop -> click **Get Data** -> select **MySQL database** -> click **Connect**.
2. **Server:** `localhost:3306` (or `127.0.0.1:3306`).
3. **Database:** `marts`.
4. **Data Connectivity Mode:** Select **Import** (Recommended for VertiPaq compression, instant cross-filtering, and offline report portability).
5. **Authentication:** Select **Database** tab -> Enter Username (`root`) and Password from your `.env` configuration -> click **Connect**.

---

## 2. Power Query (M) Script Library

Copy and paste each script into the **Advanced Editor** in Power Query (`Transform Data`).

### 2.1 Dimension Queries

#### Query 1: `dim_student`
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_dim_student = Source{[Schema="marts",Item="dim_student"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_dim_student,{
        {"student_key", Int64.Type},
        {"id_student", Int64.Type},
        {"gender", type text},
        {"region", type text},
        {"highest_education", type text},
        {"imd_band", type text},
        {"age_band", type text},
        {"disability", type text},
        {"total_courses_enrolled", Int64.Type},
        {"created_at", type datetime}
    })
in
    #"Changed Type"
```

#### Query 2: `dim_course`
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_dim_course = Source{[Schema="marts",Item="dim_course"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_dim_course,{
        {"course_key", Int64.Type},
        {"code_module", type text},
        {"code_presentation", type text},
        {"module_presentation_length", Int64.Type},
        {"semester_season", type text},
        {"presentation_year", Int64.Type},
        {"academic_year", type text},
        {"course_full_name", type text}
    })
in
    #"Changed Type"
```

#### Query 3: `dim_date`
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_dim_date = Source{[Schema="marts",Item="dim_date"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_dim_date,{
        {"week_key", Int64.Type},
        {"week_number", Int64.Type},
        {"week_label", type text},
        {"academic_phase", type text},
        {"is_early_warning_window", Int64.Type},
        {"start_day_offset", Int64.Type},
        {"end_day_offset", Int64.Type}
    }),
    #"Sorted Rows" = Table.Sort(#"Changed Type",{{"week_number", Order.Ascending}})
in
    #"Sorted Rows"
```

#### Query 4: `dim_assessment_type`
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_dim_assessment_type = Source{[Schema="marts",Item="dim_assessment_type"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_dim_assessment_type,{
        {"assessment_type_key", Int64.Type},
        {"assessment_type", type text},
        {"assessment_type_name", type text},
        {"marking_method", type text},
        {"is_exam", Int64.Type}
    })
in
    #"Changed Type"
```

### 2.2 Fact Queries

#### Query 5: `fact_student_performance` (Academic Mart)
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_fsp = Source{[Schema="marts",Item="fact_student_performance"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_fsp,{
        {"performance_key", Int64.Type},
        {"student_key", Int64.Type},
        {"course_key", Int64.Type},
        {"week_key", Int64.Type},
        {"assessment_type_key", Int64.Type},
        {"id_assessment", Int64.Type},
        {"id_student", Int64.Type},
        {"code_module", type text},
        {"code_presentation", type text},
        {"assessment_date", Int64.Type},
        {"date_submitted", Int64.Type},
        {"submission_delay", Int64.Type},
        {"is_late", Int64.Type},
        {"is_banked", Int64.Type},
        {"weight", type number},
        {"score", type number},
        {"score_clean", type number},
        {"is_missing_score", Int64.Type},
        {"weighted_score", type number},
        {"is_passed_assessment", Int64.Type}
    })
in
    #"Changed Type"
```

#### Query 6: `fact_weekly_engagement` (Early Warning Mart)
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_fwe = Source{[Schema="marts",Item="fact_weekly_engagement"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_fwe,{
        {"engagement_key", Int64.Type},
        {"student_key", Int64.Type},
        {"course_key", Int64.Type},
        {"week_key", Int64.Type},
        {"id_student", Int64.Type},
        {"code_module", type text},
        {"code_presentation", type text},
        {"week_number", Int64.Type},
        {"weekly_clicks", Int64.Type},
        {"active_days", Int64.Type},
        {"distinct_resources", Int64.Type},
        {"clicks_oucontent", Int64.Type},
        {"clicks_forumng", Int64.Type},
        {"clicks_quiz", Int64.Type},
        {"clicks_homepage", Int64.Type},
        {"clicks_subpage", Int64.Type},
        {"clicks_resource", Int64.Type},
        {"clicks_url", Int64.Type},
        {"clicks_other", Int64.Type},
        {"cumulative_clicks", Int64.Type},
        {"cumulative_active_days", Int64.Type},
        {"prev_week_clicks", Int64.Type},
        {"wow_click_change", Int64.Type},
        {"clicks_last_2_weeks", Int64.Type},
        {"assessments_submitted_so_far", Int64.Type},
        {"avg_score_so_far", type number},
        {"weighted_score_so_far", type number},
        {"late_submissions_so_far", Int64.Type},
        {"avg_submission_delay_so_far", type number},
        {"is_registered_by_week", Int64.Type},
        {"is_withdrawn_by_week", Int64.Type},
        {"final_result", type text}
    })
in
    #"Changed Type"
```

#### Query 7: `fact_risk_flag` (AI Early Warning Mart)
```powerquery
let
    Source = MySQL.Database("localhost:3306", "marts", [ReturnSingleDatabase=true]),
    marts_frf = Source{[Schema="marts",Item="fact_risk_flag"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(marts_frf,{
        {"risk_flag_key", Int64.Type},
        {"student_key", Int64.Type},
        {"course_key", Int64.Type},
        {"week_key", Int64.Type},
        {"student_id", Int64.Type},
        {"code_module", type text},
        {"code_presentation", type text},
        {"week_number", Int64.Type},
        {"risk_level", type text},
        {"risk_score", type number},
        {"rules_triggered", type text},
        {"flagged_at", type datetime}
    })
in
    #"Changed Type"
```

---

## 3. Data Model Relationships (Star Schema)

In Power BI **Model View**, establish the following **1-to-Many ($1:\infty$)** single-directional relationships:

```
              ┌───────────────────────────┐
              │        dim_course         │
              │  (PK: course_key [1])     │
              └─────────────┬─────────────┘
                            │
       ┌────────────────────┼────────────────────┐
       │ 1:*                │ 1:*                │ 1:*
       ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ fact_student_    │ │ fact_weekly_     │ │  fact_risk_flag  │
│ performance      │ │ engagement       │ │                  │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         ▲                    ▲                    ▲
         │ *                  │ *                  │ *
         └──────────┬─────────┴──────────┬─────────┘
                    │ 1                  │ 1
       ┌────────────┴──────────────┐ ┌───┴───────────────────────┐
       │        dim_student        │ │         dim_date          │
       │  (PK: student_key [1])    │ │    (PK: week_key [1])     │
       └───────────────────────────┘ └───────────────────────────┘
                    ▲
                    │ 1:*
       ┌────────────┴──────────────┐
       │    dim_assessment_type    │
       │(PK: assessment_type_key[1])│
       └───────────────────────────┘
```

| From Table (Dimension) | From Column (PK) | To Table (Fact) | To Column (FK) | Cardinality | Cross Filter |
|:---|:---|:---|:---|:---:|:---:|
| `dim_student` | `student_key` | `fact_student_performance` | `student_key` | 1 to Many ($1:*$) | Single |
| `dim_student` | `student_key` | `fact_weekly_engagement` | `student_key` | 1 to Many ($1:*$) | Single |
| `dim_student` | `student_key` | `fact_risk_flag` | `student_key` | 1 to Many ($1:*$) | Single |
| `dim_course` | `course_key` | `fact_student_performance` | `course_key` | 1 to Many ($1:*$) | Single |
| `dim_course` | `course_key` | `fact_weekly_engagement` | `course_key` | 1 to Many ($1:*$) | Single |
| `dim_course` | `course_key` | `fact_risk_flag` | `course_key` | 1 to Many ($1:*$) | Single |
| `dim_date` | `week_key` | `fact_student_performance` | `week_key` | 1 to Many ($1:*$) | Single |
| `dim_date` | `week_key` | `fact_weekly_engagement` | `week_key` | 1 to Many ($1:*$) | Single |
| `dim_date` | `week_key` | `fact_risk_flag` | `week_key` | 1 to Many ($1:*$) | Single |
| `dim_assessment_type` | `assessment_type_key` | `fact_student_performance` | `assessment_type_key` | 1 to Many ($1:*$) | Single |

---

## 4. Visual Design System (Style Guide)

- **Canvas Dimensions:** 16:9 widescreen (1280 × 720 px or 1920 × 1080 px).
- **Background:** Light off-white `#F8F9FA`. Card container background: Pure white `#FFFFFF` with 1px subtle border `#E2E8F0` and 4px corner radius.
- **Color Palette:**
  - Primary Brand / Executive Blue: `#1E3A8A` (Deep Navy)
  - Secondary Accent Blue: `#3B82F6` (Electric Blue)
  - Success / Pass / Distinction: `#10B981` (Emerald Green)
  - Warning / Medium Risk: `#F59E0B` (Amber)
  - Critical / High Risk / Withdrawal: `#EF4444` (Ruby Red)
  - Neutral Dark Typography: `#0F172A` (Slate 900)
  - Neutral Muted Typography: `#64748B` (Slate 500)
- **Typography:** Segoe UI or Aptos. Headers: 14pt-18pt Bold; KPI Callout: 22pt-28pt Bold; Body/Tables: 10pt Regular.

---

## 5. Page-by-Page Build Guide (User Dashboard Alignment)

```
+---------------------------------------------------------------------------------------------------+
|  [TITLE] Open University | Student Retention Executive Overview            [PAGE NAVIGATION TABS] |
|  Filters: code_module [All v] | code_presentation [All v] | academic_year [All v]                 |
+---------------------------------------------------------------------------------------------------+
```

---

### Page 1: Executive Overview (Verified & Locked)
*Target Audience: University Administration, Deans, Academic Directors.*  
*Primary Goal: High-level KPI monitoring of enrollment volumes, university retention benchmarks, and semester attrition trends.*

```
+-------------------+ +-------------------+ +-------------------+ +-------------------+ +-------------------+
|  Total Students   | |   Pass Rate (%)   | |  Withdrawal Rate  | |     At-Risk %     | |  Total Enrolments |
|        29K        | |       55.9%       | |       25.1%       | |       76.4%       | |        33K        |
+-------------------+ +-------------------+ +-------------------+ +-------------------+ +-------------------+
+------------------------------------------+ +------------------------------------------+ +--------------------+
| Visual 1.1: Student Outcome Distribution | | Visual 1.2: Retention Trend Across Pres. | | Visual 1.3: Module |
| (Donut Chart: Pass 42.7%, Withdrawn 23.6%| | (100% Stacked Column: 2013B to 2014J)    | | Retention Table    |
|  Fail 23.2%, Distinction 10.4%)          | |                                          | | (7 Modules + Total)|
+------------------------------------------+ +------------------------------------------+ +--------------------+
```

#### Detailed Visual Inventory & Live Verified Outcomes:
1. **Top Slicers Bar (Row 1 — 3 Slicers):**
   - **Slicer 1 (Module Slicer):** `dim_course[code_module]` (Dropdown style). Items: `AAA`, `BBB`, `CCC`, `DDD`, `EEE`, `FFF`, `GGG`.
   - **Slicer 2 (Presentation Slicer):** `dim_course[code_presentation]` (Dropdown style). Items: `2013B`, `2013J`, `2014B`, `2014J`.
   - **Slicer 3 (Academic Year Slicer):** `dim_course[academic_year]` (Dropdown style). Items: `2013`, `2014`.
2. **KPI Cards (Row 2 — 5 Horizontal Cards):**
   - **Card 1.1:** `[Total Students]` -> Displays **`29K`** (Exact distinct individuals: 28,785).
   - **Card 1.2:** `[Pass Rate]` -> Displays **`55.9%`** (Emerald Green `#10B981`).
   - **Card 1.3:** `[Withdrawal Rate]` -> Displays **`25.1%`** (Ruby Red `#EF4444`).
   - **Card 1.4:** `[At-Risk %]` -> Displays **`76.4%`** (Amber `#F59E0B` — cumulative risk across terms).
   - **Card 1.5:** `[Total Enrolments]` -> Displays **`33K`** (Exact registrations: 32,593).
3. **Visual 1.1 — Student Outcome Distribution (Donut Chart):**
   - **Legend:** `fact_weekly_engagement[final_result]`.
   - **Values:** `fact_weekly_engagement[student_key]` (Count Distinct).
   - **Live Verified Outcome:**
     - Center Callout: **`26.074K`**
     - **Pass:** `11.88K (42.74%)` (Green `#10B981`)
     - **Withdrawn:** `6.56K (23.59%)` (Orange `#F97316`)
     - **Fail:** `6.46K (23.23%)` (Red `#EF4444`)
     - **Distinction:** `2.9K (10.44%)` (Blue `#3B82F6`)
4. **Visual 1.2 — Retention & Attrition Trend Across Presentations (100% Stacked Column Chart):**
   - **X-Axis:** `dim_course[code_presentation]` (Chronological: `2013B` -> `2013J` -> `2014B` -> `2014J`).
   - **Y-Axis:** `fact_weekly_engagement[student_key]` (Count Distinct).
   - **Legend:** `final_result` (Distinction, Fail, Pass, Withdrawn).
5. **Visual 1.3 — Retention Benchmark by Course Module (Table):**
   - **Columns:** `dim_course[code_module]`, `[Total Students]`, `[Pass Rate]`, `[Withdrawal Rate]`.
   - **Live Verified Row Outcomes:**
     | code_module | Total Students | Pass Rate | Withdrawal Rate |
     |:---:|:---:|:---:|:---:|
     | **AAA** | **702** | **75.6%** | **15.0%** |
     | **BBB** | **6,484** | **57.9%** | **19.0%** |
     | **CCC** | **3,852** | **43.5%** | **38.7%** |
     | **DDD** | **5,407** | **48.3%** | **30.6%** |
     | **EEE** | **2,634** | **62.6%** | **18.7%** |
     | **FFF** | **6,799** | **53.7%** | **24.7%** |
     | **GGG** | **2,359** | **64.2%** | **8.6%** |
     | **Total** | **26,074** | **55.9%** | **25.1%** |

---

### Page 2: At-Risk Students Matrix (Verified & Locked)
*Target Audience: Student Retention Advisors, Student Support Officers, Personal Tutors.*  
*Primary Goal: Pinpoint vulnerable students early enough for intervention, examine backward-chaining rule explanations, and prioritize high-risk caseloads.*

```
+---------------------------------------------------------------------------------------+
| Slicers: week_number [All v] | risk_level [High | Low | Medium] | code_module [All v] |
+---------------------------------------------------------------------------------------+
| Visual 2.1: Course x Week At-Risk Heat-Map Matrix (Rows: Module, Cols: Week 1 to 10)  |
| [Heat-Map Matrix shaded green to deep crimson by At-Risk %]                          |
+---------------------------------------------------------------------------------------+
| Visual 2.2: Actionable Student Intervention Table                                     |
| [student_id | code_module | risk_level | Avg score | Avg clicks L2W | Submissions ...] |
+---------------------------------------------------------------------------------------+
```

#### Detailed Visual Inventory & Live Verified Outcomes:
1. **Top Slicers Bar (3 Slicers):**
   - **Slicer 1 (Week):** `dim_date[week_number]` (Dropdown).
   - **Slicer 2 (Risk Level):** `fact_risk_flag[risk_level]` (Tiles: `High`, `Low`, `Medium`).
   - **Slicer 3 (Module):** `dim_course[code_module]` (Dropdown).
2. **Visual 2.1 — Course × Week At-Risk Heat-Map Matrix:**
   - **Rows:** `dim_course[code_module]` (`AAA` through `GGG`, Total).
   - **Columns:** `dim_date[week_label]` (`Week 1` through `Week 10`, Total).
   - **Values:** `_Measures[At-Risk %]`.
   - **Conditional Formatting:** Background Color -> Field Value -> `[Heatmap Risk Color]`.
   - **Live Verified Row Outcomes:**
     - **AAA:** Week 1: 26.2%, Week 5: 26.7%, Week 10: 36.8%, Total: **65.6%**
     - **BBB:** Total: **88.3%**
     - **CCC:** Total: **89.2%** (Severe Attrition Course)
     - **DDD:** Total: **74.7%**
     - **EEE:** Total: **65.1%**
     - **FFF:** Total: **51.3%**
     - **GGG:** Total: **98.5%**
     - **Total Row:** Week 1: 42.4%, Week 2: 33.1%, Week 3: 35.7%, Week 4: 35.2%, Week 5: 33.7%, Week 6: 32.7%, Week 7: 35.9%, Week 8: 40.1%, Week 9: 37.4%, Week 10: 39.1%, Cumulative Total: **76.4%**
3. **Visual 2.2 — Actionable Student Alert Table:**
   - **Columns:** `student_id`, `code_module`, `risk_level`, `Average of risk_score`, `Average of clicks_last_2_weeks`, `Average of assessments_submitted_so_far`, `rules_triggered`.
   - **Intervention Caseload Filter:** Set `week_number` = **Week 5** and click **High** in the `risk_level` tile slicer to display the 2,292 highest priority student alerts with backward-chaining rule justifications.

---

### Page 3: Engagement Analysis (Verified & Locked)
*Target Audience: Instructional Designers, Learning Analytics Specialists.*  
*Primary Goal: Track student VLE activity patterns, examine engagement drop-offs, and identify which learning resources drive retention.*

```
+---------------------------------------------------------------------------------------+
| Slicers: code_module [All v] | week_number [All v]                                    |
+---------------------------------------------------------------------------------------+
| Visual 3.1: Weekly Engagement Trajectory  | Visual 3.2: VLE Activity Mix by Module    |
| (Line Chart: Wk 0 to 40 by final_result)  | (100% Stacked Bar: FFF, EEE, BBB, DDD...) |
+-------------------------------------------+ +-----------------------------------------+
| Visual 3.3: Week-over-Week Click Velocity (Acceleration vs. Deceleration)             |
| (Clustered Column Chart: Green positive spikes, Red negative dips)                    |
+---------------------------------------------------------------------------------------+
```

#### Detailed Visual Inventory & Live Verified Outcomes:
1. **Top Slicers Bar (2 Slicers):**
   - **Slicer 1 (Module):** `dim_course[code_module]` (Dropdown).
   - **Slicer 2 (Week):** `dim_date[week_number]` (Dropdown).
2. **Visual 3.1 (Top Left) — Weekly Engagement Trajectory by Student Outcome (Line Chart):**
   - **X-Axis:** `dim_date[week_number]` (Range 0 to 40).
   - **Y-Axis:** `_Measures[Avg Engagement (Clicks)]`.
   - **Legend:** `fact_weekly_engagement[final_result]` (Distinction, Fail, Pass, Withdrawn).
   - **Live Pattern:** Distinction and Pass sustain >55–80 clicks/week throughout the term, while Withdrawn cohorts drop below 20 clicks by Weeks 3–5.
3. **Visual 3.2 (Top Right) — VLE Activity Mix by Course Module (100% Stacked Bar Chart):**
   - **Y-Axis:** `dim_course[code_module]` (`FFF`, `EEE`, `BBB`, `DDD`, `AAA`, `CCC`).
   - **X-Axis:** Sum of `clicks_oucontent`, `clicks_quiz`, `clicks_forumng`, `clicks_homepage`, `clicks_subpage`, `clicks_resource`, `clicks_url` (0M to 15M Clicks).
   - **Live Volume:** Course `FFF` dominates absolute engagement (~16M clicks), followed by `BBB` (~5M) and `EEE` (~4.5M).
4. **Visual 3.3 (Bottom) — Week-over-Week Click Velocity (Acceleration vs. Deceleration):**
   - **X-Axis:** `dim_date[week_number]` (0 to 40).
   - **Y-Axis:** `_Measures[Clicks WoW Change]`.
   - **Live Pattern:** Surges of positive click change in weeks leading up to major assessment deadlines followed by recovery troughs.

---

### Page 4: Performance & Assessments (Milestone Grading & Timeliness)
*Target Audience: Course Instructors, Module Chairs, Assessment Officers.*  
*Primary Goal: Monitor submission deadlines, evaluate assessment difficulty, and detect grade slipping.*

```
+---------------------------------------------------------------------------------------+
| Slicers: code_module [All v] | assessment_type [All v]                                |
+-------------------------------------------+ +-----------------------------------------+
| Visual 4.1: Assessment Score Distribution | Visual 4.2: Submission Delay vs Grade     |
| (10-Point Bins with 40% Pass Line)        | (Scatter: Days Early/Late vs Grade)       |
| [Already Built on Canvas]                 | [To Build: Right Top Quadrant]            |
+-------------------------------------------+ +-----------------------------------------+
| Visual 4.3: Assessment Milestone & Difficulty Benchmarks (Table Grid)                 |
| [Columns: assessment_type | Total Submissions | Avg Score | Late % | Pass Rate %]     |
+---------------------------------------------------------------------------------------+
```

#### Detailed Visual Inventory & Expected Outcomes:
1. **Visual 4.1 — Assessment Score Distribution (Column Chart — Already Built):**
   - **X-Axis:** `score_clean (bins)` (Bin size 10).
   - **Y-Axis:** Count of `performance_key`.
   - **Red Reference Line:** Value = 40 (Passing boundary).
2. **Visual 4.2 — Timeliness vs Grade Penalty (Scatter Plot — Place Top Right):**
   - **X-Axis:** `fact_student_performance[submission_delay]` (Days: -20 early to +30 late).
   - **Y-Axis:** `fact_student_performance[score_clean]`.
   - **Legend:** `dim_course[code_module]`.
   - **Red Reference Line:** Constant line at X = 0 (Submission Deadline).
   - **Expected Verification Outcome:** On-time submissions average **76.1%**, late submissions average **74.8%** (dropping to <60% for severe delays >7 days). Overall late rate = **28.4% (49,318 submissions)**.
3. **Visual 4.3 — Assessment Milestone & Difficulty Benchmarks (Table — Place Across Bottom):**
   - **Columns:** `dim_assessment_type[assessment_type]`, Count of `performance_key` ("Total Submissions"), `[Avg Score]`, `[Late Submission %]`, `[Assessment Pass Rate]`.
   - **Expected Verification Rows (When slicer is 'All'):**
     | assessment_type | Total Submissions | Avg Score | Late Submission % | Assessment Pass Rate |
     |:---|:---:|:---:|:---:|:---:|
     | **CMA** | **70,527** | **80.9%** | **46.8%** | **97.5%** |
     | **Exam** | **4,959** | **65.6%** | **0.1%** | **88.6%** |
     | **TMA** | **98,426** | **67.0%** | **16.6%** | **94.5%** |
     | **Total** | **173,912** | **72.6%** | **28.4%** | **95.5%** |

---

### Page 5: Demographics & Retention (Equity, Diversity, & Inclusion)
*Target Audience: University Planning, EDI Committees, Student Services Administration.*  
*Primary Goal: Uncover systemic equity gaps across socioeconomic deprivation (IMD), prior education, age, region, and declared disability.*

```
+---------------------------------------------------------------------------------------+
| Slicers: gender [All v] | age_band [All v]                                            |
+-------------------------------------------+ +-----------------------------------------+
| Visual 5.1: Attrition by IMD Deprivation  | | Visual 5.2: Outcome by Education Level  |
| (100% Stacked Bar: 0-10% to 90-100%)      | | (100% Stacked Column: No Formal to PG)  |
+-------------------------------------------+ +-----------------------------------------+
| Visual 5.3: Regional Retention Rates      | | Visual 5.4: Disability Support Audit    |
| (Clustered Bar: UK Regions sorted)       | | (Clustered Column: Declared vs None)    |
+-------------------------------------------+ +-----------------------------------------+
```

#### Detailed Visual Inventory & Expected Outcomes (2 × 2 Grid Layout):
1. **Visual 5.1 (Top Left) — Socioeconomic Deprivation Impact (100% Stacked Bar Chart):**
   - **Y-Axis:** `dim_student[imd_band]`.
   - **X-Axis:** `fact_weekly_engagement[student_key]` (Count Distinct).
   - **Legend:** `fact_weekly_engagement[final_result]`.
   - **Expected Deprivation Disparity:** 0-10% decile has **37.2% Withdrawn**, while 90-100% decile has **25.9% Withdrawn** (an **11.3% retention gap**).
2. **Visual 5.2 (Top Right) — Prior Educational Attainment (100% Stacked Column Chart):**
   - **X-Axis:** `dim_student[highest_education]`.
   - **Y-Axis:** `fact_weekly_engagement[student_key]` (Count Distinct).
   - **Legend:** `fact_weekly_engagement[final_result]`.
   - **Expected Outcome:** `No Formal quals` (**42.9% Withdrawn**), `Lower Than A Level` (**35.1%**), `A Level` (**28.7%**), `HE` (**27.1%**), `Post Graduate` (**23.6%**).
3. **Visual 5.3 (Bottom Left) — UK Regional Retention Disparities (Clustered Bar Chart):**
   - **Y-Axis:** `dim_student[region]` (Sorted descending by `Withdrawal Rate`).
   - **X-Axis:** `_Measures[Withdrawal Rate]`.
   - **Expected Ranking:** North Western (35.6%), West Midlands (35.4%), East Midlands (34.8%), London (34.5%) down to Scotland (26.3%), Wales (25.1%), Ireland (23.1%).
4. **Visual 5.4 (Bottom Right) — Accessibility & Disability Support (Clustered Column Chart):**
   - **X-Axis:** `dim_student[disability]` ('N' vs 'Y').
   - **Y-Axis:** `[Pass Rate]`, `[Withdrawal Rate]`.
   - **Expected Outcome:**
     - No Disability ('N', 29,429): Pass 48.2%, Withdrawn 30.3%.
     - Declared Disability ('Y', 3,164): Pass 38.1%, Withdrawn 39.3% (**+9.0% Higher Dropout Rate**).

---

## 6. Role-Based Action Guides

### 6.1 Student Retention Advisors
- **Primary Dashboard Page:** Page 2 (*At-Risk Students Matrix*).
- **Weekly Workflow:**
  1. Set the **Week Number** slicer to the active term week (e.g., Week 4).
  2. Filter by **Risk Level = 'High'**.
  3. Sort the **Actionable Student Table** by **Risk Score** descending.
  4. Inspect the **Rules Triggered** column (e.g., *"R1: Zero clicks in last 2 weeks; R6: Missed TMA1"*).
  5. Initiate student outreach via student phone/email referencing specific missed milestones.

### 6.2 Course Instructors & Module Chairs
- **Primary Dashboard Pages:** Page 3 (*Engagement Analysis*) & Page 4 (*Performance & Assessments*).
- **Weekly Workflow:**
  1. Review **Visual 3.1** to observe overall cohort click momentum. If weekly clicks dip prematurely, dispatch an encouraging announcement or schedule an online drop-in surgery.
  2. Inspect **Visual 4.4** to verify whether a particular TMA or CMA has an abnormally high failure rate (<50%), indicating unclear questions or unreasonable rubric difficulty.

### 6.3 University Executive Leadership & Administration
- **Primary Dashboard Pages:** Page 1 (*Executive Overview*) & Page 5 (*Demographics & Retention*).
- **Term Planning Workflow:**
  1. Compare the **Pass Rate** and **Withdrawal Rate** against annual retention targets across all 22 module cohorts.
  2. Use the **IMD Band** and **Education Level** breakdowns to direct institutional hardship funds and allocate learning support specialists to high-risk courses.
