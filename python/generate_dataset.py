"""
Phase 4: Synthetic Dataset Generator
Project: Course Enrolment and Pass Rate Analysis
Author: Rashmi Singh (B.Tech 2nd Year, ABES Engineering College)

Generates three raw CSV files in data/raw/:
    1. students.csv   (~250 unique students + controlled duplicates & quality issues)
    2. courses.csv    (10 B.Tech courses + controlled text casing/spacing issues)
    3. enrolments.csv (enrolment records across Semesters 1-4 + controlled quality issues)

All random values use a fixed seed (RANDOM_SEED = 42) for full reproducibility.
"""

from pathlib import Path
import numpy as np
import pandas as pd


RANDOM_SEED = 42
PASSING_MARKS = 40
NUM_UNIQUE_STUDENTS = 250


def build_students(rng: np.random.Generator) -> pd.DataFrame:
    """Create ~250 unique B.Tech student records with controlled quality issues."""
    first_names_male = [
        "Aarav", "Aditya", "Akash", "Aman", "Ankit", "Arjun", "Ayush", "Deepak",
        "Dev", "Gaurav", "Harsh", "Ishaan", "Karan", "Kartik", "Kunal", "Manish",
        "Mohit", "Nikhil", "Pranav", "Rahul", "Raj", "Rishabh", "Rohan", "Rohit",
        "Sahil", "Saurabh", "Shivam", "Siddharth", "Tushar", "Varun", "Vikram", "Vivek",
    ]
    first_names_female = [
        "Aakanksha", "Aditi", "Ananya", "Anjali", "Anushka", "Astha", "Bhavna", "Divya",
        "Garima", "Isha", "Jhanvi", "Kajal", "Kavya", "Khushi", "Kriti", "Megha",
        "Muskan", "Nandini", "Neha", "Nisha", "Pallavi", "Pooja", "Prachi", "Priya",
        "Rashmi", "Riya", "Sakshi", "Shreya", "Simran", "Sneha", "Swati", "Tanvi",
    ]
    last_names = [
        "Agarwal", "Bansal", "Bhatia", "Chauhan", "Choudhary", "Dubey", "Garg", "Gupta",
        "Jain", "Joshi", "Kapoor", "Kashyap", "Kumar", "Malhotra", "Mehta", "Mishra",
        "Nair", "Pandey", "Patel", "Rao", "Rawat", "Saxena", "Sharma", "Shukla",
        "Singh", "Sinha", "Srivastava", "Tiwari", "Tripathi", "Verma", "Yadav",
    ]

    departments = ["CSE", "IT", "ECE", "ME", "CE"]
    dept_probs = [0.30, 0.22, 0.20, 0.16, 0.12]
    admission_years = [2023, 2024]
    year_probs = [0.60, 0.40]

    records = []
    for idx in range(1, NUM_UNIQUE_STUDENTS + 1):
        student_id = f"STU{idx:04d}"
        gender = rng.choice(["Male", "Female"], p=[0.54, 0.46])
        if gender == "Male":
            first = rng.choice(first_names_male)
        else:
            first = rng.choice(first_names_female)
        last = rng.choice(last_names)
        student_name = f"{first} {last}"
        department = rng.choice(departments, p=dept_probs)
        admission_year = int(rng.choice(admission_years, p=year_probs))

        records.append(
            {
                "student_id": student_id,
                "student_name": student_name,
                "gender": gender,
                "department": department,
                "admission_year": admission_year,
            }
        )

    df = pd.DataFrame(records)

    # --- Inject controlled data-quality issues ---
    # 1. Inconsistent text formats (casing and leading/trailing whitespace)
    df.loc[4, "student_name"] = "  " + df.loc[4, "student_name"].lower()
    df.loc[19, "student_name"] = df.loc[19, "student_name"].upper() + "  "
    df.loc[44, "student_name"] = "  " + df.loc[44, "student_name"] + " "

    df.loc[7, "gender"] = "male"
    df.loc[23, "gender"] = "F"
    df.loc[51, "gender"] = "M"
    df.loc[78, "gender"] = "female "
    df.loc[103, "gender"] = " Male"

    df.loc[12, "department"] = "cse"
    df.loc[35, "department"] = " it "
    df.loc[88, "department"] = "Ece"
    df.loc[142, "department"] = "me "
    df.loc[199, "department"] = " ce"

    # 2. Missing values
    missing_gender_idx = [15, 62, 118, 174, 211]
    df.loc[missing_gender_idx, "gender"] = np.nan

    missing_year_idx = [39, 165]
    df.loc[missing_year_idx, "admission_year"] = np.nan

    # 3. Duplicate student records (5 exact duplicate rows appended)
    dup_rows = df.iloc[[2, 28, 95, 150, 220]].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

    return df


