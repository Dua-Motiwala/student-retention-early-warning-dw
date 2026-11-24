# Power BI DAX Measures Reference Library
**Project:** University Dropout Early-Warning Warehouse & Retention Dashboard  
**Phase:** Phase 8 - Power BI Dashboard Deliverables  
**Dataset:** Open University Learning Analytics Dataset (OULAD)  
**Schema Targets:** Conformed Data Marts (`dim_student`, `dim_course`, `dim_date`, `fact_student_performance`, `fact_weekly_engagement`, `fact_risk_flag`)

---

## 1. Architecture & Measure Table Setup

For clean model governance in Power BI Desktop:
1. In the **Home** tab, click **Enter Data**.
2. Name the table `_Measures` and click **Load**.
3. Create all DAX measures below inside `_Measures` using **New Measure**.
4. Hide the placeholder column `Column1` to convert `_Measures` into a dedicated measures folder at the top of the Data pane.

---

## 2. Core Population & Academic Outcome Measures

### 2.1 Total Enrolments
```dax
Total Enrolments = 
SUM('dim_student'[total_courses_enrolled])
```
- **Description:** Total student course registrations across all presentations (32,593 registrations).
- **Format:** Whole Number (`#,##0`).

### 2.2 Total Students (Unique Individuals)
```dax
Total Students = 
DISTINCTCOUNT('dim_student'[id_student])
```
- **Description:** Distinct count of individual human learners in the cohort (28,785 unique students).
- **Format:** Whole Number (`#,##0`).

### 2.3 Total Courses Offered
```dax
Total Courses Offered = 
DISTINCTCOUNT('dim_course'[course_key])
```
- **Description:** Total distinct module presentations (22 cohorts).
- **Format:** Whole Number (`#,##0`).

### 2.4 Pass Count
```dax
Pass Count = 
CALCULATE(
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    'fact_weekly_engagement'[final_result] IN {"Pass", "Distinction"}
)
```
- **Description:** Count of unique student enrollments that culminated in academic success (Pass or Distinction).
- **Format:** Whole Number (`#,##0`).

### 2.5 Pass Rate
```dax
Pass Rate = 
DIVIDE(
    [Pass Count],
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    0
)
```
- **Description:** Percentage of students achieving course completion.
- **Format:** Percentage (`0.0%`).

### 2.6 Distinction Rate
```dax
Distinction Rate = 
DIVIDE(
    CALCULATE(
        DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
        'fact_weekly_engagement'[final_result] = "Distinction"
    ),
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    0
)
```
- **Description:** Percentage of students achieving top academic honors.
- **Format:** Percentage (`0.0%`).

### 2.7 Withdrawal Count
```dax
Withdrawal Count = 
CALCULATE(
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    'fact_weekly_engagement'[final_result] = "Withdrawn"
)
```
- **Description:** Total students who dropped out prior to course completion.
- **Format:** Whole Number (`#,##0`).

### 2.8 Withdrawal Rate
```dax
Withdrawal Rate = 
DIVIDE(
    [Withdrawal Count],
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    0
)
```
- **Description:** Percentage of students withdrawing from their enrolled module presentation.
- **Format:** Percentage (`0.0%`).

### 2.9 Failure Rate
```dax
Failure Rate = 
DIVIDE(
    CALCULATE(
        DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
        'fact_weekly_engagement'[final_result] = "Fail"
    ),
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    0
)
```
- **Description:** Percentage of enrolled students who completed assessments but failed to achieve passing marks.
- **Format:** Percentage (`0.0%`).

---

## 3. Early Warning & AI Risk Measures

### 3.1 At-Risk Student Count
```dax
At-Risk Student Count = 
CALCULATE(
    DISTINCTCOUNT('fact_risk_flag'[student_key]),
    'fact_risk_flag'[risk_level] IN {"High", "Medium"}
)
```
- **Description:** Distinct students classified as Medium or High risk by the backward-chaining AI Expert System in the active filter context.
- **Format:** Whole Number (`#,##0`).

