"""Grade Book roll-up tests (unicore_gradebook).

Validates the grade book behaviour:
- roll-up math (percentage and weighted CA component)
- auto-refresh on new / edited / deleted graded submissions
- non-graded submissions are ignored by the roll-up
- Apply CA marks respects the grade entry state guard and the
  [0, internal_max] bound
- per-line Apply action
- assignment weight constraint
"""

import odoo
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('post_install', '-at_install')
class UniCoreGradeBookRollupTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'GB Test Faculty',
            'code': 'GBTF',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'GB Test Dept',
            'code': 'GBTD',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'GB Test B.Sc.',
            'code': 'GB-BSC',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Science',
            'credit_system': 'credit_hours',
            'duration_years': 4,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'GB Test Campus',
            'code': 'GBTCCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': 'GB Test AY 2028-29',
            'code': 'GBTAY2829',
            'date_start': '2028-07-01',
            'date_end': '2029-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'GB Test ODD 2028-29',
            'code': 'GBTODD-2829',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2028-07-15',
            'date_end': '2028-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })
        # internal_assessment_marks drives max_ca_marks on the
        # grade book and internal_max on the grade entry.
        cls.course = cls.env['unicore.course'].create({
            'name': 'GB Test Mathematics',
            'code': 'GBM401',
            'credit_hours': 4.0,
            'internal_assessment_marks': 50.0,
            'external_assessment_marks': 50.0,
            'total_marks': 100.0,
            'passing_marks': 40.0,
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
            'company_id': cls.company.id,
        })
        cls.student = cls.env['unicore.student'].create({
            'name': 'GradeBook',
            'last_name': 'Rollup Test',
            'gender': 'female',
            'date_of_birth': '2002-04-10',
            'email': 'gb.rollup@example.com',
            'mobile': '+914444444444',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2026,
            'admission_date': '2026-06-01',
        })

    def setUp(self):
        super().setUp()
        self.student.action_enroll()
        self.enrollment = self.env['unicore.enrollment'].create({
            'student_id': self.student.id,
            'course_offering_id': self.offering.id,
        })
        self.config = self.env['unicore.gradebook.config'].create({
            'course_offering_id': self.offering.id,
            'assignment_weight_pct': 20.0,
        })
        self.assignment_a = self.env['unicore.assignment'].create({
            'title': 'GB Assignment A',
            'course_offering_id': self.offering.id,
            'assignment_type': 'homework',
            'max_marks': 10.0,
            'due_date': '2028-09-01',
            'company_id': self.company.id,
        })
        self.assignment_b = self.env['unicore.assignment'].create({
            'title': 'GB Assignment B',
            'course_offering_id': self.offering.id,
            'assignment_type': 'project',
            'max_marks': 20.0,
            'due_date': '2028-09-15',
            'company_id': self.company.id,
        })

    # ------- HELPERS -------

    def _grade_submission(self, assignment, marks, state='graded'):
        """Create a graded submission for the test student."""
        return self.env['unicore.assignment.submission'].create({
            'assignment_id': assignment.id,
            'student_id': self.student.id,
            'enrollment_id': self.enrollment.id,
            'state': state,
            'marks_obtained': marks,
        })

    def _grade_entry(self, state='draft'):
        entry = self.env['unicore.grade.entry'].create({
            'enrollment_id': self.enrollment.id,
        })
        if state == 'submitted':
            entry.action_submit()
        elif state == 'verified':
            entry.action_submit()
            entry.action_verify()
        return entry

    # ------- TESTS -------

    def test_01_rollup_math(self):
        """assignment_percentage and weighted CA component."""
        self._grade_submission(self.assignment_a, 8.0)
        self._grade_submission(self.assignment_b, 10.0)

        line = self.config.student_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.graded_assignment_count, 2)
        self.assertEqual(line.total_possible_marks, 30.0)
        self.assertEqual(line.total_obtained_marks, 18.0)
        self.assertAlmostEqual(line.assignment_percentage, 60.0,
                               places=2)
        # max_ca_marks = 50, weight 20%, pct 60%
        # component = 50 * 0.20 * 0.60 = 6.0
        self.assertAlmostEqual(line.computed_ca_component, 6.0,
                               places=2)

    def test_02_auto_refresh_on_new_graded_submission(self):
        """New graded submission auto-refreshes roll-up; non-graded
        submissions are ignored."""
        sub_a = self._grade_submission(self.assignment_a, 8.0)
        line = self.config.student_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.graded_assignment_count, 1)
        self.assertEqual(line.total_obtained_marks, 8.0)

        # Editing the graded marks refreshes the roll-up.
        sub_a.write({'marks_obtained': 9.0})
        self.assertEqual(line.total_obtained_marks, 9.0)

        # A second graded submission is picked up automatically.
        self._grade_submission(self.assignment_b, 10.0)
        self.assertEqual(line.graded_assignment_count, 2)
        self.assertAlmostEqual(line.computed_ca_component, 6.0,
                               places=2)

        # A draft submission does NOT feed the roll-up.
        self._grade_submission(self.assignment_a, 5.0, state='draft')
        self.assertEqual(line.graded_assignment_count, 2)

        # Deleting a graded submission drops its snapshot line.
        sub_b = self.env['unicore.assignment.submission'].search([
            ('assignment_id', '=', self.assignment_b.id),
            ('student_id', '=', self.student.id),
        ], limit=1)
        sub_b.unlink()
        self.assertEqual(line.graded_assignment_count, 1)
        self.assertEqual(line.total_possible_marks, 10.0)

    def test_03_apply_respects_state_guard(self):
        """Apply writes editable entries only, never entry_state."""
        self._grade_submission(self.assignment_a, 8.0)
        self._grade_submission(self.assignment_b, 10.0)
        line = self.config.student_line_ids
        self.assertAlmostEqual(line.computed_ca_component, 6.0,
                               places=2)

        entry = self._grade_entry(state='draft')
        self.assertTrue(line.can_apply_ca_marks)
        self.assertFalse(line.is_synced)

        self.config.action_apply_ca_marks()
        self.assertAlmostEqual(entry.internal_marks, 6.0, places=2)
        self.assertEqual(entry.entry_state, 'draft')
        self.assertTrue(line.is_synced)
        self.assertTrue(line.can_apply_ca_marks)

        # Once submitted + verified the entry is no longer editable.
        entry.action_submit()
        entry.action_verify()
        self.assertFalse(line.can_apply_ca_marks)

        # A later roll-up change must NOT touch the verified entry.
        self._grade_submission(self.assignment_a, 10.0)
        self.config.action_apply_ca_marks()
        self.assertAlmostEqual(entry.internal_marks, 6.0, places=2)
        self.assertEqual(entry.entry_state, 'verified')

    def test_04_apply_bounded_to_internal_max(self):
        """Applied CA marks stay within [0, internal_max]."""
        # Weight 100% with perfect scores caps at internal_max (50).
        self.config.write({'assignment_weight_pct': 100.0})
        self._grade_submission(self.assignment_a, 10.0)
        self._grade_submission(self.assignment_b, 20.0)
        line = self.config.student_line_ids
        self.assertAlmostEqual(line.assignment_percentage, 100.0,
                               places=2)
        self.assertAlmostEqual(line.computed_ca_component, 50.0,
                               places=2)
        self.assertLessEqual(line.computed_ca_component,
                             line.max_ca_marks)

        entry = self._grade_entry(state='draft')
        self.config.action_apply_ca_marks()
        self.assertAlmostEqual(entry.internal_marks, 50.0, places=2)
        self.assertLessEqual(entry.internal_marks, entry.internal_max)

    def test_05_assignment_weight_constraint(self):
        """Weight must stay within [0, 100]."""
        with self.assertRaises(ValidationError):
            self.config.write({'assignment_weight_pct': 150.0})
        with self.assertRaises(ValidationError):
            self.config.write({'assignment_weight_pct': -5.0})

    def test_06_apply_line(self):
        """Per-line Apply action mirrors config-level guard."""
        self._grade_submission(self.assignment_a, 8.0)
        self._grade_submission(self.assignment_b, 10.0)
        line = self.config.student_line_ids

        entry = self._grade_entry(state='draft')
        line.action_apply_line()
        self.assertAlmostEqual(entry.internal_marks, 6.0, places=2)

        # Verified entries raise a UserError on per-line apply.
        entry.action_submit()
        entry.action_verify()
        with self.assertRaises(UserError):
            line.action_apply_line()

    def test_07_sync_progress_stats(self):
        """_compute_stats exposes sync progress on the config."""
        self._grade_submission(self.assignment_a, 8.0)
        self._grade_submission(self.assignment_b, 10.0)
        self.assertEqual(self.config.student_count, 1)
        self.assertEqual(self.config.synced_count, 0)
        self.assertEqual(self.config.pending_count, 1)
        self.assertEqual(self.config.sync_progress_pct, 0)

        self._grade_entry(state='draft')
        self.config.action_apply_ca_marks()
        self.assertEqual(self.config.synced_count, 1)
        self.assertEqual(self.config.pending_count, 0)
        self.assertEqual(self.config.sync_progress_pct, 100)