def build_courses() -> pd.DataFrame:
    """Create 10 realistic B.Tech courses with minor text format inconsistencies."""
    courses_data = [
        ("BT101", "Engineering Mathematics I", "Foundation", 4),
        ("BT102", "Programming in Python", "Core", 4),
        ("BT103", "Data Structures and Algorithms", "Core", 4),
        ("BT104", "Digital Electronics", "Core", 3),
        ("BT105", "Database Management Systems", "Core", 4),
        ("BT106", "Engineering Mechanics", "Foundation", 3),
        ("BT107", "Computer Networks", "Core", 3),
        ("BT108", "Discrete Mathematics", "Foundation", 4),
        ("BT109", "Operating Systems", "Core", 4),
        ("BT110", "Data Analytics Fundamentals", "Elective", 3),
    ]
    df = pd.DataFrame(
        courses_data,
        columns=["course_id", "course_name", "course_category", "credits"],
    )

    # Controlled text formatting issues for Phase 6 cleaning
    df.loc[1, "course_category"] = "core "
    df.loc[5, "course_category"] = " foundation"
    df.loc[9, "course_category"] = "ELECTIVE"

    return df


def build_enrolments(
    rng: np.random.Generator,
    students_df: pd.DataFrame,
    courses_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create enrolment records across Semesters 1-4 maintaining valid student_id
    and course_id relationships, plus controlled data-quality issues.
    """
    # Use unique clean student IDs and course IDs so relationships remain valid
    valid_students = students_df[["student_id", "department", "admission_year"]].drop_duplicates(
        subset=["student_id"]
    )
    course_ids = courses_df["course_id"].tolist()

    # Course popularity weights and difficulty (mean marks, std marks)
    course_weights = np.array([0.13, 0.15, 0.13, 0.09, 0.12, 0.08, 0.09, 0.07, 0.08, 0.06])
    course_weights = course_weights / course_weights.sum()

    course_score_profile = {
        "BT101": (61, 16),
        "BT102": (71, 14),
        "BT103": (52, 18),
        "BT104": (57, 16),
        "BT105": (67, 15),
        "BT106": (47, 17),
        "BT107": (64, 15),
        "BT108": (45, 18),
        "BT109": (59, 16),
        "BT110": (74, 12),
    }

    # Semester schedule mapping by (admission_batch, semester) -> (academic_year, start_date, days_window)
    schedule_2023 = {
        1: ("2023-24", "2023-08-01", 40),
        2: ("2023-24", "2024-01-08", 40),
        3: ("2024-25", "2024-08-01", 40),
        4: ("2024-25", "2025-01-06", 40),
    }
    schedule_2024 = {
        1: ("2024-25", "2024-08-01", 40),
        2: ("2024-25", "2025-01-06", 40),
    }

    # Slight semester progression offset in marks
    semester_shift = {1: 1.5, 2: 0.0, 3: -1.5, 4: 2.5}

    records = []
    enrol_counter = 1

    for _, stu in valid_students.iterrows():
        stu_id = stu["student_id"]
        # 2023 batch covers Semesters 1-4; 2024 batch covers Semesters 1-2
        adm_year = stu["admission_year"]
        if pd.isna(adm_year) or int(adm_year) == 2023:
            available_sems = [1, 2, 3, 4]
            active_schedule = schedule_2023
        else:
            available_sems = [1, 2]
            active_schedule = schedule_2024

        # Each student takes 1-2 courses per available semester from our 10-course catalog
        chosen_courses_all = []
        for sem in available_sems:
            num_courses_in_sem = int(rng.choice([1, 2], p=[0.35, 0.65]))
            # Avoid picking the exact same course twice for the same student if possible
            remaining = [c for c in course_ids if c not in chosen_courses_all]
            if len(remaining) < num_courses_in_sem:
                remaining = course_ids
            rem_idx = [course_ids.index(c) for c in remaining]
            rem_weights = course_weights[rem_idx]
            rem_weights = rem_weights / rem_weights.sum()

            picked = rng.choice(remaining, size=num_courses_in_sem, replace=False, p=rem_weights)
            chosen_courses_all.extend(picked.tolist())

            acad_year, start_str, window_days = active_schedule[sem]
            base_date = pd.Timestamp(start_str)

            for cid in picked:
                offset_days = int(rng.integers(0, window_days))
                enrol_date = (base_date + pd.Timedelta(days=offset_days)).strftime("%Y-%m-%d")

                mean_m, std_m = course_score_profile[cid]
                raw_mark = rng.normal(mean_m + semester_shift[sem], std_m)
                marks = int(np.clip(np.round(raw_mark), 5, 99))

                # Realistic positive link between marks and attendance
                att_base = 52 + (marks * 0.42) + rng.normal(0, 7)
                attendance = round(float(np.clip(att_base, 35.0, 100.0)), 1)

                result = "Pass" if marks >= PASSING_MARKS else "Fail"

                records.append(
                    {
                        "enrolment_id": f"ENR{enrol_counter:05d}",
                        "student_id": stu_id,
                        "course_id": cid,
                        "semester": sem,
                        "academic_year": acad_year,
                        "enrolment_date": enrol_date,
                        "marks": marks,
                        "attendance_percentage": attendance,
                        "result": result,
                    }
                )
                enrol_counter += 1

    df = pd.DataFrame(records)
    # Cast semester to object so we can inject realistic dirty text values too
    df["semester"] = df["semester"].astype(object)

    n = len(df)

    # --- Inject controlled data-quality issues ---
    # 1. Missing values in marks, attendance_percentage, result
    missing_marks_idx = rng.choice(n, size=12, replace=False)
    df.loc[missing_marks_idx, "marks"] = np.nan

    available_idx = [i for i in range(n) if i not in set(missing_marks_idx)]
    missing_att_idx = rng.choice(available_idx, size=10, replace=False)
    df.loc[missing_att_idx, "attendance_percentage"] = np.nan

    missing_res_idx = rng.choice(available_idx, size=8, replace=False)
    df.loc[missing_res_idx, "result"] = np.nan

    # 2. Invalid marks (< 0 or > 100)
    clean_pool = [
        i for i in range(n)
        if i not in set(missing_marks_idx) and i not in set(missing_res_idx)
    ]
    invalid_marks_idx = rng.choice(clean_pool, size=8, replace=False)
    invalid_mark_values = [-8, -3, 104, 112, 125, -15, 108, 130]
    for idx_pos, bad_val in zip(invalid_marks_idx, invalid_mark_values):
        df.loc[idx_pos, "marks"] = bad_val

    # 3. Inconsistent text formats in result and semester
    text_pool = [i for i in clean_pool if i not in set(invalid_marks_idx)]
    dirty_res_idx = rng.choice(text_pool, size=12, replace=False)
    for j, idx_pos in enumerate(dirty_res_idx):
        val = str(df.loc[idx_pos, "result"])
        if j % 3 == 0:
            df.loc[idx_pos, "result"] = val.lower()
        elif j % 3 == 1:
            df.loc[idx_pos, "result"] = val.upper()
        else:
            df.loc[idx_pos, "result"] = f" {val} "

    dirty_sem_idx = rng.choice(text_pool, size=6, replace=False)
    for idx_pos in dirty_sem_idx:
        df.loc[idx_pos, "semester"] = f"Sem {df.loc[idx_pos, 'semester']}"

    # 4. Incorrect / mixed date formats in enrolment_date
    date_idx = rng.choice(n, size=24, replace=False)
    for k, idx_pos in enumerate(date_idx):
        parsed_dt = pd.Timestamp(df.loc[idx_pos, "enrolment_date"])
        if k < 10:
            df.loc[idx_pos, "enrolment_date"] = parsed_dt.strftime("%d/%m/%Y")
        elif k < 18:
            df.loc[idx_pos, "enrolment_date"] = parsed_dt.strftime("%d-%b-%Y")
        elif k < 21:
            df.loc[idx_pos, "enrolment_date"] = parsed_dt.strftime("%Y/%m/%d")
        else:
            df.loc[idx_pos, "enrolment_date"] = "2024-13-45"  # invalid calendar date

    # 5. Duplicate enrolment rows (10 exact duplicates appended)
    dup_enrol_idx = rng.choice(n, size=10, replace=False)
    dup_enrol_rows = df.iloc[dup_enrol_idx].copy()
    df = pd.concat([df, dup_enrol_rows], ignore_index=True)

    return df


def main() -> None:
    """Generate raw datasets and save them inside data/raw/."""
    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(RANDOM_SEED)

    students_df = build_students(rng)
    courses_df = build_courses()
    enrolments_df = build_enrolments(rng, students_df, courses_df)

    students_path = raw_dir / "students.csv"
    courses_path = raw_dir / "courses.csv"
    enrolments_path = raw_dir / "enrolments.csv"

    students_df.to_csv(students_path, index=False)
    courses_df.to_csv(courses_path, index=False)
    enrolments_df.to_csv(enrolments_path, index=False)

    print("Raw datasets generated successfully in:", raw_dir)
    print(f"  students.csv   -> {students_df.shape[0]} rows, {students_df.shape[1]} columns")
    print(f"  courses.csv    -> {courses_df.shape[0]} rows, {courses_df.shape[1]} columns")
    print(f"  enrolments.csv -> {enrolments_df.shape[0]} rows, {enrolments_df.shape[1]} columns")


if __name__ == "__main__":
    main()
