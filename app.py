import streamlit as st
import pandas as pd
from io import StringIO

# Define a grade order for sorting
grade_order = ['F', 'D-', 'D','D+', 'C-', 'C', 'C+', 'B-', 'B', 'B+', 'A-', 'A', 'A+']
grade_mapping = {grade: i for i, grade in enumerate(grade_order)}

passing_grades = {
    'Pre': grade_order[3:],  # Grades from D+ and above
    'Eng': grade_order[4:],  # Grades from C- and above
}

LEVELS = ['1Freshman', '2Sophomore', '3Junior', '4Senior','5Final']
TERMS = ['Fall','Spring']

def validate_credits(prereq_df, selected_courses):
    # Filter the DataFrame for the selected courses
    filtered_df = prereq_df[prereq_df['Course Code'].isin(selected_courses)]
    
    # Calculate the total credits
    filtered_df = filtered_df.drop_duplicates(subset=['Course Code'])
    total_credits = filtered_df['Credits'].sum()
    exceed_status = total_credits > 21
    return total_credits, exceed_status

def check_passing_grades(university_requirements, student_history):
    status = []
    programs = []
    courses = []
    terms = []
    levels = []

    for _, row in student_history.iterrows():
        course = row['Course Code']
        grade = row['Grade']
        
        filtered_row = university_requirements[university_requirements['Course Code'] == str(course).strip()]
        if not filtered_row.empty:
            program = filtered_row['Program'].values[0]
            course_name = filtered_row['Course Name'].values[0]
            term = filtered_row['Term'].values[0]
            level = filtered_row['Level'].values[0]
            
            terms.append(term)
            levels.append(level)
            courses.append(course_name)
            programs.append(program)
            
            if grade in passing_grades.get(program, []): 
                status.append('Pass')
            else:
                status.append('Fail')
        else:
            terms.append('Empty')
            levels.append('Empty')
            courses.append('No course, c-as belong to Eng Program')
            programs.append('Eng')
            
            if grade in passing_grades.get('Eng', []):
                status.append('Pass')
            else:
                status.append('Fail')

    # Add the results to the student_history DataFrame
    student_history['Course Name'] = courses
    student_history['Status'] = status
    student_history['Program'] = programs
    student_history['Level'] = levels
    student_history['Term'] = terms
    return student_history

def check_pre_engineering(student_history):
    fail_courses = student_history[student_history['Status'] == 'Fail']
    return fail_courses

def check_prerequisites(selected_courses, history_df, prereq_df):
    completed_courses = {row['Course Code'].strip(): row['Grade'].strip() for _, row in history_df.iterrows() if row['Status'] == 'Pass'}
    results = []

    for course in selected_courses:
        prereqs = prereq_df[prereq_df['Course Code'] == course]

        if prereqs.empty:
            results.append({"Course Code": course, "Status": "No prerequisite information available", "Missing":None})
            continue

        missing_prereqs = []
        for prereq_col in ['Prereq 1', 'Prereq 2']:
            prereq = prereqs[prereq_col].values[0].strip()
            if prereq != "-" and prereq not in completed_courses:
                missing_prereqs.append(prereq)

        if missing_prereqs:
            results.append({"Course Code": course, "Status": "Missing ", "Missing": missing_prereqs})
        else:
            results.append({"Course Code": course, "Status": "Met", "Missing":None})

    return pd.DataFrame(results)

def clean_student_history_data(df):
    df = df.drop('Rank',axis=1)
    # Extract text between brackets and update the column
    df['Grade'] = df['Grade'].str.extract(r'\((.*?)\)')
    df.rename(columns={'Course name': 'Course Code'}, inplace=True)
    # Drop Courses of S25
    df = df[~df['Course Code'].str.endswith('S25')]
    # Keep only text before the first '-'
    df['Course Code'] = df['Course Code'].str.split('-', n=1).str[0]
    # Filter rows with both text and digits
    df = df[df['Course Code'].str.contains(r'[A-Za-z]', na=False) & df['Course Code'].str.contains(r'\d', na=False)]

    # Keep the row with the highest grade for each course
    df['Grade_rank'] = df['Grade'].map(grade_mapping)
    df = df.sort_values(by=['Course Code', 'Grade_rank'], ascending=[True, False]).drop_duplicates(subset=['Course Code'], keep='first')
    df = df.drop(columns=['Grade_rank'])
    return df

