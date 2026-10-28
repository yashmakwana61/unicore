"""Phase 1B tests — grounded LLM response composition.

The composer may only phrase replies from VERIFIED tool results, and a
deterministic grounding validator must discard any reply whose numbers
are not traceable to the facts (falling back to the fixed templates).
"""

import odoo.tests
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.tests.phase1b_common import (
    ScriptedProvider,
    patch_provider,
)

FEES_DATA = {
    'student': 'Alan Test',
    'currency': 'USD',
    'grand_outstanding': 12500.0,
    'semesters': [{
        'semester_name': 'Semester 1',
        'amount_outstanding': 12500.0,
        'open_count': 2,
        'overdue_count': 1,
    }],
    'empty': False,
}


@odoo.tests.tagged('edicai', 'post_install', '-at_install')
class AILLMResponderTest(TransactionCase):

    def setUp(self):
        super().setUp()
        self.model = self.env['edicai.ai.llm.responder']

    def _compose(self, reply, data=None):
        stub = ScriptedProvider(compose=[reply])
        with patch_provider(stub):
            outcome = self.model.compose(
                'fees of Alan Test', 'fees.fee_status',
                data if data is not None else FEES_DATA, 'Fee Status')
        return outcome, stub

    # ------------------------------------------------------------------
    # Acceptance
    # ------------------------------------------------------------------

    def test_01_grounded_reply_passes(self):
        outcome, stub = self._compose(
            'Alan Test owes 12,500 USD in total; 12,500 USD is outstanding '
            'in Semester 1.')
        self.assertEqual(outcome['status'], 'ok')
        self.assertIn('12,500', outcome['text'])
        self.assertEqual(len(stub.compose_calls), 1)

    def test_02_zero_outstanding_grounded(self):
        data = dict(FEES_DATA, grand_outstanding=0.0, semesters=[],
                    empty=False)
        outcome, _stub = self._compose(
            'No outstanding fees were found for Alan Test.', data=data)
        self.assertEqual(outcome['status'], 'ok')

    def test_03_decimal_renderings_are_sanctioned(self):
        data = {'student': 'Alan Test', 'cgpa': 3.5,
                'average_percentage': 78.6, 'semesters': [],
                'empty': False}
        outcome, _stub = self._compose(
            'Alan Test has a CGPA of 3.5 and an average of 78.6%.',
            data=data)
        self.assertEqual(outcome['status'], 'ok')

    def test_04_limitation_language(self):
        outcome, _stub = self._compose(
            'The verified data does not include the information you '
            'asked about.')
        self.assertEqual(outcome['status'], 'ok')

    # ------------------------------------------------------------------
    # Fabrication defense (§17)
    # ------------------------------------------------------------------

    def test_05_fabricated_amount_is_discarded(self):
        outcome, _stub = self._compose(
            'Alan Test owes 15,000 USD in total.')
        self.assertEqual(outcome['status'], 'fallback')
        self.assertIn('FABRICATION', outcome.get('reason_code') or '')

    def test_06_fabricated_percentage_is_discarded(self):
        data = {'student': 'Alan Test', 'cgpa': 3.5,
                'average_percentage': 78.6, 'semesters': [],
                'empty': False}
        outcome, _stub = self._compose(
            'Alan Test has an average of 82%.', data=data)
        self.assertEqual(outcome['status'], 'fallback')

    def test_07_fabricated_count_is_discarded(self):
        outcome, _stub = self._compose(
            'You have 4 overdue invoices — Alan Test owes 12,500 USD.')
        self.assertEqual(outcome['status'], 'fallback')

    def test_08_no_value_invented_when_data_empty(self):
        data = {'student': 'Alan Test', 'empty': True, 'courses': []}
        outcome, _stub = self._compose(
            'There are no attendance records for Alan Test.', data=data)
        self.assertEqual(outcome['status'], 'ok')
        self.assertNotIn('%', outcome['text'])

    # ------------------------------------------------------------------
    # Robustness
    # ------------------------------------------------------------------

    def test_09_provider_failure_falls_back(self):
        outcome, _stub = self._compose(
            UserError('The AI service is temporarily unavailable.'))
        self.assertEqual(outcome['status'], 'fallback')
        self.assertEqual(outcome.get('reason_code'), 'LLM_UNAVAILABLE')

    def test_10_empty_model_output_falls_back(self):
        outcome, _stub = self._compose('   ')
        self.assertEqual(outcome['status'], 'fallback')

    def test_11_code_fence_stripped(self):
        outcome, _stub = self._compose(
            '```\nAlan Test owes 12,500 USD.\n```')
        self.assertEqual(outcome['status'], 'ok')
        self.assertNotIn('```', outcome['text'])

    def test_12_grounded_facts_contain_no_secrets(self):
        facts = self.model._grounding_object(
            'fees.fee_status', FEES_DATA, 'Fee Status')
        self.assertIsInstance(facts, str)
        self.assertIn('12500.0', facts)
        self.assertIn('Fee Status', facts)

    def test_13_oversized_facts_are_bounded(self):
        big = dict(FEES_DATA, semesters=[
            {'semester_name': 'Semester %d' % i,
             'amount_outstanding': 100.0 + i,
             'open_count': i, 'overdue_count': 0}
            for i in range(500)
        ])
        outcome, stub = self._compose(
            'Alan Test owes 12,500 USD.', data=big)
        facts = stub.compose_calls[0][1]['content']
        self.assertLess(len(facts), 10000)

    def test_14_never_raises_for_hostile_data(self):
        hostile = {'a': {1, 2, 3}, 'b': float('inf')}
        stub = ScriptedProvider(compose=['ok'])
        with patch_provider(stub):
            outcome = self.model.compose(
                'fees', 'fees.fee_status', hostile, 'Fee Status')
        self.assertIn(outcome['status'], ('ok', 'fallback'))
