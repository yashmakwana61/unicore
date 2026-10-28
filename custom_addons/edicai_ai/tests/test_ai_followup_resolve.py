"""Phase 2B — follow-up schema, detection, date + applicant resolution.

Strict schema of ``admission.schedule_followup``; deterministic
detection; deterministic natural-language date/time resolution anchored
on Odoo's user-local ``today``; permission-aware applicant resolution.
"""

from datetime import timedelta

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_action_resolve import (
    missing_followup_fields,
    extract_followup_date_phrase,
    extract_followup_fields,
    is_followup_request,
    parse_followup_date,
    validate_followup_entities,
)
from odoo.addons.edicai_ai.tests.phase2b_common import Phase2BFixtures


@odoo.tests.tagged('edicai', 'security', '-at_install', 'post_install')
class TestFollowupSchema(TransactionCase, Phase2BFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_followup_core(suffix='FSC')

    def test_01_unknown_field_rejects_whole_proposal(self):
        clean, ok, invalid = validate_followup_entities({
            'applicant': 'Rahul Verma', 'date': 'tomorrow',
            'user_id': 5})
        self.assertFalse(ok)
        self.assertEqual(
            invalid, ['unknown_fields:user_id'])

    def test_02_length_limits_reject_without_trimming(self):
        clean, ok, invalid = validate_followup_entities({
            'applicant': 'x' * 121, 'date': 'tomorrow'})
        self.assertFalse(ok)
        self.assertIn('applicant', invalid)
        clean, ok, invalid = validate_followup_entities({
            'applicant': 'Rahul', 'date': 'tomorrow',
            'purpose': 'y' * 201})
        self.assertFalse(ok)
        self.assertIn('purpose', invalid)
        clean, ok, invalid = validate_followup_entities(
            {'applicant': 'Rahul Verma', 'date': 'tomorrow at 11 AM',
             'purpose': 'z' * 200})
        self.assertTrue(ok, invalid)

    def test_03_missing_fields_helper(self):
        self.assertEqual(
            missing_followup_fields({}), ['applicant', 'date'])
        self.assertEqual(
            missing_followup_fields({'applicant': 'Rahul'}),
            ['date'])
        self.assertEqual(
            missing_followup_fields(
            {'applicant': 'Rahul', 'date': 'tomorrow'}), [])

    def test_03a_impossible_explicit_date_is_not_kept_in_draft(self):
        clean, ok, invalid = validate_followup_entities({
            'applicant': 'Rahul Verma', 'date': '2026-02-30',
        })
        self.assertFalse(ok)
        self.assertIn('date', invalid)
        fields, _rest = extract_followup_fields(
            'applicant: Rahul Verma, when: 2026-02-30')
        self.assertNotIn('date', fields)

    def test_04_detection_literal_phrases(self):
        self.assertTrue(is_followup_request(
            'please schedule a follow-up with Rahul tomorrow'))
        self.assertTrue(is_followup_request(
            'set a follow up for the applicant on Friday'))
        self.assertTrue(is_followup_request(
            'remind the admission team to follow up with this '
            'applicant tomorrow'))
        self.assertTrue(is_followup_request(
            'schedule a follow-up at 11:30'))
        self.assertTrue(is_followup_request(
            'I want a follow-up with Rahul'))

    def test_05_detection_read_only_never_triggers(self):
        self.assertFalse(is_followup_request(''))
        self.assertFalse(is_followup_request(
            'show follow-ups for Rahul'))
        self.assertFalse(is_followup_request(
            'what are the follow-ups due this week'))
        self.assertFalse(is_followup_request(
            'create an admission inquiry for physics'))

    def test_06_date_tomorrow_with_time(self):
        today = self._resolve_anchor()
        state, iso, time_str = parse_followup_date(
            'tomorrow at 11 AM', today=today)
        self.assertEqual(state, 'ok')
        self.assertEqual(iso, (today + timedelta(days=1)).isoformat())
        self.assertEqual(time_str, '11:00')

    def test_07_date_explicit_and_weekday(self):
        today = self._resolve_anchor()
        iso_explicit = (today + timedelta(days=30)).isoformat()
        state, iso, time_str = parse_followup_date(
            '%s at 15:00' % iso_explicit, today=today)
        self.assertEqual((state, iso, time_str),
                         ('ok', iso_explicit, '15:00'))
        day_first = (today + timedelta(days=40)).strftime('%d-%m-%Y')
        state, iso, _t = parse_followup_date(
            day_first, today=today)
        self.assertEqual(state, 'ok')
        self.assertEqual(iso, (today + timedelta(days=40)).isoformat())
        # bare weekday → next occurrence strictly after today
        state, iso, _t = parse_followup_date('friday', today=today)
        self.assertEqual(state, 'ok')
        self.assertGreater(iso, today.isoformat())
        self.assertLessEqual(iso, (today + timedelta(days=7))
                             .isoformat())

    def test_08_next_weekday(self):
        today = self._resolve_anchor()
        _state, upcoming, _t = parse_followup_date('monday', today=today)
        _state, nxt, _t = parse_followup_date(
            'next monday', today=today)
        from datetime import date as _date
        self.assertEqual(
            nxt, (_date.fromisoformat(upcoming) +
                  timedelta(days=7)).isoformat())

    def test_09_invalid_dates_fail_safely(self):
        today = self._resolve_anchor()
        for phrase in ('last week', 'today', 'sometime next month',
                       '2030-02-30', '31-02-2030'):
            state, _iso, _t = parse_followup_date(phrase, today=today)
            self.assertEqual(state, 'invalid', phrase)
        state, _iso, _t = parse_followup_date('', today=today)
        self.assertEqual(state, 'missing')

    def test_10_time_normalization(self):
        today = self._resolve_anchor()
        self.assertEqual(parse_followup_date(
            'tomorrow at 11:32 pm', today=today)[2], '23:32')
        self.assertEqual(parse_followup_date(
            'tomorrow at 12:45 am', today=today)[2], '00:45')
        self.assertEqual(parse_followup_date(
            'tomorrow at 15:00', today=today)[2], '15:00')
        self.assertEqual(
            parse_followup_date('tomorrow at 99:00', today=today)[0],
            'invalid')
        self.assertEqual(parse_followup_date(
            'tomorrow at 11:99', today=today)[0], 'invalid')
        self.assertEqual(
            parse_followup_date('tomorrow', today=today)[2], None)

    def test_11_extraction_consumes_date_before_names(self):
        fields, _rest = extract_followup_fields(
            'schedule a follow up with Rahul Verma tomorrow at 3 PM')
        self.assertIn('date', fields)
        self.assertIn('3 PM', fields['date'])
        self.assertEqual(fields.get('applicant'), 'Rahul Verma')
        fields, _rest = extract_followup_fields(
            'schedule a follow-up\napplicant: Rahul Verma\n'
            'purpose: documents pending')
        self.assertEqual(fields.get('applicant'), 'Rahul Verma')
        self.assertEqual(fields.get('purpose'), 'documents pending')

    def test_12_phrase_span_extraction(self):
        phrase, rest = extract_followup_date_phrase(
            'remind me to follow up with this applicant tomorrow')
        self.assertEqual(phrase, 'tomorrow')
        self.assertNotIn('tomorrow', rest)


@odoo.tests.tagged('edicai', 'security', '-at_install', 'post_install')
class TestFollowupResolution(TransactionCase, Phase2BFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_followup_core(suffix='FRS', ambiguous=True)

    def _resolver(self):
        return self.env['edicai.ai.action.resolve'].with_user(
            self.registrar)

    def test_01_unique_applicant_by_name(self):
        status, rec, _names = self._resolver().resolve_applicant(
            'Rahul Verma', self.company)
        self.assertEqual(status, 'ok')
        self.assertEqual(rec.id, self.applicant.id)

    def test_02_unique_applicant_by_email(self):
        status, rec, _names = self._resolver().resolve_applicant(
            self.applicant.email, self.company)
        self.assertEqual(status, 'ok')
        self.assertEqual(rec.id, self.applicant.id)

    def test_03_unique_applicant_by_mobile(self):
        status, rec, _names = self._resolver().resolve_applicant(
            self.applicant.mobile, self.company)
        self.assertEqual(status, 'ok')
        self.assertEqual(rec.id, self.applicant.id)

    def test_04_ambiguous_applicant_never_guessed(self):
        status, _rec, names = self._resolver().resolve_applicant(
            'Rahul', self.company)
        self.assertEqual(status, 'ambiguous')
        self.assertGreaterEqual(len(names), 2)

    def test_05_unknown_applicant_not_found(self):
        status, _rec, _names = self._resolver().resolve_applicant(
            'Nobody Here', self.company)
        self.assertEqual(status, 'not_found')

    def test_06_empty_hint_is_missing(self):
        status, _rec, _names = self._resolver().resolve_applicant(
            '', self.company)
        self.assertEqual(status, 'missing')

    def test_07_full_followup_resolution_ok(self):
        outcome = self._resolver().resolve_followup(
            {'applicant': 'Rahul Verma', 'date': 'tomorrow at 2 pm'})
        self.assertEqual(outcome['status'], 'ok')
        today = self._resolve_anchor()
        self.assertEqual(outcome['applicant'].id, self.applicant.id)
        self.assertEqual(
            outcome['date_iso'], (today + timedelta(days=1)).isoformat())
        self.assertEqual(outcome['time'], '14:00')

    def test_08_full_resolution_states(self):
        self.assertEqual(
            self._resolver().resolve_followup(
                {'date': 'tomorrow'})['status'], 'missing')
        self.assertEqual(
            self._resolver().resolve_followup(
                {'applicant': 'Nobody',
                 'date': 'tomorrow'})['status'], 'not_found')
        self.assertEqual(
            self._resolver().resolve_followup(
                {'applicant': 'Rahul',
                 'date': 'tomorrow'})['status'], 'clarify')
        self.assertEqual(
            self._resolver().resolve_followup(
                {'applicant': 'Rahul Verma',
                 'date': 'whenever'})['status'], 'invalid_date')
