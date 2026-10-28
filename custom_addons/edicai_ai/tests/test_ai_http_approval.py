"""Phase 4 — HTTP lifecycle test over the REAL chatbot surface.

Covers the complete two-user approval boundary through actual
``POST /edicai_ai/chat/send`` requests:

    requester phrase → preview (nothing changed)
        → requester confirm → submitted + Approval required
        → approver lists pending approvals
        → approver approves → canonical execution → verification
        → duplicate approval replays honestly

The database state is asserted between turns through fresh COMMITTED
cursors (the HTTP requests run in their own processes/transactions).
"""

import odoo.tests
from odoo.tests.common import HttpCase

from odoo.addons.edicai_ai.tests.phase4_common import (
    FLAG_ACTION_WRITE,
    FLAG_ACTION_FOLLOWUP,
    FLAG_APPROVAL,
    FLAG_WORKFLOW,
    Phase4Fixtures,
)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIApprovalHttpHarness(HttpCase, Phase4Fixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_approval_core()
        cls._set_ai_flag('edicai_ai.orchestrator_enabled', 'True')
        cls.passwords = {
            cls.requester.login: 'staff_pwd_1!',
            cls.approver.login: 'staff_pwd_1!',
            cls.bystander.login: 'staff_pwd_1!',
        }

    @classmethod
    def tearDownClass(cls):
        for key in (FLAG_APPROVAL, FLAG_WORKFLOW,
                    FLAG_ACTION_FOLLOWUP, FLAG_ACTION_WRITE):
            cls.env['ir.config_parameter'].sudo().set_param(
                key, 'False')
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
        """Apply a callback through a REAL committed cursor."""
        from odoo import api

        registry = self.env.registry
        with registry.cursor() as cr:
            env = api.Environment(cr, api.SUPERUSER_ID, {})
            callback(env)
            cr.commit()

    def _request(self):
        return ('request a projector needed by tomorrow at the '
                'central campus reason: lab sessions')

    # ------------------------------------------------------------------
    # The complete real two-user flow
    # ------------------------------------------------------------------

    def test_01_full_approval_boundary_two_users(self):
        # (1) REQUESTER: phrase → preview; nothing changed yet.
        requester_session = self.env[
            'edicai.ai.chat.session'].sudo().search([
                ('user_id', '=', self.requester.id),
            ], limit=1)
        if not requester_session or requester_session.user_id.id != \
                self.requester.id:
            self._fresh_cursor(lambda env: env['edicai.ai.chat.session']
                               .create({'title': 'HTTP approval A',
                                        'user_id':
                                            self.requester.id}))
            requester_session = self.env[
                'edicai.ai.chat.session'].sudo().search([
                    ('user_id', '=', self.requester.id)], limit=1)
        preview = self._send(requester_session.id, self._request(),
                             self.requester.login)
        self.assertIn('Submit this asset request for approval?',
                      preview['reply'])
        self.assertIn('Nothing has been changed yet.',
                      preview['reply'])
        # Business layer untouched by a preview.
        self._fresh_cursor(lambda env: self.assertEqual(
            env['edicai.asset.request'].search_count([
                ('reason', '=', 'lab sessions')]), 0))
        # (2) REQUESTER: confirm → submitted; approval is NOT granted.
        confirmed = self._send(requester_session.id, 'confirm',
                               self.requester.login)
        self.assertIn('Approval required.', confirmed['reply'])
        self.assertIn('Status: Waiting for approval.',
                      confirmed['reply'])
        self.assertIn('Requested by: %s' % self.requester.name,
                      confirmed['reply'])
        self.assertIn('Asset request AR/', confirmed['reply'])
        # (3) Grounded state: request submitted, approver designated,
        #     approval row PENDING — stored server-side only.
        state = {}

        def _read_state(env):
            row = env['edicai.ai.pending.approval'].search([], limit=1)
            self.assertTrue(row)
            state['row_id'] = row.id
            state['ref'] = row.ref
            state['status'] = row.status
            state['request_name'] = row.request_name
            target = env['edicai.asset.request'].browse(
                row.request_res_id)
            state['target_state'] = target.state
            state['approver'] = target.approver_id.id

        self._fresh_cursor(_read_state)
        self.assertEqual(state['status'], 'pending')
        self.assertEqual(state['target_state'], 'submitted')
        self.assertTrue(state['ref'])
        # (4) APPROVER: another USER — lists the pending approvals.
        approver_session = self.env[
            'edicai.ai.chat.session'].sudo().search([
                ('user_id', '=', self.approver.id)], limit=1)
        if not approver_session or approver_session.user_id.id != \
                self.approver.id:
            self._fresh_cursor(lambda env: env['edicai.ai.chat.session']
                               .create({'title': 'HTTP approval B',
                                        'user_id': self.approver.id}))
            approver_session = self.env[
                'edicai.ai.chat.session'].sudo().search([
                    ('user_id', '=', self.approver.id)], limit=1)
        listing = self._send(approver_session.id,
                             'what approvals are waiting for me?',
                             self.approver.login)
        self.assertIn('Pending approvals (1)', listing['reply'])
        self.assertIn(state['ref'], listing['reply'])
        # (5) APPROVER: approves through the lane — canonical execute.
        approved = self._send(
            approver_session.id, 'approve %s' % state['ref'],
            self.approver.login)
        self.assertIn('has been approved', approved['reply'])
        self.assertIn('Approved by: %s' % self.approver.name,
                      approved['reply'])
        # (6) Verified business state — the exact approved operation.
        self._fresh_cursor(lambda env: self.assertEqual(
            env['edicai.asset.request'].search([
                ('name', '=', state['request_name'])],
                limit=1).state, 'approved'))
        self._fresh_cursor(lambda env: self.assertEqual(
            env['edicai.ai.pending.approval'].browse(
                state['row_id']).status, 'executed'))
        # (7) Duplicate approval → honest replay, no second execution.
        again = self._send(
            approver_session.id, 'approve %s' % state['ref'],
            self.approver.login)
        self.assertIn('Already done', again['reply'])
        self.assertIn(state['request_name'], again['reply'])

    # ------------------------------------------------------------------
    # Security probes over HTTP
    # ------------------------------------------------------------------

    def test_02_requester_cannot_self_approve_over_http(self):
        session = self._ensure_session(self.requester, 'HTTP self')
        self._send(session.id, self._request(),
                   self.requester.login)
        confirm = self._send(session.id, 'confirm',
                             self.requester.login)
        self.assertIn('Approval required.', confirm['reply'])
        row = {}

        def _grab(env):
            r = env['edicai.ai.pending.approval'].search([], limit=1)
            row['ref'] = r.ref

        self._fresh_cursor(_grab)
        bypass = self._send(session.id, 'approve %s' % row['ref'],
                            self.requester.login)
        self.assertIn('cannot approve or reject your own request',
                      bypass['reply'].lower())
        self._fresh_cursor(lambda env: self.assertEqual(
            env['edicai.ai.pending.approval'].search([], limit=1)
            .status, 'pending'))

    def test_03_bystander_denied_over_http(self):
        session = self._ensure_session(self.bystander,
                                       'HTTP bystander')
        denied = self._send(session.id, 'approve anything',
                            self.bystander.login)
        self.assertIn('⚠️', denied['reply'])

    def test_04_material_change_invalidates_over_http(self):
        requester_session = self._ensure_session(
            self.requester, 'HTTP material change requester')
        approver_session = self._ensure_session(
            self.approver, 'HTTP material change approver')
        self._send(requester_session.id, self._request(),
                   self.requester.login)
        submitted = self._send(requester_session.id, 'confirm',
                               self.requester.login)
        self.assertIn('Approval required.', submitted['reply'])
        row_info = {}

        def _find(env):
            row = env['edicai.ai.pending.approval'].search([
                ('session_id', '=', requester_session.id),
                ('status', '=', 'pending'),
            ], order='id desc', limit=1)
            row_info.update({'id': row.id, 'ref': row.ref,
                             'request_id': row.request_res_id})

        self._fresh_cursor(_find)
        self._fresh_cursor(lambda env: env['edicai.asset.request'].browse(
            row_info['request_id']).write({'reason': 'changed after submit'}))
        decision = self._send(
            approver_session.id, 'approve %s' % row_info['ref'],
            self.approver.login)
        self.assertIn('no longer valid because the request changed',
                      decision['reply'].lower())
        state = {}

        def _check(env):
            row = env['edicai.ai.pending.approval'].browse(row_info['id'])
            target = env['edicai.asset.request'].browse(
                row_info['request_id'])
            state.update({'approval': row.status, 'target': target.state})

        self._fresh_cursor(_check)
        self.assertEqual(state, {'approval': 'invalidated',
                                 'target': 'submitted'})

    def _ensure_session(self, user, title):
        session = self.env['edicai.ai.chat.session'].sudo().search([
            ('user_id', '=', user.id)], limit=1)
        if not session or session.user_id.id != user.id:
            self._fresh_cursor(
                lambda env: env['edicai.ai.chat.session'].create(
                    {'title': title, 'user_id': user.id}))
            session = self.env['edicai.ai.chat.session'].sudo().search(
                [('user_id', '=', user.id)], limit=1)
        return session
