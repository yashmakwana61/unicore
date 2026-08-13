import odoo
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisGradingTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Arts',
            'code': 'TFA',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test English',
            'code': 'TENG',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'Test B.A. English',
            'code': 'TEST-BA-ENG',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Arts Campus',
            'code': 'TARTSCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2027-28',
            'code': 'TAY2728',
            'date_start': '2027-07-01',
            'date_end': '2028-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Test ODD 2027-28',
            'code': 'TODD-2728',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2027-07-15',
            'date_end': '2027-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.course = cls.env['oacis.course'].create({
            'name': 'Test English Literature',
            'code': 'TEL401',
            'credit_hours': 4.0,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.offering = cls.env['oacis.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'company_id': cls.company.id,
        })
        cls.student = cls.env['oacis.student'].create({
            'name': 'Grading',
            'last_name': 'Test Student',
            'gender': 'female',
            'date_of_birth': '2001-09-10',
            'email': 'grading.test@example.com',
            'mobile': '+913333333333',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })

    def setUp(self):
        super().setUp()
        self.student.action_enroll()
        self.enrollment = self.env['oacis.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })

    def test_01_grade_entry_create(self):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 35.0,
            'external_marks': 55.0,
        })
        self.assertEqual(grade.total_marks_obtained, 90.0)
        self.assertAlmostEqual(grade.percentage, 90.0, places=2)
        self.assertTrue(grade.letter_grade)

    def test_02_grade_point_calculation(self):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 40.0,
            'external_marks': 45.0,
        })
        self.assertAlmostEqual(grade.percentage, 85.0, places=2)
        self.assertTrue(grade.is_pass)
        self.assertGreater(grade.grade_point, 0.0)

    def test_03_failing_grade(self):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 10.0,
            'external_marks': 10.0,
        })
        self.assertAlmostEqual(grade.percentage, 20.0, places=2)
        self.assertFalse(grade.is_pass)
        self.assertEqual(grade.letter_grade, 'F')

    def test_04_cgpa_recomputes_on_new_grade(self):
        self.assertEqual(self.student.cgpa, 0.0)
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 38.0,
            'external_marks': 52.0,
        })
        grade.action_submit()
        grade.action_verify()
        grade.action_publish()
        self.assertGreater(self.student.cgpa, 0.0)

    def test_05_grade_entry_state_flow(self):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 30.0,
            'external_marks': 50.0,
        })
        self.assertEqual(grade.entry_state, 'draft')
        grade.action_submit()
        self.assertEqual(grade.entry_state, 'submitted')
        grade.action_verify()
        self.assertEqual(grade.entry_state, 'verified')
        grade.action_publish()
        self.assertEqual(grade.entry_state, 'published')
        grade.action_lock()
        self.assertEqual(grade.entry_state, 'locked')

    def test_06_grade_locked_cannot_be_edited(self):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 30.0,
            'external_marks': 50.0,
        })
        grade.action_submit()
        grade.action_verify()
        grade.action_publish()
        grade.action_lock()
        self.assertEqual(grade.entry_state, 'locked')
        with self.assertRaises(UserError):
            grade.action_reset_draft()

    def test_07_semester_result_generation(self):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
            'internal_marks': 38.0,
            'external_marks': 52.0,
        })
        grade.action_submit()
        grade.action_verify()
        grade.action_publish()

        count = self.env['oacis.semester.result'].generate_results_for_semester(
            self.semester.id, self.company.id,
        )
        self.assertEqual(count, 1)

        result = self.env['oacis.semester.result'].search([
            ('student_id', '=', self.student.id),
            ('semester_id', '=', self.semester.id),
        ], limit=1)
        self.assertTrue(result)
        self.assertGreater(result.semester_gpa, 0.0)
        self.assertEqual(result.credits_attempted, 4.0)
        self.assertEqual(result.credits_earned, 4.0)
        self.assertEqual(result.result_status, 'pass')

    def test_08_internal_marks_cannot_exceed_max(self):
        with self.assertRaises(ValidationError):
            self.env['oacis.grade.entry'].create({
                'enrollment_id': self.enrollment.id,
                'internal_marks': 99.0,
                'external_marks': 10.0,
            })

    def test_09_external_marks_cannot_exceed_max(self):
        with self.assertRaises(ValidationError):
            self.env['oacis.grade.entry'].create({
                'enrollment_id': self.enrollment.id,
                'internal_marks': 10.0,
                'external_marks': 99.0,
            })
