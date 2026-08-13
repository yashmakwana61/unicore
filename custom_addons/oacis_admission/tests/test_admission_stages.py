"""Phase 2: configurable, per-company admission pipeline stages.

Verifies that:
- the 13 default stages are seeded for the main company and lazily for any
  newly created company (via the res.company hook);
- applicant ``state`` and ``stage_id`` stay in sync in both directions
  (kanban drag / stage write -> state, and state writes -> stage);
- ``action_advance_stage`` walks the pipeline by sequence and raises on
  terminal / last stages;
- stages are fully isolated per company.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

EXPECTED = [
    ('Inquiry', 10, 'inquiry'),
    ('Applied', 20, 'applied'),
    ('Documents Pending', 30, 'documents_pending'),
    ('Under Review', 40, 'under_review'),
    ('Shortlisted', 50, 'shortlisted'),
    ('Entrance Scheduled', 60, 'entrance_scheduled'),
    ('Merit Listed', 70, 'merit_listed'),
    ('Offer Sent', 80, 'offer_sent'),
    ('Fee Pending', 90, 'fee_pending'),
    ('Confirmed', 100, 'confirmed'),
    ('Rejected', 110, 'rejected'),
    ('Withdrawn', 120, 'withdrawn'),
    ('Waitlisted', 130, 'waitlisted'),
]


@tagged('unicore', 'unit')
class UniCoreAdmissionStageTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.campus = cls.env['unicore.campus'].create({
            'name': 'Stage Campus',
            'code': 'STGC',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': '2025-2026',
            'code': '2025',
            'date_start': '2025-06-01',
            'date_end': '2026-05-31',
        })
        cls.cycle = cls.env['unicore.admission.cycle'].create({
            'name': 'Stage Intake 2025-26',
            'code': 'STG-2526',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2025-03-01',
            'end_date': '2025-08-31',
            'state': 'active',
            'company_id': cls.company.id,
        })
        # University-type institutions require a department on the program.
        faculty = cls.env['unicore.faculty'].create({
            'name': 'Faculty of Arts',
            'code': 'FA',
            'company_id': cls.company.id,
        })
        department = cls.env['unicore.department'].create({
            'name': 'Humanities',
            'code': 'HUM',
            'faculty_id': faculty.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'Stage B.A.',
            'code': 'STGBA',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3.0,
            'total_credits': 90,
            'department_id': department.id,
            'company_id': cls.company.id,
        })

        # Re-seed is idempotent: main company already has its pipeline from
        # the module seed data, so this must return (not duplicate) stages.
        cls.stages = cls.env['unicore.admission.stage']._ensure_default_stages(
            cls.company)

    def _applicant_vals(self, **overrides):
        vals = {
            'name': 'Ravi Kumar',
            'email': 'ravi.kumar@example.com',
            'mobile': '9122222222',
            'gender': 'male',
            'date_of_birth': date(2006, 2, 20),
            'cycle_id': self.cycle.id,
            'campus_id': self.campus.id,
            'program_id': self.program.id,
            'company_id': self.company.id,
        }
        vals.update(overrides)
        return vals

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def test_01_default_pipeline_seeded_for_main_company(self):
        """Main company has exactly the 13 default stages, ordered."""
        stages = self.env['unicore.admission.stage'].search(
            [('company_id', '=', self.company.id)], order='sequence, id')
        self.assertEqual(len(stages), 13)
        got = [(s.name, s.sequence, s.state) for s in stages]
        self.assertEqual(got, EXPECTED)

    def test_02_ensure_default_stages_is_idempotent(self):
        """Re-seeding an existing pipeline returns it without duplicating."""
        before = self.env['unicore.admission.stage'].search_count(
            [('company_id', '=', self.company.id)])
        again = self.env['unicore.admission.stage']._ensure_default_stages(
            self.company)
        after = self.env['unicore.admission.stage'].search_count(
            [('company_id', '=', self.company.id)])
        self.assertEqual(before, after)
        self.assertEqual(before, len(again))

    def test_03_new_company_gets_lazy_default_pipeline(self):
        """Creating a company auto-seeds its own 13-stage pipeline."""
        company_b = self.env['res.company'].create({'name': 'Stage Branch B'})
        stages_b = self.env['unicore.admission.stage'].sudo().search(
            [('company_id', '=', company_b.id)], order='sequence, id')
        self.assertEqual(len(stages_b), 13)
        # Each stage belongs to B, and mirrors the default mapping.
        for stage, expected in zip(stages_b, EXPECTED):
            self.assertEqual(stage.company_id, company_b)
            self.assertEqual(stage.name, expected[0])
            self.assertEqual(stage.state, expected[2])

    # ------------------------------------------------------------------
    # state <-> stage sync
    # ------------------------------------------------------------------

    def test_04_create_applicant_defaults_stage_from_state(self):
        """A new applicant's stage is derived from its initial state."""
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals(state='applied'))
        self.assertTrue(applicant.stage_id)
        self.assertEqual(applicant.stage_id.state, 'applied')
        self.assertEqual(applicant.stage_id.name, 'Applied')

        # Default state 'inquiry' also resolves.
        applicant2 = self.env['unicore.admission.applicant'].create(
            self._applicant_vals(email='ravi2@example.com'))
        self.assertEqual(applicant2.state, 'inquiry')
        self.assertEqual(applicant2.stage_id.state, 'inquiry')

    def test_05_stage_write_syncs_state_and_color(self):
        """Kanban drag: writing stage_id drives state and card color."""
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals())
        offer_stage = self.env['unicore.admission.stage']._get_stage_for_state(
            self.company.id, 'offer_sent')
        applicant.stage_id = offer_stage
        self.assertEqual(applicant.state, 'offer_sent')
        self.assertEqual(applicant.color, offer_stage.color)

    def test_06_state_write_syncs_stage(self):
        """Action buttons / API: writing state drives stage_id."""
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals())
        applicant.write({'state': 'shortlisted'})
        self.assertEqual(applicant.stage_id.state, 'shortlisted')
        self.assertEqual(applicant.stage_id.name, 'Shortlisted')

    # ------------------------------------------------------------------
    # Advance action
    # ------------------------------------------------------------------

    def test_07_advance_stage_moves_by_sequence(self):
        """Advance walks the pipeline in sequence order."""
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals())
        self.assertEqual(applicant.state, 'inquiry')
        applicant.action_advance_stage()
        self.assertEqual(applicant.state, 'applied')
        self.assertEqual(applicant.stage_id.name, 'Applied')
        # Two more advances to make sure it keeps moving.
        applicant.action_advance_stage()
        self.assertEqual(applicant.state, 'documents_pending')
        applicant.action_advance_stage()
        self.assertEqual(applicant.state, 'under_review')

    def test_08_advance_stage_raises_on_terminal(self):
        """Terminal stages cannot be advanced."""
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals())
        confirmed = self.env['unicore.admission.stage']._get_stage_for_state(
            self.company.id, 'confirmed')
        applicant.stage_id = confirmed
        self.assertEqual(applicant.state, 'confirmed')
        with self.assertRaises(UserError):
            applicant.action_advance_stage()

    def test_09_advance_stage_raises_on_last_stage(self):
        """The last non-terminal stage (Waitlisted) cannot be advanced."""
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals())
        waitlisted = self.env['unicore.admission.stage']._get_stage_for_state(
            self.company.id, 'waitlisted')
        applicant.stage_id = waitlisted
        self.assertEqual(applicant.state, 'waitlisted')
        with self.assertRaises(UserError):
            applicant.action_advance_stage()

    # ------------------------------------------------------------------
    # Isolation
    # ------------------------------------------------------------------

    def test_10_stages_are_per_company(self):
        """Stage resolution is scoped to the applicant's company."""
        company_b = self.env['res.company'].create({'name': 'Stage Branch C'})
        applied_a = self.env['unicore.admission.stage']._get_stage_for_state(
            self.company.id, 'applied')
        applied_b = self.env['unicore.admission.stage']._get_stage_for_state(
            company_b.id, 'applied')
        self.assertTrue(applied_a)
        self.assertTrue(applied_b)
        self.assertNotEqual(applied_a.id, applied_b.id)
        self.assertEqual(applied_a.company_id, self.company)
        self.assertEqual(applied_b.company_id, company_b)

        # A main-company applicant always resolves to main-company stages.
        applicant = self.env['unicore.admission.applicant'].create(
            self._applicant_vals())
        applicant.write({'state': 'fee_pending'})
        self.assertEqual(applicant.stage_id.company_id, self.company)
