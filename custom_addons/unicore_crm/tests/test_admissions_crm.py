import odoo
from datetime import date, timedelta
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'crm')
class UniCoreAdmissionsCrmTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'Test Faculty of Admissions',
            'code': 'TFA',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'Test Admissions Office',
            'code': 'TADM',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'Test B.A. Admissions',
            'code': 'TEST-BA',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'Test Admissions Campus',
            'code': 'TACAMP',
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
        cls.cycle = cls.env['unicore.admission.cycle'].create({
            'name': 'Test Cycle 2025',
            'code': 'TCYC25',
            'campus_id': cls.campus.id,
            'academic_year_id': cls.academic_year.id,
            'start_date': '2025-06-01',
            'end_date': '2025-08-31',
            'company_id': cls.company.id,
        })
        cls.env['unicore.admission.cycle.seat'].create({
            'cycle_id': cls.cycle.id,
            'program_id': cls.program.id,
            'total_seats': 50,
        })
        cls.cycle.action_activate()

        cls.applicant = cls.env['unicore.admission.applicant'].create({
            'name': 'Jane Applicant',
            'last_name': 'Doe',
            'email': 'jane.applicant@example.com',
            'mobile': '+911111111111',
            'gender': 'female',
            'date_of_birth': '2000-06-15',
            'cycle_id': cls.cycle.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'company_id': cls.company.id,
        })

    # -------------------- AUTO-CREATE --------------------

    def test_01_auto_create_lead(self):
        """Creating an applicant in 'inquiry' state auto-creates a lead."""
        lead = self.applicant.crm_lead_id
        self.assertTrue(lead, 'A CRM lead must be auto-created')
        self.assertEqual(lead.type, 'opportunity')
        self.assertEqual(lead.contact_name, 'Jane Applicant')
        self.assertEqual(lead.email_from, 'jane.applicant@example.com')
        self.assertEqual(lead.phone, '+911111111111')
        self.assertEqual(lead.applicant_id, self.applicant)
        self.assertEqual(lead.company_id, self.company)

    def test_02_lead_stage_matches_inquiry(self):
        """The lead's stage should reflect the 'inquiry' state."""
        lead = self.applicant.crm_lead_id
        stage = lead.stage_id
        self.assertEqual(stage.uni_admission_state, 'inquiry')
        self.assertIn('inquiry', stage.name.lower())

    def test_03_smart_button_action(self):
        """The smart button action opens the linked CRM lead."""
        action = self.applicant.action_view_crm_lead()
        self.assertEqual(action['res_model'], 'crm.lead')
        self.assertEqual(action['res_id'], self.applicant.crm_lead_id.id)
        self.assertEqual(action['view_mode'], 'form')

    # -------------------- APPLICANT → LEAD SYNC --------------------

    def test_04_state_change_syncs_lead_stage(self):
        """Changing the applicant state updates the lead stage."""
        lead = self.applicant.crm_lead_id
        self.applicant.write({'state': 'applied'})
        self.assertEqual(lead.stage_id.uni_admission_state, 'applied')

    def test_05_lead_stage_syncs_applicant_state(self):
        """Changing the lead stage in CRM updates the applicant state."""
        lead = self.applicant.crm_lead_id
        applied_stage = self.env['crm.stage'].search(
            [('uni_admission_state', '=', 'applied')], limit=1)
        self.assertTrue(applied_stage, 'Applied stage must exist')
        lead.write({'stage_id': applied_stage.id})
        self.assertEqual(self.applicant.state, 'applied')

    def test_06_no_infinite_loop_on_two_way_sync(self):
        """Two-way sync must not loop infinitely."""
        lead = self.applicant.crm_lead_id
        # Move applicant to under_review — lead stage should follow.
        self.applicant.write({'state': 'under_review'})
        self.assertEqual(lead.stage_id.uni_admission_state, 'under_review')
        # Move lead back to inquiry — applicant state should follow.
        inquiry_stage = self.env['crm.stage'].search(
            [('uni_admission_state', '=', 'inquiry')], limit=1)
        lead.write({'stage_id': inquiry_stage.id})
        self.assertEqual(self.applicant.state, 'inquiry')

    def test_07_sync_updates_existing_lead(self):
        """action_sync_to_crm updates an existing lead's fields."""
        self.applicant.email = 'updated.sync@test.com'
        self.applicant.action_sync_to_crm()
        self.assertEqual(
            self.applicant.crm_lead_id.email_from, 'updated.sync@test.com')

    def test_08_crm_lead_count(self):
        """crm_lead_count is 1 for an applicant with a linked lead."""
        self.assertEqual(self.applicant.crm_lead_count, 1)