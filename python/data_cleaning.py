"""
Phase 6: Data Cleaning Pipeline
Project: Course Enrolment and Pass Rate Analysis
Author: Rashmi Singh (B.Tech 2nd Year, ABES Engineering College)

Reads raw CSV files from data/raw/ (never modifying them), applies documented
cleaning and validation rules from documentation/data_dictionary.xlsx, preserves
all non-duplicate records (no silent deletions), saves cleaned CSVs in data/clean/,
and logs every cleaning action in reports/data_quality_log.csv.
"""

from pathlib import Path
import re
import pandas as pd


PASSING_MARKS = 40
VALID_DEPARTMENTS = {"CSE", "IT", "ECE", "ME", "CE"}
VALID_CATEGORIES = {"Foundation", "Core", "Elective"}
VALID_CREDITS = {3, 4}
VALID_ADMISSION_YEARS = {2023, 2024}
VALID_ACADEMIC_YEARS = {"2023-24", "2024-25"}
VALID_SEMESTERS = {1, 2, 3, 4}


def add_log(log_entries: list[dict], issue: str, rule_applied: str, rows_affected: int) -> None:
    """Append a structured entry to the data quality audit log."""
    log_entries.append(
        {
            "issue": issue,
            "rule_applied": rule_applied,
            "rows_affected": int(rows_affected),
        }
    )


def clean_id_series(series: pd.Series) -> pd.Series:
    """Strip whitespace and uppercase non-null ID strings while preserving nulls."""
    cleaned = series.astype("string").str.strip().str.upper()
    return cleaned.mask(cleaned == "", pd.NA)


def clean_text_series(series: pd.Series, case: str = "strip") -> pd.Series:
    """Trim whitespace and optionally apply title/upper/lower case while preserving nulls."""
    cleaned = series.astype("string").str.strip()
    cleaned = cleaned.mask(cleaned == "", pd.NA)
    if case == "title":
        return cleaned.str.title()
    if case == "upper":
        return cleaned.str.upper()
    if case == "lower":
        return cleaned.str.lower()
    return cleaned


def count_text_changes(raw_series: pd.Series, clean_series: pd.Series) -> int:
    """Count non-null values whose string representation changed after cleaning."""
    raw_str = raw_series.astype("string")
    both_valid = raw_str.notna() & clean_series.notna()
    return int((raw_str[both_valid] != clean_series[both_valid]).sum())


def count_rows_with_any_missing(df: pd.DataFrame, cols: list[str]) -> tuple[int, dict[str, int]]:
    """Count unique rows missing at least one required column, plus per-column counts."""
    per_col = {col: int(df[col].isna().sum()) for col in cols}
    unique_rows_affected = int(df[cols].isna().any(axis=1).sum())
    return unique_rows_affected, per_col


