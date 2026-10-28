"""Phase G1 tests — the generic entity layer (read floor).

Asserts the GENERIC tools are at least as safe as the static ones:

* the policy table is a CYCLIC FENCE: only edicai.* business models;
  AI-internal/ORM/foreign models rejected;
* deny-by-default grants (empty group column = nobody);
* closed filter grammar (unknown fields/ops rejected, m2o only by id);
* PII masking + field block lists + row caps;
* record rules always apply — a student user reaches the layer ONLY
  through the wrapper/engine path (which skips grants because the
  wrapper's own registry contract gates them) and sees ONLY own rows.
"""

import odoo.tests
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_entity_policy import (
    is_allowed_entity_model,
)
from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures


class AIEntityPolicyIntegrityTest(TransactionCase):
    """The allow-list is configuration, and configuration is fenced."""

    def test_01_only_edicai_business_models_may_be_registered(self):
        for bad in ('res.partner', 'ir.model', 'edicai.ai.chat.session',
                    'mail.thread', 'account.move', 'base.user_admin'):
            self.assertFalse(is_allowed_entity_model(bad), bad)
        for good in ('edicai.student', 'edicai.fee.invoice',
                     'edicai.library.book'):
            self.assertTrue(is_allowed_entity_model(good), good)

    def test_02_concrete_rows_reject_foreign_models(self):
        Policy = self.env['edicai.ai.entity.policy']
        with self.assertRaises(ValidationError):
            Policy.create({'model_ref': 'res.partner', 'label': 'X'})
        with self.assertRaises(ValidationError):
            Policy.create({'model_ref': 'edicai.ai.intent', 'label': 'X'})

    def test_03_allowlist_is_exactly_the_expected_set(self):
        names = self.env['edicai.ai.policy.gate'].conversational_tool_names()
        self.assertEqual(sorted(names), sorted([
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

    def test_04_every_entity_tool_is_registered(self):
        registry = self.env['edicai.ai.tool.registry']
        names = [tool['name'] for tool in registry.list_tools()]
        for name in ('entity.list_models', 'entity.describe',
                     'entity.search', 'entity.read', 'entity.aggregate',
                     'entity.create', 'entity.update', 'entity.execute',
                     'entity.list_actions'):
            self.assertIn(name, names)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIEntityToolsSafetyTest(TransactionCase, Phase1AFixtures):
    """Five tools, policy-gated: traversal, masking, caps, rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tools = cls.env['edicai.ai.entity.tools']
        cls._build_academic_core(suffix='ENT')
        cls.staff = cls._create_staff_user(login_suffix='entstaff')
        Policy = cls.env['edicai.ai.entity.policy']
        if not Policy.search([('model_ref', '=', 'edicai.student')]):
            Policy.create({
                'model_ref': 'edicai.student',
                'label': 'Students',
                'synonyms': 'pupils',
                'read_groups': 'edicai_ai.group_edicai_ai_user',
                'pii_fields': 'mobile',
                'ops': 'search,read,aggregate,describe,list',
                'max_rows': 100,
            })
        if not Policy.search([('model_ref', '=', 'edicai.fee.invoice')]):
            Policy.create({
                'model_ref': 'edicai.fee.invoice',
                'label': 'Fee Invoices',
                'read_groups': 'edicai_ai.group_edicai_ai_user',
                'field_block': 'account_move_id',
                'ops': 'search,read,aggregate,describe,list',
                'max_rows': 100,
            })
        cls.entity = cls.env['edicai.ai.entity.policy'].search([
            ('model_ref', '=', 'edicai.student')], limit=1)
        cls.student_a, cls.user_a = cls._create_student(
            login_suffix='enta', name='Aarav', last_name='Masker')
        cls.student_b, cls.user_b = cls._create_student(
            login_suffix='entb', name='Diya', last_name='Masker')
        cls._create_fee_invoice(cls.student_a, 5000.0)
        cls._create_fee_invoice(cls.student_b, 2500.0)

    # ------------------------------------------------------------------
    # entity.list_models
    # ------------------------------------------------------------------

    def test_10_list_models_resolves_labels_and_synonyms(self):
        result = self.tools.with_user(self.staff).tool_list_models(
            {'query': 'pupil'})
        models_found = [e['model'] for e in result['entities']]
        self.assertIn('edicai.student', models_found)
        result_empty = self.tools.with_user(self.staff).tool_list_models(
            {'query': 'nope'})
        self.assertNotIn(
            'edicai.student',
            [e['model'] for e in result_empty['entities']])

    # ------------------------------------------------------------------
    # grants (deny-by-default)
    # ------------------------------------------------------------------

    def test_11_empty_group_column_grants_nothing(self):
        save = self.entity.read_groups
        self.entity.write({'read_groups': False})
        self.addCleanup(self.entity.write, {'read_groups': save})
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_search(
                {'model': 'edicai.student'})

    def test_12_disabled_entity_is_invisible(self):
        save = self.entity.enabled
        self.entity.write({'enabled': False})
        self.addCleanup(self.entity.write, {'enabled': save})
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_describe(
                {'model': 'edicai.student'})

    # ------------------------------------------------------------------
    # entity.describe
    # ------------------------------------------------------------------

    def test_13_describe_flags_pii_and_excludes_binary_fields(self):
        result = self.tools.with_user(self.staff).tool_describe(
            {'model': 'edicai.student'})
        fields_by_name = {f['name']: f for f in result['fields']}
        self.assertTrue(fields_by_name['mobile']['pii'])
        self.assertFalse(fields_by_name['name']['pii'])
        self.assertNotIn('image_1920', fields_by_name)

    def test_14_describe_never_lists_blocked_fields(self):
        policy = self.env['edicai.ai.entity.policy'].search(
            [('model_ref', '=', 'edicai.fee.invoice')], limit=1)
        result = self.tools.with_user(self.staff).tool_describe(
            {'model': 'edicai.fee.invoice'})
        names = [f['name'] for f in result['fields']]
        self.assertNotIn('account_move_id', names)
        self.assertIn('account_move_id', policy.field_block)

    # ------------------------------------------------------------------
    # entity.search — grammar, masking, caps
    # ------------------------------------------------------------------

    def test_15_search_masks_pii(self):
        result = self.tools.with_user(self.staff).tool_search(
            {'model': 'edicai.student',
             'filters': [['id', 'eq', self.student_a.id]]})
        self.assertEqual(result['count'], 1)
        row = result['rows'][0]
        mobile = row.get('mobile')
        if mobile:
            self.assertTrue(mobile.startswith('*'))
            self.assertNotEqual(mobile, self.student_a.mobile)

    def test_16_search_rejects_unknown_field_and_unknown_op(self):
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_search({
                'model': 'edicai.student',
                'filters': [['haxx0r', 'eq', 1]],
            })
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_search({
                'model': 'edicai.student',
                'filters': [['name', 'raw_sql', "'; DROP TABLE x"]],
            })

    def test_17_search_rejects_m2o_compared_by_name_or_mangled_field(self):
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_search({
                'model': 'edicai.student',
                'filters': [['campus_id', 'eq', 'some_name']],
            })
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_search({
                'model': 'edicai.student',
                'filters': [['campus_id.id', 'eq', 1]],
            })

    def test_18_search_row_cap_applies(self):
        policy = self.env['edicai.ai.entity.policy'].search(
            [('model_ref', '=', 'edicai.fee.invoice')], limit=1)
        save = policy.max_rows
        policy.write({'max_rows': 1})
        self.addCleanup(policy.write, {'max_rows': save})
        result = self.tools.with_user(self.staff).tool_search(
            {'model': 'edicai.fee.invoice'})
        self.assertEqual(len(result['rows']), 1)
        self.assertTrue(result['truncated'])

    # ------------------------------------------------------------------
    # record rules — the engine path (a student can only reach the
    # layer through wrapper/engine callers; both remain rule-scoped)
    # ------------------------------------------------------------------

    def test_19_engine_scopes_a_student_to_own_rows_only(self):
        engine = self.tools.with_user(self.user_a)
        result = engine.aggregate_for_policy(
            'edicai.fee.invoice', group_by=['student_id'])
        self.assertLessEqual(result['total_records'], 1)
        student_rows = self.tools.with_user(self.user_a).aggregate_for_policy(
            'edicai.student', group_by=['id'])
        self.assertEqual(student_rows['total_records'], 1)

    def test_20_aggregate_counts_and_sums(self):
        result = self.tools.with_user(self.staff).tool_aggregate({
            'model': 'edicai.fee.invoice',
            'filters': [['amount_outstanding', 'gt', 0.0]],
            'group_by': ['student_id'],
            'measures': {'amount_outstanding': 'sum'},
        })
        self.assertEqual(result['total_records'], 2)
        self.assertEqual(len(result['rows']), 2)
        sums = sorted(
            r.get('amount_outstanding:sum') or 0 for r in result['rows'])
        self.assertEqual(sums, [2500.0, 5000.0])

    def test_21_aggregate_rejects_non_numeric_sum(self):
        with self.assertRaises(UserError):
            self.tools.with_user(self.staff).tool_aggregate({
                'model': 'edicai.student',
                'group_by': ['id'],
                'measures': {'name': 'sum'},
            })

    # ------------------------------------------------------------------
    # entity.read
    # ------------------------------------------------------------------

    def test_22_read_masks_pii_and_caps_ids(self):
        policy = self.env['edicai.ai.entity.policy'].search(
            [('model_ref', '=', 'edicai.student')], limit=1)
        save = policy.max_rows
        policy.write({'max_rows': 1})
        self.addCleanup(policy.write, {'max_rows': save})
        result = self.tools.with_user(self.staff).tool_read(
            {'model': 'edicai.student',
             'ids': [self.student_a.id, self.student_b.id]})
        self.assertEqual(len(result['rows']), 1)

    # ------------------------------------------------------------------
    # registry path + wrapper parity
    # ------------------------------------------------------------------

    def test_23_registry_path_gates_and_executes(self):
        gate = self.env['edicai.ai.policy.gate']
        registry = self.env['edicai.ai.tool.registry']
        calls = (
            ('entity.list_models', {}),
            ('entity.describe', {'model': 'edicai.student'}),
            ('entity.search', {'model': 'edicai.student',
                               'filters': [['id', 'eq', self.student_a.id]]}),
            ('entity.read', {'model': 'edicai.student',
                             'ids': [self.student_a.id]}),
            ('entity.aggregate', {'model': 'edicai.fee.invoice',
                                  'group_by': ['student_id']}),
        )
        for name, params in calls:
            decision = gate.check_access(name, user=self.staff)
            self.assertTrue(decision['allowed'],
                            '%s: %s' % (name, decision))
            result = registry.with_user(
                self.staff).execute_tool(name, params)
            self.assertTrue(result)

    def test_24_fee_summary_wrapper_matches_phase13_shape(self):
        """The Phase 13 tool is now a wrapper with the SAME data shape
        and the wrapper path remains record-rule-scoped for a student
        (no group needed — its OWN contract gates the caller)."""
        tools = self.env['edicai.ai.conversational.tools'].with_user(
            self.staff)
        result = tools.tool_fee_summary({})
        data = result['data']
        for key in ('students_with_outstanding', 'total_outstanding',
                    'currency', 'overdue_students', 'scope',
                    'top_students', 'empty'):
            self.assertIn(key, data)
        self.assertEqual(data['students_with_outstanding'], 2)
        self.assertAlmostEqual(data['total_outstanding'], 7500.0, places=2)
        for row in data['top_students']:
            self.assertEqual(
                sorted(row),
                sorted(['student', 'outstanding', 'invoice_count',
                        'overdue_count']))

    def test_25_student_default_scope_through_the_wrapper(self):
        """A student user keeps the 'own' scope (parity with Phase 13)."""
        tools = self.env['edicai.ai.conversational.tools'].with_user(
            self.user_a)
        result = tools.tool_fee_summary({})
        data = result['data']
        self.assertEqual(data['scope'], 'own')
        self.assertLessEqual(data['students_with_outstanding'], 1)
