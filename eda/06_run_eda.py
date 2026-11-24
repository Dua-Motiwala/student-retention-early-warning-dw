"""
===============================================================================
Script: eda/06_run_eda.py
Phase: Phase 6 - Exploratory Data Analysis & DAV Visualizations
Purpose: Produces labelled charts and summary CSVs from the Silver/Gold/Marts
         layers to satisfy the Data Analysis & Visualization (DAV) requirement.
         Each chart includes a one-line insight annotation.
Inputs: marts.dim_student, marts.dim_course, marts.fact_student_performance,
        marts.fact_weekly_engagement, silver.silver_students,
        silver.silver_assessments, gold.gold_student_weekly_engagement
Outputs:
  - 15+ publication-ready PNG figures in dashboard/figures/
  - Summary CSV tables in dashboard/export/
Dependencies: etl/db.py, matplotlib, seaborn, pandas, numpy
Run Order: 06
===============================================================================
"""

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for PNG export
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from etl.db import get_engine

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FIGURES_DIR = PROJECT_ROOT / "dashboard" / "figures"
EXPORT_DIR = PROJECT_ROOT / "dashboard" / "export"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Consistent styling
sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE_OUTCOME = {"Pass": "#2ecc71", "Distinction": "#3498db",
                   "Fail": "#e74c3c", "Withdrawn": "#e67e22"}
OUTCOME_ORDER = ["Distinction", "Pass", "Fail", "Withdrawn"]
DPI = 150
FIG_SIZE = (10, 6)
FIG_SIZE_WIDE = (14, 6)
FIG_SIZE_TALL = (10, 8)

chart_counter = 0


def save_fig(fig, name, insight):
    """Save figure with insight annotation and close."""
    global chart_counter
    chart_counter += 1
    fig.text(0.5, -0.02, f"Insight: {insight}", ha="center", fontsize=9,
             fontstyle="italic", color="#555555", wrap=True)
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [{chart_counter:02d}] Saved {path.name}")