### 3.2 High-Risk Student Count
```dax
High-Risk Student Count = 
CALCULATE(
    DISTINCTCOUNT('fact_risk_flag'[student_key]),
    'fact_risk_flag'[risk_level] = "High"
)
```
- **Description:** Immediate priority intervention candidates flagged with score >= 50.0.
- **Format:** Whole Number (`#,##0`).

### 3.3 Medium-Risk Student Count
```dax
Medium-Risk Student Count = 
CALCULATE(
    DISTINCTCOUNT('fact_risk_flag'[student_key]),
    'fact_risk_flag'[risk_level] = "Medium"
)
```
- **Description:** Advisory alert group exhibiting early symptoms of disengagement (score 25.0 - 49.0).
- **Format:** Whole Number (`#,##0`).

### 3.4 Low-Risk Student Count
```dax
Low-Risk Student Count = 
CALCULATE(
    DISTINCTCOUNT('fact_risk_flag'[student_key]),
    'fact_risk_flag'[risk_level] = "Low"
)
```
- **Description:** Normal academic progression cohort (score < 25.0).
- **Format:** Whole Number (`#,##0`).

### 3.5 At-Risk %
```dax
At-Risk % = 
DIVIDE(
    [At-Risk Student Count],
    DISTINCTCOUNT('fact_risk_flag'[student_key]),
    0
)
```
- **Description:** Proportion of evaluated cohort requiring academic or advisor intervention.
- **Format:** Percentage (`0.0%`).

### 3.6 Average Risk Score
```dax
Average Risk Score = 
AVERAGE('fact_risk_flag'[risk_score])
```
- **Description:** Mean AI-calibrated risk probability score (0.00 to 100.00).
- **Format:** Decimal (`0.0`).

### 3.7 Early Detection Lead Time (Weeks)
```dax
Early Detection Lead Time (Weeks) = 
11.0
```
- **Description:** Empirical median advance notice provided by the AI system prior to formal student withdrawal (derived from Phase 7 validation).
- **Format:** Decimal (`0.0`).

---

## 4. Longitudinal Engagement & Velocity Measures

### 4.1 Total Clicks
```dax
Total Clicks = 
SUM('fact_weekly_engagement'[weekly_clicks])
```
- **Description:** Total volume of VLE interaction clicks recorded.
- **Format:** Whole Number (`#,##0`).

### 4.2 Average Engagement (Clicks per Student)
```dax
Avg Engagement (Clicks) = 
DIVIDE(
    [Total Clicks],
    DISTINCTCOUNT('fact_weekly_engagement'[student_key]),
    0
)
```
- **Description:** Average weekly VLE interaction clicks per student in the selected week/presentation.
- **Format:** Decimal (`#,##0.0`).

### 4.3 Active Days per Week
```dax
Avg Active Days = 
AVERAGE('fact_weekly_engagement'[active_days])
```
- **Description:** Mean number of active learning days per week (0 to 7).
- **Format:** Decimal (`0.0`).

### 4.4 Previous Week Clicks
```dax
Prev Week Clicks = 
SUM('fact_weekly_engagement'[prev_week_clicks])
```
- **Description:** Aggregate clicks recorded in week $N-1$ (zero target leakage).
- **Format:** Whole Number (`#,##0`).

### 4.5 Week-over-Week Click Change (Velocity)
```dax
Clicks WoW Change = 
SUM('fact_weekly_engagement'[wow_click_change])
```
- **Description:** Absolute difference in clicks compared to previous week (`weekly_clicks - prev_week_clicks`).
- **Format:** Whole Number (`+#,##0;-#,##0;0`).

### 4.6 Week-over-Week Click % Change
```dax
Clicks WoW % = 
DIVIDE(
    [Clicks WoW Change],
    [Prev Week Clicks],
    0
)
```
- **Description:** Percentage acceleration or deceleration in student learning engagement.
- **Format:** Percentage (`+0.0%;-0.0%;0.0%`).

### 4.7 Cumulative Clicks
```dax
Avg Cumulative Clicks = 
AVERAGE('fact_weekly_engagement'[cumulative_clicks])
```
- **Description:** Running total of student interactions from course onboarding to active week.
- **Format:** Whole Number (`#,##0`).