def parse_mixed_date(date_val: object) -> pd.Timestamp:
    """Parse supported raw date formats into a Timestamp, or NaT if invalid."""
    if pd.isna(date_val):
        return pd.NaT
    text = str(date_val).strip()
    if not text:
        return pd.NaT

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%Y/%m/%d"):
        try:
            return pd.to_datetime(text, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def clean_students(
    students_raw: pd.DataFrame,
    enrolments_raw: pd.DataFrame,
    log_entries: list[dict],
) -> pd.DataFrame:
    """Clean students dataset: standardise IDs first, deduplicate, clean text, validate fields."""
    df = students_raw.copy()

    # 1. Standardise primary key strings BEFORE duplicate detection
    raw_sid = df["student_id"].copy()
    df["student_id"] = clean_id_series(df["student_id"])
    sid_fmt_changed = count_text_changes(raw_sid, df["student_id"])
    if sid_fmt_changed > 0:
        add_log(
            log_entries,
            "Inconsistent student_id formatting",
            "Trimmed whitespace and uppercased student_id before duplicate detection",
            sid_fmt_changed,
        )

    # 2. Detect and remove exact duplicate rows, then non-exact duplicate primary keys (no double-counting)
    exact_dups = int(df.duplicated().sum())
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    add_log(
        log_entries,
        "Exact duplicate student rows",
        "Removed exact duplicate rows across all columns (keep='first')",
        exact_dups,
    )

    pk_dup_mask = df["student_id"].notna() & df.duplicated(subset=["student_id"], keep="first")
    dup_pk_count = int(pk_dup_mask.sum())
    df = df.loc[~pk_dup_mask].reset_index(drop=True)
    add_log(
        log_entries,
        "Duplicate student_id primary keys (non-exact)",
        "Removed remaining duplicate student_id rows after exact deduplication (keep='first')",
        dup_pk_count,
    )

    # 3. Standardise student_name whitespace and Title Case
    raw_name = df["student_name"].copy()
    df["student_name"] = clean_text_series(df["student_name"], case="title")
    name_changed = count_text_changes(raw_name, df["student_name"])
    add_log(
        log_entries,
        "Inconsistent student_name formatting",
        "Trimmed leading/trailing whitespace and converted student_name to Title Case",
        name_changed,
    )

    # 4. Handle missing gender and map variants to Male / Female / Unknown
    missing_gender = int(clean_text_series(df["gender"]).isna().sum())
    gender_map = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}
    raw_gender = df["gender"].copy()
    norm_gender = clean_text_series(df["gender"], case="lower")
    mapped_gender = norm_gender.map(gender_map)
    invalid_gender_count = int((norm_gender.notna() & mapped_gender.isna()).sum())
    df["gender"] = mapped_gender.fillna("Unknown")

    gender_format_changed = count_text_changes(raw_gender, mapped_gender)
    add_log(
        log_entries,
        "Missing gender values in students",
        "Replaced missing gender values with 'Unknown' (no rows deleted)",
        missing_gender,
    )
    add_log(
        log_entries,
        "Inconsistent gender text formats",
        "Trimmed spaces and mapped variants (m/male -> Male, f/female -> Female)",
        gender_format_changed,
    )
    if invalid_gender_count > 0:
        add_log(
            log_entries,
            "Unrecognised gender values",
            "Mapped unrecognised non-null gender entries to 'Unknown' (no rows deleted)",
            invalid_gender_count,
        )

    # 5. Standardise and validate department codes
    raw_dept = df["department"].copy()
    df["department"] = clean_text_series(df["department"], case="upper")
    dept_changed = count_text_changes(raw_dept, df["department"])
    invalid_dept_count = int((df["department"].notna() & ~df["department"].isin(VALID_DEPARTMENTS)).sum())
    add_log(
        log_entries,
        "Inconsistent department text formats",
        "Trimmed spaces and converted department codes to uppercase (CSE, IT, ECE, ME, CE)",
        dept_changed,
    )
    add_log(
        log_entries,
        "Invalid department codes (outside CSE, IT, ECE, ME, CE)",
        "Validated department against allowed codes without deleting rows",
        invalid_dept_count,
    )

    # 6. Validate required fields in students (unique affected rows, no silent deletions)
    req_stu_rows, req_stu_cols = count_rows_with_any_missing(
        df, ["student_id", "student_name", "department"]
    )
    add_log(
        log_entries,
        "Missing required fields in students",
        f"Checked required columns (student_id, student_name, department) without deleting rows; per-column counts: {req_stu_cols}",
        req_stu_rows,
    )

    # 7. Validate admission_year strictly against {2023, 2024}; infer only originally missing values
    raw_adm = df["admission_year"].copy()
    missing_adm_mask = raw_adm.isna() | (raw_adm.astype("string").str.strip() == "")
    missing_adm_raw = int(missing_adm_mask.sum())

    num_adm = pd.to_numeric(raw_adm, errors="coerce")
    non_numeric_adm = int((~missing_adm_mask & num_adm.isna()).sum())
    non_int_adm = int((num_adm.notna() & (num_adm % 1 != 0)).sum())
    out_of_set_adm = int(
        (num_adm.notna() & (num_adm % 1 == 0) & ~num_adm.isin(list(VALID_ADMISSION_YEARS))).sum()
    )
    invalid_adm_total = non_numeric_adm + non_int_adm + out_of_set_adm

    # Keep only 2023 and 2024 as integers; set non-numeric, non-integer, and out-of-set values to pd.NA
    valid_adm_mask = num_adm.notna() & (num_adm % 1 == 0) & num_adm.isin(list(VALID_ADMISSION_YEARS))
    df["admission_year"] = num_adm.where(valid_adm_mask, pd.NA).astype("Int64")

    if missing_adm_raw > 0:
        sem1_map = (
            enrolments_raw.assign(
                clean_sid=clean_id_series(enrolments_raw["student_id"]),
                sem_num=pd.to_numeric(
                    enrolments_raw["semester"].astype("string").str.extract(r"(\d+)")[0],
                    errors="coerce",
                ),
            )
            .query("sem_num == 1")
            .dropna(subset=["clean_sid", "academic_year"])
            .drop_duplicates(subset=["clean_sid"])
            .set_index("clean_sid")["academic_year"]
            .astype(str)
            .str.strip()
            .str[:4]
        )
        inferred_count = 0
        for idx in df.index[missing_adm_mask]:
            sid = df.loc[idx, "student_id"]
            if pd.notna(sid) and sid in sem1_map.index and sem1_map.loc[sid].isdigit():
                inferred_yr = int(sem1_map.loc[sid])
                if inferred_yr in VALID_ADMISSION_YEARS:
                    df.loc[idx, "admission_year"] = inferred_yr
                    inferred_count += 1
        add_log(
            log_entries,
            "Missing admission_year in students (inferred)",
            f"Detected {missing_adm_raw} originally missing admission_year value(s); inferred {inferred_count} from Semester 1 academic_year",
            inferred_count,
        )
        unresolved_missing_adm = missing_adm_raw - inferred_count
        if unresolved_missing_adm > 0:
            add_log(
                log_entries,
                "Unresolved missing admission_year in students",
                "Preserved unresolved originally missing admission_year as nullable Int64 null without deleting rows",
                unresolved_missing_adm,
            )

    add_log(
        log_entries,
        "Invalid admission_year values (outside {2023, 2024})",
        f"Validated admission_year strictly against {{2023, 2024}}; set non-numeric, non-integer, and out-of-set values to pd.NA (non_numeric={non_numeric_adm}, non_integer={non_int_adm}, out_of_set={out_of_set_adm})",
        invalid_adm_total,
    )

    return df


