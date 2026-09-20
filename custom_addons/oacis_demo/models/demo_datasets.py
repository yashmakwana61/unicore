"""Oacis Demo — per-institution-type dataset definitions.

Each entry is keyed by the exact ``institution_type`` value from
``oacis.institution.profile`` (plus the ``legacy`` fallback, which behaves
as a university).  Datasets describe *what* to create; the generator in
``demo_generator.py`` describes *how* and *in which order*.

Volumes marked ``None`` are taken from the linked ``oacis.demo.profile``
record so admins can tune sizes without editing code.
"""

# Academic-unit type codes (see oacis_academic_generic data).
UNIT_FACULTY = 'FAC'
UNIT_DEPARTMENT = 'DEP'
UNIT_GRADE = 'GRADE'
UNIT_STREAM = 'STREAM'
UNIT_BATCH = 'BATCH'
UNIT_OTHER = 'OTHER'

# year_type -> (semester_type codes, display names) for the two demo terms.
TERMS = {
    'semester': [('odd', 'Odd Semester'), ('even', 'Even Semester')],
    'term': [('term_1', 'Term 1'), ('term_2', 'Term 2')],
    'trimester': [('trimester_1', 'Trimester 1'), ('trimester_2', 'Trimester 2')],
    'quarter': [('quarter_1', 'Quarter 1'), ('quarter_2', 'Quarter 2')],
    'annual': [('annual', 'Annual Session'), ('annual', 'Annual Session')],
}

