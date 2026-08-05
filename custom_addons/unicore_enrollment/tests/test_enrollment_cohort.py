"""Phase 7 regression suite: enrollment cohort rollup.

Verifies that `unicore.enrollment` carries the cohort context of its student:

* Legacy (academic_year) -> enrollment.batch_year + 'Batch YYYY' label.
* K-12 grade_batch      -> enrollment.grade_level_id + label = grade.
* Training rolling      -> enrollment.cohort_start_date + label = date.

The stored related fields make enrollments searchable / groupable by cohort
(K-12 sections per grade, training intakes). Purely additive: no new required
fields, no behavior change, and legacy enrollments are untouched.
"""

import odoo
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'unit')
class UniCoreEnrollmentCohortTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        # Deterministic legacy baseline: main company starts with NO profile.
        cls.company.institution_profile_id = False

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'P7 Faculty of Science',
            'code': 'PFSCI',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'P7 Mathematics',
            'code': 'P7MATH',
            'faculty_id': cls.faculty.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'P7 B.Sc. Maths',
            'code': 'P7BSCMATH',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'P7 Campus',
            'code': 'P7CAMPUS',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': 'P7 AY 2026-27',
            'code': 'P7AY2627',
            'date_start': '2026-07-01',
            'date_end': '2027-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'P7 EVEN 2026-27',
            'code': 'P7EVEN',
            'semester_type': 'even',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2027-01-15',
            'date_end': '2027-05-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        cls.course = cls.env['unicore.course'].create({
            'name': 'P7 Linear Algebra',
            'code': 'P7LA301',
            'credit_hours': 4.0,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.offering = cls.env['unicore.course.offering'].create({
            'course_id': cls.course.id,
            'semester_id': cls.semester.id,
            'academic_year_id': cls.academic_year.id,
            'program_id': cls.program.id,
            'campus_id': cls.campus.id,
            'offering_state': 'open',
            'max_enrollment': 60,
            'company_id': cls.company.id,
        })
        cls.grade_type = cls.env.ref(
            'unicore_academic_generic.unit_type_grade_level')

    def _student(self, program_id, email, **kw):
        vals = {
            'name': 'P7 Student',
            'gender': 'male',
            'date_of_birth': '2001-06-15',
            'email': email,
            'mobile': '+911111111111',
            'company_id': self.company.id,
            'campus_id': self.campus.id,
            'program_id': program_id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        }
        vals.update(kw)
        student = self.env['unicore.student'].create(vals)
        student.action_enroll()
        return student

    def _enroll(self, student):
        return self.env['unicore.enrollment'].create({
            'student_id': student.id,
            'course_offering_id': self.offering.id,
        })

    def _school_kit(self, tag):
        self.company.institution_profile_id = self.env[
            'unicore.institution.profile'
        ].create({
            'name': 'P7 School %s' % tag,
            'code': 'P7SCH%s' % tag,
            'institution_type': 'school',
            'is_legacy_university': False,
        }).id
        return self.env['unicore.academic.unit'].create({
            'name': 'Grade 5',
            'code': 'P7G5',
            'unit_type_id': self.grade_type.id,
            'company_id': self.company.id,
        })

    def _school_program(self, code, cohort_kind, unit):
        return self.env['unicore.program'].create({
            'name': 'P7 School Program %s' % code,
            'code': code,
            'program_type': 'undergraduate',
            'degree_title': 'P7 Diploma',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'academic_unit_id': unit.id,
            'cohort_kind': cohort_kind,
        })

    def test_01_legacy_enrollment_cohort(self):
        """Legacy enrollment carries batch_year + 'Batch YYYY' label."""
        self.company.institution_profile_id = False
        student = self._student(self.program.id, 'p7.legacy@example.com')
        enrollment = self._enroll(student)
        self.assertEqual(enrollment.cohort_kind, 'academic_year')
        self.assertEqual(enrollment.batch_year, 2025)
        self.assertFalse(enrollment.grade_level_id)
        self.assertFalse(enrollment.cohort_start_date)
        self.assertEqual(enrollment.cohort_label, 'Batch 2025')

    def test_02_grade_enrollment_cohort(self):
        """K-12 enrollment carries the student's grade level."""
        unit = self._school_kit('A')
        program = self._school_program('P7GB1', 'grade_batch', unit)
        student = self._student(program.id, 'p7.grade@example.com',
                                grade_level_id=unit.id)
        enrollment = self._enroll(student)
        self.assertEqual(enrollment.cohort_kind, 'grade_batch')
        self.assertEqual(enrollment.grade_level_id, unit)
        self.assertEqual(enrollment.cohort_label, unit.display_name)

    def test_03_rolling_enrollment_cohort(self):
        """Training enrollment carries the intake / cohort start date."""
        unit = self._school_kit('B')
        program = self._school_program('P7ROLL1', 'rolling', unit)
        student = self._student(program.id, 'p7.roll@example.com')
        # Phase 5 auto-fill set cohort_start_date from admission_date.
        self.assertEqual(str(student.cohort_start_date), '2025-06-01')
        enrollment = self._enroll(student)
        self.assertEqual(enrollment.cohort_kind, 'rolling')
        self.assertEqual(str(enrollment.cohort_start_date), '2025-06-01')
        self.assertEqual(enrollment.cohort_label, '2025-06-01')

    def test_04_enrollment_searchable_by_cohort(self):
        """Stored relateds make enrollments searchable / groupable by cohort."""
        unit = self._school_kit('C')
        rolling = self._school_program('P7ROLL2', 'rolling', unit)
        gb = self._school_program('P7GB2', 'grade_batch', unit)
        r = self._student(rolling.id, 'p7.search.r@example.com')
        g = self._student(gb.id, 'p7.search.g@example.com',
                          grade_level_id=unit.id)
        er = self._enroll(r)
        eg = self._enroll(g)
        self.assertEqual(
            self.env['unicore.enrollment'].search(
                [('cohort_kind', '=', 'rolling')]),
            er,
        )
        self.assertEqual(
            self.env['unicore.enrollment'].search(
                [('grade_level_id', '=', unit.id)]),
            eg,
        )
        self.assertEqual(
            self.env['unicore.enrollment'].search(
                [('cohort_start_date', '=', '2025-06-01')]),
            er,
        )
