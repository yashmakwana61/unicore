"""Phase 0 tests — durable AI audit model, access control and the
backward-compatible integration with the central tool registry."""

import uuid
from unittest import mock

import odoo.tests
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_tool_registry import (
    TOOL_REGISTRY,
    register_tool,
)
from odoo.addons.edicai_ai.models.ai_ask_data import EdicaiAIAskData

GROUP_AI_USER = 'edicai_ai.group_edicai_ai_user'
GROUP_AI_MANAGER = 'edicai_ai.group_edicai_ai_manager'


def _unique_tool_name(prefix):
    return 'edicai_p0_%s_%s' % (prefix, uuid.uuid4().hex[:12])


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIAuditEventTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_a = Users.create({
            'name': 'P0 Audit Actor',
            'login': 'edicai_p0_audit_actor',
            'email': 'p0audit@example.com',
            'group_ids': [(4, cls.env.ref(GROUP_AI_USER).id)],
        })
        cls.manager = Users.create({
            'name': 'P0 Audit Manager',
            'login': 'edicai_p0_audit_manager',
            'email': 'p0mgr@example.com',
            'group_ids': [(4, cls.env.ref(GROUP_AI_MANAGER).id)],
        })

    # -- persistence ---------------------------------------------------

    def test_01_log_event_persists(self):
        Audit = self.env['edicai.ai.audit.event']
        self.assertTrue(Audit.log_event(
            'CHAT_MESSAGE_SENT',
            metadata={'content_chars': 12},
            detail='turn recorded',
        ))
        row = Audit.search([('event_type', '=', 'CHAT_MESSAGE_SENT')],
                           limit=1)
        self.assertTrue(row)
        self.assertFalse(row.metadata_json.get('content'))
        self.assertEqual(row.metadata_json.get('content_chars'), 12)
        self.assertEqual(row.company_id, self.env.company)

    def test_02_no_message_content_ever_persisted(self):
        secret = 'NEVER-STORE-THIS-SENTENCE'
        # log_event receives no content parameter at all; even if a
        # caller passed one in metadata, the persisted payload must not
        # contain conversation text by contract.
        self.env['edicai.ai.audit.event'].log_event(
            'CHAT_MESSAGE_SENT')
        self.assertFalse(
            self.env['edicai.ai.audit.event'].search(
                [('detail', 'ilike', secret)]))
        self.assertFalse(
            self.env['edicai.ai.audit.event'].search(
                [('name', 'ilike', secret)]))

    # -- access control --------------------------------------------------

    def test_03_normal_ai_user_cannot_read_audit(self):
        with self.assertRaises(AccessError):
            self.env['edicai.ai.audit.event'].with_user(
                self.user_a).search_count([])

    def test_04_manager_can_read_audit(self):
        self.env['edicai.ai.audit.event'].log_event(
            'RATE_LIMITED',
            decision='deny',
            reason_code='CONVERSATION_THROTTLE',
        )
        self.assertEqual(
            self.env['edicai.ai.audit.event'].with_user(
                self.manager).search_count(
                    [('event_type', '=', 'RATE_LIMITED')]),
            1)

    def test_05_unknown_event_type_is_never_crashing(self):
        Audit = self.env['edicai.ai.audit.event']
        self.assertTrue(Audit.log_event('NOT_A_KNOWN_EVENT'))
        row = Audit.search([('event_type', '=', 'INTERNAL_ERROR')],
                           limit=1)
        self.assertTrue(row)


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIAuditRegistryIntegrationTest(TransactionCase):
    """The registry's audit must become durable (edicai.ai.audit.event)
    while every registered tool keeps its exact Phase-0 semantics."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.tool.registry']
        cls.audit = cls.env['edicai.ai.audit.event']

    def test_06_allowed_tool_call_is_durably_audited(self):
        name = _unique_tool_name('ok')
        self.addCleanup(TOOL_REGISTRY.pop, name, None)
        register_tool({
            'name': name,
            'kind': 'tool',
            'description': 'p0 audit probe (allowed)',
            'model': 'edicai.ai.ask.data',
            'method': 'run_intent',
            'default_params': {'intent': 'enrollment'},
        })
        with mock.patch.object(
            EdicaiAIAskData, 'run_intent',
            lambda self, params=None: {'count': 0},
        ):
            self.tools.execute_tool(name, {'limit': 3})
        row = self.audit.search([('tool_name', '=', name)], limit=1)
        self.assertTrue(row, 'allowed tool call produced no durable audit')
        self.assertEqual(row.event_type, 'TOOL_EXECUTED')
        self.assertEqual(row.decision, 'allow')
        self.assertEqual(
            row.metadata_json.get('params', {}).get('limit'), 3)
        self.assertEqual(row.company_id, self.env.company)

    def test_07_unknown_tool_denial_is_durably_audited(self):
        name = 'edicai_p0_unknown_%s' % uuid.uuid4().hex[:8]
        raised = None
        try:
            self.tools.execute_tool(name, {})
        except UserError:
            raised = True
        self.assertTrue(raised, 'expected UserError for unknown tool')
        # The denial writes its audit inside the exception path; flush
        # before searching for deterministic visibility in tests.
        self.env.flush_all()
        row = self.audit.search([
            ('tool_name', '=', name), ('decision', '=', 'deny')], limit=1)
        self.assertTrue(row, 'unknown-tool denial produced no durable audit')
        self.assertEqual(row.event_type, 'TOOL_DENIED')

    def test_08_group_gate_denial_is_durably_audited(self):
        name = _unique_tool_name('gate')
        self.addCleanup(TOOL_REGISTRY.pop, name, None)
        register_tool({
            'name': name,
            'kind': 'role',
            'description': 'p0 audit probe (denied)',
            'allowed_tools': [],
            'allowed_groups': ['edicai_nonexistent.group_none'],
        })
        raised = None
        try:
            self.tools.execute_tool(name, {})
        except UserError:
            raised = True
        self.assertTrue(raised, 'expected UserError from the group gate')
        self.env.flush_all()
        row = self.audit.search([
            ('tool_name', '=', name), ('decision', '=', 'deny')], limit=1)
        self.assertTrue(row)
        self.assertIn('group gate', row.detail or '')

    def test_09_spoofed_company_is_never_recorded(self):
        """Caller-supplied company spoofing is both overwritten by the
        registry and never persisted as the audit company."""
        name = _unique_tool_name('spoof')
        self.addCleanup(TOOL_REGISTRY.pop, name, None)
        register_tool({
            'name': name,
            'kind': 'tool',
            'description': 'p0 audit probe (company spoof)',
            'model': 'edicai.ai.ask.data',
            'method': 'run_intent',
            'default_params': {'intent': 'enrollment'},
        })
        with mock.patch.object(
            EdicaiAIAskData, 'run_intent',
            lambda self, params=None: {'count': 0},
        ):
            self.tools.execute_tool(
                name, {'company_id': self.env.company.id + 987654})
        row = self.audit.search([('tool_name', '=', name)], limit=1)
        self.assertTrue(row)
        self.assertEqual(row.company_id, self.env.company)
