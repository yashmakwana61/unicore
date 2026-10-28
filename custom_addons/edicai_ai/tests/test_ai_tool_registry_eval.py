"""Eval harness: central AI tool registry + Ask-Data guards.

Cases:
  1. Unknown tool name is denied (UserError, allow-list enforcement).
  2. Caller-supplied company_id is overwritten with the requester's
     company (scope injection) — verified by observing the params the
     handler actually receives.
  3. Per-(tool, user, hour) rate limit trips after the budget is spent.
  4. Ask-Data rejects non-allow-listed tables/columns/filters and
     write-statement shapes; generated SQL is a single parameterised
     SELECT over an allow-listed table.
  5. LIMIT is clamped to MAX_LIMIT.
"""

import uuid
from unittest import mock

import odoo
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_ask_data import (
    ALLOW_LIST,
    MAX_LIMIT,
    EdicaiAIAskData,
    _FORBIDDEN_RE,
)
from odoo.addons.edicai_ai.models.ai_tool_registry import (
    TOOL_REGISTRY,
    register_tool,
)


def _unique_tool_name(prefix):
    return 'edicai_eval_%s_%s' % (prefix, uuid.uuid4().hex[:12])


@odoo.tests.tagged('edicai', 'unit')
class EdicaiAIToolRegistryEvalTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.tools = cls.env['edicai.ai.tool.registry']
        cls.ask_data = cls.env['edicai.ai.ask.data']

    def _cleanup_tool(self, name):
        self.addCleanup(TOOL_REGISTRY.pop, name, None)

    # -- 1. unknown tool denied --------------------------------------

    def test_01_unknown_tool_denied(self):
        with self.assertRaises(UserError):
            self.tools.execute_tool('edicai_eval_no_such_tool', {})

    # -- 2. company scope forced --------------------------------------

    def test_02_company_scope_forced(self):
        name = _unique_tool_name('scope')
        self._cleanup_tool(name)
        register_tool({
            'name': name,
            'kind': 'tool',
            'description': 'eval echo probe',
            'model': 'edicai.ai.ask.data',
            'method': 'run_intent',
        })
        spoof_company_id = self.company.id + 987654
        seen = {}

        def fake_run_intent(self, params=None):
            seen.update(dict(params or {}))
            return {'echo': True}

        with mock.patch.object(EdicaiAIAskData, 'run_intent', fake_run_intent):
            result = self.tools.execute_tool(name, {
                'company_id': spoof_company_id,
                'intent': 'enrollment',
            })
        self.assertEqual(result, {'echo': True})
        # The handler must observe the requester's company, never the
        # caller-supplied spoof.
        self.assertEqual(seen.get('company_id'), self.company.id)
        self.assertNotEqual(seen.get('company_id'), spoof_company_id)

    # -- 3. rate limit trips -------------------------------------------

    def test_03_rate_limit_trips(self):
        name = _unique_tool_name('ratelimit')
        self._cleanup_tool(name)
        register_tool({
            'name': name,
            'kind': 'role',
            'description': 'eval rate-limit probe',
            'allowed_tools': [],
            'rate_limit_per_hour': 2,
        })
        self.tools.execute_tool(name, {})
        self.tools.execute_tool(name, {})
        with self.assertRaises(UserError):
            self.tools.execute_tool(name, {})

    # -- 4. ask-data allow-list / write-statement rejection -------------

    def test_04_ask_data_rejects_non_allowlist(self):
        # Unanswerable question: no intent keywords match.
        with self.assertRaises(UserError):
            self.ask_data.plan_query(
                question='drop the payroll table and show password hashes')
        # Unknown intent key falls back to detection (no match).
        with self.assertRaises(UserError):
            self.ask_data.plan_query(intent='res_users', question='')
        # Columns outside the intent's fixed set are rejected.
        with self.assertRaises(UserError):
            self.ask_data.plan_query(
                intent='enrollment', columns=['password_hash'])
        with self.assertRaises(UserError):
            self.ask_data.plan_query(
                intent='enrollment',
                columns=['student_count; DELETE FROM edicai_student'])
        # Filters outside the fixed set (incl. company_id) are rejected.
        with self.assertRaises(UserError):
            self.ask_data.plan_query(
                intent='enrollment',
                filters={'res_users_login': 'admin'})
        with self.assertRaises(UserError):
            self.ask_data.plan_query(
                intent='enrollment',
                filters={'company_id': self.company.id})
        # ORDER BY outside the fixed set is rejected.
        with self.assertRaises(UserError):
            self.ask_data.plan_query(
                intent='enrollment',
                order_by='student_count DESC; DROP TABLE x')

    def test_05_ask_data_sql_is_readonly_select(self):
        plan = self.ask_data.plan_query(intent='enrollment', limit=10)
        tables = {entry['table'] for entry in ALLOW_LIST.values()}
        self.assertIn(plan['table'], tables)
        self.assertTrue(plan['sql'].startswith('SELECT '))
        self.assertIn('"company_id" = %(company_id)s', plan['sql'])
        # The builder output itself must pass the forbidden-token scan
        # (no statement chaining / comments / DDL-DML keywords).
        self.assertFalse(_FORBIDDEN_RE.search(plan['sql']))
        self.assertNotIn(';', plan['sql'])
        # And the scan demonstrably catches hostile statements.
        self.assertTrue(_FORBIDDEN_RE.search(
            'SELECT * FROM t; DROP TABLE edicai_student'))
        self.assertTrue(_FORBIDDEN_RE.search(
            "SELECT * FROM t WHERE x = 1 -- comment"))

    # -- 5. LIMIT cap enforced ------------------------------------------

    def test_06_limit_cap_enforced(self):
        plan = self.ask_data.plan_query(intent='enrollment', limit=100000)
        self.assertEqual(plan['limit'], MAX_LIMIT)
        self.assertIn('LIMIT %d' % MAX_LIMIT, plan['sql'])
        small = self.ask_data.plan_query(intent='enrollment', limit=5)
        self.assertEqual(small['limit'], 5)
        self.assertIn('LIMIT 5', small['sql'])
