"""Phase 1B tests — bounded session context model.

Covers: sanitisation (fail-closed), bounds, schema strictness,
pending clarification state and the not-authorization invariant
(context stores topics only; its keys can never grant anything).
"""

import json

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_context import (
    EMPTY_CONTEXT,
    MAX_STR,
    MAX_TURNS,
)


@odoo.tests.tagged('edicai', 'post_install', '-at_install')
class AIContextModelTest(TransactionCase):

    def setUp(self):
        super().setUp()
        self.model = self.env['edicai.ai.conversation.context']
        self.session = self.env['edicai.ai.chat.session'].create({
            'title': 'ctx-%s' % self.id,
        })

    # ------------------------------------------------------------------
    # Fail-closed loading
    # ------------------------------------------------------------------

    def test_01_empty_session_gives_empty_context(self):
        context = self.model.get(self.session)
        self.assertEqual(context['v'], EMPTY_CONTEXT['v'])
        self.assertEqual(context['turns'], [])
        self.assertFalse(context['pending'])

    def test_02_corrupted_json_fails_closed(self):
        self.session.write({'context_json': 'NOT JSON {{'})
        context = self.model.get(self.session)
        self.assertEqual(context['turns'], [])
        self.assertFalse(context['pending'])

    def test_03_unknown_schema_version_dropped(self):
        self.session.write({'context_json': json.dumps({'v': 99})})
        context = self.model.get(self.session)
        self.assertEqual(context['turns'], [])
        self.assertFalse(context['pending'])

    def test_04_invalid_turns_are_dropped(self):
        blob = json.dumps({
            'v': 1,
            'turns': [
                {'intent': 'not-an-intent', 'ok': True},        # not allow-listed? schema doesn't check list membership; ok stays
                {'intent': 'fees.fee_status', 'ok': 'yes'},    # ok not True -> dropped
                'garbage',                                      # non-dict -> stop
            ],
            'pending': {'kind': 'bogus-k', 'intent': 'fees.fee_status'},
        })
        self.session.write({'context_json': blob})
        context = self.model.get(self.session)
        # Only structurally valid turns survive (the first has a string
        # intent and ok=True at schema level).
        self.assertEqual(len(context['turns']), 1)
        self.assertFalse(context['pending'])  # invalid kind dropped

    # ------------------------------------------------------------------
    # Recording + bounds
    # ------------------------------------------------------------------

    def test_05_record_turn_persists_and_clears_pending(self):
        self.model.set_pending(
            self.session, 'fees.fee_status', 'student', question='Which?')
        self.assertTrue(self.model.get(self.session)['pending'])
        self.model.record_turn(
            self.session, 'fees.fee_status', 'Fee Status',
            student='Alan Test', ok=True)
        context = self.model.get(self.session)
        self.assertFalse(context['pending'])
        self.assertEqual(len(context['turns']), 1)
        turn = context['turns'][0]
        self.assertEqual(turn['intent'], 'fees.fee_status')
        self.assertEqual(turn['student'], 'Alan Test')
        self.assertTrue(turn['ok'])

    def test_06_turns_are_bounded(self):
        for index in range(MAX_TURNS + 4):
            self.model.record_turn(
                self.session, 'fees.fee_status', 'Fee Status',
                student='Student %d' % index, ok=True)
        context = self.model.get(self.session)
        self.assertEqual(len(context['turns']), MAX_TURNS)
        # Oldest dropped, newest kept.
        self.assertEqual(context['turns'][-1]['student'], 'Student %d'
                         % (MAX_TURNS + 3))

    def test_07_strings_are_trimmed(self):
        long_student = 'x' * (MAX_STR + 50)
        self.model.record_turn(
            self.session, 'fees.fee_status', 'Fee Status',
            student=long_student, ok=True)
        turn = self.model.get(self.session)['turns'][-1]
        self.assertEqual(len(turn['student']), MAX_STR)

    def test_08_json_blob_is_bounded(self):
        for index in range(200):
            self.model.record_turn(
                self.session, 'fees.fee_status', 'Fee Status',
                student='y' * MAX_STR, ok=True)
        blob = self.session.context_json or ''
        self.assertLessEqual(len(blob), 4000)

    # ------------------------------------------------------------------
    # Schema strictness (no content, no auth semantics)
    # ------------------------------------------------------------------

    def test_09_context_store_schema_keys_only(self):
        self.model.record_turn(
            self.session, 'fees.fee_status', 'Fee Status',
            student='Alan Test', semester=False, ok=True)
        blob = json.loads(self.session.context_json)
        self.assertEqual(set(blob.keys()), {'v', 'turns', 'pending'})
        turn = blob['turns'][-1]
        self.assertEqual(
            set(turn.keys()),
            {'intent', 'source', 'student', 'semester', 'ok'})

    def test_10_last_topic_and_pending_helpers(self):
        self.model.record_turn(
            self.session, 'grading.grade_summary', 'Grade Summary',
            student='Alan Test', ok=True)
        topic = self.model.last_topic(self.model.get(self.session))
        self.assertEqual(topic['intent'], 'grading.grade_summary')
        self.assertFalse(
            self.model.pending_topic(self.model.get(self.session)))

    def test_11_failed_turn_not_recorded_as_topic(self):
        self.model.record_turn(
            self.session, 'fees.fee_status', 'Fee Status', ok=False)
        self.assertFalse(self.model.last_topic(self.model.get(self.session)))

    def test_12_none_session_is_safe(self):
        self.model.record_turn(None, 'fees.fee_status', 'Fee Status')
        self.model.set_pending(None, 'fees.fee_status', 'student')
        self.model.clear_pending(None)
        context = self.model.get(None)
        self.assertEqual(context['turns'], [])

    def test_13_context_is_not_authorization(self):
        """The stored payload carries only topic display data — it can
        never encode a user, group, rule or permission."""
        self.model.record_turn(
            self.session, 'fees.fee_status', 'Fee Status',
            student='Alan Test', ok=True)
        blob = json.dumps(self.model.get(self.session))
        for forbidden in ('group', 'allowed', 'user_id', 'sudo',
                          'password', 'permission'):
            self.assertNotIn(forbidden, blob.lower())

    def test_14_structured_query_state_is_bounded_and_not_auth_state(self):
        self.assertTrue(self.model.set_query(self.session, {
            'intent': 'admission.program_search',
            'tool': 'admission.program_search',
            'domain': 'admission', 'operation': 'search',
            'scope': 'collection',
            'filters': {'program_query': 'B.Com', 'campus': 'Ahmedabad',
                        'ignored_domain': 'x'},
            'entities': {'program_query': 'B.Com'},
            'record_ids': [5, 6], 'signature': 'digest',
        }))
        query = self.model.get_query(self.session)
        self.assertEqual(query['filters'], {
            'program_query': 'B.Com', 'campus': 'Ahmedabad'})
        self.assertEqual(query['record_ids'], [5, 6])
        for forbidden in ('user_id', 'group', 'permission', 'allowed'):
            self.assertNotIn(forbidden, (self.session.query_state_json or '').lower())

    def test_15_expired_query_state_fails_closed(self):
        self.session.write({'query_state_json': json.dumps({
            'v': 1, 'intent': 'admission.program_search',
            'tool': 'admission.program_search', 'operation': 'search',
            'scope': 'collection', 'filters': {}, 'entities': {},
            'record_ids': [3], 'signature': 'old', 'expires_at': 1,
        })})
        self.assertFalse(self.model.get_query(self.session))