def clean_courses(courses_raw: pd.DataFrame, log_entries: list[dict]) -> pd.DataFrame:
    """Clean courses dataset: standardise IDs first, deduplicate, validate credits & required fields."""
    df = courses_raw.copy()

    # 1. Standardise primary key course_id BEFORE duplicate detection
    raw_cid = df["course_id"].copy()
    df["course_id"] = clean_id_series(df["course_id"])
    cid_fmt_changed = count_text_changes(raw_cid, df["course_id"])
    if cid_fmt_changed > 0:
        add_log(
            log_entries,
            "Inconsistent course_id formatting",
            "Trimmed whitespace and uppercased course_id before duplicate detection",
            cid_fmt_changed,
        )

    # 2. Exact duplicates and remaining PK duplicates without double-counting
    exact_dups = int(df.duplicated().sum())
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    add_log(
        log_entries,
        "Exact duplicate course rows",
        "Checked and removed exact duplicate rows in courses (keep='first')",
        exact_dups,
    )

    pk_dup_mask = df["course_id"].notna() & df.duplicated(subset=["course_id"], keep="first")
    pk_dups = int(pk_dup_mask.sum())
    df = df.loc[~pk_dup_mask].reset_index(drop=True)
    add_log(
        log_entries,
        "Duplicate course_id primary keys (non-exact)",
        "Checked and removed remaining duplicate course_id keys (keep='first')",
        pk_dups,
    )

    # 3. Standardise course_name & course_category
    raw_cname = df["course_name"].copy()
    df["course_name"] = clean_text_series(df["course_name"], case="strip")
    cname_changed = count_text_changes(raw_cname, df["course_name"])
    if cname_changed > 0:
        add_log(
            log_entries,
            "Inconsistent course_name whitespace",
            "Trimmed leading/trailing whitespace in course_name",
            cname_changed,
        )

    raw_cat = df["course_category"].copy()
    df["course_category"] = clean_text_series(df["course_category"], case="title")
    cat_changed = count_text_changes(raw_cat, df["course_category"])
    invalid_cat = int((df["course_category"].notna() & ~df["course_category"].isin(VALID_CATEGORIES)).sum())
    add_log(
        log_entries,
        "Inconsistent course_category formatting",
        "Trimmed spaces and converted course_category to Title Case (Foundation, Core, Elective)",
        cat_changed,
    )
    add_log(
        log_entries,
        "Invalid course_category values",
        "Validated course_category against {Foundation, Core, Elective} without deleting rows",
        invalid_cat,
    )

    # 4. Validate course credits strictly against {3, 4} (nullable Int64, no silent deletions)
    raw_credits = df["credits"].copy()
    missing_credits = int(raw_credits.isna().sum())
    num_credits = pd.to_numeric(raw_credits, errors="coerce")
    non_numeric_credits = int((raw_credits.notna() & num_credits.isna()).sum())
    out_of_set_credits = int(
        (num_credits.notna() & ~num_credits.isin(list(VALID_CREDITS))).sum()
    )

    valid_credits_mask = num_credits.isin(list(VALID_CREDITS))
    df["credits"] = num_credits.where(valid_credits_mask, pd.NA).astype("Int64")

    add_log(
        log_entries,
        "Missing or invalid course credits (outside {3, 4})",
        f"Validated credits strictly against {{3, 4}} and cast to nullable Int64 (invalid/missing set to null); missing={missing_credits}, non_numeric={non_numeric_credits}, outside_set={out_of_set_credits}",
        missing_credits + non_numeric_credits + out_of_set_credits,
    )

    # 5. Validate required fields in courses (unique affected rows, no silent deletions)
    req_course_rows, req_course_cols = count_rows_with_any_missing(
        df, ["course_id", "course_name", "course_category", "credits"]
    )
    add_log(
        log_entries,
        "Missing required fields in courses",
        f"Checked required columns (course_id, course_name, course_category, credits) without deleting rows; per-column counts: {req_course_cols}",
        req_course_rows,
    )

    return df