def filter_courses_by_level(university_requirements, level_input):
    # Determine the levels to include
    if level_input in LEVELS:
        levels_to_include = LEVELS[:LEVELS.index(level_input)+1]
    else:
        raise ValueError("Invalid level input. Choose from: Freshman, Sophomore, Junior, Senior, Final.")

    filtered_df = university_requirements[university_requirements['Level'].isin(levels_to_include)]

    return filtered_df

def suggested_courses(university_requirements, student_history):
    completed_courses = {row['Course Code'].strip() for _, row in student_history.iterrows() if row['Status'] == 'Pass'}
    failed_courses = {row['Course Code'].strip() for _, row in student_history.iterrows() if row['Status'] == 'Fail'}
    courses_by_level = filter_courses_by_level(university_requirements, selected_level)['Course Code']
    courses_not_validated = set(courses_by_level) - completed_courses
    suggested = check_prerequisites(courses_not_validated, student_history, university_requirements)
    
    suggested = pd.merge(suggested, university_requirements, on="Course Code", how="left")[['Level', 'Term','Course Code', 'Course Name', 'Status', 'Missing']]
    suggested['Course Status'] = suggested['Course Code'].apply(lambda x: 'Fail' if x in failed_courses else 'Unenrolled')

    return suggested
    
def get_info_from_university_prerequiest(university_requirements, courses_prereq_checked):
    Courses = courses_prereq_checked['Course Code']
    merged_df = pd.merge(courses_prereq_checked, university_requirements, on="Course Code", how="left")
    return merged_df

st.set_page_config(page_title='SP - Study Plan', page_icon=':ambulance:')
st.title("MedTech - Engineering School")

# Sidebar
st.sidebar.header("Input Data")
university_requirements_file = st.sidebar.file_uploader("Upload University Requirements", type=["csv", "xlsx"])
student_history_file = st.sidebar.file_uploader("Upload Student History", type=["csv", "xlsx"])
input_course_group = st.sidebar.text_area("Enter Selected Courses")

#student_level = st.sidebar.text_area("Enter Student Level Student:Level").split(':')
selected_level = st.sidebar.pills("Levels", LEVELS, selection_mode="single")
selected_term = st.sidebar.pills("Terms", TERMS, selection_mode="single")


if st.sidebar.button("Check"):
    selected_courses = []
    course_group = []

    if input_course_group:
        try:
            course_group = pd.read_csv(StringIO(input_course_group), delimiter="\t") 
            selected_courses = list(course_group['Course Code'])
        except Exception as e:
            st.error(f"Error parsing data: {e}")
    if university_requirements_file and student_history_file:
        
        # Read the files
        university_requirements = pd.read_csv(university_requirements_file) if university_requirements_file.name.endswith(".csv") else pd.read_excel(university_requirements_file)
        student_history = pd.read_csv(student_history_file) if student_history_file.name.endswith(".csv") else pd.read_excel(student_history_file)

        student_history = clean_student_history_data(student_history)
        student_history = check_passing_grades(university_requirements,student_history)

        
        # Body
        st.dataframe(student_history, use_container_width=True)

        st.header("Selected Courses")
        st.dataframe(course_group, use_container_width=True)
        
        total_credits, exceed_status = validate_credits(university_requirements, selected_courses)
        st.subheader(f"Total Credits: {total_credits} {'(Exceeds 21)' if exceed_status else '(Valid)'}")
        

        failing_courses = check_pre_engineering(student_history)
        st.subheader("Failed Courses")
        st.dataframe(failing_courses,use_container_width=True)
        
        prerequisite_status = check_prerequisites(selected_courses, student_history, university_requirements)
        st.subheader("Check Prerequisites")
        st.dataframe(prerequisite_status,use_container_width=True)

        # prereq for suggested courses 
        recomanded_courses=suggested_courses(university_requirements, student_history)
        st.subheader("Suggested Courses Check ")
        st.dataframe(recomanded_courses,use_container_width=True)

        if input_course_group:
            st.subheader("Confirmed Courses")
            met_courses = prerequisite_status[prerequisite_status['Status'] == 'Met']
            met_courses = pd.merge(met_courses, course_group, on="Course Code", how="left") 
            horizontal_data = []
            for x, y in zip(met_courses['Course Code'], met_courses['Group']):
                horizontal_data.extend([x, y.upper()])
            course_excel_format = pd.DataFrame([horizontal_data], columns=[f"Col{i+1}" for i in range(len(horizontal_data))])
            st.dataframe(course_excel_format,use_container_width=True)

    else:
        st.sidebar.error("Please upload all required files and enter selected courses.")