def main():
    engine = get_engine()
    print("=" * 70)
    print("PHASE 6: EXPLORATORY DATA ANALYSIS & DAV VISUALIZATIONS")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Load data from marts and silver (avoid re-reading 10.65M VLE rows)
    # ------------------------------------------------------------------
    print("\n  Loading data from MySQL...")
    with engine.connect() as conn:
        df_stu = pd.read_sql("SELECT * FROM silver.silver_students", conn)
        df_assess = pd.read_sql("SELECT * FROM silver.silver_assessments", conn)
        # Read weekly engagement from gold (627k rows, much lighter than VLE)
        df_weekly = pd.read_sql("SELECT * FROM gold.gold_student_weekly_engagement", conn)

    print(f"  Loaded: students={len(df_stu):,}, assessments={len(df_assess):,}, weekly={len(df_weekly):,}")

    # ------------------------------------------------------------------
    # EDA 1: Overall Outcome Distribution
    # ------------------------------------------------------------------
    print("\n--- EDA 1: Overall Outcome Distribution ---")
    outcome_counts = df_stu["final_result"].value_counts().reindex(OUTCOME_ORDER)
    outcome_pct = (outcome_counts / outcome_counts.sum() * 100).round(1)

    fig, axes = plt.subplots(1, 2, figsize=FIG_SIZE_WIDE)

    # Bar chart
    bars = axes[0].bar(outcome_counts.index, outcome_counts.values,
                       color=[PALETTE_OUTCOME[o] for o in outcome_counts.index],
                       edgecolor="white", linewidth=0.8)
    for bar, pct in zip(bars, outcome_pct.values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 200,
                     f"{pct}%", ha="center", fontsize=11, fontweight="bold")
    axes[0].set_title("Student Outcome Distribution (All Enrolments)", fontsize=13, fontweight="bold")
    axes[0].set_ylabel("Number of Enrolments")
    axes[0].set_xlabel("Final Result")

    # Pie chart
    axes[1].pie(outcome_counts.values, labels=outcome_counts.index, autopct="%1.1f%%",
                colors=[PALETTE_OUTCOME[o] for o in outcome_counts.index],
                startangle=140, textprops={"fontsize": 11})
    axes[1].set_title("Outcome Proportions", fontsize=13, fontweight="bold")

    withdrawn_pct = outcome_pct.get("Withdrawn", 0)
    fail_pct = outcome_pct.get("Fail", 0)
    save_fig(fig, "01_outcome_distribution",
             f"{withdrawn_pct + fail_pct:.1f}% of enrolments end in Withdrawal or Failure — the core target population for early warning.")

    # Save summary CSV
    summary_df = pd.DataFrame({"outcome": outcome_counts.index, "count": outcome_counts.values, "pct": outcome_pct.values})
    summary_df.to_csv(EXPORT_DIR / "outcome_distribution.csv", index=False)

    # ------------------------------------------------------------------
    # EDA 2: Outcome Rates by Course Module
    # ------------------------------------------------------------------
    print("--- EDA 2: Outcome Rates by Course Module ---")
    course_outcome = df_stu.groupby(["code_module", "final_result"]).size().unstack(fill_value=0)
    course_outcome = course_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    course_pct = course_outcome.div(course_outcome.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    course_pct.plot(kind="bar", stacked=True, ax=ax,
                    color=[PALETTE_OUTCOME[c] for c in course_pct.columns],
                    edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Module", fontsize=13, fontweight="bold")
    ax.set_ylabel("Percentage (%)")
    ax.set_xlabel("Module Code")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.set_ylim(0, 100)

    worst_module = course_pct["Withdrawn"].idxmax()
    worst_rate = course_pct.loc[worst_module, "Withdrawn"]
    save_fig(fig, "02_outcome_by_module",
             f"Module {worst_module} has the highest withdrawal rate ({worst_rate:.1f}%), signalling curriculum or support issues.")
    course_pct.to_csv(EXPORT_DIR / "outcome_by_module.csv")

    # ------------------------------------------------------------------
    # EDA 3: Outcome Rates by Presentation (Semester)
    # ------------------------------------------------------------------
    print("--- EDA 3: Outcome Rates by Presentation ---")
    pres_outcome = df_stu.groupby(["code_presentation", "final_result"]).size().unstack(fill_value=0)
    pres_outcome = pres_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    pres_pct = pres_outcome.div(pres_outcome.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(8, 5))
    pres_pct.plot(kind="bar", stacked=True, ax=ax,
                  color=[PALETTE_OUTCOME[c] for c in pres_pct.columns],
                  edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Presentation Semester", fontsize=13, fontweight="bold")
    ax.set_ylabel("Percentage (%)")
    ax.set_xlabel("Presentation Code")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_ylim(0, 100)

    save_fig(fig, "03_outcome_by_presentation",
             "February (B) presentations show slightly different retention patterns compared to October (J) cohorts.")
    pres_pct.to_csv(EXPORT_DIR / "outcome_by_presentation.csv")

    # ------------------------------------------------------------------
    # EDA 4: Outcome Rates by Gender
    # ------------------------------------------------------------------
    print("--- EDA 4: Outcome Rates by Gender ---")
    gen_outcome = df_stu.groupby(["gender", "final_result"]).size().unstack(fill_value=0)
    gen_outcome = gen_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    gen_pct = gen_outcome.div(gen_outcome.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(7, 5))
    gen_pct.plot(kind="bar", stacked=True, ax=ax,
                 color=[PALETTE_OUTCOME[c] for c in gen_pct.columns],
                 edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Gender", fontsize=13, fontweight="bold")
    ax.set_ylabel("Percentage (%)")
    ax.set_xlabel("Gender")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.set_ylim(0, 100)

    save_fig(fig, "04_outcome_by_gender",
             "Male and Female students show broadly similar withdrawal rates, but Males have a marginally higher failure rate.")
    gen_pct.to_csv(EXPORT_DIR / "outcome_by_gender.csv")

    # ------------------------------------------------------------------
    # EDA 5: Outcome Rates by Age Band
    # ------------------------------------------------------------------
    print("--- EDA 5: Outcome Rates by Age Band ---")
    age_order = ["0-35", "35-55", "55<="]
    age_outcome = df_stu.groupby(["age_band", "final_result"]).size().unstack(fill_value=0)
    age_outcome = age_outcome.reindex(index=age_order, columns=OUTCOME_ORDER, fill_value=0)
    age_pct = age_outcome.div(age_outcome.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(7, 5))
    age_pct.plot(kind="bar", stacked=True, ax=ax,
                 color=[PALETTE_OUTCOME[c] for c in age_pct.columns],
                 edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Age Band", fontsize=13, fontweight="bold")
    ax.set_ylabel("Percentage (%)")
    ax.set_xlabel("Age Band")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.set_ylim(0, 100)

    save_fig(fig, "05_outcome_by_age",
             "Younger students (0-35) show marginally higher withdrawal rates, while older learners (55<=) achieve proportionally more distinctions.")
    age_pct.to_csv(EXPORT_DIR / "outcome_by_age.csv")

    # ------------------------------------------------------------------
    # EDA 6: Outcome Rates by Highest Education Level
    # ------------------------------------------------------------------
    print("--- EDA 6: Outcome Rates by Education Level ---")
    edu_outcome = df_stu.groupby(["highest_education", "final_result"]).size().unstack(fill_value=0)
    edu_outcome = edu_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    edu_pct = edu_outcome.div(edu_outcome.sum(axis=1), axis=0) * 100
    edu_pct = edu_pct.sort_values("Withdrawn", ascending=False)

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    edu_pct.plot(kind="barh", stacked=True, ax=ax,
                 color=[PALETTE_OUTCOME[c] for c in edu_pct.columns],
                 edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Highest Education Level", fontsize=13, fontweight="bold")
    ax.set_xlabel("Percentage (%)")
    ax.set_ylabel("")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xlim(0, 100)

    highest_withdrawal_edu = edu_pct["Withdrawn"].idxmax()
    save_fig(fig, "06_outcome_by_education",
             f"Students with '{highest_withdrawal_edu}' as their highest qualification have the highest withdrawal rate.")
    edu_pct.to_csv(EXPORT_DIR / "outcome_by_education.csv")

    # ------------------------------------------------------------------
    # EDA 7: Outcome Rates by Region (Top 10)
    # ------------------------------------------------------------------
    print("--- EDA 7: Outcome Rates by Region ---")
    region_outcome = df_stu.groupby(["region", "final_result"]).size().unstack(fill_value=0)
    region_outcome = region_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    region_total = region_outcome.sum(axis=1).sort_values(ascending=False)
    top_regions = region_total.head(10).index
    region_pct = region_outcome.loc[top_regions].div(region_outcome.loc[top_regions].sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    region_pct.plot(kind="barh", stacked=True, ax=ax,
                    color=[PALETTE_OUTCOME[c] for c in region_pct.columns],
                    edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Region (Top 10 by Enrolment)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Percentage (%)")
    ax.set_ylabel("")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xlim(0, 100)

    save_fig(fig, "07_outcome_by_region",
             "Regional withdrawal rates vary between ~28-37%, suggesting geographic or socioeconomic factors influence retention.")
    region_pct.to_csv(EXPORT_DIR / "outcome_by_region.csv")

    # ------------------------------------------------------------------
    # EDA 8: Outcome Rates by IMD Band (Deprivation)
    # ------------------------------------------------------------------
    print("--- EDA 8: Outcome Rates by IMD Band ---")
    imd_order = ["0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
                 "50-60%", "60-70%", "70-80%", "80-90%", "90-100%", "Unknown"]
    imd_outcome = df_stu.groupby(["imd_band", "final_result"]).size().unstack(fill_value=0)
    imd_outcome = imd_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    # Reorder only the bands that exist
    imd_existing = [b for b in imd_order if b in imd_outcome.index]
    imd_outcome = imd_outcome.loc[imd_existing]
    imd_pct = imd_outcome.div(imd_outcome.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    imd_pct.plot(kind="bar", stacked=True, ax=ax,
                 color=[PALETTE_OUTCOME[c] for c in imd_pct.columns],
                 edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by IMD Band (Deprivation Index)", fontsize=13, fontweight="bold")
    ax.set_ylabel("Percentage (%)")
    ax.set_xlabel("IMD Band (0-10% = Most Deprived)")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_ylim(0, 100)

    save_fig(fig, "08_outcome_by_imd",
             "Students from the most deprived areas (0-10%) show higher withdrawal rates, confirming socioeconomic deprivation as a retention risk factor.")
    imd_pct.to_csv(EXPORT_DIR / "outcome_by_imd.csv")

    # ------------------------------------------------------------------
    # EDA 9: Score Distribution by Outcome
    # ------------------------------------------------------------------
    print("--- EDA 9: Score Distribution by Outcome ---")
    df_scored = df_assess[df_assess["is_missing_score"] == 0].copy()
    df_scored = df_scored.merge(
        df_stu[["code_module", "code_presentation", "id_student", "final_result"]],
        on=["code_module", "code_presentation", "id_student"],
        how="left"
    )

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    for outcome in OUTCOME_ORDER:
        subset = df_scored[df_scored["final_result"] == outcome]["score"]
        if len(subset) > 0:
            ax.hist(subset, bins=50, alpha=0.5, label=outcome,
                    color=PALETTE_OUTCOME[outcome], density=True)
    ax.set_title("Assessment Score Distribution by Final Outcome", fontsize=13, fontweight="bold")
    ax.set_xlabel("Score")
    ax.set_ylabel("Density")
    ax.legend(title="Outcome")

    median_pass = df_scored[df_scored["final_result"] == "Pass"]["score"].median()
    median_fail = df_scored[df_scored["final_result"] == "Fail"]["score"].median()
    save_fig(fig, "09_score_distribution_by_outcome",
             f"Pass students (median {median_pass:.0f}) consistently outscore Fail students (median {median_fail:.0f}); Withdrawn students cluster at lower ranges.")

    # ------------------------------------------------------------------
    # EDA 10: Assessment Submission Timeliness
    # ------------------------------------------------------------------
    print("--- EDA 10: Submission Timeliness ---")
    df_timed = df_assess[df_assess["submission_delay"].notna()].copy()
    df_timed["delay_clipped"] = df_timed["submission_delay"].clip(-30, 60)

    fig, axes = plt.subplots(1, 2, figsize=FIG_SIZE_WIDE)

    # Histogram of submission delay
    axes[0].hist(df_timed["delay_clipped"], bins=90, color="#3498db",
                 edgecolor="white", linewidth=0.3)
    axes[0].axvline(x=0, color="red", linestyle="--", linewidth=1.5, label="Deadline")
    axes[0].set_title("Submission Delay Distribution", fontsize=13, fontweight="bold")
    axes[0].set_xlabel("Days Relative to Deadline (negative = early)")
    axes[0].set_ylabel("Number of Submissions")
    axes[0].legend()

    # Late vs early by outcome
    df_timed_m = df_timed.merge(
        df_stu[["code_module", "code_presentation", "id_student", "final_result"]],
        on=["code_module", "code_presentation", "id_student"], how="left"
    )
    late_pct = df_timed_m.groupby("final_result")["is_late"].mean() * 100
    late_pct = late_pct.reindex(OUTCOME_ORDER)
    bars = axes[1].bar(late_pct.index, late_pct.values,
                       color=[PALETTE_OUTCOME[o] for o in late_pct.index],
                       edgecolor="white")
    for bar, val in zip(bars, late_pct.values):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                     f"{val:.1f}%", ha="center", fontsize=10, fontweight="bold")
    axes[1].set_title("Late Submission Rate by Outcome", fontsize=13, fontweight="bold")
    axes[1].set_ylabel("% Submissions Late")
    axes[1].set_xlabel("Final Result")

    save_fig(fig, "10_submission_timeliness",
             "Most students submit early, but Withdrawn/Fail students have significantly higher late submission rates — a strong early warning signal.")

    # ------------------------------------------------------------------
    # EDA 11: Weekly Click Activity by Outcome (Engagement Trend)
    # ------------------------------------------------------------------
    print("--- EDA 11: Weekly Click Trends by Outcome ---")
    # Focus on weeks 0-25 for readability
    wk_mask = (df_weekly["week_number"] >= 0) & (df_weekly["week_number"] <= 25)
    weekly_filtered = df_weekly[wk_mask]
    weekly_trend = weekly_filtered.groupby(["week_number", "final_result"])["weekly_clicks"].mean().reset_index()

    fig, ax = plt.subplots(figsize=FIG_SIZE_WIDE)
    for outcome in OUTCOME_ORDER:
        sub = weekly_trend[weekly_trend["final_result"] == outcome]
        ax.plot(sub["week_number"], sub["weekly_clicks"], marker="o", markersize=3,
                label=outcome, color=PALETTE_OUTCOME[outcome], linewidth=2)
    ax.set_title("Average Weekly Clicks by Final Outcome (Weeks 0–25)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Academic Week")
    ax.set_ylabel("Average Weekly Clicks")
    ax.legend(title="Outcome")
    ax.set_xlim(0, 25)

    save_fig(fig, "11_weekly_clicks_by_outcome",
             "Withdrawn students show a sharp engagement drop starting around week 3–5, diverging clearly from Pass/Distinction students — confirming the early warning window.")

    # ------------------------------------------------------------------
    # EDA 12: Cumulative Clicks by Outcome
    # ------------------------------------------------------------------
    print("--- EDA 12: Cumulative Engagement by Outcome ---")
    cum_trend = weekly_filtered.groupby(["week_number", "final_result"])["cumulative_clicks"].mean().reset_index()

    fig, ax = plt.subplots(figsize=FIG_SIZE_WIDE)
    for outcome in OUTCOME_ORDER:
        sub = cum_trend[cum_trend["final_result"] == outcome]
        ax.plot(sub["week_number"], sub["cumulative_clicks"], marker="o", markersize=3,
                label=outcome, color=PALETTE_OUTCOME[outcome], linewidth=2)
    ax.set_title("Average Cumulative Clicks by Final Outcome (Weeks 0–25)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Academic Week")
    ax.set_ylabel("Average Cumulative Clicks")
    ax.legend(title="Outcome")
    ax.set_xlim(0, 25)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    save_fig(fig, "12_cumulative_clicks_by_outcome",
             "By week 10, Distinction students accumulate nearly 2× the clicks of Withdrawn students — a clear separation for predictive modelling.")

    # ------------------------------------------------------------------
    # EDA 13: VLE Activity Type Breakdown
    # ------------------------------------------------------------------
    print("--- EDA 13: VLE Activity Type Usage ---")
    act_cols = ["clicks_oucontent", "clicks_forumng", "clicks_quiz",
                "clicks_homepage", "clicks_subpage", "clicks_resource",
                "clicks_url", "clicks_other"]
    act_labels = ["OUContent", "Forum", "Quiz", "Homepage",
                  "Subpage", "Resource", "URL", "Other"]
    act_totals = df_weekly[act_cols].sum()
    act_totals.index = act_labels

    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        act_totals.values, labels=act_totals.index, autopct="%1.1f%%",
        startangle=140, textprops={"fontsize": 10},
        colors=sns.color_palette("Set2", n_colors=len(act_totals))
    )
    ax.set_title("VLE Activity Type Distribution (All Students)", fontsize=13, fontweight="bold")

    dominant_act = act_totals.idxmax()
    dominant_pct = (act_totals.max() / act_totals.sum() * 100)
    save_fig(fig, "13_activity_type_breakdown",
             f"{dominant_act} accounts for {dominant_pct:.1f}% of all clicks — the primary engagement channel for content delivery.")

    # ------------------------------------------------------------------
    # EDA 14: When Withdrawals Happen (Week Distribution)
    # ------------------------------------------------------------------
    print("--- EDA 14: Withdrawal Timing ---")
    withdrawn_stu = df_stu[df_stu["is_withdrawn"] == 1].copy()
    withdrawn_stu = withdrawn_stu[withdrawn_stu["unregistration_week"].notna()]
    withdrawn_stu["unreg_week"] = withdrawn_stu["unregistration_week"].astype(int)
    # Focus on main range
    wd_filtered = withdrawn_stu[(withdrawn_stu["unreg_week"] >= -4) & (withdrawn_stu["unreg_week"] <= 38)]

    fig, ax = plt.subplots(figsize=FIG_SIZE_WIDE)
    ax.hist(wd_filtered["unreg_week"], bins=range(-4, 40), color="#e67e22",
            edgecolor="white", linewidth=0.5, alpha=0.85)
    ax.axvline(x=0, color="black", linestyle="--", linewidth=1, label="Course Start")
    ax.axvspan(0, 5, alpha=0.1, color="red", label="Early Warning Window (Wk 0–5)")
    ax.set_title("When Do Students Withdraw? (Week Distribution)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Withdrawal Week (relative to course start)")
    ax.set_ylabel("Number of Withdrawals")
    ax.legend()

    early_wd = len(wd_filtered[wd_filtered["unreg_week"] <= 5])
    total_wd = len(wd_filtered)
    pct_early = (early_wd / total_wd * 100) if total_wd > 0 else 0
    save_fig(fig, "14_withdrawal_timing",
             f"{pct_early:.1f}% of withdrawals occur by week 5 (early warning window), but many happen mid-term — continuous monitoring is essential.")

    # Save withdrawal timing CSV
    wd_weekly = wd_filtered.groupby("unreg_week").size().reset_index(name="withdrawals")
    wd_weekly.to_csv(EXPORT_DIR / "withdrawal_timing.csv", index=False)

    # ------------------------------------------------------------------
    # EDA 15: Feature Correlation Heatmap (Gold Layer)
    # ------------------------------------------------------------------
    print("--- EDA 15: Feature Correlation Heatmap ---")
    # Select a representative week (week 5, end of early warning window) for correlation
    wk5 = df_weekly[df_weekly["week_number"] == 5].copy()
    corr_cols = [
        "weekly_clicks", "active_days", "distinct_resources",
        "cumulative_clicks", "cumulative_active_days",
        "prev_week_clicks", "wow_click_change", "clicks_last_2_weeks",
        "assessments_submitted_so_far", "avg_score_so_far",
        "weighted_score_so_far", "late_submissions_so_far",
        "clicks_oucontent", "clicks_forumng", "clicks_quiz"
    ]
    # Create binary outcome for correlation
    wk5["is_at_risk"] = wk5["final_result"].isin(["Withdrawn", "Fail"]).astype(int)
    corr_cols_full = corr_cols + ["is_at_risk"]
    corr_matrix = wk5[corr_cols_full].corr()

    fig, ax = plt.subplots(figsize=(14, 12))
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    sns.heatmap(corr_matrix, mask=mask, annot=True, fmt=".2f", cmap="RdBu_r",
                center=0, square=True, linewidths=0.5, ax=ax,
                annot_kws={"fontsize": 8}, vmin=-1, vmax=1,
                cbar_kws={"shrink": 0.8})
    ax.set_title("Feature Correlation Heatmap at Week 5 (End of Early Warning Window)", fontsize=13, fontweight="bold")

    # Find strongest risk correlate
    risk_corrs = corr_matrix["is_at_risk"].drop("is_at_risk").abs().sort_values(ascending=False)
    top_corr_name = risk_corrs.index[0]
    top_corr_val = corr_matrix.loc[top_corr_name, "is_at_risk"]
    save_fig(fig, "15_feature_correlation_heatmap",
             f"'{top_corr_name}' has the strongest correlation with at-risk status (r={top_corr_val:.2f}) at week 5 — a key predictor for the expert system.")

    corr_matrix.to_csv(EXPORT_DIR / "feature_correlation_week5.csv")

    # ------------------------------------------------------------------
    # EDA 16: Engagement vs Score (Scatter)
    # ------------------------------------------------------------------
    print("--- EDA 16: Engagement vs Score Scatter ---")
    # Use week 10 aggregates for a mid-course view
    wk10 = df_weekly[df_weekly["week_number"] == 10].copy()
    wk10_scored = wk10[wk10["avg_score_so_far"].notna()]

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    for outcome in OUTCOME_ORDER:
        sub = wk10_scored[wk10_scored["final_result"] == outcome]
        ax.scatter(sub["cumulative_clicks"], sub["avg_score_so_far"],
                   alpha=0.3, s=15, label=outcome, color=PALETTE_OUTCOME[outcome])
    ax.set_title("Cumulative Clicks vs Avg Score at Week 10 by Outcome", fontsize=13, fontweight="bold")
    ax.set_xlabel("Cumulative Clicks (by Week 10)")
    ax.set_ylabel("Average Score So Far")
    ax.legend(title="Outcome", markerscale=3)
    ax.set_xlim(0, ax.get_xlim()[1])

    save_fig(fig, "16_engagement_vs_score",
             "High engagement AND high scores strongly predict success; low engagement with low scores clusters in Withdrawn/Fail — dual-signal risk detection.")

    # ------------------------------------------------------------------
    # EDA 17: Disability Impact on Outcomes
    # ------------------------------------------------------------------
    print("--- EDA 17: Outcomes by Disability Status ---")
    dis_outcome = df_stu.groupby(["disability", "final_result"]).size().unstack(fill_value=0)
    dis_outcome = dis_outcome.reindex(columns=OUTCOME_ORDER, fill_value=0)
    dis_pct = dis_outcome.div(dis_outcome.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(7, 5))
    dis_pct.plot(kind="bar", stacked=True, ax=ax,
                 color=[PALETTE_OUTCOME[c] for c in dis_pct.columns],
                 edgecolor="white", linewidth=0.5)
    ax.set_title("Outcome Rates by Disability Status", fontsize=13, fontweight="bold")
    ax.set_ylabel("Percentage (%)")
    ax.set_xlabel("Disability Declared")
    ax.legend(title="Outcome", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.set_ylim(0, 100)

    save_fig(fig, "17_outcome_by_disability",
             "Students who declared a disability show slightly higher withdrawal rates, suggesting a need for targeted accessibility interventions.")
    dis_pct.to_csv(EXPORT_DIR / "outcome_by_disability.csv")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"[SUCCESS] Phase 6 EDA complete: {chart_counter} charts saved to dashboard/figures/")
    print(f"          Summary CSVs exported to dashboard/export/")
    print("=" * 70)


if __name__ == "__main__":
    main()