def clean_enrolments(
    enrolments_raw: pd.DataFrame,
    students_clean: pd.DataFrame,
    courses_clean: pd.DataFrame,
    log_entries: list[dict],
) -> pd.DataFrame:
    """Clean enrolments dataset strictly preserving non-duplicate rows."""
    df = enrolments_raw.copy()

    # 1. Standardise PK and FK strings BEFORE duplicate detection
    raw_eid = df["enrolment_id"].copy()
    raw_sid = df["student_id"].copy()
    raw_cid = df["course_id"].copy()

    df["enrolment_id"] = clean_id_series(df["enrolment_id"])
    df["student_id"] = clean_id_series(df["student_id"])
    df["course_id"] = clean_id_series(df["course_id"])

    id_fmt_changes = (
        count_text_changes(raw_eid, df["enrolment_id"])
        + count_text_changes(raw_sid, df["student_id"])
        + count_text_changes(raw_cid, df["course_id"])
    )
    if id_fmt_changes > 0:
        add_log(
            log_entries,
            "Inconsistent PK/FK ID formatting in enrolments",
            "Trimmed whitespace and uppercased enrolment_id, student_id, course_id before deduplication",
            id_fmt_changes,
        )

    # 2. Remove exact duplicate rows, then remaining non-exact PK duplicates (no double-counting)
    exact_dups = int(df.duplicated().sum())
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    add_log(
        log_entries,
        "Exact duplicate enrolment rows",
        "Removed exact duplicate rows across all columns (keep='first')",
        exact_dups,
    )

    pk_dup_mask = df["enrolment_id"].notna() & df.duplicated(subset=["enrolment_id"], keep="first")
    pk_dups = int(pk_dup_mask.sum())
    df = df.loc[~pk_dup_mask].reset_index(drop=True)
    add_log(
        log_entries,
        "Duplicate enrolment_id primary keys (non-exact)",
        "Removed remaining duplicate enrolment_id rows after exact deduplication (keep='first')",
        pk_dups,
    )

    # 3. Standardise and validate semester strictly within 1-4 (nullable Int64)
    raw_sem = clean_text_series(df["semester"], case="strip")
    missing_sem = int(raw_sem.isna().sum())
    non_digit_sem_mask = raw_sem.notna() & ~raw_sem.str.isdigit()
    extracted_sem = raw_sem.str.extract(r"^\s*(?:sem(?:ester)?\s*)?(-?\d+)\s*$", flags=re.IGNORECASE)[0]
    sem_numeric = pd.to_numeric(extracted_sem, errors="coerce")

    valid_sem_mask = sem_numeric.isin(list(VALID_SEMESTERS))
    converted_text_sem = int((non_digit_sem_mask & valid_sem_mask).sum())
    invalid_sem_count = int((raw_sem.notna() & ~valid_sem_mask).sum())

    df["semester"] = sem_numeric.where(valid_sem_mask, pd.NA).astype("Int64")

    add_log(
        log_entries,
        "Non-numeric semester text format (e.g. 'Sem 1')",
        "Extracted integer semester (1-4) from valid text labels and cast to Int64",
        converted_text_sem,
    )
    add_log(
        log_entries,
        "Missing or invalid semester values (outside 1-4)",
        f"Set invalid/out-of-range semester values to nullable Int64 null without deleting rows; missing={missing_sem}, invalid={invalid_sem_count}",
        missing_sem + invalid_sem_count,
    )

    # 4. Standardise and validate academic_year against {'2023-24', '2024-25'}
    raw_acad = df["academic_year"].copy()
    df["academic_year"] = clean_text_series(df["academic_year"], case="strip")
    acad_fmt_changed = count_text_changes(raw_acad, df["academic_year"])
    if acad_fmt_changed > 0:
        add_log(
            log_entries,
            "Inconsistent academic_year whitespace",
            "Trimmed whitespace in academic_year",
            acad_fmt_changed,
        )

    missing_acad = int(df["academic_year"].isna().sum())
    invalid_acad = int((df["academic_year"].notna() & ~df["academic_year"].isin(VALID_ACADEMIC_YEARS)).sum())
    add_log(
        log_entries,
        "Missing or invalid academic_year (outside 2023-24, 2024-25)",
        f"Validated academic_year against {{2023-24, 2024-25}} without silently deleting records; missing={missing_acad}, invalid={invalid_acad}",
        missing_acad + invalid_acad,
    )

    # 5. Validate required fields in enrolments (unique affected rows, no silent deletions)
    req_enrol_rows, req_enrol_cols = count_rows_with_any_missing(
        df, ["enrolment_id", "student_id", "course_id", "semester", "academic_year"]
    )
    add_log(
        log_entries,
        "Missing required key/period fields in enrolments",
        f"Checked required columns (enrolment_id, student_id, course_id, semester, academic_year) without deleting rows; per-column counts: {req_enrol_cols}",
        req_enrol_rows,
    )

    # 6. Separate missing enrolment_date counts from mixed-format and invalid/unparseable date counts
    raw_date_str = clean_text_series(df["enrolment_date"], case="strip")
    missing_date_mask = raw_date_str.isna()
    missing_dates_count = int(missing_date_mask.sum())

    non_missing_dates = raw_date_str[~missing_date_mask]
    parsed_non_missing = non_missing_dates.apply(parse_mixed_date)

    non_iso_mask = ~non_missing_dates.str.match(r"^\d{4}-\d{2}-\d{2}$")
    non_iso_valid_count = int((non_iso_mask & parsed_non_missing.notna()).sum())
    invalid_dates_count = int(parsed_non_missing.isna().sum())

    parsed_all = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    parsed_all.loc[~missing_date_mask] = parsed_non_missing

    df["enrolment_date"] = pd.Series(pd.NA, index=df.index, dtype="string")
    valid_dt_mask = parsed_all.notna()
    df.loc[valid_dt_mask, "enrolment_date"] = parsed_all.loc[valid_dt_mask].dt.strftime("%Y-%m-%d")

    add_log(
        log_entries,
        "Missing enrolment_date values",
        "Retained missing enrolment_date as null without deleting rows",
        missing_dates_count,
    )
    add_log(
        log_entries,
        "Mixed valid enrolment_date formats standardised",
        "Parsed DD/MM/YYYY, DD-Mon-YYYY, and YYYY/MM/DD dates into ISO YYYY-MM-DD",
        non_iso_valid_count,
    )
    add_log(
        log_entries,
        "Invalid / unparseable enrolment_date values",
        "Set invalid non-empty dates (e.g. '2024-13-45') to null without deleting rows",
        invalid_dates_count,
    )

    # 7. Convert marks to numeric; separate missing vs non-numeric vs out-of-range (0-100)
    raw_marks = df["marks"].copy()
    missing_marks_raw = int(raw_marks.isna().sum())
    numeric_marks = pd.to_numeric(raw_marks, errors="coerce")
    non_numeric_marks = int((raw_marks.notna() & numeric_marks.isna()).sum())
    out_of_range_mask = numeric_marks.notna() & ((numeric_marks < 0) | (numeric_marks > 100))
    out_of_range_count = int(out_of_range_mask.sum())

    numeric_marks = numeric_marks.mask(out_of_range_mask, pd.NA)
    df["marks"] = numeric_marks.astype("Float64")

    add_log(
        log_entries,
        "Missing marks values",
        "Retained missing marks as null (NA); excluded from average/pass-rate denominators",
        missing_marks_raw,
    )
    add_log(
        log_entries,
        "Invalid out-of-range or non-numeric marks (outside 0-100)",
        f"Converted non-numeric or out-of-range marks (<0 or >100) to null without deleting rows; non_numeric={non_numeric_marks}, out_of_range={out_of_range_count}",
        non_numeric_marks + out_of_range_count,
    )

    # 8. Attendance percentage numeric conversion and missing/range check
    raw_att = df["attendance_percentage"].copy()
    missing_att_raw = int(raw_att.isna().sum())
    numeric_att = pd.to_numeric(raw_att, errors="coerce")
    non_numeric_att = int((raw_att.notna() & numeric_att.isna()).sum())
    out_of_range_att_mask = numeric_att.notna() & ((numeric_att < 0) | (numeric_att > 100))
    out_of_range_att = int(out_of_range_att_mask.sum())

    numeric_att = numeric_att.mask(out_of_range_att_mask, pd.NA)
    df["attendance_percentage"] = numeric_att.astype("Float64")

    add_log(
        log_entries,
        "Missing attendance_percentage values",
        "Retained missing attendance_percentage as null without deleting rows",
        missing_att_raw,
    )
    if non_numeric_att + out_of_range_att > 0:
        add_log(
            log_entries,
            "Invalid attendance_percentage (non-numeric or outside 0-100)",
            "Set invalid attendance_percentage to null without deleting rows",
            non_numeric_att + out_of_range_att,
        )

    # 9. Recalculate result strictly from valid marks (>= 40 Pass, < 40 Fail, else Missing/Invalid)
    old_result = df["result"].copy()
    new_result = pd.Series("Missing/Invalid", index=df.index, dtype="string")
    valid_marks_mask = df["marks"].notna()
    new_result.loc[valid_marks_mask & (df["marks"] >= PASSING_MARKS)] = "Pass"
    new_result.loc[valid_marks_mask & (df["marks"] < PASSING_MARKS)] = "Fail"

    missing_res_raw = int(clean_text_series(old_result).isna().sum())
    inconsistent_res_count = count_text_changes(old_result, new_result)
    df["result"] = new_result

    add_log(
        log_entries,
        "Missing result values in raw data",
        "Recalculated result from valid marks or labelled 'Missing/Invalid' when marks unavailable",
        missing_res_raw,
    )
    add_log(
        log_entries,
        "Inconsistent or recalculated result values",
        "Standardised text and enforced marks >= 40 -> Pass, < 40 -> Fail, unavailable -> Missing/Invalid",
        inconsistent_res_count,
    )

    # 10. Referential integrity checks (no silent deletions)
    orphan_students = int((df["student_id"].notna() & ~df["student_id"].isin(students_clean["student_id"])).sum())
    orphan_courses = int((df["course_id"].notna() & ~df["course_id"].isin(courses_clean["course_id"])).sum())
    add_log(
        log_entries,
        "Referential integrity check: student_id",
        "Verified all non-null enrolments.student_id exist in cleaned students.student_id",
        orphan_students,
    )
    add_log(
        log_entries,
        "Referential integrity check: course_id",
        "Verified all non-null enrolments.course_id exist in cleaned courses.course_id",
        orphan_courses,
    )

    return df


