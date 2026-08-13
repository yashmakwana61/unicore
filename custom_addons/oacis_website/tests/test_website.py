
import odoo
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('unicore', 'website')
class UniCoreWebsiteTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['unicore.faculty'].create({
            'name': 'Test Faculty of Admissions Web',
            'code': 'TFAW',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['unicore.department'].create({
            'name': 'Test Admissions Web Office',
            'code': 'TAWO',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['unicore.program'].create({
            'name': 'Test B.A. Web',
            'code': 'TEST-BA-WEB',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 120,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['unicore.campus'].create({
            'name': 'Test Web Campus',
            'code': 'TWCAMP',
            'company_id': cls.company.id,
        })
        cls.academic_year = cls.env['unicore.academic.year'].create({
            'name': 'Test AY 2025-26 Web',
            'code': 'TAY2526W',
            'date_start': '2025-07-01',
            'date_end': '2026-06-30',
            'year_state': 'cancelled',
            'is_current': False,
            'company_id': cls.company.id,
        })
        cls.semester = cls.env['unicore.semester'].create({
            'name': 'Test ODD 2025-26 Web',
            'code': 'TODD-2526W',
            'semester_type': 'odd',
            'academic_year_id': cls.academic_year.id,
            'date_start': '2025-07-15',
            'date_end': '2025-11-30',
            'semester_state': 'ongoing',
            'company_id': cls.company.id,
        })

        cls.website = cls.env['website'].create({
            'name': 'Test Admissions Website',
            'domain': 'admissions.test.com',
            'unicore_admissions_page': True,
            'company_id': cls.company.id,
        })

        cls.livechat_channel = cls.env['im_livechat.channel'].create({
            'name': 'Admissions Live Chat',
            'unicore_admissions_channel': True,
            'company_id': cls.company.id,
        })

    # -------------------- WEBSITE --------------------

    def test_01_website_admissions_flag(self):
        """The admissions website should have the flag set."""
        self.assertTrue(self.website.unicore_admissions_page)

    def test_02_website_enquiry_count(self):
        """admissions_enquiry_count reflects linked leads."""
        lead = self.env['crm.lead'].create({
            'name': 'Web Enquiry',
            'type': 'opportunity',
            'website_enquiry': True,
            'website_page_url': '/admissions/enquire',
            'company_id': self.company.id,
        })
        self.website.invalidate_recordset()
        self.assertEqual(self.website.admissions_enquiry_count, 1)

    # -------------------- LIVECHAT --------------------

    def test_03_livechat_admissions_flag(self):
        """The admissions livechat channel should have the flag set."""
        self.assertTrue(self.livechat_channel.unicore_admissions_channel)

    # -------------------- CRM LEAD --------------------

    def test_04_website_enquiry_lead(self):
        """A website enquiry lead should have the flag set."""
        lead = self.env['crm.lead'].create({
            'name': 'Test Web Enquiry',
            'type': 'opportunity',
            'website_enquiry': True,
            'website_page_url': '/admissions/enquire',
            'company_id': self.company.id,
        })
        self.assertTrue(lead.website_enquiry)
        self.assertEqual(lead.website_page_url, '/admissions/enquire')

    def test_05_view_website_page_action(self):
        """Smart button action opens the website page."""
        lead = self.env['crm.lead'].create({
            'name': 'Test Web Page Action',
            'type': 'opportunity',
            'website_enquiry': True,
            'website_page_url': 'https://admissions.test.com/enquire',
            'company_id': self.company.id,
        })
        action = lead.action_view_website_page()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(
            action['url'], 'https://admissions.test.com/enquire')
        self.assertEqual(action['target'], 'new')

    def test_06_lead_without_website_url(self):
        """action_view_website_page raises UserError when no URL."""
        lead = self.env['crm.lead'].create({
            'name': 'Test No URL',
            'type': 'opportunity',
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError):
            lead.action_view_website_page()
