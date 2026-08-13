import odoo
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisCourseEnrollmentTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Science',
            'code': 'TFS',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['oacis.department'].create({
            'name': 'Test Mathematics',
            'code': 'TMATH',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['oacis.program'].create({
            'name': 'Test B.Sc. Maths',
            'code': 'TEST-BSC-MATH',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['oacis.campus'].create({
            'name': 'Test Science Campus',
            'code': 'TSCICAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['oacis.academic.year'].create({
            'name': 'Test AY 2026-27',
            'code': 'TAY2627',
            'date_start': '2026-07-01',
            'date_end': '2027-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['oacis.semester'].create({
            'name': 'Test EVEN 2026-27',
            'code': 'TEVEN-2627',
            'semester_type': 'even',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2027-01-15',
            'date_end': '2027-05-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.course = cls.env['oacis.course'].create({
            'name': 'Test Linear Algebra',
            'code': 'TLA301',
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
            'max_enrollment': 60,
            'company_id': cls.company.id,
        })
        cls.student = cls.env['oacis.student'].create({
            'name': 'Test',
            'last_name': 'Student',
            'gender': 'male',
            'date_of_birth': '2001-06-15',
            'email': 'test.student@example.com',
            'mobile': '+911111111111',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })

    def setUp(self):
        super().setUp()
        self.student.action_enroll()

    def test_01_enrollment_create_basic(self):
        enrollment = self.env['oacis.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })
        self.assertTrue(enrollment.id > 0)
        self.assertEqual(enrollment.enrollment_state, 'registered')
        self.assertEqual(enrollment.course_id.id, self.course.id)
        self.assertEqual(enrollment.semester_id.id, self.semester.id)

    def test_02_duplicate_enrollment_blocked(self):
        self.env['oacis.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })
        with self.assertRaises(Exception):
            self.env['oacis.enrollment'].create({
                'student_id': self.student.id,
                'course_offering_id': self.offering.id,
            })

    def test_03_enrollment_requires_active_student(self):
        self.student.write({
            'student_state': 'graduated',
            'actual_graduation_date': '2025-06-15',
        })
        with self.assertRaises(UserError):
            self.env['oacis.enrollment'].create({
                'student_id': self.student.id,
                'course_offering_id': self.offering.id,
            })

    def test_04_enrollment_max_capacity(self):
        self.offering.write({
            'max_enrollment': 1,
            'min_enrollment': 0,
        })
        self.env['oacis.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })
        student2 = self.env['oacis.student'].create({
            'name': 'Second',
            'last_name': 'Student',
            'gender': 'male',
            'date_of_birth': '2002-07-20',
            'email': 'second@example.com',
            'mobile': '+912222222222',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        student2.action_enroll()
        with self.assertRaises(UserError):
            self.env['oacis.enrollment'].create({
                'student_id': student2.id,
                'course_offering_id': self.offering.id,
            })

    def test_05_enrollment_requires_open_offering(self):
        self.offering.offering_state = 'draft'
        with self.assertRaises(UserError):
            self.env['oacis.enrollment'].create({
                'student_id': self.student.id,
                'course_offering_id': self.offering.id,
            })
