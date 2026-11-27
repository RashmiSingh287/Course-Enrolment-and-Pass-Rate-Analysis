"""
Phase 7 / Phase 9: Exploratory Data Analysis, KPI Computation & Visualisation
Project: Course Enrolment and Pass Rate Analysis
Author: Rashmi Singh (B.Tech 2nd Year, ABES Engineering College)

Reads only the cleaned CSV datasets from data/clean/, joins tables using
primary/foreign keys, calculates all required KPIs and grouped summaries,
exports results to reports/kpis.json, and generates four labelled Matplotlib
charts in reports/charts/.
"""

import json
import math
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PASSING_MARKS = 40
CHART_PALETTE = {
    "primary": "#1F4E79",
    "secondary": "#2E75B6",
    "accent": "#4FA3D1",
    "pass": "#2E8B57",
    "fail": "#C0392B",
    "neutral": "#5D6D7E",
    "grid": "#D9E1E8",
}


def load_clean_data(clean_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three cleaned CSV files read-only from data/clean/."""
    students_df = pd.read_csv(clean_dir / "students.csv")
    courses_df = pd.read_csv(clean_dir / "courses.csv")
    enrolments_df = pd.read_csv(clean_dir / "enrolments.csv")
    return students_df, courses_df, enrolments_df


def build_merged_dataframe(
    students_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    enrolments_df: pd.DataFrame,
) -> pd.DataFrame:
    """Join enrolments with students (student_id) and courses (course_id)."""
    merged = enrolments_df.merge(
        students_df,
        on="student_id",
        how="left",
        validate="many_to_one",
    )
    merged = merged.merge(
        courses_df,
        on="course_id",
        how="left",
        validate="many_to_one",
    )
    return merged


def safe_pct(numerator: int, denominator: int) -> float | None:
    """Compute percentage safely rounded to 2 decimals, or None if denominator is 0."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def calc_avg_marks(series: pd.Series) -> float | None:
    """Compute mean marks rounded to 2 decimals, or None when no valid marks exist."""
    valid = series.dropna().astype(float)
    if len(valid) == 0:
        return None
    return round(float(valid.mean()), 2)


def calculate_kpis(
    students_df: pd.DataFrame,
    courses_df: pd.DataFrame,
    merged_df: pd.DataFrame,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calculate all project KPIs and grouped tables.

    Returns:
        kpis_dict: JSON-serialisable dictionary of all KPIs and summaries.
        course_summary_df: Course-level demand and performance table.
        semester_summary_df: Semester-level performance table.
        department_summary_df: Department-level demand and performance table.
        monthly_trend_df: Chronological monthly enrolment counts.
    """
    total_students = int(students_df["student_id"].nunique())
    total_courses = int(courses_df["course_id"].nunique())
    total_enrolments = int(merged_df["enrolment_id"].nunique())

    # Academic performance uses only valid graded records (excludes Missing/Invalid)
    valid_perf_df = merged_df[merged_df["result"].isin(["Pass", "Fail"])].copy()
    valid_enrolments_count = int(len(valid_perf_df))
    missing_invalid_count = int((merged_df["result"] == "Missing/Invalid").sum())

    passed_enrolments = int((valid_perf_df["result"] == "Pass").sum())
    failed_enrolments = int((valid_perf_df["result"] == "Fail").sum())

    overall_pass_rate = safe_pct(passed_enrolments, valid_enrolments_count)
    overall_fail_rate = safe_pct(failed_enrolments, valid_enrolments_count)

    valid_marks = merged_df["marks"].dropna().astype(float)
    valid_marks_count = int(valid_marks.count())
    average_marks = round(float(valid_marks.sum() / valid_marks_count), 2) if valid_marks_count > 0 else None

    # --- Course-wise demand (all enrolments) & performance (valid results) ---
    course_demand = (
        merged_df.groupby(["course_id", "course_name", "course_category", "credits"], as_index=False)
        .agg(enrolment_count=("enrolment_id", "count"))
    )

    course_perf = (
        valid_perf_df.groupby("course_id", as_index=False)
        .agg(
            valid_enrolments=("enrolment_id", "count"),
            pass_count=("result", lambda s: int((s == "Pass").sum())),
            fail_count=("result", lambda s: int((s == "Fail").sum())),
            average_marks=("marks", calc_avg_marks),
        )
    )

    course_summary_df = course_demand.merge(course_perf, on="course_id", how="left").fillna(
        {"valid_enrolments": 0, "pass_count": 0, "fail_count": 0}
    )
    course_summary_df["pass_rate"] = course_summary_df.apply(
        lambda r: safe_pct(int(r["pass_count"]), int(r["valid_enrolments"])), axis=1
    )
    course_summary_df["fail_rate"] = course_summary_df.apply(
        lambda r: safe_pct(int(r["fail_count"]), int(r["valid_enrolments"])), axis=1
    )
    course_summary_df = course_summary_df.sort_values(
        by=["enrolment_count", "course_id"], ascending=[False, True]
    ).reset_index(drop=True)

    # --- Semester-wise enrolment & performance (Semesters 1-4) ---
    sem_demand = (
        merged_df.groupby("semester", as_index=False)
        .agg(enrolment_count=("enrolment_id", "count"))
    )
    sem_perf = (
        valid_perf_df.groupby("semester", as_index=False)
        .agg(
            valid_enrolments=("enrolment_id", "count"),
            pass_count=("result", lambda s: int((s == "Pass").sum())),
            fail_count=("result", lambda s: int((s == "Fail").sum())),
            average_marks=("marks", calc_avg_marks),
        )
    )
    semester_summary_df = sem_demand.merge(sem_perf, on="semester", how="left").fillna(
        {"valid_enrolments": 0, "pass_count": 0, "fail_count": 0}
    )
    semester_summary_df["pass_rate"] = semester_summary_df.apply(
        lambda r: safe_pct(int(r["pass_count"]), int(r["valid_enrolments"])), axis=1
    )
    semester_summary_df["fail_rate"] = semester_summary_df.apply(
        lambda r: safe_pct(int(r["fail_count"]), int(r["valid_enrolments"])), axis=1
    )
    semester_summary_df = semester_summary_df.sort_values(by="semester").reset_index(drop=True)

    # --- Department-wise enrolment & performance ---
    dept_students = (
        students_df.groupby("department", as_index=False)
        .agg(unique_students=("student_id", "nunique"))
    )
    dept_demand = (
        merged_df.groupby("department", as_index=False)
        .agg(enrolment_count=("enrolment_id", "count"))
    )
    dept_perf = (
        valid_perf_df.groupby("department", as_index=False)
        .agg(
            valid_enrolments=("enrolment_id", "count"),
            pass_count=("result", lambda s: int((s == "Pass").sum())),
            fail_count=("result", lambda s: int((s == "Fail").sum())),
            average_marks=("marks", calc_avg_marks),
        )
    )
    department_summary_df = (
        dept_students.merge(dept_demand, on="department", how="left")
        .merge(dept_perf, on="department", how="left")
        .fillna({"enrolment_count": 0, "valid_enrolments": 0, "pass_count": 0, "fail_count": 0})
    )
    department_summary_df["pass_rate"] = department_summary_df.apply(
        lambda r: safe_pct(int(r["pass_count"]), int(r["valid_enrolments"])), axis=1
    )
    department_summary_df["fail_rate"] = department_summary_df.apply(
        lambda r: safe_pct(int(r["fail_count"]), int(r["valid_enrolments"])), axis=1
    )
    department_summary_df = department_summary_df.sort_values(
        by="enrolment_count", ascending=False
    ).reset_index(drop=True)

    # --- Academic year & result distribution ---
    acad_year_df = (
        merged_df.groupby("academic_year", as_index=False)
        .agg(enrolment_count=("enrolment_id", "count"))
        .sort_values(by="academic_year")
        .reset_index(drop=True)
    )
    result_distribution = {
        str(k): int(v) for k, v in merged_df["result"].value_counts().items()
    }

    # --- Monthly enrolment trend (valid ISO enrolment_date only) ---
    parsed_dates = pd.to_datetime(merged_df["enrolment_date"], format="%Y-%m-%d", errors="coerce")
    null_date_count = int(parsed_dates.isna().sum())
    valid_date_df = merged_df.loc[parsed_dates.notna(), ["enrolment_id"]].copy()
    valid_date_df["year_month"] = parsed_dates.loc[parsed_dates.notna()].dt.to_period("M").astype(str)

    monthly_trend_df = (
        valid_date_df.groupby("year_month", as_index=False)
        .agg(enrolment_count=("enrolment_id", "count"))
        .sort_values(by="year_month")
        .reset_index(drop=True)
    )

    # --- Attendance vs Marks relationship (rows with both non-null) ---
    att_marks_df = merged_df[["attendance_percentage", "marks", "result"]].dropna(
        subset=["attendance_percentage", "marks"]
    )
    att_vals = att_marks_df["attendance_percentage"].astype(float)
    mark_vals = att_marks_df["marks"].astype(float)
    pearson_r = round(float(att_vals.corr(mark_vals)), 4) if len(att_marks_df) > 1 else None

    att_valid_all = merged_df["attendance_percentage"].dropna().astype(float)
    pass_att = att_marks_df.loc[att_marks_df["result"] == "Pass", "attendance_percentage"].astype(float)
    fail_att = att_marks_df.loc[att_marks_df["result"] == "Fail", "attendance_percentage"].astype(float)

    attendance_summary = {
        "valid_attendance_count": int(att_valid_all.count()),
        "paired_attendance_marks_count": int(len(att_marks_df)),
        "average_attendance_all": round(float(att_valid_all.mean()), 2) if len(att_valid_all) > 0 else None,
        "average_attendance_pass": round(float(pass_att.mean()), 2) if len(pass_att) > 0 else None,
        "average_attendance_fail": round(float(fail_att.mean()), 2) if len(fail_att) > 0 else None,
        "pearson_correlation_attendance_marks": pearson_r,
    }

    kpis_dict = {
        "metadata": {
            "passing_marks_threshold": PASSING_MARKS,
            "excluded_missing_invalid_results": missing_invalid_count,
            "excluded_null_enrolment_dates_for_monthly_trend": null_date_count,
        },
        "overall_kpis": {
            "total_students": total_students,
            "total_courses": total_courses,
            "total_enrolments": total_enrolments,
            "valid_graded_enrolments": valid_enrolments_count,
            "passed_enrolments": passed_enrolments,
            "failed_enrolments": failed_enrolments,
            "overall_pass_rate": overall_pass_rate,
            "overall_fail_rate": overall_fail_rate,
            "average_marks": average_marks,
        },
        "result_distribution": result_distribution,
        "academic_year_enrolment": acad_year_df.to_dict(orient="records"),
        "course_wise_enrolment_count": course_summary_df[
            ["course_id", "course_name", "enrolment_count"]
        ].to_dict(orient="records"),
        "course_wise_pass_rate": course_summary_df[
            ["course_id", "course_name", "valid_enrolments", "pass_count", "pass_rate", "average_marks"]
        ].sort_values(by="pass_rate", ascending=False).to_dict(orient="records"),
        "failure_count_by_course": course_summary_df[
            ["course_id", "course_name", "valid_enrolments", "fail_count", "fail_rate"]
        ].sort_values(by=["fail_count", "fail_rate"], ascending=[False, False]).to_dict(orient="records"),
        "semester_wise_pass_rate": semester_summary_df.to_dict(orient="records"),
        "department_wise_summary": department_summary_df.to_dict(orient="records"),
        "monthly_enrolment_trend": monthly_trend_df.to_dict(orient="records"),
        "attendance_vs_marks": attendance_summary,
    }

    return kpis_dict, course_summary_df, semester_summary_df, department_summary_df, monthly_trend_df


def sanitize_for_json(obj: object) -> object:
    """Recursively convert NumPy/Pandas scalars and NaN/Inf/NA/NaT values to strict JSON primitives."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        obj = obj.item()
    if obj is None or obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if pd.isna(obj):
        return None
    return obj


def _reject_invalid_json_constant(value: str) -> None:
    """Reject non-standard JSON constants (NaN, Infinity, -Infinity) during strict verification."""
    raise ValueError(f"Invalid JSON constant detected: {value}")


def save_kpis_json(kpis: dict, output_path: Path) -> None:
    """Write calculated KPIs dictionary as strict valid JSON and verify with parse_constant."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_kpis = sanitize_for_json(kpis)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean_kpis, f, indent=2, allow_nan=False)
    with open(output_path, "r", encoding="utf-8") as f:
        json.load(f, parse_constant=_reject_invalid_json_constant)


def plot_monthly_enrolment_trend(monthly_df: pd.DataFrame, output_path: Path) -> None:
    """Create and save Chart 1: Monthly Enrolment Trend."""
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = monthly_df["year_month"]
    y = monthly_df["enrolment_count"]

    ax.plot(
        x,
        y,
        marker="o",
        linewidth=2.4,
        markersize=7,
        color=CHART_PALETTE["primary"],
    )
    ax.fill_between(range(len(x)), y, alpha=0.12, color=CHART_PALETTE["secondary"])

    for idx, val in enumerate(y):
        ax.annotate(
            f"{int(val)}",
            (idx, val),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=9,
            fontweight="bold",
            color=CHART_PALETTE["primary"],
        )

    ax.set_title("Monthly Enrolment Trend", fontsize=14, fontweight="bold", pad=14)
    ax.set_xlabel("Month (YYYY-MM)", fontsize=11, labelpad=10)
    ax.set_ylabel("Number of Enrolments", fontsize=11, labelpad=10)
    ax.set_ylim(0, max(y) * 1.18 if len(y) > 0 else 10)
    ax.grid(axis="y", linestyle="--", alpha=0.5, color=CHART_PALETTE["grid"])
    plt.xticks(rotation=30, ha="right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_course_enrolment(course_df: pd.DataFrame, output_path: Path) -> None:
    """Create and save Chart 2: Student Enrolment by Course."""
    plot_df = course_df.sort_values(by="enrolment_count", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10.5, 6))

    bars = ax.barh(
        plot_df["course_name"],
        plot_df["enrolment_count"],
        color=CHART_PALETTE["secondary"],
        height=0.62,
    )

    for bar in bars:
        width = bar.get_width()
        ax.annotate(
            f"{int(width)}",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=9.5,
            fontweight="bold",
            color="#222222",
        )

    ax.set_title("Student Enrolment by Course", fontsize=14, fontweight="bold", pad=14)
    ax.set_xlabel("Total Enrolments", fontsize=11, labelpad=10)
    ax.set_ylabel("Course Name", fontsize=11, labelpad=10)
    ax.set_xlim(0, plot_df["enrolment_count"].max() * 1.15)
    ax.grid(axis="x", linestyle="--", alpha=0.5, color=CHART_PALETTE["grid"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_course_pass_percentage(course_df: pd.DataFrame, output_path: Path) -> None:
    """Create and save Chart 3: Course-wise Pass Percentage."""
    plot_df = (
        course_df.dropna(subset=["pass_rate"])
        .sort_values(by="pass_rate", ascending=True)
        .reset_index(drop=True)
    )
    fig, ax = plt.subplots(figsize=(10.5, 6))

    if plot_df.empty:
        ax.text(0.5, 0.5, "No valid graded enrolments available", ha="center", va="center", fontsize=12)
        ax.set_axis_off()
    else:
        bars = ax.barh(
            plot_df["course_name"],
            plot_df["pass_rate"].astype(float),
            color=CHART_PALETTE["pass"],
            height=0.62,
        )

        for bar in bars:
            width = bar.get_width()
            ax.annotate(
                f"{width:.2f}%",
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(5, 0),
                textcoords="offset points",
                va="center",
                ha="left",
                fontsize=9.5,
                fontweight="bold",
                color="#222222",
            )

        ax.set_xlabel("Pass Percentage (%)", fontsize=11, labelpad=10)
        ax.set_ylabel("Course Name", fontsize=11, labelpad=10)
        ax.set_xlim(0, 108)
        ax.grid(axis="x", linestyle="--", alpha=0.5, color=CHART_PALETTE["grid"])
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    ax.set_title("Course-wise Pass Percentage", fontsize=14, fontweight="bold", pad=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_semester_performance(semester_df: pd.DataFrame, output_path: Path) -> None:
    """Create and save Chart 4: Semester-wise Academic Performance."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.2))

    # Left subplot: Pass Percentage by Semester (exclude null pass_rate rows)
    pass_df = semester_df.dropna(subset=["pass_rate"]).reset_index(drop=True)
    if pass_df.empty:
        ax1.text(0.5, 0.5, "No valid graded data", ha="center", va="center", fontsize=11)
        ax1.set_axis_off()
    else:
        sem_labels_pass = [f"Sem {int(s)}" for s in pass_df["semester"]]
        bars = ax1.bar(
            sem_labels_pass,
            pass_df["pass_rate"].astype(float),
            color=CHART_PALETTE["primary"],
            width=0.52,
        )
        for bar in bars:
            height = bar.get_height()
            ax1.annotate(
                f"{height:.2f}%",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                fontsize=9.5,
                fontweight="bold",
                color="#222222",
            )
        ax1.set_xlabel("Semester", fontsize=10.5, labelpad=8)
        ax1.set_ylabel("Pass Percentage (%)", fontsize=10.5, labelpad=8)
        ax1.set_ylim(0, 108)
        ax1.grid(axis="y", linestyle="--", alpha=0.5, color=CHART_PALETTE["grid"])
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
    ax1.set_title("Semester-wise Pass Rate (%)", fontsize=12, fontweight="bold", pad=10)

    # Right subplot: Average Marks by Semester (exclude null average_marks rows)
    avg_df = semester_df.dropna(subset=["average_marks"]).reset_index(drop=True)
    if avg_df.empty:
        ax2.text(0.5, 0.5, "No valid marks data", ha="center", va="center", fontsize=11)
        ax2.set_axis_off()
    else:
        sem_labels_avg = [f"Sem {int(s)}" for s in avg_df["semester"]]
        avg_vals = avg_df["average_marks"].astype(float)
        ax2.plot(
            sem_labels_avg,
            avg_vals,
            marker="o",
            linewidth=2.4,
            markersize=7,
            color=CHART_PALETTE["secondary"],
        )
        for idx, val in enumerate(avg_vals):
            ax2.annotate(
                f"{val:.2f}",
                (idx, val),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=9.5,
                fontweight="bold",
                color=CHART_PALETTE["secondary"],
            )
        ax2.set_xlabel("Semester", fontsize=10.5, labelpad=8)
        ax2.set_ylabel("Average Marks (out of 100)", fontsize=10.5, labelpad=8)
        ax2.set_ylim(0, 100)
        ax2.grid(axis="y", linestyle="--", alpha=0.5, color=CHART_PALETTE["grid"])
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
    ax2.set_title("Semester-wise Average Marks", fontsize=12, fontweight="bold", pad=10)

    fig.suptitle("Semester-wise Academic Performance", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def main() -> None:
    """Execute EDA calculations, export kpis.json, and generate all 4 charts."""
    project_root = Path(__file__).resolve().parent.parent
    clean_dir = project_root / "data" / "clean"
    reports_dir = project_root / "reports"
    charts_dir = reports_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    students_df, courses_df, enrolments_df = load_clean_data(clean_dir)
    merged_df = build_merged_dataframe(students_df, courses_df, enrolments_df)

    kpis, course_df, semester_df, department_df, monthly_df = calculate_kpis(
        students_df, courses_df, merged_df
    )

    save_kpis_json(kpis, reports_dir / "kpis.json")

    plot_monthly_enrolment_trend(monthly_df, charts_dir / "monthly_enrolment_trend.png")
    plot_course_enrolment(course_df, charts_dir / "course_enrolment_count.png")
    plot_course_pass_percentage(course_df, charts_dir / "course_pass_percentage.png")
    plot_semester_performance(semester_df, charts_dir / "semester_academic_performance.png")

    print("=== EDA & KPI SUMMARY ===")
    for key, val in kpis["overall_kpis"].items():
        print(f"  {key}: {val}")
    print("\nCourse Summary:")
    print(course_df.to_string(index=False))
    print("\nSemester Summary:")
    print(semester_df.to_string(index=False))
    print("\nDepartment Summary:")
    print(department_df.to_string(index=False))
    print("\nAttendance vs Marks:", kpis["attendance_vs_marks"])


if __name__ == "__main__":
    main()
