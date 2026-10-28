"""Phase G4 — deterministic re-validation of LLM proposals.

The governing invariant: **the LLM can never widen policy**.  Every
``entity.search`` proposal is re-validated against

* the proposal schema (closed key set, bounded sizes/types), and
* the caller's real grants + the closed filter grammar (the SAME
  ``_compile_filter`` the execution path uses),

*before* it can reach the orchestrator.  Anything invalid invalidates the
WHOLE proposal (fallback, never repaired).

No provider is consulted here: these tests call the validators directly.
"""

import json

import odoo.tests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_intent import (
    INTENT_ENTITY_ACTIONS,
    INTENT_ENTITY_MODELS,
    INTENT_ENTITY_SEARCH,
)
from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIEntityProposalTest(TransactionCase, Phase1AFixtures):
    """Schema + grant + grammar re-validation of entity proposals."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_academic_core(suffix='PROP')
        cls.staff = cls._create_staff_user(login_suffix='prop')
        cls.understanding = cls.env[
            'edicai.ai.llm.understanding'].with_user(cls.staff)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate(self, entities):
        return self.understanding._validate_entity_search(entities)

    def _parse(self, intent, entities):
        return self.understanding._parse_proposal(json.dumps({
            'intent': intent,
            'entities': entities,
            'clarification_required': False,
        }))

    def _valid(self, **overrides):
        target = {
            'model': 'edicai.student',
            'filters': [['student_state', 'eq', 'admitted']],
            'fields': 'name,id',
            'order': '',
            'limit': 10,
        }
        target.update(overrides)
        return target

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_01_valid_proposal_is_normalized(self):
        clean, ok = self._validate(self._valid())
        self.assertTrue(ok)
        self.assertEqual(clean['model'], 'edicai.student')
        # The SYMBOLIC op is kept; execution compiles it a second time.
        self.assertEqual(clean['filters'], [
            ['student_state', 'eq', 'admitted']])
        self.assertEqual(clean['limit'], 10)

    def test_02_parse_accepts_a_valid_search_proposal(self):
        proposal = self._parse(INTENT_ENTITY_SEARCH, self._valid())
        self.assertEqual(proposal['status'], 'raw_ok')
        self.assertEqual(proposal['intent'], INTENT_ENTITY_SEARCH)
        self.assertEqual(
            proposal['entities']['model'], 'edicai.student')

    def test_03_limit_is_capped_but_never_raised(self):
        clean, ok = self._validate(self._valid(limit=25))
        self.assertTrue(ok)
        self.assertLessEqual(clean['limit'], 25)

    # ------------------------------------------------------------------
    # Model allow-list (deny-by-default)
    # ------------------------------------------------------------------

    def test_10_unknown_model_is_refused(self):
        _clean, ok = self._validate(self._valid(model='res.partner'))
        self.assertFalse(ok)

    def test_11_structurally_forbidden_families_are_refused(self):
        for model in ('ir.model', 'res.users', 'edicai.ai.audit.event',
                      'edicai.ai.entity.policy'):
            _clean, ok = self._validate(self._valid(model=model))
            self.assertFalse(ok, model)

    def test_12_execute_only_entity_is_not_searchable(self):
        """Student documents are execute-only by seed policy."""
        _clean, ok = self._validate(
            self._valid(model='edicai.student.document', fields='name'))
        self.assertFalse(ok)

    def test_13_uninstalled_or_garbage_model_is_refused(self):
        for model in ('no.such.model', '', None, 42):
            _clean, ok = self._validate(self._valid(model=model))
            self.assertFalse(ok, model)

    # ------------------------------------------------------------------
    # Closed filter grammar
    # ------------------------------------------------------------------

    def test_20_unknown_operator_is_refused(self):
        _clean, ok = self._validate(
            self._valid(filters=[['name', 'matches', 'x']]))
        self.assertFalse(ok)

    def test_21_sql_operator_smuggle_is_refused(self):
        for op in ('=', '!=', 'ilike or 1=1', 'in; drop'):
            _clean, ok = self._validate(
                self._valid(filters=[['name', op, 'x']]))
            self.assertFalse(ok, op)

    def test_22_unknown_field_is_refused(self):
        _clean, ok = self._validate(
            self._valid(filters=[['not_a_real_field', 'eq', 1]]))
        self.assertFalse(ok)

    def test_23_dotted_join_path_is_refused(self):
        _clean, ok = self._validate(
            self._valid(filters=[['partner_id.id', 'eq', 1]]))
        self.assertFalse(ok)

    def test_24_operator_family_is_enforced_per_field_type(self):
        # ``like`` is not valid on a selection field.
        _clean, ok = self._validate(
            self._valid(filters=[['student_state', 'like', 'adm']]))
        self.assertFalse(ok)

    def test_25_malformed_filter_entries_are_refused(self):
        for entry in (
                ['name', 'eq'],            # too short
                ['name', 'eq', 'x', 'y'],  # too long
                'name,eq,x',               # not a triple at all
                [(['name'], 'eq', 'x')],   # non-string field
        ):
            _clean, ok = self._validate(self._valid(filters=[entry]))
            self.assertFalse(ok, entry)

    def test_26_filter_value_types_are_bounded_scalars(self):
        for value in ({'a': 1}, [['nested']], object()):
            _clean, ok = self._validate(
                self._valid(filters=[['name', 'eq', value]]))
            self.assertFalse(ok, repr(value))

    def test_27_filter_count_is_capped(self):
        filters = [['name', 'ilike', 'x%d' % i] for i in range(9)]
        _clean, ok = self._validate(self._valid(filters=filters))
        self.assertFalse(ok)

    # ------------------------------------------------------------------
    # Schema integrity (no smuggling sideways)
    # ------------------------------------------------------------------

    def test_28_in_operator_accepts_a_bounded_list(self):
        clean, ok = self._validate(self._valid(
            filters=[['student_state', 'in', ['admitted', 'active']]]))
        self.assertTrue(ok, clean)
        self.assertEqual(clean['filters'][0][1], 'in')

    def test_29_in_operator_refuses_unbounded_or_nested_lists(self):
        for value in ([], ['x'] * 51, [['x']], ['x', {'y': 1}]):
            clean, ok = self._validate(self._valid(
                filters=[['student_state', 'in', value]]))
            self.assertFalse(ok, value)

    def test_30_extra_keys_are_refused(self):
        raw = self._valid()
        raw['domain'] = [['name', '=', 'x']]
        _clean, ok = self._validate(raw)
        self.assertFalse(ok)

    def test_31_mutation_style_keys_are_refused(self):
        for key in ('action', 'method', 'sudo', 'ids', 'values'):
            raw = self._valid()
            raw[key] = 'x'
            _clean, ok = self._validate(raw)
            self.assertFalse(ok, key)

    def test_32_limit_bounds_and_type(self):
        for limit in (0, -1, 201, True, '10', 10.5):
            _clean, ok = self._validate(self._valid(limit=limit))
            self.assertFalse(ok, limit)

    def test_33_discovery_intents_take_no_entities(self):
        for intent in (INTENT_ENTITY_MODELS, INTENT_ENTITY_ACTIONS):
            proposal = self._parse(intent, {'model': 'edicai.student'})
            self.assertEqual(proposal['status'], 'invalid', intent)
            proposal = self._parse(intent, {})
            self.assertEqual(proposal['status'], 'raw_ok', intent)

    def test_34_search_proposal_is_allow_listed(self):
        proposal = self._parse('entity.delete_everything', {})
        self.assertEqual(proposal['status'], 'invalid')

    def test_35_non_object_proposal_is_refused(self):
        for raw in ('', 'not json', '[1, 2, 3]', 'null'):
            self.assertEqual(
                self.understanding._parse_proposal(raw)['status'],
                'invalid', raw)

    # ------------------------------------------------------------------
    # Catalog is the LLM's ONLY menu
    # ------------------------------------------------------------------

    def test_40_catalog_lists_granted_models_only(self):
        catalog = self.understanding._render_entity_catalog()
        self.assertIn('edicai.student', catalog)
        self.assertIn('edicai.fee.invoice', catalog)
        for forbidden in ('res.partner', 'ir.model', 'res.users',
                          'edicai.ai.audit.event'):
            self.assertNotIn(forbidden, catalog)

    def test_41_execute_only_entity_is_hidden_from_the_catalog(self):
        """Documents have no read grant, so they are not offered."""
        catalog = self.understanding._render_entity_catalog()
        self.assertNotIn('edicai.student.document', catalog)

    # ------------------------------------------------------------------
    # Execution re-validates (never trusts the proposal)
    # ------------------------------------------------------------------

    def test_50_tool_search_compiles_symbolic_filters(self):
        tools = self.env['edicai.ai.entity.tools'].with_user(self.staff)
        data = tools.tool_search(self._valid())
        self.assertNotIn('error_code', data)
        self.assertEqual(data['model'], 'edicai.student')
        self.assertIn('rows', data)

    def test_51_tool_search_refuses_compiled_domains(self):
        """A pre-compiled domain must not bypass the closed grammar."""
        tools = self.env['edicai.ai.entity.tools'].with_user(self.staff)
        with self.assertRaises(UserError):
            tools.tool_search({
                'model': 'edicai.student',
                'filters': [('name', '=', 'x')],
                'fields': 'name',
                'limit': 5,
            })

    def test_52_tool_search_still_refuses_ungranted_model(self):
        tools = self.env['edicai.ai.entity.tools'].with_user(self.staff)
        with self.assertRaises(UserError):
            tools.tool_search({
                'model': 'res.partner',
                'filters': [],
                'fields': 'name',
                'limit': 5,
            })
