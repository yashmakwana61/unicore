"""Question catalogue coverage + aggregate tools (Phase 13).

The catalogue (``models/ai_question_catalogue.py``) is the organisation's
phrasing matrix: every question a user may type, mapped to the tool
that answers it.  These tests make it a REGRESSION-PROOF asset:

* every catalogued pattern matches its own real example sentence;
* every example sentence routes to its intended tool;
* every allow-listed conversational tool is covered by at least one
  phrasing (no tool the AI can never reach);
* every catalogued intent has a policy contract (no orphan intent);
* the aggregate tools answer cohort questions with NUMBERS, scoped by
  the caller's rights;
* an aggregate phrasing never degrades into a per-entity question.
"""

import odoo.tests
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_intent import (
    AGGREGATE_INTENTS,
    INTENT_ATTENDANCE_SUMMARY,
    INTENT_FEES,
    INTENT_FEES_SUMMARY,
    INTENT_PROGRAMS,
    INTENT_TIMETABLE,
)
from odoo.addons.edicai_ai.models.ai_policy import CONVERSATIONAL_TOOL_SPEC
from odoo.addons.edicai_ai.models.ai_question_catalogue import (
    CATALOGUE_EXAMPLES,
    CATALOGUE_INTENTS,
    QUESTION_CATALOGUE,
)
from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIQuestionCatalogueCoverageTest(TransactionCase, Phase1AFixtures):
    """Every catalogued phrasing must route to its tool."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intent = cls.env['edicai.ai.intent']
        cls._build_academic_core(suffix='CAT')
        cls.staff = cls._create_staff_user(login_suffix='catstaff')

    def test_01_every_pattern_matches_its_own_example(self):
        import re
        broken = []
        for intent, pattern, sample in CATALOGUE_EXAMPLES:
            if not re.search(pattern, sample, re.IGNORECASE):
                broken.append((pattern, sample))
        self.assertFalse(
            broken,
            'catalogued patterns that do not match their example: %s'
            % (broken[:8],))

    def test_02_every_example_routes_to_its_intent(self):
        failures = []
        for intent, _pattern, sample in CATALOGUE_EXAMPLES:
            parsed = self.intent.parse(sample)
            if parsed.get('intent') != intent:
                failures.append(
                    '%r -> %s (expected %s)'
                    % (sample, parsed.get('intent'), intent))
        self.assertFalse(
            failures,
            'catalogued phrasings that do not route as declared: %s'
            % (failures[:10],))

    def test_03_every_static_tool_is_covered_by_the_catalogue(self):
        """Every INTENT-tool needs catalogued phrasings.

        Mutations (create/update/execute) stay exempt (confirm-flow).
        Schema inspection (describe) stays exempt; generic READ search
        is covered via the LLM proposal path (Phase G4) and not required
        to have keyword phrasings.  ``entity.aggregate`` is likewise
        parameterized (model/filters/group_by/measures): its real-world
        phrasings are already served by the two aggregate intents
        (fees.fee_summary, attendance.shortage_summary), and the generic
        aggregate path is proposed-only until G5 mines prompts for it.
        """
        covered = {entry['intent'] for entry in QUESTION_CATALOGUE}
        entity_tools = {
            'entity.describe',
            'entity.read',
            'entity.search',
            'entity.aggregate',
            'entity.create',
            'entity.update',
            'entity.execute',
        }
        missing = sorted(
            set(CONVERSATIONAL_TOOL_SPEC) - covered - entity_tools)
        self.assertFalse(
            missing,
            'allow-listed tools with no catalogued phrasing: %s' % (missing,))

    def test_04_every_catalogued_intent_has_a_policy_contract(self):
        for intent in CATALOGUE_INTENTS:
            self.assertIn(
                intent, CONVERSATIONAL_TOOL_SPEC,
                'catalogued intent without a policy contract: %s' % intent)

    def test_05_aggregate_phrasings_beat_the_per_entity_rules(self):
        """A cohort question must never be read as a student question."""
        for text in (
            'How many students have outstanding fees?',
            'Hi, Can you tell me how many students have outstanding fees?',
            'count the students with pending fees',
            'total number of students owing money',
            'just count the number of student',
            'how many students are below the attendance policy',
        ):
            parsed = self.intent.parse(text)
            self.assertIn(
                parsed.get('intent'), AGGREGATE_INTENTS,
                '%r routed to %s (expected an aggregate intent)'
                % (text, parsed.get('intent')))

    def test_06_per_entity_phrasings_still_route_to_the_entity_tool(self):
        for text, expected in (
            ('what is my fee status', INTENT_FEES),
            ('how much do i owe', INTENT_FEES),
            ('are there any timetable clashes', INTENT_TIMETABLE),
            ('what programs are offered', INTENT_PROGRAMS),
        ):
            parsed = self.intent.parse(text)
            self.assertEqual(parsed.get('intent'), expected, text)


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIAggregateToolTest(TransactionCase, Phase1AFixtures):
    """The aggregate tools answer cohort questions with NUMBERS."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_academic_core(suffix='AGG')
        cls.staff = cls._create_staff_user(login_suffix='aggstaff')
        cls.student_a, cls.user_a = cls._create_student(
            login_suffix='agga', name='Aarav', last_name='Payer')
        cls.student_b, cls.user_b = cls._create_student(
            login_suffix='aggb', name='Diya', last_name='Payer')
        cls._create_fee_invoice(cls.student_a, 5000.0)
        cls._create_fee_invoice(cls.student_b, 2500.0)

    def test_01_fee_summary_counts_students_and_totals(self):
        tools = self.env['edicai.ai.conversational.tools'].with_user(self.staff)
        result = tools.tool_fee_summary({})
        self.assertNotIn('error_code', result)
        data = result['data']
        self.assertEqual(data['students_with_outstanding'], 2)
        self.assertAlmostEqual(data['total_outstanding'], 7500.0, places=2)
        self.assertTrue(data['top_students'])

    def test_02_fee_summary_counts_every_student_with_dues(self):
        """One invoice per student per semester — a third student joins
        the cohort with a smaller amount."""
        student_c, _user_c = self._create_student(
            login_suffix='aggc', name='Isha', last_name='Payer')
        self._create_fee_invoice(student_c, 1000.0)
        tools = self.env['edicai.ai.conversational.tools'].with_user(self.staff)
        result = tools.tool_fee_summary({})
        data = result['data']
        self.assertEqual(data['students_with_outstanding'], 3)
        self.assertAlmostEqual(data['total_outstanding'], 8500.0, places=2)

    def test_03_restricted_student_only_sees_own_record(self):
        """A portal student may not aggregate other students' fees."""
        tools = self.env['edicai.ai.conversational.tools'].with_user(self.user_a)
        result = tools.tool_fee_summary({})
        data = result['data']
        self.assertEqual(data['scope'], 'own')
        self.assertLessEqual(data['students_with_outstanding'], 1)

    def test_04_aggregate_tools_are_policy_allowed(self):
        gate = self.env['edicai.ai.policy.gate']
        for tool in (INTENT_FEES_SUMMARY, INTENT_ATTENDANCE_SUMMARY):
            decision = gate.check_access(tool, user=self.staff)
            self.assertTrue(decision['allowed'], '%s: %s' % (tool, decision))

    def test_05_aggregate_intents_are_registered(self):
        registry = self.env['edicai.ai.tool.registry']
        names = [t['name'] for t in registry.list_tools()]
        self.assertIn(INTENT_FEES_SUMMARY, names)
        self.assertIn(INTENT_ATTENDANCE_SUMMARY, names)

    def test_06_aggregate_reply_contains_the_number(self):
        """The reply must state the COUNT, not ask which student."""
        orchestrator = self.env['edicai.ai.orchestrator']
        template = orchestrator._compose_fee_summary({
            'students_with_outstanding': 3,
            'total_outstanding': 12345.0,
            'currency': 'INR',
            'overdue_students': 1,
            'top_students': [
                {'student': 'Aarav Patel', 'outstanding': 5000.0,
                 'invoice_count': 1, 'overdue_count': 0}],
            'empty': False,
        })
        self.assertIn('3', template)
        self.assertIn('12,345', template)
        self.assertNotIn('Which student', template)

    def test_07_aggregate_reply_for_an_empty_cohort(self):
        orchestrator = self.env['edicai.ai.orchestrator']
        template = orchestrator._compose_fee_summary({
            'students_with_outstanding': 0,
            'total_outstanding': 0.0,
            'currency': 'INR',
            'overdue_students': 0,
            'top_students': [],
            'empty': True,
        })
        self.assertIn('No student', template)
