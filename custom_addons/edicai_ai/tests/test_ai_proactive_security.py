"""Phase 5 — SECURITY tests for the proactive slice (§23).

* insight rows are per-user: nobody can read or mutate another
  user's insight (record rules, no sudo);
* insights are company-scoped — no cross-institution visibility;
* unauthorized users get NOTHING, even when evidence exists;
* the LLM advisory can never select or introduce records;
* the slice contains no sudo anywhere (static source assertion);
* record visibility is the repository's own record rules: a faculty
  user's detection is a strict SUBSET of the registrar's.
"""

import inspect

import odoo
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models import ai_proactive as slice_module
from odoo.addons.edicai_ai.tests.phase5_common import (
    Phase5Fixtures,
)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIProactiveSecurityHarness(TransactionCase, Phase5Fixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_proactive_core(suffix='PQJ')
        cls._build_company2_chain()
        cls.s_short = cls._student_af('qja', 'Sameer', short=True,
                                      own=True)
        cls.s_short_b = cls._student_af(
            'qjc', 'Anaya', short=True,
            entry=cls.timetable_entry_b, offering=cls.offering_b)
        cls.s_ok, _usr = cls._create_student('qjb', name='Nikhil')
        cls._make_present(cls.s_ok, cls.timetable_entry)
        # Registrar A gets a surfaced insight.
        cls.session_a = cls._chat_session(cls.p5_registrar,
                                          title='P5 sec A')
        out = cls.env['edicai.ai.proactive'].with_user(
            cls.p5_registrar).handle_turn('good morning',
                                          cls.session_a)
        if not out:
            raise AssertionError('registrar surface failed')
        row = cls.env['edicai.ai.proactive.insight'].with_user(
            cls.p5_registrar)._row_for(
            cls.p5_registrar.id, cls.company.id)
        if not row:
            raise AssertionError('registrar insight row missing')
        cls.registrar_row_id = row.id

    def _insight_for(self, user):
        return self.env['edicai.ai.proactive.insight'].with_user(user)

    def _router_for(self, user, company=None):
        router = self.env['edicai.ai.proactive'].with_user(user)
        if company is not None:
            router = router.with_company(company)
        return router

    # ------------------------------------------------------------------
    # per-user isolation of the insight rows
    # ------------------------------------------------------------------

    def test_01_other_users_cannot_see_or_touch_the_row(self):
        self.assertTrue(self.registrar_row_id)
        faculty_rows = self._insight_for(self.p5_faculty)
        self.assertFalse(faculty_rows._row_for(
            self.p5_faculty.id, self.company.id))
        self.assertFalse(faculty_rows.search([]))
        with self.assertRaises(AccessError):
            faculty_rows.browse(self.registrar_row_id).write({
                'severity': 'low'})

    def test_02_manager_reads_but_never_writes(self):
        manager_rows = self._insight_for(self.p5_manager)
        row = manager_rows.browse(self.registrar_row_id)
        self.assertTrue(row)
        self.assertEqual(row.user_id.id, self.p5_registrar.id)
        with self.assertRaises(AccessError):
            manager_rows.browse(self.registrar_row_id).write({
                'status': 'dismissed'})

    # ------------------------------------------------------------------
    # company isolation
    # ------------------------------------------------------------------

    def test_03_cross_company_scope(self):
        """A user anchored in the second institution sees nothing of
        the first institution's insight; their own surface creates a
        separate company-2 row."""
        admin2_rows = self._insight_for(self.p5_admin2)
        self.assertFalse(admin2_rows._row_for(
            self.p5_admin2.id, self.q2_company.id))
        self.assertFalse(admin2_rows.search([
            ('company_id', '=', self.company.id)]))
        session2 = self._chat_session(
            self.p5_admin2, title='P5 sec C')
        out = self._router_for(
            self.p5_admin2, company=self.q2_company).handle_turn(
            'good morning', session2)
        self.assertTrue(out)
        row2 = admin2_rows._row_for(
            self.p5_admin2.id, self.q2_company.id)
        self.assertTrue(row2)
        self.assertEqual(row2.company_id.id, self.q2_company.id)
        # company-2 policy is NOT eligibility-linked → MEDIUM.
        self.assertEqual(row2.severity, 'medium')

    # ------------------------------------------------------------------
    # group gate + record-rule scoping
    # ------------------------------------------------------------------

    def test_04_unauthorized_users_get_nothing(self):
        user = self.p5_bystander
        session = self.env['edicai.ai.chat.session'].with_user(
            user).create({'title': 'P5 sec none'})
        self.assertIsNone(
            self._router_for(user).handle_turn('good morning',
                                               session))
        self.assertFalse(self._insight_for(user)._row_for(
            user.id, self.company.id))
        self.assertIsNone(
            self._router_for(user).detect_signal(user=user))

    def test_05_no_beyond_own_visibility(self):
        """The AI adds NOTHING to the user's own ORM visibility: the
        detector's exact evidence equals what the same user reads
        directly under the repository's record rules (union of the
        internal-user company rule with role rules — the module's own
        semantics)."""
        for user in (self.p5_faculty, self.p5_registrar):
            direct = self.env['edicai.attendance.record'].with_user(
                user).search([('shortage_alert', '=', True)])
            # the detector's documented qualification: evidence needs
            # at least one HELD session (0% with nothing marked is
            # not a review-worthy situation)
            direct_rows = [
                r for r in direct if r.total_sessions_held > 0]
            direct_pairs = {(r.student_id.id,
                             r.course_offering_id.id or 0)
                            for r in direct_rows}
            detected = self._router_for(user).detect_signal()
            signal_pairs = {
                (r['student_id'], r['offering_id'])
                for r in detected['rows']}
            self.assertEqual(signal_pairs, direct_pairs)
            self.assertTrue(direct_pairs)

    # ------------------------------------------------------------------
    # LLM can never select/introduce records
    # ------------------------------------------------------------------

    def test_06_llm_cannot_select_or_introduce_records(self):
        self._set_ai_flag('edicai_ai.conversation_llm_enabled', 'True')
        from unittest.mock import patch
        hostile = ('{"flagged_pairs": 99, "student_ids": '
                   '[9999, 8888]}')
        session = self.env['edicai.ai.chat.session'].with_user(
            self.p5_registrar).create({'title': 'P5 hostile'})
        with patch(('odoo.addons.edicai_ai.models'
                    '.edicai_ai_provider.EdicaiAIProvider.chat'),
                   return_value=hostile):
            out = self._router_for(self.p5_registrar).handle_turn(
                'good morning', session)
        self.assertTrue(out)
        row = self._insight_for(self.p5_registrar)._row_for(
            self.p5_registrar.id, self.company.id)
        self.assertEqual(row.source_count, 2)
        pairs = {d['student_id'] for d in row.read_snapshot()}
        self.assertEqual(pairs, {self.s_short.id, self.s_short_b.id})
        self.assertNotIn('9999', row.evidence_json)
        self.assertNotIn('8888', row.evidence_json)

    # ------------------------------------------------------------------
    # static no-sudo assertion
    # ------------------------------------------------------------------

    def test_07_no_sudo_in_the_slice(self):
        source = inspect.getsource(slice_module)
        self.assertNotIn('.sudo()', source)
        self.assertNotIn('sudo()', source.replace('.sudo()', ''))