def main() -> None:
    """Run the full Phase 6 data cleaning pipeline and save clean CSVs + audit log."""
    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / "data" / "raw"
    clean_dir = project_root / "data" / "clean"
    reports_dir = project_root / "reports"

    clean_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Load raw files read-only
    students_raw = pd.read_csv(raw_dir / "students.csv")
    courses_raw = pd.read_csv(raw_dir / "courses.csv")
    enrolments_raw = pd.read_csv(raw_dir / "enrolments.csv")

    log_entries: list[dict] = []

    students_clean = clean_students(students_raw, enrolments_raw, log_entries)
    courses_clean = clean_courses(courses_raw, log_entries)
    enrolments_clean = clean_enrolments(enrolments_raw, students_clean, courses_clean, log_entries)

    # Save cleaned CSV files ONLY inside data/clean/
    students_clean.to_csv(clean_dir / "students.csv", index=False)
    courses_clean.to_csv(clean_dir / "courses.csv", index=False)
    enrolments_clean.to_csv(clean_dir / "enrolments.csv", index=False)

    # Save data quality audit log inside reports/
    dq_log_df = pd.DataFrame(log_entries, columns=["issue", "rule_applied", "rows_affected"])
    dq_log_df.to_csv(reports_dir / "data_quality_log.csv", index=False)

    print("=== DATA QUALITY SUMMARY ===")
    print(
        f"Raw row counts   -> students: {len(students_raw)}, "
        f"courses: {len(courses_raw)}, enrolments: {len(enrolments_raw)}"
    )
    print(
        f"Clean row counts -> students: {len(students_clean)}, "
        f"courses: {len(courses_clean)}, enrolments: {len(enrolments_clean)}"
    )
    print("\nData Quality Log:")
    print(dq_log_df.to_string(index=False))


if __name__ == "__main__":
    main()
