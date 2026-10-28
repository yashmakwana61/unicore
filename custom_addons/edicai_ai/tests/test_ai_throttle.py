"""Phase 0 tests — orchestrator feature flag (infrastructure only) and
the conversation-level throttle, including coexistence with the
existing tool-level rate limits."""

import uuid
from unittest import mock

import odoo.tests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_tool_registry import (
    TOOL_REGISTRY,
    register_tool,
)

GROUP_AI_USER = 'edicai_ai.group_edicai_ai_user'


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIOrchestratorFlagTest(TransactionCase):

    def test_01_flag_defaults_to_off(self):
        self.assertFalse(
            self.env['edicai.ai.config'].is_orchestrator_enabled())

    def test_02_flag_can_be_enabled_explicitly(self):
        cp = self.env['ir.config_parameter'].sudo()
        cp.set_param('edicai_ai.orchestrator_enabled', 'True')
        try:
            self.assertTrue(
                self.env['edicai.ai.config'].is_orchestrator_enabled())
        finally:
            cp.set_param('edicai_ai.orchestrator_enabled', 'False')
        self.assertFalse(
            self.env['edicai.ai.config'].is_orchestrator_enabled())


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIConversationThrottleTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_a = Users.create({
            'name': 'P0 Throttle User A',
            'login': 'edicai_p0_thr_a',
            'email': 'p0thr_a@example.com',
            'group_ids': [(4, cls.env.ref(GROUP_AI_USER).id)],
        })
        cls.user_b = Users.create({
            'name': 'P0 Throttle User B',
            'login': 'edicai_p0_thr_b',
            'email': 'p0thr_b@example.com',
            'group_ids': [(4, cls.env.ref(GROUP_AI_USER).id)],
        })
        cls.config = cls.env['edicai.ai.config']

    def setUp(self):
        super().setUp()
        cp = self.env['ir.config_parameter'].sudo()
        cp.set_param('edicai_ai.throttle_turns', '2')
        cp.set_param('edicai_ai.throttle_window_minutes', '5')

    def _session_for(self, user):
        return self.env['edicai.ai.chat.session'].with_user(user).create({
            'title': 'throttle-%s' % uuid.uuid4().hex[:6],
        })

    def _turn(self, session, user, role='user', content='x'):
        return self.env['edicai.ai.chat.message'].with_user(user).create({
            'session_id': session.id,
            'role': role,
            'content': content,
            'sequence': 10,
        })

    def test_03_under_limit_allowed(self):
        allowed, info = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertTrue(allowed)
        self.assertEqual(info['turns'], 2)
        self.assertEqual(info['window_minutes'], 5)
        self.assertEqual(info['used'], 0)

    def test_04_limit_blocks_further_turns(self):
        session = self._session_for(self.user_a)
        self._turn(session, self.user_a, content='first')
        allowed, info = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertTrue(allowed)
        self.assertEqual(info['used'], 1)
        self._turn(session, self.user_a, content='second')
        allowed, info = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertFalse(allowed)
        self.assertEqual(info['used'], 2)

    def test_05_throttle_is_per_user(self):
        mine = self._session_for(self.user_a)
        theirs = self._session_for(self.user_b)
        self._turn(theirs, self.user_b, content='b1')
        self._turn(theirs, self.user_b, content='b2')
        # User A's own quota is untouched by user B's turns.
        allowed, info = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertTrue(allowed)
        self.assertEqual(info['used'], 0)
        self._turn(mine, self.user_a, content='a1')
        allowed, _ = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertTrue(allowed)
        self._turn(mine, self.user_a, content='a2')
        allowed, _ = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertFalse(allowed)

    def test_06_assistant_messages_do_not_count(self):
        session = self._session_for(self.user_a)
        self._turn(session, self.user_a, role='assistant')
        allowed, info = self.config.check_conversation_throttle(
            user=self.user_a)
        self.assertTrue(allowed)
        self.assertEqual(info['used'], 0)

    def test_07_tool_level_rate_limit_still_coexists(self):
        """Conversation throttle layers on top of — never replaces —
        the registry's per-tool hourly rate limit."""
        name = 'edicai_p0_ratelimit_%s' % uuid.uuid4().hex[:10]
        self.addCleanup(TOOL_REGISTRY.pop, name, None)
        register_tool({
            'name': name,
            'kind': 'role',
            'description': 'p0 coexistence probe',
            'allowed_tools': [],
            'rate_limit_per_hour': 1,
        })
        self.env['edicai.ai.tool.registry'].execute_tool(name, {})
        with self.assertRaises(UserError):
            self.env['edicai.ai.tool.registry'].execute_tool(name, {})
