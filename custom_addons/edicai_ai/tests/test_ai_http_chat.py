"""Phase 1A — HTTP chat regression harness.

Real HTTP-level tests over the ACTUAL chatbot controller routes
(`/edicai_ai/chat/...`) using HttpCase — not ORM-only substitutes.

Covered (Prompt #04 §4 items 1–10):

1. authenticated user can access their own chat session/messages
2. authenticated user cannot access another user's session
3. foreign session behaves as RECORD_NOT_FOUND with an IDENTICAL safe
   payload to a nonexistent one (no existence oracle)
4. chat message creation stays isolated per user
5. feature flag OFF preserves the pre-Phase-1 provider chat behaviour
   (incl. sanitised provider errors)
6. rate limiting returns the sanitised RATE_LIMITED payload
7. audit events are produced for the real HTTP turns
8. ownership is enforced through the actual controller path
9. foreign delete_session cannot archive another user's session
10. no existence oracle distinguishing foreign vs nonexistent ids
Plus: feature flag ON serves the grounded orchestrator reply with its
source label — no sudo path anywhere.
"""

import json

import odoo.tests
from odoo.tests.common import HttpCase

from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures

FLAG_ORCHESTRATOR = 'edicai_ai.orchestrator_enabled'

_CHAT_RPC_FAILED = 'chat rpc request failed'


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIChatHttpHarness(HttpCase, Phase1AFixtures):
    """HTTP-level behaviour of the chatbot controller."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Flag = cls.env['ir.config_parameter'].sudo()
        cls._flag_param = Flag
        cls._flag_param.set_param(FLAG_ORCHESTRATOR, 'False')

        # Chat sessions require the internal AI-user group (student
        # logins are portal-only in this suite), so the HTTP isolation
        # flows run as STAFF users; the grounding flow names the fixture
        # student explicitly ("fee status of Dom Grounded").
        cls._build_academic_core(suffix='HTTP')
        cls.user_a = cls._create_staff_user(login_suffix='http_a')
        cls.user_b = cls._create_staff_user(login_suffix='http_b')
        cls.user_c = cls._create_staff_user(login_suffix='http_c')
        cls.user_staff = cls._create_staff_user(login_suffix='http_staff')
        cls.user_d_student, _portal_d = cls._create_student(
            login_suffix='http_d', name='Dom', last_name='Grounded')
        cls._create_fee_invoice(cls.user_d_student, 12500.0,
                                semester=cls.semester)

        cls.passwords = {
            cls.user_a.login: 'staff_pwd_1!',
            cls.user_b.login: 'staff_pwd_1!',
            cls.user_c.login: 'staff_pwd_1!',
            cls.user_staff.login: 'staff_pwd_1!',
        }

    @classmethod
    def tearDownClass(cls):
        cls._flag_param.set_param(FLAG_ORCHESTRATOR, 'False')
        super().tearDownClass()

    def _rpc(self, route, params, login=None):
        """One authenticated JSON-RPC call over the real controller."""
        if login:
            self.authenticate(login, self.passwords[login])
        response = self.url_open(
            route, json=self.build_rpc_payload(params))
        self.assertEqual(
            response.status_code, 200,
            'HTTP layer broke for route %s: %s' % (route, response.text))
        body = response.json()
        self.assertNotIn(
            'error', body,
            'unexpected jsonrpc error envelope for %s: %s'
            % (route, body))
        return body['result']

    def _new_session(self, login):
        result = self._rpc('/edicai_ai/chat/new_session', {}, login=login)
        self.assertIn('id', result)
        return result['id']

    # ------------------------------------------------------------------
    # 1 + 4 — own session access and message isolation
    # ------------------------------------------------------------------

    def test_01_owner_can_create_read_and_send(self):
        session_id = self._new_session(self.user_a.login)
        send = self._rpc('/edicai_ai/chat/send', {
            'session_id': session_id,
            'message': 'hello from A (flag off)',
        }, login=self.user_a.login)
        # Flag OFF: the legacy provider path runs; without a configured
        # API key it fails safely — the reply must be a SANITISED fixed
        # text (item 5), never a traceback or provider body.
        self.assertIsInstance(send, dict)
        self.assertIn('reply', send)
        self.assertTrue(send.get('error_code'))
        self.assertNotIn('Traceback', send['reply'])
        self.assertNotIn('api key', send['reply'].lower())
        messages = self._rpc('/edicai_ai/chat/messages', {
            'session_id': session_id,
        }, login=self.user_a.login)
        # The Phase 0 provider-error path persists the user turn only;
        # no assistant placeholder is written on failure.
        roles = [m['role'] for m in messages]
        self.assertEqual(roles, ['user'])
        self.assertEqual(messages[0]['content'],
                         'hello from A (flag off)')

    # ------------------------------------------------------------------
    # 2 + 3 + 10 — cross-user denial, identical safe payloads
    # ------------------------------------------------------------------

    def test_02_foreign_and_nonexistent_sessions_indistinguishable(self):
        session_a = self._new_session(self.user_a.login)
        foreign = self._rpc(
            '/edicai_ai/chat/send',
            {'session_id': session_a, 'message': 'foreign'},
            login=self.user_b.login)
        nonexistent = self._rpc(
            '/edicai_ai/chat/send',
            {'session_id': 999999999, 'message': 'nonexistent'},
            login=self.user_b.login)
        self.assertEqual(foreign.get('error_code'),
                         'RECORD_NOT_FOUND')
        self.assertEqual(
            (foreign.get('error'), foreign.get('error_code')),
            (nonexistent.get('error'), nonexistent.get('error_code')),
            'foreign and nonexistent ids must yield the SAME safe '
            'payload (no existence oracle)')

    def test_03_foreign_messages_denied_safely(self):
        """Phase 0 semantics: the messages route NEVER advertises
        existence — a foreign (or nonexistent) session returns the same
        empty list as a session with no messages, leaking nothing."""
        session_a = self._new_session(self.user_a.login)
        foreign = self._rpc('/edicai_ai/chat/messages', {
            'session_id': session_a,
        }, login=self.user_b.login)
        nonexistent = self._rpc('/edicai_ai/chat/messages', {
            'session_id': 999999999,
        }, login=self.user_b.login)
        self.assertEqual(foreign, [])
        self.assertEqual(nonexistent, [])

    # ------------------------------------------------------------------
    # 4 + 8 — isolation survives real HTTP writes
    # ------------------------------------------------------------------

    def test_04_messages_stay_isolated_per_user(self):
        session_a = self._new_session(self.user_a.login)
        session_b = self._new_session(self.user_b.login)
        self._rpc('/edicai_ai/chat/send', {
            'session_id': session_a,
            'message': 'A turn one',
        }, login=self.user_a.login)
        self._rpc('/edicai_ai/chat/send', {
            'session_id': session_b,
            'message': 'B turn one',
        }, login=self.user_b.login)
        messages_b = self._rpc('/edicai_ai/chat/messages', {
            'session_id': session_b,
        }, login=self.user_b.login)
        contents = [m['content'] for m in messages_b
                    if m['role'] == 'user']
        self.assertIn('B turn one', contents)
        for content in contents:
            self.assertNotIn('A turn', content)

    def test_05_foreign_delete_session_cannot_archive_owner(self):
        session_a = self._new_session(self.user_a.login)
        # B deletes A's session: the controller reports success-shaped
        # response (no oracle) but A's session must stay ACTIVE.
        self._rpc('/edicai_ai/chat/delete_session', {
            'session_id': session_a,
        }, login=self.user_b.login)
        still_active = self.env['edicai.ai.chat.session'].search_count([
            ('id', '=', session_a),
            ('active', '=', True),
        ])
        self.assertEqual(still_active, 1)
        # A keeps full access afterwards (ownership enforced in prod).
        messages = self._rpc('/edicai_ai/chat/messages', {
            'session_id': session_a,
        }, login=self.user_a.login)
        self.assertIsInstance(messages, list)

    # ------------------------------------------------------------------
    # Workspace sidebar (Claude-like history) — owner-only rename,
    # searchable session list, foreign sessions stay invisible.
    # ------------------------------------------------------------------

    def test_10_session_list_is_owner_scoped_and_searchable(self):
        session_a = self._new_session(self.user_a.login)
        self._rpc('/edicai_ai/chat/rename_session', {
            'session_id': session_a,
            'title': 'Edicai QA Ledger Review',
        }, login=self.user_a.login)
        sessions = self._rpc('/edicai_ai/chat/sessions', {}, login=self.user_a.login)
        titles = [s['title'] for s in sessions]
        self.assertIn('Edicai QA Ledger Review', titles)
        # the sidebar payload carries what the date grouping needs
        entry = next(s for s in sessions if s['id'] == session_a)
        self.assertTrue(entry.get('write_date'))
        # search narrows the list
        found = self._rpc('/edicai_ai/chat/sessions', {
            'query': 'Ledger',
        }, login=self.user_a.login)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['id'], session_a)
        # a foreign session never shows up in B's list
        sessions_b = self._rpc('/edicai_ai/chat/sessions', {}, login=self.user_b.login)
        self.assertNotIn(session_a, [s['id'] for s in sessions_b])

    def test_11_owner_can_rename_own_session(self):
        session_a = self._new_session(self.user_a.login)
        result = self._rpc('/edicai_ai/chat/rename_session', {
            'session_id': session_a,
            'title': 'Renamed conversation',
        }, login=self.user_a.login)
        self.assertTrue(result.get('success'))
        self.assertEqual(result['title'], 'Renamed conversation')
        session = self.env['edicai.ai.chat.session'].browse(session_a)
        self.assertEqual(session.title, 'Renamed conversation')

    def test_12_foreign_rename_cannot_touch_another_users_session(self):
        session_a = self._new_session(self.user_a.login)
        original = self.env['edicai.ai.chat.session'].browse(session_a).title
        # B renames A's session — the owner record rule makes it
        # invisible, so the title must NOT change.
        self._rpc('/edicai_ai/chat/rename_session', {
            'session_id': session_a,
            'title': 'Hijacked',
        }, login=self.user_b.login)
        self.assertEqual(
            self.env['edicai.ai.chat.session'].browse(session_a).title,
            original)

    def test_13_empty_rename_is_rejected(self):
        session_a = self._new_session(self.user_a.login)
        original = self.env['edicai.ai.chat.session'].browse(session_a).title
        response = self.url_open(
            '/edicai_ai/chat/rename_session',
            json=self.build_rpc_payload({
                'session_id': session_a,
                'title': '   ',
            }))
        body = response.json()
        # the standard SAFE error payload (no stack trace, no internals)
        result = body.get('result') or {}
        self.assertEqual(result.get('error_code'), 'VALIDATION_FAILED')
        self.assertTrue(result.get('error'))
        self.assertEqual(
            self.env['edicai.ai.chat.session'].browse(session_a).title,
            original)

    # ------------------------------------------------------------------
    # 6 — throttle on the real route (fresh user, fresh window)
    # ------------------------------------------------------------------

    def test_06_conversation_throttle_returns_sanitized_rate_limited(self):
        CP = self.env['ir.config_parameter'].sudo()
        CP.set_param('edicai_ai.throttle_turns', '1')
        CP.set_param('edicai_ai.throttle_window_minutes', '5')
        try:
            session_c = self._new_session(self.user_c.login)
            first = self._rpc('/edicai_ai/chat/send', {
                'session_id': session_c,
                'message': 'first turn',
            }, login=self.user_c.login)
            self.assertTrue(first.get('error_code'))  # provider error, fine
            second = self._rpc('/edicai_ai/chat/send', {
                'session_id': session_c,
                'message': 'second turn',
            }, login=self.user_c.login)
            self.assertEqual(second.get('error_code'), 'RATE_LIMITED')
            self.assertNotIn('Traceback', second.get('error') or '')
            # Third user turn must NOT be persisted (throttle pre-writes).
            # Only the first user turn exists — the provider error path
            # writes no assistant placeholder (Phase 0 behaviour).
            messages_c = self._rpc('/edicai_ai/chat/messages', {
                'session_id': session_c,
            }, login=self.user_c.login)
            self.assertEqual(
                [m['role'] for m in messages_c],
                ['user'])
        finally:
            CP.set_param('edicai_ai.throttle_turns', '30')
            CP.set_param('edicai_ai.throttle_window_minutes', '5')

    # ------------------------------------------------------------------
    # 7 — audit on real turns
    # ------------------------------------------------------------------

    def test_07_audit_events_written_for_http_turns(self):
        session_a = self._new_session(self.user_a.login)
        self._rpc('/edicai_ai/chat/send', {
            'session_id': session_a,
            'message': 'audit probe',
        }, login=self.user_a.login)
        Audit = self.env['edicai.ai.audit.event'].sudo()
        events = Audit.search([
            ('conversation_id', '=', session_a),
        ])
        event_types = set(events.mapped('event_type'))
        self.assertIn('CHAT_CREATED', event_types)
        self.assertIn('CHAT_MESSAGE_SENT', event_types)
        self.assertIn('AI_PROVIDER_ERROR', event_types)
        # No raw message content is ever persisted in the audit.
        for event in events:
            self.assertNotIn('audit probe', (event.detail or ''))
            self.assertNotIn('audit probe', json.dumps(
                event.metadata_json or {}))

    # ------------------------------------------------------------------
    # Flag ON — grounded orchestrator via real HTTP
    # ------------------------------------------------------------------

    def test_08_flag_on_serves_grounded_reply_with_source(self):
        self._flag_param.set_param(FLAG_ORCHESTRATOR, 'True')
        try:
            session_d = self._new_session(self.user_staff.login)
            send = self._rpc('/edicai_ai/chat/send', {
                'session_id': session_d,
                'message': 'fee status of Dom Grounded',
            }, login=self.user_staff.login)
            self.assertEqual(send.get('source'), 'Fee Status')
            self.assertIn('12,500', send.get('reply') or '')
            self.assertNotIn('Traceback', send.get('reply'))
            persisted = self._rpc('/edicai_ai/chat/messages', {
                'session_id': session_d,
            }, login=self.user_staff.login)
            assistant = [m for m in persisted if m['role'] == 'assistant']
            self.assertTrue(assistant)
            self.assertEqual(assistant[-1].get('source'), 'Fee Status')
            self.assertIn('12,500', assistant[-1]['content'])
            source_persisted = self.env['edicai.ai.chat.message'].search([
                ('session_id', '=', session_d),
                ('role', '=', 'assistant'),
            ])
            self.assertEqual(
                source_persisted.mapped('source_tool'), ['Fee Status'])
        finally:
            self._flag_param.set_param(FLAG_ORCHESTRATOR, 'False')

    def test_09_flag_on_unsupported_write_request_refused(self):
        self._flag_param.set_param(FLAG_ORCHESTRATOR, 'True')
        try:
            session = self._new_session(self.user_staff.login)
            result = self._rpc('/edicai_ai/chat/send', {
                'session_id': session,
                'message': 'Delete this student',
            }, login=self.user_staff.login)
            self.assertIn("I can't perform that action yet.",
                          result.get('reply') or '')
            # No tool source is attached to refusals.
            self.assertFalse(result.get('source'))
        finally:
            self._flag_param.set_param(FLAG_ORCHESTRATOR, 'False')