DATASETS = {
    'university': {
        'year_type': 'semester',
        'faculties': [
            ('Faculty of Engineering and Technology', 'ENG'),
            ('Faculty of Business Administration', 'BUS'),
        ],
        'departments': [
            # (name, code, faculty_code)
            ('Department of Computer Science', 'CS', 'ENG'),
            ('Department of Electronics and Communication', 'EC', 'ENG'),
            ('Department of Management Studies', 'MGMT', 'BUS'),
        ],
        'programs': [
            # (name, code, dept_code, program_type, degree, years, credits, fee)
            ('Bachelor of Technology in Computer Science', 'BTECH-CS', 'CS',
             'undergraduate', 'Bachelor of Technology', 4.0, 160, 45000.0),
            ('Bachelor of Technology in Electronics', 'BTECH-EC', 'EC',
             'undergraduate', 'Bachelor of Technology', 4.0, 160, 42000.0),
            ('Master of Business Administration', 'MBA', 'MGMT',
             'postgraduate', 'Master of Business Administration', 2.0, 90, 55000.0),
        ],
        'specialisations': [
            ('Artificial Intelligence', 'AI', 'BTECH-CS'),
            ('Software Engineering', 'SE', 'BTECH-CS'),
        ],
        'courses': [
            # (name, code, dept_code, category, type, credits)
            ('Introduction to Programming', 'CS101', 'CS', 'core', 'theory_practical', 4.0),
            ('Discrete Mathematics', 'MATH101', 'CS', 'core', 'theory', 3.0),
            ('Digital Logic Design', 'CS102', 'CS', 'core', 'theory_practical', 4.0),
            ('Communication Skills', 'ENG101', 'CS', 'general', 'theory', 2.0),
            ('Data Structures and Algorithms', 'CS201', 'CS', 'core', 'theory_practical', 4.0),
            ('Principles of Management', 'MBA101', 'MGMT', 'core', 'theory', 3.0),
            ('Business Statistics', 'MBA102', 'MGMT', 'core', 'theory', 3.0),
            ('Web Development Fundamentals', 'CS104', 'CS', 'elective', 'theory_practical', 3.0),
        ],
        'fee_lines': [
            ('Tuition Fee', 'tuition', 45000.0),
            ('Library Fee', 'library', 5000.0),
            ('Examination Fee', 'exam', 3000.0),
            ('Development Fee', 'development', 2000.0),
        ],
    },
    'college': {
        'year_type': 'semester',
        'faculties': [
            ('Faculty of Arts and Science', 'FAS'),
            ('Faculty of Commerce', 'FCOM'),
        ],
        'departments': [
            ('Department of Computer Science', 'CS', 'FAS'),
            ('Department of Mathematics', 'MATH', 'FAS'),
            ('Department of Commerce', 'COM', 'FCOM'),
        ],
        'programs': [
            ('Bachelor of Science in Computer Science', 'BSC-CS', 'CS',
             'undergraduate', 'Bachelor of Science', 3.0, 120, 30000.0),
            ('Bachelor of Science in Mathematics', 'BSC-MATH', 'MATH',
             'undergraduate', 'Bachelor of Science', 3.0, 120, 28000.0),
            ('Bachelor of Commerce', 'BCOM', 'COM',
             'undergraduate', 'Bachelor of Commerce', 3.0, 120, 26000.0),
        ],
        'specialisations': [
            ('Data Science', 'DS', 'BSC-CS'),
        ],
        'courses': [
            ('Programming Fundamentals', 'CS101', 'CS', 'core', 'theory_practical', 4.0),
            ('Calculus I', 'MATH101', 'MATH', 'core', 'theory', 4.0),
            ('Financial Accounting', 'COM101', 'COM', 'core', 'theory', 3.0),
            ('English Communication', 'ENG101', 'CS', 'general', 'theory', 2.0),
            ('Database Systems', 'CS201', 'CS', 'core', 'theory_practical', 4.0),
            ('Business Economics', 'COM102', 'COM', 'core', 'theory', 3.0),
        ],
        'fee_lines': [
            ('Tuition Fee', 'tuition', 30000.0),
            ('Library Fee', 'library', 3000.0),
            ('Examination Fee', 'exam', 2000.0),
            ('Development Fee', 'development', 1500.0),
        ],
    },
    'school': {
        'year_type': 'term',
        # Generic-unit tree: Grade levels only (K12 profile allows GRADE).
        'units': [
            # (name, code, unit_type_code)
            ('Grade 8', 'G8', UNIT_GRADE),
            ('Grade 9', 'G9', UNIT_GRADE),
            ('Grade 10', 'G10', UNIT_GRADE),
        ],
        # Minimal rigid anchor: one faculty + department satisfies the
        # required faculty.member.department_id for teacher records.
        'faculties': [('General Studies', 'GEN-F')],
        'departments': [('General Department', 'GEN-D', 'GEN-F')],
        'programs': [
            # Classes anchored to grade units (academic_unit codes).
            ('Class 8 - General', 'CLS-8', 'G8', 15000.0),
            ('Class 9 - General', 'CLS-9', 'G9', 16000.0),
            ('Class 10 - General', 'CLS-10', 'G10', 17000.0),
        ],
        'courses': [
            ('Mathematics', 'SUB-MATH', 'core', 'theory', 1.0),
            ('English', 'SUB-ENG', 'core', 'theory', 1.0),
            ('Science', 'SUB-SCI', 'core', 'theory_practical', 1.0),
            ('Social Studies', 'SUB-SST', 'core', 'theory', 1.0),
            ('Computer Basics', 'SUB-COMP', 'elective', 'theory_practical', 1.0),
        ],
        'fee_lines': [
            ('Tuition Fee', 'tuition', 15000.0),
            ('Library Fee', 'library', 1500.0),
            ('Examination Fee', 'exam', 1200.0),
            ('Transport Fee', 'transport', 4000.0),
        ],
    },
    'training': {
        'year_type': 'semester',
        'units': [
            ('Batch A - Full Stack', 'BT-A', UNIT_BATCH),
            ('Batch B - Data Analytics', 'BT-B', UNIT_BATCH),
        ],
        'faculties': [('Skill Development', 'SKL-F')],
        'departments': [('Training Department', 'TRN-D', 'SKL-F')],
        'programs': [
            ('Full Stack Development Course', 'TRN-FULL', 'BT-A', 20000.0),
            ('Data Analytics Course', 'TRN-DATA', 'BT-B', 22000.0),
        ],
        'courses': [
            ('HTML & CSS Basics', 'MOD-WEB', 'core', 'theory_practical', 2.0),
            ('Python Programming', 'MOD-PY', 'core', 'theory_practical', 3.0),
            ('SQL for Analytics', 'MOD-SQL', 'core', 'theory_practical', 2.0),
            ('Project Work', 'MOD-PROJ', 'project', 'project', 4.0),
        ],
        'fee_lines': [
            ('Course Fee', 'tuition', 20000.0),
            ('Material Fee', 'library', 2000.0),
            ('Certification Fee', 'exam', 1500.0),
        ],
    },
    'academy': {
        'year_type': 'term',
        'units': [
            ('JEE Batch 2026', 'JEE-26', UNIT_BATCH),
            ('NEET Batch 2026', 'NEET-26', UNIT_BATCH),
        ],
        'faculties': [('Test Preparation', 'TST-F')],
        'departments': [('Academy Department', 'ACA-D', 'TST-F')],
        'programs': [
            ('JEE Preparation Batch', 'ACA-JEE', 'JEE-26', 12000.0),
            ('NEET Preparation Batch', 'ACA-NEET', 'NEET-26', 12000.0),
        ],
        'courses': [
            ('Physics', 'SUB-PHY', 'core', 'theory', 1.0),
            ('Chemistry', 'SUB-CHE', 'core', 'theory', 1.0),
            ('Mathematics', 'SUB-MATH', 'core', 'theory', 1.0),
            ('Biology', 'SUB-BIO', 'core', 'theory', 1.0),
            ('Mock Test Series', 'MOCK-01', 'elective', 'theory', 1.0),
        ],
        'fee_lines': [
            ('Tuition Fee', 'tuition', 12000.0),
            ('Material Fee', 'library', 1500.0),
            ('Test Series Fee', 'exam', 1000.0),
        ],
    },
    'coaching': {
        'year_type': 'semester',
        'units': [
            ('Morning Batch', 'MORN', UNIT_BATCH),
            ('Evening Batch', 'EVE', UNIT_BATCH),
        ],
        'faculties': [('Coaching Wing', 'CCH-F')],
        'departments': [('Coaching Department', 'CCH-D', 'CCH-F')],
        'programs': [
            ('Spoken English Coaching', 'CCH-ENG', 'MORN', 8000.0),
            ('Aptitude Coaching', 'CCH-APT', 'EVE', 8000.0),
        ],
        'courses': [
            ('Grammar & Vocabulary', 'CCH-GR', 'core', 'theory', 1.0),
            ('Speaking Practice', 'CCH-SP', 'core', 'theory_practical', 1.0),
            ('Quantitative Aptitude', 'CCH-QA', 'core', 'theory', 1.0),
            ('Logical Reasoning', 'CCH-LR', 'core', 'theory', 1.0),
        ],
        'fee_lines': [
            ('Coaching Fee', 'tuition', 8000.0),
            ('Material Fee', 'library', 1000.0),
        ],
    },
}

# Fallback when the company has no institution profile (legacy behavior).
DATASETS['legacy'] = DATASETS['university']

FIRST_NAMES_MALE = [
    'Aarav', 'Kabir', 'Aryan', 'Vivaan', 'Rohan', 'Arjun', 'Aditya',
    'Ishaan', 'Krishna', 'Manav', 'Nikhil', 'Parth', 'Rahul', 'Sahil',
    'Varun', 'Yash', 'Dev', 'Farhan', 'Gaurav', 'Harsh',
]
FIRST_NAMES_FEMALE = [
    'Diya', 'Myra', 'Zara', 'Nisha', 'Ananya', 'Priya', 'Sneha',
    'Kavya', 'Riya', 'Tanvi', 'Pooja', 'Neha', 'Shreya', 'Divya',
    'Kiran', 'Meera', 'Aisha', 'Ritu', 'Simran', 'Vidya',
]
LAST_NAMES = [
    'Patel', 'Shah', 'Joshi', 'Desai', 'Mehta', 'Sharma', 'Verma',
    'Singh', 'Chauhan', 'Bhatt', 'Reddy', 'Gupta', 'Nair', 'Iyer',
    'Khan', 'Das', 'Kulkarni', 'Menon', 'Pillai', 'Rathore',
]
