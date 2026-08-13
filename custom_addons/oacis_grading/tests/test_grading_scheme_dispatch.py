import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('oacis', 'unit')
class OacisGradingSchemeDispatchTest(TransactionCase):
    """Phase 2: the grade-entry result dispatch keys on the effective
    grading scheme of the company.

    - credit_gpa (legacy default)  -> student.cgpa
    - simple/weighted percentage   -> student.average_percentage
    - pass_fail / rubric / cert    -> student.courses_passed/failed
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Legacy baseline: no profile set -> effective scheme = credit_gpa.
        cls.company.institution_profile_id = False

        cls.faculty = cls.env['oacis.faculty'].create({
            'name': 'Test Faculty of Arts',
            'code': 'TFAA',
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
        cls.course2 = cls.env['oacis.course'].create({
            'name': 'Test World History',
            'code': 'TWH402',
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
        cls.offering2 = cls.env['oacis.course.offering'].create({
            'course_id': cls.course2.id,
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
            'email': 'grading.dispatch@example.com',
            'mobile': '+914444444444',
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
        self.enrollment2 = self.env['oacis.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering2.id,
        })

    def _publish(self, enrollment, internal, external):
        grade = self.env['oacis.grade.entry'].create({
            'enrollment_id': enrollment.id,
            'internal_marks': internal,
            'external_marks': external,
        })
        grade.action_submit()
        grade.action_verify()
        grade.action_publish()
        return grade

    def test_01_legacy_credit_gpa_dispatch(self):
        self.company.institution_profile_id = False
        self.assertEqual(self.student.cgpa, 0.0)
        self._publish(self.enrollment, 38.0, 52.0)
        self.assertGreater(self.student.cgpa, 0.0)
        # Percentage fields are not touched on the legacy path.
        self.assertEqual(self.student.average_percentage, 0.0)

    def test_02_simple_percentage_dispatch(self):
        scheme = self.env.ref(
            'oacis_institution_profile.grading_scheme_simple_percentage',
        )
        profile = self.env['oacis.institution.profile'].create({
            'name': 'Test School',
            'code': 'TEST-SCHOOL-PCT',
            'institution_type': 'school',
            'is_legacy_university': False,
            'grading_scheme_id': scheme.id,
        })
        self.company.institution_profile_id = profile.id
        grade = self._publish(self.enrollment, 38.0, 52.0)
        self.assertAlmostEqual(
            self.student.average_percentage, grade.percentage, places=2,
        )
        self.assertEqual(self.student.cgpa, 0.0)

    def test_03_pass_fail_dispatch(self):
        scheme = self.env.ref(
            'oacis_institution_profile.grading_scheme_pass_fail',
        )
        profile = self.env['oacis.institution.profile'].create({
            'name': 'Test Training',
            'code': 'TEST-TRAIN-PF',
            'institution_type': 'training',
            'is_legacy_university': False,
            'grading_scheme_id': scheme.id,
        })
        self.company.institution_profile_id = profile.id
        # One passing grade.
        self._publish(self.enrollment, 38.0, 52.0)
        self.assertEqual(self.student.courses_passed, 1)
        self.assertEqual(self.student.courses_failed, 0)
        # One failing grade on a second enrollment.
        self._publish(self.enrollment2, 10.0, 10.0)
        self.assertEqual(self.student.courses_passed, 1)
        self.assertEqual(self.student.courses_failed, 1)
