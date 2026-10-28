"""Phase 5 — HTTP lifecycle test over the REAL chatbot surface.

Proves the proactive experience end-to-end through actual
``POST /edicai_ai/chat/send`` requests:

    eligible user turn → proactive surfaced (unrequested)
        → "why?" → grounded fresh evidence
        → "what should i do?" → advisory recommendation
        ... and NO business mutation anywhere ...

then the NEGATIVE case: an unauthorized user's turns never leak the
signal, and a disabled flag keeps the whole layer inert.
"""

import odoo.tests
from odoo.tests.common import HttpCase

from odoo.addons.edicai_ai.tests.phase5_common import (
    FLAG_PROACTIVE,
    Phase5Fixtures,
)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIProactiveHttpHarness(HttpCase, Phase5Fixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_proactive_core(suffix='PQH')
        cls._set_ai_flag(FLAG_PROACTIVE, 'True')
        cls.s_short = cls._student_af('qha', 'Sameer', short=True,
                                      own=True)
        cls.s_ok = cls._student_af('qhb', 'Nikhil', short=False,
                                   own=True)
        cls.s_short_b = cls._student_af(
            'qhc', 'Anaya', short=True,
            entry=cls.timetable_entry_b, offering=cls.offering_b)
        cls.passwords = {
            cls.p5_registrar.login: 'staff_pwd_1!',
            cls.p5_bystander.login: 'staff_pwd_1!',
        }

    @classmethod
    def tearDownClass(cls):
        cls._set_ai_flag(FLAG_PROACTIVE, 'False')
        super().tearDownClass()

    def _rpc(self, route, params, login=None):
        if login:
            self.authenticate(login, self.passwords[login])
        response = self.url_open(route,
                                 json=self.build_rpc_payload(params))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn('error', body)
        return body['result']

    def _send(self, session_id, message, login):
        return self._rpc('/edicai_ai/chat/send', {
            'session_id': session_id,
            'message': message,
        }, login=login)

    def _fresh_cursor(self, callback):
        from odoo import api
        registry = self.env.registry
        with registry.cursor() as cr:
            env = api.Environment(cr, api.SUPERUSER_ID, {})
            callback(env)
            cr.commit()

    def _states(self):
        """Full attendance-state fingerprints (committed view)."""
        fingerprint = {}

        def _collect(env):
            fingerprint['records'] = sorted(
                (r.id, r.status) for r in
                env['edicai.attendance.record'].search([]))
            fingerprint['sessions'] = sorted(
                (s.id, s.session_state) for s in
                env['edicai.attendance.session'].search([]))
            fingerprint['insights'] = [
                (row.id, row.user_id.id, row.company_id.id,
                 row.status, row.severity)
                for row in
                env['edicai.ai.proactive.insight'].search([])]

        self._fresh_cursor(_collect)
        return fingerprint

    def _session_for(self, user, title):
        holder = {}

        def _create(env):
            holder['id'] = env['edicai.ai.chat.session'] \
                .with_user(user).create({'title': title}).id

        self._fresh_cursor(_create)
        return holder['id']

    # ------------------------------------------------------------------
    # The real eligible-user flow
    # ------------------------------------------------------------------

    def test_01_proactive_http_lifecycle_no_mutation(self):
        before = self._states()
        session = self._session_for(
            self.p5_registrar, 'HTTP proactive A')
        # (1) A plain, unmatched turn surfaces the proactive notice —
        #     the user never asked for attendance anything.
        first = self._send(session, 'good morning',
                           self.p5_registrar.login)
        self.assertIn('I noticed something that may need your '
                      'attention.', first['reply'])
        self.assertIn('2 student/offering pair(s)', first['reply'])
        self.assertIn('Severity: HIGH', first['reply'])
        self.assertIn('Sameer P5Batch', first['reply'])
        self.assertIn('Anaya P5Batch', first['reply'])
        self.assertIn('advisory only', first['reply'])
        # (2) 'why?' → grounded, FRESH evidence.
        why = self._send(session, 'why?', self.p5_registrar.login)
        self.assertIn('Current evidence for the flagged pairs:',
                      why['reply'])
        self.assertIn('Sameer P5Batch', why['reply'])
        self.assertIn('50.0% attendance (minimum 75%', why['reply'])
        self.assertIn('I will not change any records', why['reply'])
        # (3) 'what should i do?' → advisory only.
        advice = self._send(session, 'what should i do?',
                            self.p5_registrar.login)
        self.assertIn('Recommended next step (advisory only',
                      advice['reply'])
        self.assertIn('I will not change any records',
                      advice['reply'])
        # (4) NO business mutation: all attendance fingerprints
        #     identical, and exactly ONE insight surfaced for the
        #     eligible user.
        after = self._states()
        self.assertEqual(after['records'], before['records'])
        self.assertEqual(after['sessions'], before['sessions'])
        mine = [row for row in after['insights']
                if row[1] == self.p5_registrar.id]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0][3], 'surfaced')
        self.assertEqual(mine[0][4], 'high')

    def test_04_cleared_evidence_resolves_over_http_and_why_stays_fresh(self):
        session = self._session_for(
            self.p5_registrar, 'HTTP proactive cleared evidence')
        first = self._send(session, 'good morning', self.p5_registrar.login)
        self.assertIn('Sameer P5Batch', first['reply'])

        # Cure both seeded attendance deficits through the canonical
        # session state machine, then ask why through the actual HTTP chat.
        def _cure(env):
            for student in (self.s_short, self.s_short_b):
                record = env['edicai.attendance.record'].with_user(
                    self.p5_admin).search([
                        ('student_id', '=', student.id),
                        ('status', '=', 'absent'),
                    ], order='id asc', limit=1)
                session_row = record.session_id.with_user(
                    self.p5_admin).with_context(
                        force_write_closed_session=True)
                session_row.action_reopen_session()
                record.with_user(self.p5_admin).write({'status': 'present'})
                session_row.action_close_session()

        self._fresh_cursor(_cure)
        why = self._send(session, 'why?', self.p5_registrar.login)
        self.assertIn('no longer holds', why['reply'].lower())
        self.assertNotIn('Sameer P5Batch', why['reply'])
        self.assertNotIn('Anaya P5Batch', why['reply'])

        result = {}
        self._fresh_cursor(lambda env: result.update({
            'status': env['edicai.ai.proactive.insight'].search([
                ('user_id', '=', self.p5_registrar.id),
                ('company_id', '=', self.company.id),
            ], limit=1).status,
            'audit_count': env['edicai.ai.audit.event'].search_count([
                ('event_type', '=', 'PROACTIVE_SIGNAL_RESOLVED'),
                ('user_id', '=', self.p5_registrar.id),
            ]),
        }))
        self.assertEqual(result['status'], 'resolved')
        self.assertGreaterEqual(result['audit_count'], 1)

        later = self._send(session, 'good morning again',
                           self.p5_registrar.login)
        self.assertNotIn('I noticed something', later['reply'])

    def test_02_unauthorized_user_never_leaked(self):
        session = self._session_for(
            self.p5_bystander, 'HTTP proactive B')
        reply = self._send(session, 'good morning',
                           self.p5_bystander.login)
        # no proactive content in ANY shape
        self.assertNotIn('I noticed something', reply['reply'])
        self.assertNotIn('Sameer P5Batch', reply['reply'])
        self.assertNotIn('Anaya P5Batch', reply['reply'])
        # no insight row for the unauthorized user at all
        after = self._states()
        self.assertTrue(
            all(row[1] != self.p5_bystander.id
                for row in after['insights']))

    def test_03_flag_off_disables_the_lane(self):
        self._set_ai_flag(FLAG_PROACTIVE, 'False')
        try:
            session = self._session_for(
                self.p5_registrar, 'HTTP proactive flagoff')
            reply = self._send(session, 'good morning',
                               self.p5_registrar.login)
            self.assertNotIn('I noticed something', reply['reply'])
        finally:
            self._set_ai_flag(FLAG_PROACTIVE, 'True')
