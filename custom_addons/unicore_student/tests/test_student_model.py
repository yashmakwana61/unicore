from datetime import date, timedelta

import odoo
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreStudentModelTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'Test Faculty of Engineering',
            'code': 'TFE',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'Test Computer Science',
            'code': 'TCS',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'Test B.Tech CS',
            'code': 'TEST-BTECH-CS',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Technology',
            'credit_system': 'credit_hours',
            'duration_years': 4,
            'total_credits': 160,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'Test Main Campus',
            'code': 'TMAINCAMPUS',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': 'Test AY 2025-26',
            'code': 'TAY2526',
            'date_start': '2025-07-01',
            'date_end': '2026-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'Test ODD 2025-26',
            'code': 'TODD-2526',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })

        cls.student_vals = {
            'name': 'John',
            'last_name': 'Doe',
            'gender': 'male',
            'date_of_birth': '2000-01-15',
            'email': 'john.doe@example.com',
            'mobile': '+911234567890',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        }

    def test_01_student_create_basic(self):
        student = self.env['unicore.student'].create(dict(self.student_vals))
        self.assertTrue(student.id > 0, 'Student record must be created with a valid ID')
        self.assertTrue(student.student_id_number, 'Student ID number must be generated')
        self.assertNotEqual(student.student_id_number, '/', 'Student ID must not be the fallback "/"')
        self.assertTrue(student.partner_id, 'A partner record must be auto-created')
        self.assertEqual(student.student_state, 'admitted', 'Default student state must be "admitted"')

    def test_02_student_id_sequence_unique(self):
        s1 = self.env['unicore.student'].create(dict(self.student_vals))
        vals2 = dict(self.student_vals, email='jane.doe@example.com', mobile='+919876543210')
        s2 = self.env['unicore.student'].create(vals2)
        self.assertNotEqual(
            s1.student_id_number, s2.student_id_number,
            'Each student must receive a unique student_id_number',
        )
        self.assertNotEqual(s1.student_id_number, '/')
        self.assertNotEqual(s2.student_id_number, '/')

    def test_03_student_display_name(self):
        student = self.env['unicore.student'].create(dict(self.student_vals))
        self.assertEqual(student.display_name, 'John Doe')

        student_with_middle = self.env['unicore.student'].create(
            dict(self.student_vals, name='Alice', middle_name='Marie', last_name='Smith',
                 email='alice@example.com', mobile='+911111111111'),
        )
        self.assertEqual(student_with_middle.display_name, 'Alice Marie Smith')

    def test_04_student_cgpa_default(self):
        student = self.env['unicore.student'].create(dict(self.student_vals))
        self.assertEqual(student.cgpa, 0.0, 'New student must have CGPA of 0.0')

    def test_05_student_email_is_unique_per_company(self):
        self.env['unicore.student'].create(dict(self.student_vals))
        with self.assertRaises(Exception):
            self.env['unicore.student'].create(dict(self.student_vals))

    def test_06_student_state_transitions(self):
        student = self.env['unicore.student'].create(dict(self.student_vals))
        self.assertEqual(student.student_state, 'admitted')

        student.action_enroll()
        self.assertEqual(student.student_state, 'enrolled')

        student.current_semester_id = self.semester.id
        student.action_activate()
        self.assertEqual(student.student_state, 'active')

    def test_07_student_graduate(self):
        student = self.env['unicore.student'].create(dict(self.student_vals))
        student.action_enroll()
        student.current_semester_id = self.semester.id
        student.action_activate()

        student.total_credits_earned = 160
        student.action_graduate()
        self.assertEqual(student.student_state, 'graduated')
        self.assertEqual(student.actual_graduation_date, date.today())

    def test_08_student_graduate_fails_if_insufficient_credits(self):
        student = self.env['unicore.student'].create(dict(self.student_vals))
        student.action_enroll()
        with self.assertRaises(UserError):
            student.action_graduate()

    def test_09_student_company_isolation(self):
        company2 = self.env['res.company'].create({'name': 'Second University'})
        campus2 = self.env['unicore.campus'].create({
            'name': 'Second Campus',
            'code': 'SECCAMP',
            'company_id': company2.id,
        })
        program2 = self.env['unicore.program'].create({
            'name': 'Second Program',
            'code': 'SECPROG',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Second',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': self.department.id,
            'company_id': company2.id,
        })
        s1 = self.env['unicore.student'].create(dict(self.student_vals))
        s2 = self.env['unicore.student'].create({
            'name': 'Jane',
            'last_name': 'Smith',
            'gender': 'female',
            'date_of_birth': '2001-03-20',
            'email': 'jane@second.com',
            'mobile': '+919876543210',
            'company_id': company2.id,
            'campus_id': campus2.id,
            'program_id': program2.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        students_company1 = self.env['unicore.student'].search([('company_id', '=', self.company.id)])
        self.assertIn(s1, students_company1)
        self.assertNotIn(s2, students_company1)

    def test_10_student_min_age_validation(self):
        too_young = dict(
            self.student_vals,
            name='Baby',
            email='baby@example.com',
            mobile='+911234567891',
            date_of_birth=str(date.today() - timedelta(days=365 * 5)),
        )
        with self.assertRaises(ValidationError):
            self.env['unicore.student'].create(too_young)


@odoo.tests.tagged('unicore', 'unit')
class UniCoreCurriculumDependencyCheck(TransactionCase):
    """Placeholder: enrollment/grading/attendance tests live in their own modules."""

    def test_module_loaded(self):
        self.assertTrue(True)
