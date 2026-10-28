"""Prompt-11 — Manual QA Toolkit tests.

Proves the administrator-only utility:

* the group guard is real (fail-CLOSED for non-managers);
* persona creation is idempotent and uses ONLY existing groups;
* the ground-truth dataset is deterministic and repeatable
  (identical results on a second run; no duplicates);
* the live ground-truth report matches the documented truths;
* the test-state reset is strictly test-scoped (chat sessions /
  expired pending actions) and NEVER touches business records.
"""

import odoo.tests

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIQAToolkitHarness(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.toolkit = cls.env['edicai.ai.qa.toolkit']

    def test_01_non_manager_is_denied(self):
        """Fail-CLOSED: a plain staff user cannot drive the toolkit."""
        outsider = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Plain Staff',
                'login': 'qa_guard_probe',
                'email': 'guard@probe.test',
                'password': 'probe_pwd_1!',
                'group_ids': [(4, self.env.ref(
                    'edicai_ai.group_edicai_ai_user').id)],
            })
        with self.assertRaises(AccessError):
            self.toolkit.with_user(outsider).create_qa_personas()
        with self.assertRaises(AccessError):
            self.toolkit.with_user(outsider).create_qa_ground_truth_dataset()
        with self.assertRaises(AccessError):
            self.toolkit.with_user(outsider).reset_qa_test_state()

    def test_02_personas_existing_groups_only_idempotent(self):
        report = self.toolkit.create_qa_personas()
        self.assertTrue(report['created'])
        # idempotent: the second call creates nothing new
        report2 = self.toolkit.create_qa_personas()
        self.assertFalse(report2['created'])
        self.assertEqual(len(report2['existing']), len(report['created']))
        for login in report['created']:
            user = self.env['res.users'].search(
                [('login', '=', login)], limit=1)
            self.assertTrue(user, login)
            self.assertTrue(user.has_group('edicai_ai.group_edicai_ai_user'),
                            '%s must be able to reach the chatbot' % login)
        # persona catalogue lists the student security persona too
        logins = {row['login'] for row in self.toolkit.list_qa_personas()}
        self.assertIn('qa_student', logins)

    def test_03_dataset_deterministic_and_repeatable(self):
        first = self.toolkit.create_qa_ground_truth_dataset()
        self.assertTrue(first['short_student'])
        counts_1 = self.env['edicai.attendance.session'].search_count([])
        students_1 = self.env['edicai.student'].search_count(
            [('last_name', 'in', ('QA-001', 'QA-002'))])
        second = self.toolkit.create_qa_ground_truth_dataset()
        counts_2 = self.env['edicai.attendance.session'].search_count([])
        students_2 = self.env['edicai.student'].search_count(
            [('last_name', 'in', ('QA-001', 'QA-002'))])
        self.assertEqual(counts_1, counts_2)
        self.assertEqual(students_1, students_2)
        self.assertEqual(first['policy'], '80/85', second['policy'])

    def test_04_ground_truth_report_matches_documented_truths(self):
        self.toolkit.create_qa_ground_truth_dataset()
        truth = self.toolkit.qa_ground_truth_report()
        self.assertTrue(truth['exists'])
        self.assertEqual(truth['student_code'], 'TEST-STUDENT-001')
        # 3 present out of 4 held → exactly 75.0 %
        self.assertAlmostEqual(truth['attendance_pct'], 75.0)
        self.assertEqual(truth['min_required_pct'], 80.0)
        self.assertTrue(truth['shortage_expected'])
        # healthy student 4/4 → 100 %, never short
        self.assertAlmostEqual(truth['healthy_student_pct'], 100.0)
        # outstanding tuition recorded as ground truth
        self.assertGreater(truth['fee_outstanding'], 0.0)

    def test_05_reset_is_test_scoped_only(self):
        self.toolkit.create_qa_personas()
        persona = self.env['res.users'].search(
            [('login', '=', 'qa_faculty')], limit=1)
        with_user = self.env['edicai.ai.chat.session'].with_user(persona)
        session = with_user.create({})
        student_before = self.env['edicai.student'].search_count([])
        invoice_before = self.env['edicai.fee.invoice'].search_count([])
        report = self.toolkit.reset_qa_test_state()
        self.assertIn('archived', report['summary'])
        # chat session archived, NOT deleted
        self.assertFalse(session.active)
        # business records untouched
        self.assertEqual(
            self.env['edicai.student'].search_count([]), student_before)
        self.assertEqual(
            self.env['edicai.fee.invoice'].search_count([]),
            invoice_before)