---

## 5. Academic Assessment & Timeliness Measures

### 5.1 Average Assessment Score
```dax
Avg Score = 
AVERAGE('fact_student_performance'[score_clean])
```
- **Description:** Mean score across all submitted continuous assessments (imputed missing = 0.00).
- **Format:** Decimal (`0.0`).

### 5.2 Average Weighted Score
```dax
Avg Weighted Score = 
AVERAGE('fact_student_performance'[weighted_score])
```
- **Description:** Mean earned contribution toward 100-mark final grade.
- **Format:** Decimal (`0.00`).

### 5.3 Total Assessments Submitted
```dax
Total Assessments Submitted = 
COUNTROWS('fact_student_performance')
```
- **Description:** Total TMA, CMA, and Exam submissions recorded.
- **Format:** Whole Number (`#,##0`).

### 5.4 Assessment Pass Rate
```dax
Assessment Pass Rate = 
DIVIDE(
    CALCULATE(
        COUNTROWS('fact_student_performance'),
        'fact_student_performance'[is_passed_assessment] = 1
    ),
    COUNTROWS('fact_student_performance'),
    0
)
```
- **Description:** Proportion of individual assessments graded $\ge 40.0\%$.
- **Format:** Percentage (`0.0%`).

### 5.5 Late Submission Count
```dax
Late Submission Count = 
CALCULATE(
    COUNTROWS('fact_student_performance'),
    'fact_student_performance'[is_late] = 1
)
```
- **Description:** Number of assessment submissions submitted after the scheduled deadline.
- **Format:** Whole Number (`#,##0`).

### 5.6 Late Submission %
```dax
Late Submission % = 
DIVIDE(
    [Late Submission Count],
    COUNTROWS('fact_student_performance'),
    0
)
```
- **Description:** Proportion of assignments submitted late (key behavioral signal for disengagement).
- **Format:** Percentage (`0.0%`).

### 5.7 Average Submission Delay (Days)
```dax
Avg Submission Delay (Days) = 
AVERAGE('fact_student_performance'[submission_delay])
```
- **Description:** Mean days submitted relative to deadline (negative = submitted early, positive = overdue).
- **Format:** Decimal (`+0.0;-0.0;0.0`).

---

## 6. Dynamic Formatting & UI Helper Measures

### 6.1 Risk KPI Card Color
```dax
Risk KPI Color = 
SWITCH(
    TRUE(),
    [At-Risk %] >= 0.40, "#E74C3C",  -- Red (Critical Attrition)
    [At-Risk %] >= 0.25, "#E67E22",  -- Orange (Moderate Concern)
    "#2ECC71"                        -- Green (Healthy Retention)
)
```
- **Usage:** In Power BI, apply to **KPI Card / Callout Value -> Conditional Formatting -> Field Value -> [Risk KPI Color]**.

### 6.2 Matrix Heatmap Color Scale
```dax
Heatmap Risk Color = 
VAR RiskPct = [At-Risk %]
RETURN
SWITCH(
    TRUE(),
    RiskPct >= 0.50, "#C0392B",  -- Deep Crimson (>50% at risk)
    RiskPct >= 0.35, "#E74C3C",  -- High Red
    RiskPct >= 0.25, "#F39C12",  -- Amber Warning
    RiskPct >= 0.15, "#F1C40F",  -- Yellow Attention
    "#2ECC71"                    -- Low Risk Green (<15%)
)
```
- **Usage:** Apply to Matrix visual **Cell Elements -> Background Color -> Field Value -> [Heatmap Risk Color]**.

### 6.3 Dynamic Filter Title
```dax
Dynamic Page Title = 
VAR SelCourse = SELECTEDVALUE('dim_course'[code_module], "All Modules")
VAR SelPres = SELECTEDVALUE('dim_course'[code_presentation], "All Presentations")
VAR SelWeek = SELECTEDVALUE('dim_date'[week_label], "All Weeks")
RETURN
"Student Retention & Early Warning Monitor | " & SelCourse & " (" & SelPres & ") - " & SelWeek
```
- **Usage:** Apply to Header Text visual or Visual Header Title text.
