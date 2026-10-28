"""Eval harness: Library Buddy Copilot safety properties.

Cases:
  1. renew_eligibility changes nothing: the loan's due date,
     renewal count and state are identical before and after the call
     (the tool returns a draft action for human confirmation only).
  2. reserve_request duplicate raises: a second reservation for the
     same member + book is rejected (one active reservation rule).
"""

import odoo
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


@odoo.tests.tagged('edicai', 'unit')
class EdicaiLibraryCopilotEvalTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        cls.faculty = cls.env['edicai.faculty'].create({
            'name': 'Eval Library Faculty',
            'code': 'EVLFA',
            'company_id': cls.company.id,
        })
        cls.department = cls.env['edicai.department'].create({
            'name': 'Eval Library Dept',
            'code': 'EVLDEPT',
            'faculty_id': cls.faculty.id,
            'company_id': cls.company.id,
        })
        cls.program = cls.env['edicai.program'].create({
            'name': 'Eval Library Program',
            'code': 'EVL-BA',
            'program_type': 'undergraduate',
            'degree_title': 'Bachelor of Arts',
            'credit_system': 'credit_hours',
            'duration_years': 3,
            'total_credits': 90,
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })
        cls.campus = cls.env['edicai.campus'].create({
            'name': 'Eval Library Campus',
            'code': 'EVLCAMP',
            'company_id': cls.company.id,
        })
        cls.student_a = cls.env['edicai.student'].create({
            'name': 'EvalLib',
            'last_name': 'Member A',
            'gender': 'male',
            'date_of_birth': '2000-01-15',
            'email': 'evallib.memberA@example.com',
            'mobile': '+916666666661',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.student_b = cls.env['edicai.student'].create({
            'name': 'EvalLib',
            'last_name': 'Member B',
            'gender': 'female',
            'date_of_birth': '2001-02-20',
            'email': 'evallib.memberB@example.com',
            'mobile': '+916666666662',
            'company_id': cls.company.id,
            'campus_id': cls.campus.id,
            'program_id': cls.program.id,
            'batch_year': 2025,
            'admission_date': '2025-06-01',
        })
        cls.member_a = cls.env['edicai.library.member'].create({
            'member_type': 'student',
            'student_id': cls.student_a.id,
            'company_id': cls.company.id,
        })
        cls.member_b = cls.env['edicai.library.member'].create({
            'member_type': 'student',
            'student_id': cls.student_b.id,
            'company_id': cls.company.id,
        })
        cls.book = cls.env['edicai.library.book'].create({
            'title': 'Eval Copilot Test Book',
            'isbn': 'EVAL-978000000001',
            'company_id': cls.company.id,
        })
        cls.copy = cls.env['edicai.library.book.copy'].create({
            'book_id': cls.book.id,
            'company_id': cls.company.id,
        })
        # Single copy issued to member A -> zero available copies, so
        # member B may reserve (and only once).
        cls.issue = cls.env['edicai.library.issue'].create({
            'member_id': cls.member_a.id,
            'book_copy_id': cls.copy.id,
            'company_id': cls.company.id,
        })

    def setUp(self):
        super().setUp()
        self.copilot = self.env['library.ai.copilot']

    def test_01_renew_eligibility_changes_no_due_dates(self):
        issue = self.issue
        before = (issue.due_date, issue.renewal_count, issue.issue_state)
        result = self.copilot.renew_eligibility(issue.id)
        self.assertIn('eligible', result)
        self.assertIn('proposed_action', result)
        issue.invalidate_recordset()
        after = (issue.due_date, issue.renewal_count, issue.issue_state)
        self.assertEqual(before, after)

    def test_02_reserve_request_duplicate_raises(self):
        self.assertEqual(self.book.available_copies, 0)
        first = self.copilot.reserve_request(
            self.book.id, member_id=self.member_b.id)
        self.assertTrue(first['reservation_id'])
        with self.assertRaises(UserError):
            self.copilot.reserve_request(
                self.book.id, member_id=self.member_b.id)
