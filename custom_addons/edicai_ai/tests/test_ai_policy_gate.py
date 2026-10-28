"""Phase 1A tests — tool contracts + the application policy gate."""

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_policy import (
    CONVERSATIONAL_TOOL_SPEC,
)

GROUP_AI_USER = 'edicai_ai.group_edicai_ai_user'


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIConversationalContractTest(TransactionCase):
    """Contract surface for allow-listed conversational tools."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.policy = cls.env['edicai.ai.policy.gate']
        cls.tool_names = cls.policy.conversational_tool_names()

    def test_01_allowlist_is_exactly_the_conversational_set(self):
        """Phase 1A tools + Phase 13 aggregates + G1 floor + G2."""
        self.assertEqual(sorted(self.tool_names), sorted([
            'attendance.shortage_report',
            'attendance.shortage_summary',
            'admission.program_search',
            'admission.applicant_list',
            'admission.followup_list',
            'grievance.summary',
            'grading.grade_summary',
            'fees.fee_status',
            'fees.fee_summary',
            'timetable.clash_check',
            'timetable.view',
            'entity.list_models',
            'entity.describe',
            'entity.search',
            'entity.read',
            'entity.aggregate',
            'entity.create',
            'entity.update',
            'entity.execute',
            'entity.list_actions',
        ]))

    def test_02_contracts_are_read_only_or_staging_mutations(self):
        """G2/G3: the ONLY mutation contracts stage pending actions —
        they never write business data at tool time."""
        mutation = ('entity.create', 'entity.update', 'entity.execute')
        for name, spec in CONVERSATIONAL_TOOL_SPEC.items():
            if name in mutation:
                self.assertEqual(spec['risk_level'], 'MUTATION', name)
                self.assertIn('stages', spec['description'], name)
            else:
                self.assertEqual(spec['risk_level'], 'READ_ONLY', name)
            self.assertTrue(spec['conversational'], name)

    def test_03_every_contract_has_explicit_schema(self):
        for name, spec in CONVERSATIONAL_TOOL_SPEC.items():
            self.assertTrue(spec['description'], name)
            self.assertIn('input_schema', spec, name)
            self.assertIn('output_schema', spec, name)
            self.assertIn('existing_logic', spec, name)
            self.assertIn('authorization', spec, name)
            self.assertIn('error_mapping', spec, name)
            self.assertIn('citation', spec, name)
            groups = spec['authorization']['allowed_groups']
            self.assertEqual(groups, [GROUP_AI_USER], name)
            self.assertEqual(spec['authorization']['scope'], 'company')

    def test_04_every_contract_is_registered_in_central_registry(self):
        """The conversational tools self-register in PYTHON at module
        load (restart-resilient); the in-memory TOOL_REGISTRY must
        contain all five of them (kind=tool, correct handler model)."""
        from odoo.addons.edicai_ai.models.ai_tool_registry import (
            TOOL_REGISTRY,
        )
        for name in self.tool_names:
            self.assertIn(name, TOOL_REGISTRY,
                          'conversational tool %s not registered' % name)
            spec = TOOL_REGISTRY[name]
            self.assertEqual(spec.get('kind'), 'tool', name)
            self.assertIn(
                spec.get('model'),
                ('edicai.ai.conversational.tools', 'edicai.ai.entity.tools'),
                name)
            self.assertTrue(spec.get('allowed_groups'), name)

    def test_05_contracts_reference_existing_methods(self):
        env = self.env
        from odoo.addons.edicai_ai.models.ai_tool_registry import (
            TOOL_REGISTRY,
        )
        for name in self.tool_names:
            model = TOOL_REGISTRY[name]['model']
            method = TOOL_REGISTRY[name]['method']
            # The edicai_ai handler model is always installed; business
            # module dependencies are checked by TOOL_UNAVAILABLE
            # mapping at runtime, not here.
            if model == 'edicai.ai.conversational.tools':
                self.assertIn(model, env)
                self.assertTrue(getattr(env[model], method, None), name)


@odoo.tests.tagged('edicai', 'security', 'unit')
class AIPolicyGateTest(TransactionCase):
    """LLM-free authorization: the gate never trusts the message."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.policy = cls.env['edicai.ai.policy.gate']
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.allowed_user = Users.create({
            'name': 'Gate Allowed User',
            'login': 'gate_allowed_user',
            'email': 'gate_allowed@test.edu',
            'group_ids': [(4, cls.env.ref(GROUP_AI_USER).id)],
        })
        cls.denied_user = Users.create({
            'name': 'Gate Denied User',
            'login': 'gate_denied_user',
            'email': 'gate_denied@test.edu',
            'group_ids': [],
        })

    def test_01_allowed_holder_passes_for_all_tools(self):
        for name in self.policy.conversational_tool_names():
            decision = self.policy.check_access(
                name, user=self.allowed_user)
            self.assertTrue(decision['allowed'], name)
            self.assertEqual(decision['reason_code'], 'OK', name)

    def test_02_missing_group_is_denied(self):
        decision = self.policy.check_access(
            'fees.fee_status', user=self.denied_user)
        self.assertFalse(decision['allowed'])
        self.assertIn('GROUP_GATE', decision['reason_code'])

    def test_03_non_conversational_tool_is_denied(self):
        """Even a tool the registry know (Ask-Data) must fail the
        conversational gate — Phase 1A allow-list is separate."""
        decision = self.policy.check_access(
            'ask_data.enrollment', user=self.allowed_user)
        self.assertFalse(decision['allowed'])
        self.assertEqual(
            decision['reason_code'], 'NOT_IN_CONVERSATIONAL_ALLOWLIST')

    def test_04_empty_or_foreign_names_denied(self):
        for name in (False, '', 'unknown.tool', '"][" inject'):
            decision = self.policy.check_access(
                name, user=self.allowed_user)
            self.assertFalse(decision['allowed'], str(name))

    def test_05_anonymous_public_user_never_authorized(self):
        public_user = self.env.ref('base.public_user')
        decision = self.policy.check_access(
            'fees.fee_status', user=public_user)
        self.assertFalse(decision['allowed'])
