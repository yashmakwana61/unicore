"""Phase 1 stub PRG-01: progression decisions stamp decided_by+date.

Copy to: custom_addons/edicai_progression/tests/test_progression_decision.py
Register in custom_addons/edicai_progression/tests/__init__.py.
Covers matrix: PRG-01.
"""
from odoo import fields, tests
from odoo.exceptions import ValidationError


@tests.tagged('edicai', 'edicai_phase1', 'integration', 'post_install', '-at_install')
class EdicaiProgressionDecisionTest(tests.common.SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        faculty = cls.env['edicai.faculty'].create({
            'name': 'Faculty of Arts', 'code': 'FAX',
            'company_id': cls.company.id})
        department = cls.env['edicai.department'].create({
            'name': 'History', 'code': 'HIX', 'faculty_id': faculty.id})
        program = cls.env['edicai.program'].create({
            'name': 'B.A History', 'code': 'BAX', 'degree_title': 'B.A',
            'program_type': 'undergraduate', 'credit_system': 'credit_hours',
            'total_credits': 120, 'duration_years': 3,
            'department_id': department.id, 'company_id': cls.company.id})
        campus = cls.env['edicai.campus'].create({
            'name': 'Main Campus', 'code': 'PRC', 'company_id': cls.company.id})
        cls.year = cls.env['edicai.academic.year'].create({
            'name': '2033-2034', 'code': 'PR33',
            'date_start': '2033-06-01', 'date_end': '2034-05-31',
            'year_type': 'term'})
        cls.student = cls.env['edicai.student'].create({
            'name': 'Prog', 'last_name': 'Student', 'email': 'prog@edicai.edu',
            'mobile': '9000000021', 'gender': 'male',
            'date_of_birth': '2005-03-03', 'campus_id': campus.id,
            'program_id': program.id, 'batch_year': '2026',
            'student_state': 'active'})

    def test_01_promote_stamps_actor_and_date(self):
        """PRG-01: promote stamps decided_by + decision_date."""
        record = self.env['edicai.progression.record'].create({
            'student_id': self.student.id, 'academic_year_id': self.year.id})
        self.assertEqual(record.decision, 'pending')
        record.action_promote()
        self.assertEqual(record.decision, 'promoted')
        self.assertTrue(record.decided_by)
        self.assertTrue(record.decision_date)

    def test_02_decision_requires_actor(self):
        """PRG-01 negative: decided state without actor/date rejected."""
        record = self.env['edicai.progression.record'].create({
            'student_id': self.student.id, 'academic_year_id': self.year.id})
        with self.assertRaises(ValidationError):
            record.write({'decision': 'dismissed'})
            record.flush_recordset()
