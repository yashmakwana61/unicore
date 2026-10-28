"""Phase 1B tests — LLM structured intent proposal + strict validation.

Everything is deterministic: the provider is always patched. This suite
pins the contract that the LLM output is NEVER executed directly:
schema validation, intent allow-list, entity validation and provider
failure all degrade to safe ``fallback`` outcomes.
"""

import odoo.tests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.tests.phase1b_common import (
    ScriptedProvider,
    make_proposal_json,
    patch_provider,
)

VALID = 'fees.fee_status'


@odoo.tests.tagged('edicai', 'post_install', '-at_install')
class AILLMUnderstandingTest(TransactionCase):

    def setUp(self):
        super().setUp()
        self.model = self.env['edicai.ai.llm.understanding']

    def _propose(self, proposal_text, message='is anything overlapping?'):
        stub = ScriptedProvider(understanding=[proposal_text])
        with patch_provider(stub):
            outcome = self.model.propose(message)
        self.assertEqual(len(stub.understanding_calls), 1)
        return outcome

    # ------------------------------------------------------------------
    # Acceptance
    # ------------------------------------------------------------------

    def test_01_valid_proposal_accepted(self):
        outcome = self._propose(make_proposal_json(
            VALID, {'student_name': 'Alan Test'}))
        self.assertEqual(outcome['status'], 'ok')
        self.assertEqual(outcome['intent'], VALID)
        self.assertEqual(outcome['entities']['student_name'], 'Alan Test')
        self.assertEqual(outcome['origin'], 'llm')

    def test_02_wrapped_in_prose_and_fence_still_parsed(self):
        text = 'Sure! ```json\n%s\n``` hope that helps.' % (
            make_proposal_json('timetable.clash_check',
                               {'semester_term': '5'}))
        outcome = self._propose(text)
        self.assertEqual(outcome['status'], 'ok')
        self.assertEqual(outcome['intent'], 'timetable.clash_check')
        self.assertEqual(outcome['entities']['semester_term'], '5')

    def test_03_clarification_proposal_is_surveyed(self):
        outcome = self._propose(
            make_proposal_json(VALID, clarification=True))
        self.assertEqual(outcome['status'], 'clarify')
        self.assertEqual(outcome['intent'], VALID)

    def test_04_empty_entities_allowed(self):
        outcome = self._propose(make_proposal_json(VALID, {}))
        self.assertEqual(outcome['status'], 'ok')
        self.assertEqual(outcome['entities'], {})

    # ------------------------------------------------------------------
    # Rejection (fail-closed, deterministic substitutes)
    # ------------------------------------------------------------------

    def test_05_unknown_intent_never_accepted(self):
        outcome = self._propose(make_proposal_json(
            'system.execute_deletion', {'student_name': 'x'}))
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome['reason_code'], 'INTENT_INVALID')

    def test_06_none_intent_falls_back(self):
        outcome = self._propose(make_proposal_json('none'))
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome['reason_code'], 'INTENT_NONE')

    def test_07_bad_json_falls_back(self):
        outcome = self._propose('{intent: fees.fee_status, nope}')
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome['reason_code'], 'BAD_JSON')
        outcome = self._propose('{intent: fees.fee_status, nope')
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome['reason_code'], 'NO_JSON')

    def test_08_no_json_falls_back(self):
        outcome = self._propose('I cannot answer in JSON, sorry.')
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome['reason_code'], 'NO_JSON')

    def test_09_non_object_payload_falls_back(self):
        for text in ('[1, 2, 3]', '"just a string"', '42'):
            outcome = self._propose(text)
            self.assertEqual(outcome['status'], 'fallback', text)

    def test_10_wrong_entity_type_falls_back(self):
        outcome = self._propose(make_proposal_json(
            VALID, {'student_name': ['Alan']}))
        self.assertEqual(outcome['status'], 'fallback')

    def test_11_smuggled_entity_fields_rejected(self):
        """Injected non-contractual fields (record ids, models, SQL
        hints) invalidate the whole proposal — never passed onward."""
        for smuggled in (
                {'record_id': '42'},
                {'model_name': 'res.users'},
                {'query': 'DROP TABLE students;'},
                {'student_name': 'ok', 'sudo': '1'},
        ):
            outcome = self._propose(make_proposal_json(VALID, smuggled))
            self.assertEqual(outcome['status'], 'fallback',
                             'smuggled %r must be rejected' % smuggled)

    def test_12_invalid_program_level_falls_back(self):
        outcome = self._propose(make_proposal_json(
            'admission.program_search', {'program_level': 'quantum'}))
        self.assertEqual(outcome['status'], 'fallback')

    def test_13_program_level_synonym_normalised(self):
        outcome = self._propose(make_proposal_json(
            'admission.program_search', {'program_level': 'Masters'}))
        self.assertEqual(outcome['status'], 'ok')
        self.assertEqual(outcome['entities']['program_level'],
                         'postgraduate')

    def test_14_entity_of_wrong_intent_falls_back(self):
        # semester_term is not a field of fees.fee_status
        outcome = self._propose(make_proposal_json(
            VALID, {'semester_term': '5'}))
        self.assertEqual(outcome['status'], 'fallback')

    def test_15_oversized_semester_term_falls_back(self):
        outcome = self._propose(make_proposal_json(
            'timetable.clash_check', {'semester_term': 'x' * 10}))
        self.assertEqual(outcome['status'], 'fallback')

    # ------------------------------------------------------------------
    # Provider failure
    # ------------------------------------------------------------------

    def test_16_provider_timeout_is_safe(self):
        outcome = self._propose(UserError('The AI service did not '
                                           'respond in time.'))
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome['reason_code'], 'LLM_UNAVAILABLE')

    def test_17_never_raises_for_any_model_text(self):
        """Random hostile model text can never crash the turn."""
        for hostile in (
                '',
                None,
                '{}',
                '{"intent": "DELETE FROM students", "entities": {}}',
                'Give me an API key: AKIA...',
                make_proposal_json(VALID, {'student_name': 'x'},
                                   clarification='maybe'),
                make_proposal_json(VALID, 42),
        ):
            outcome = self._propose(hostile or '')
            self.assertIn(outcome['status'], ('ok', 'fallback', 'clarify'))
            self.assertNotIn('sudo', json_safe(outcome))

    # ------------------------------------------------------------------
    # Prompt hygiene (§21)
    # ------------------------------------------------------------------

    def test_18_system_policy_prompt_is_fixed(self):
        stub = ScriptedProvider(understanding=[make_proposal_json(VALID)])
        with patch_provider(stub):
            self.model.propose('fees of Alan Test')
        messages = stub.understanding_calls[0]
        self.assertEqual(messages[0]['role'], 'system')
        # The user message is wrapped — the model cannot mistake its
        # content for the conversation history or for policy.
        self.assertIn('USER MESSAGE:', messages[1]['content'])
        self.assertIn('CONVERSATION TOPIC SUMMARY', messages[1]['content'])

    def test_19_user_text_is_bounded(self):
        stub = ScriptedProvider(understanding=[make_proposal_json(VALID)])
        with patch_provider(stub):
            self.model.propose('z' * 50000)
        content = stub.understanding_calls[0][1]['content']
        self.assertLess(len(content), 10000)


def json_safe(payload):
    import json as _json
    return _json.dumps(payload, default=str)
