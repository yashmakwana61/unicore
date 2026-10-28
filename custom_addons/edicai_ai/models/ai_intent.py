"""Phase 1A — controlled intent grammar for the conversational layer.

A DETERMINISTIC classifier: the natural-language turn is mapped to one
allow-listed intent (or UNKNOWN / UNSUPPORTED) via fixed regular
expressions and keyword lists only. The LLM provider is NOT used for
intent detection in Phase 1A, so:

* no prompt-injection payload can steer free-form model output into an
  executable tool name — there is no such output; every supported
  intent maps to a fixed tool name that the policy gate and the
  central registry validate again before execution.
* classification is reproducible, cheap, and provider-independent
  (no LLM_UNAVAILABLE failure mode on the conversational read loop).

Intent map (stable identifiers, used in audit metadata):

    attendance.shortage_report
    fees.fee_status
    timetable.clash_check
    grading.grade_summary
    admission.program_search

Statuses:

* ``supported``   — routed to the intent's tool through the policy gate.
* ``unknown``     — deterministic safe "I don't know" reply.
* ``unsupported`` — write actions / adversarial phrasings; safe
  "I can't perform that action yet." reply. Never routed to a tool.

Ambiguity is entity-level, not intent-level: when entity extraction
cannot resolve a single record (e.g. the explicit student name a staff
member asked about matches several records), the TOOL HANDLER returns a
bounded clarification list instead of guessing. The grammar itself
never selects between candidates silently.
"""

import logging
import re

from odoo import api, models

from odoo.addons.edicai_ai.models.ai_question_catalogue import (
    AGGREGATE_INTENTS as _CATALOGUE_AGGREGATE_INTENTS,
    CATALOGUE_PATTERNS,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent names (stable identifiers, also used as tool names)
# ---------------------------------------------------------------------------

INTENT_ATTENDANCE = 'attendance.shortage_report'
INTENT_FEES = 'fees.fee_status'
INTENT_TIMETABLE = 'timetable.clash_check'
INTENT_TIMETABLE_VIEW = 'timetable.view'
INTENT_GRADES = 'grading.grade_summary'
INTENT_PROGRAMS = 'admission.program_search'
INTENT_APPLICANT_LIST = 'admission.applicant_list'
INTENT_FOLLOWUP_LIST = 'admission.followup_list'
INTENT_GRIEVANCE_SUMMARY = 'grievance.summary'

# Aggregate (cohort) variants — "how many students ...", "total
# outstanding ...". A cohort question is never a student-name question,
# so these intents are matched BEFORE the per-entity ones.
INTENT_FEES_SUMMARY = 'fees.fee_summary'
INTENT_ATTENDANCE_SUMMARY = 'attendance.shortage_summary'

# Generic entity layer (Phase G4): the two self-describing discovery
# intents are deterministic (catalogue phrasings); ``entity.search`` has
# NO deterministic rule — its model/filter parameters arrive ONLY as a
# validated LLM proposal (fail-closed on every missing piece).
INTENT_ENTITY_MODELS = 'entity.list_models'
INTENT_ENTITY_ACTIONS = 'entity.list_actions'
INTENT_ENTITY_SEARCH = 'entity.search'

_ENTITY_INTENTS = (
    INTENT_ENTITY_MODELS,
    INTENT_ENTITY_ACTIONS,
    INTENT_ENTITY_SEARCH,
)

SUPPORTED_INTENTS = (
    INTENT_ATTENDANCE,
    INTENT_FEES,
    INTENT_TIMETABLE,
    INTENT_TIMETABLE_VIEW,
    INTENT_GRADES,
    INTENT_PROGRAMS,
    INTENT_APPLICANT_LIST,
    INTENT_FOLLOWUP_LIST,
    INTENT_GRIEVANCE_SUMMARY,
    INTENT_FEES_SUMMARY,
    INTENT_ATTENDANCE_SUMMARY,
    *_ENTITY_INTENTS,
)

#: Intents answered with cohort numbers instead of one named entity.
AGGREGATE_INTENTS = (
    INTENT_FEES_SUMMARY,
    INTENT_ATTENDANCE_SUMMARY,
    INTENT_GRIEVANCE_SUMMARY,
)

# Intent → safe source label shown to the user / persisted on the reply.
INTENT_SOURCE_LABEL = {
    INTENT_ATTENDANCE: 'Attendance Report',
    INTENT_FEES: 'Fee Status',
    INTENT_TIMETABLE: 'Timetable Clashes',
    INTENT_TIMETABLE_VIEW: 'Timetable',
    INTENT_GRADES: 'Grade Summary',
    INTENT_PROGRAMS: 'Admission Programs',
    INTENT_APPLICANT_LIST: 'Admission Applicants',
    INTENT_FOLLOWUP_LIST: 'Admission Follow-ups',
    INTENT_GRIEVANCE_SUMMARY: 'Grievance Summary',
    INTENT_FEES_SUMMARY: 'Outstanding Fees (all students)',
    INTENT_ATTENDANCE_SUMMARY: 'Attendance Shortage (all students)',
    INTENT_ENTITY_MODELS: 'AI Entities',
    INTENT_ENTITY_ACTIONS: 'Record Actions',
    INTENT_ENTITY_SEARCH: 'AI Entity Search',
}

# ---------------------------------------------------------------------------
# Statuses
# ---------------------------------------------------------------------------

STATUS_SUPPORTED = 'supported'
STATUS_UNKNOWN = 'unknown'
STATUS_UNSUPPORTED = 'unsupported'

# ---------------------------------------------------------------------------
# Rules: keyword lists (validated with word boundaries, case-insensitive)
# ---------------------------------------------------------------------------

_ATTENDANCE_WORDS = ('attendance', 'attendence', 'shortage')

_FEES_WORDS = ('fee', 'fees', 'outstanding', 'due', 'dues', 'owe', 'owing',
               'pending fees', 'fees remaining', 'paid so far')

_TIMETABLE_WORDS = ('clash', 'clashes', 'conflict', 'conflicts',
                    'double-booked', 'double booked', 'timetable',)

_GRADES_WORDS = ('grade', 'grades', 'cgpa', 'gpa', 'marks',
                 'semester result', 'semester results',
                 'academic performance', 'academic results')

_PROGRAMS_WORDS = ('program', 'programs', 'programme', 'programmes',
                   'degree offered', 'degrees offered', 'tuition',
                   'admission program', 'admission programs')

# ``_KEYWORDS`` drives detection order: the first intent with a hit wins.
_INTENT_RULES = (
    (INTENT_ATTENDANCE, _ATTENDANCE_WORDS),
    (INTENT_FEES, _FEES_WORDS),
    (INTENT_TIMETABLE, _TIMETABLE_WORDS),
    (INTENT_GRADES, _GRADES_WORDS),
    (INTENT_PROGRAMS, _PROGRAMS_WORDS),
)

# Compound phrasings that contain no bare keyword, e.g. "how many
# classes have I missed", "how much do I owe".
_EXTRA_PATTERNS = (
    (INTENT_ATTENDANCE, (
        r'how\s+many\s+classes\s+\w*\s*(have\s+)?i\s+missed',
        r'am\s+i\s+short\s+(on|of)',
        r'how\s+is\s+my\s+attendance',
        r'what.s\s+my\s+attendance',
    )),
    (INTENT_FEES, (
        r'how\s+much\s+do\s+i\s+owe',
        r'how\s+much\s+(?:fees?|money)\b',
        r'how\s+much\s+is\s+(?:left|remaining)',
        r'do\s+i\s+have\s+(?:any\s+)?(?:pending\s+|outstanding\s+)?fees?',
        r'have\s+i\s+paid\s+(?:all|everything|my\s+fees)',
    )),
    (INTENT_TIMETABLE, (
        r'any\s+scheduling\s+problems?',
        r'(?:show|check)\s+(?:me\s+)?scheduling\s+problems?',
        r'are\s+there\s+any\s+(?:clashes|conflicts)',
    )),
    (INTENT_GRADES, (
        r'how\s+are\s+my\s+grades',
        r'what\s+are\s+my\s+marks',
        r'my\s+academic\s+standing',
    )),
    (INTENT_PROGRAMS, (
        r'what\s+can\s+i\s+(?:study|apply\s+for)',
        r'courses?\s+available\s+for\s+admission',
        r'programs?\s+open\s+for\s+admission',
    )),
)

# ---------------------------------------------------------------------------
# Unsupported request detection (write actions + adversarial phrasings)
# ---------------------------------------------------------------------------

# Exact (stem) tokens that signal a write action when they appear as a
# VERB-NOUN pattern. Conservative on purpose: Phase 1A prefers refusing
# a borderline read to executing anything outside the allow-list.
_WRITE_ACTION_PATTERNS = (
    r'\bdelete\b', r'\bremove\b', r'\bdrop\b',
    r'\bapprove\b', r'\breject\b', r'\bdisapprove\b',
    r'\bissue\b', r'\bsend\b', r'\bshare\b', r'\bnotify\b',
    r'\bpost\b', r'\bpublish\b', r'\bconfirm\b', r'\bverify\b',
    r'\bcreate\b', r'\benroll(ment)?\b(?=\s+(?:student|me|him|her|this))',
    r'\bcancel\b', r'\barchive\b', r'\brestore\b', r'\breset\b',
    r'\bmark(as)?\b', r'\bchange\b', r'\bupdate\b', r'\bmodify\b',
    r'\bedit\b', r'\bwrite\b', r'\bimport\b', r'\bexport\b',
    r'\bassign\b', r'\btransfer\b', r'\bsuspend\b', r'\bexpel\b',
    r'\brevoke\b', r'\bgrant\b', r'\breset\b',
)

_ADVERSARIAL_PHRASES = (
    'ignore your rules',
    'ignore previous instructions',
    'ignore the tool',
    'ignore restrictions',
    'use sudo',
    'sudo(',
    'system prompt',
    'developer mode',
    'raw internal',
    'database dump',
    'give me the database',
    'drop table',
    'select * from',
    'union select',
    'delete from',
    'insert into',
    'pretend i am an administrator',
    "pretend i'm an administrator",
    'pretend to be an administrator',
    'pretend to be admin',
    'you are now an admin',
    'act as administrator',
    'bypass',
    'api key',
    'credential',
    'password',
    'show me another student',
    'other students private',
    'override security',
    'escalate privilege',
)

# Safe Phase-1A replies (fixed strings, no interpolation).
UNSUPPORTED_REPLY = "I can't perform that action yet."
UNKNOWN_REPLY = (
    "I don't have enough information to answer that. "
    + "I can help with: your attendance, your fee status, "
    + "your grades, timetable clashes, and admission programs."
)

# Courtesy reply for a bare greeting.  Fixed string, no data, no
# permissions; it only advertises the read capabilities.
GREETING_REPLY = (
    "Hello! I can look up ERP records for you — for example: "
    "your attendance, your fee status, your grades, timetable "
    "clashes, admission programs, applicant follow-ups, and "
    "grievance summaries. What would you like to know?"
)

# Deterministic clarification prompts (asked by handlers, listed here
# for the No-GUESS invariant).
CLARIFY_STUDENT = 'Which student do you mean?'
CLARIFY_SEMESTER = 'Which semester do you mean?'


class EdicaiAIIntent(models.AbstractModel):
    """Controlled intent grammar / entity extraction (Phase 1A)."""

    _name = 'edicai.ai.intent'
    _description = 'AI Conversational Intent Grammar (read-only)'

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    @api.model
    def _word_match(self, text, word):
        """Word-boundary match for a keyword stem."""
        return re.search(
            r'(?<!\w)%s(?!\w)' % re.escape(word),
            text,
            re.IGNORECASE,
        ) is not None

    @api.model
    def _pattern_match(self, text, pattern):
        try:
            return re.search(pattern, text, re.IGNORECASE) is not None
        except re.error:
            # A broken rule must fail CLOSED (no classification).
            _logger.error('ai_intent: invalid pattern %r.', pattern)
            return False

    @api.model
    def is_unsupported_request(self, text):
        """True when the text asks for a write action."""
        return any(
            self._pattern_match(text, pattern)
            for pattern in _WRITE_ACTION_PATTERNS
        )

    @api.model
    def is_adversarial_request(self, text):
        """True for prompt-injection / privilege-escalation phrasings."""
        lowered = (text or '').lower()
        return any(phrase in lowered for phrase in _ADVERSARIAL_PHRASES)

    # ------------------------------------------------------------------
    # Entity extraction (bounded, never authoritative)
    # ------------------------------------------------------------------

    @api.model
    def extract_semester_term(self, text):
        """Extract a semester mention (e.g. 'semester 5', 'semester V').

        :returns: the term string or ``False``.
        """
        match = re.search(
            r'semester\s*(?:number\s*)?([0-9]{1,2}|[ivxIVX]{1,4}|'
            r'one|two|three|four|five|six|seven|eight|nine|ten)\b',
            text,
            re.IGNORECASE,
        )
        if not match:
            return False
        token = match.group(1)
        if token.lower() in ('one', 'two', 'three', 'four', 'five',
                             'six', 'seven', 'eight', 'nine', 'ten'):
            token = str(['one', 'two', 'three', 'four', 'five', 'six',
                         'seven', 'eight', 'nine', 'ten'].index(token.lower())
                        + 1)
        return token

    @api.model
    def extract_student_name(self, text):
        """Extract an explicit student-name phrase.

        Only explicit, capitalized 1-4 word names after *for* / *of*
        are considered (e.g. "attendance for Priya Sharma"). We never
        infer names from bare pronouns or lowercase fragments; when no
        name is found the handlers fall back to the safe clarification
        path instead of guessing.
        """
        for connector in ('for', 'of'):
            match = re.search(
                r'\b%s\s+([\w][\w.-]*(?:\s+[\w][\w.-]*){0,3})\b'
                % connector, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip().rstrip('.,?!')
                return name
        return False

    @api.model
    def extract_program_filter(self, text):
        """Extract ``(level, query)`` hints for program search.

        ``level`` is only returned when it matches a known
        ``edicai.program.program_type`` value (validated against an
        allow-list here; anything else is dropped and delegated
        without filter — never guessed).
        """
        level = False
        for candidate in ('undergraduate', 'postgraduate', 'doctoral',
                          'diploma', 'certificate'):
            if self._word_match(text, candidate):
                level = candidate
                break
        # Query: quoted phrase or an explicit program code/name adjacent
        # to a program noun. An unresolved requested code is still passed
        # to the delegated search (which returns zero), never dropped.
        query = False
        quoted = re.search(r'"([^"]{2,60})"', text)
        if quoted:
            query = quoted.group(1).strip()
        if not query:
            patterns = (
                r'\b(?:find|show|list|search)\s+(?:me\s+)?'
                r'([a-z][a-z0-9.&/-]{1,24})\s+'
                r'(?:programs?|programmes?|degrees?|courses?)\b',
                r'\b(?:programs?|programmes?|degrees?|courses?)\s+'
                r'(?:for|in|like)\s+([a-z][a-z0-9.&/-]{1,24})\b',
            )
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip().rstrip('.,?!')
                    if candidate.lower() not in (
                            'undergraduate', 'postgraduate', 'doctoral',
                            'diploma', 'certificate', 'all', 'active'):
                        query = candidate[:60]
                        break
        return level, query

    # ------------------------------------------------------------------
    # Deterministic classification
    # ------------------------------------------------------------------

    @api.model
    def parse(self, text):
        """Classify one user turn.

        :returns: dict with keys:
            ``status``   — 'supported' | 'unknown' | 'unsupported'
            ``intent``   — the intent identifier or False
            ``tool``     — same as intent (tool == intent name); the
                           caller still validates against the registry.
            ``source_label`` — display citation label or False
            ``entities`` — extracted entity hints (semester term,
                           student name, program level/query).
        """
        text = str(text or '').strip()
        result = {
            'status': STATUS_UNKNOWN,
            'intent': False,
            'tool': False,
            'source_label': False,
            'entities': {
                'semester_term': False,
                'student_name': False,
                'program_level': False,
                'program_query': False,
            },
        }
        if not text:
            return result

        # 1. Adversarial phrasings NEVER become supported read intents.
        if self.is_adversarial_request(text):
            result['status'] = STATUS_UNSUPPORTED
            return result

        # 2. Write actions are unsupported in Phase 1A (read-only).
        if self.is_unsupported_request(text):
            result['status'] = STATUS_UNSUPPORTED
            return result

        # 3. The QUESTION CATALOGUE decides first: it holds the phrasings
        #    a real user types, aggregate (cohort) variants included. A
        #    cohort question must never be answered with "which student
        #    do you mean?".
        matched = False
        for intent, patterns in CATALOGUE_PATTERNS:
            if any(self._pattern_match(text, p) for p in patterns):
                matched = intent
                break

        # 4. Deterministic intent match (first rule wins).
        if not matched:
            for intent, keywords in _INTENT_RULES:
                if any(self._word_match(text, kw) for kw in keywords):
                    matched = intent
                    break
        if not matched:
            for intent, patterns in _EXTRA_PATTERNS:
                if any(self._pattern_match(text, p) for p in patterns):
                    matched = intent
                    break
        if not matched:
            return result
        # A clash/conflict noun is more specific than a generic timetable
        # mention ("check my timetable for clashes" remains a scan).
        if matched == INTENT_TIMETABLE_VIEW and re.search(
                r'\b(clash|clashes|conflict|conflicts|double[\s-]booked)\b',
                text, re.I):
            matched = INTENT_TIMETABLE

        result['intent'] = matched
        result['tool'] = matched
        result['source_label'] = INTENT_SOURCE_LABEL.get(matched, 'ERP Data')
        result['status'] = STATUS_SUPPORTED
        result['entities'] = {
            'semester_term': self.extract_semester_term(text),
            'student_name': self.extract_student_name(text),
        }
        # Keep common program codes explicit even when another domain was
        # requested. The orchestrator either applies a supported filter or
        # asks for clarification; it never drops the constraint.
        code_hint = re.search(
            r'\b(?:BCA|BBA|MBA|MCA|B\.?Com|B\.?Sc|M\.?Com)\b',
            text, re.I)
        if code_hint:
            result['entities']['program_query'] = code_hint.group(0)
        campus_hint = re.search(
            r'\b(?:at|from)\s+([\w-]+(?:\s+[\w-]+){0,2})\s+campus\b',
            text, re.I)
        if campus_hint:
            result['entities']['campus'] = re.sub(
                r'\s+campus$', '', campus_hint.group(1).strip(), flags=re.I)
        if matched == INTENT_PROGRAMS:
            level, query = self.extract_program_filter(text)
            result['entities']['program_level'] = level
            result['entities']['program_query'] = query or \
                result['entities'].get('program_query') or False
            campus = re.search(
                r'\b(?:at|from)\s+([\w-]+(?:\s+[\w-]+){0,2}?)'
                r'(?:\s+campus)?(?:\b|$)', text, re.I)
            if campus:
                result['entities']['campus'] = re.sub(
                    r'\s+campus$', '', campus.group(1).strip(), flags=re.I)
        if matched == INTENT_APPLICANT_LIST:
            states = (
                (r'\binquiry\s+stage\b', 'inquiry'),
                (r'\bapplied\b', 'applied'),
                (r'\bdocument(?:s)?\s+pending\b', 'documents_pending'),
                (r'\bunder\s+review\b', 'under_review'),
                (r'\bshortlisted\b', 'shortlisted'),
                (r'\bentrance\s+scheduled\b', 'entrance_scheduled'),
                (r'\bmerit\s+listed\b', 'merit_listed'),
                (r'\boffer\s+sent\b', 'offer_sent'),
                (r'\bfee\s+pending\b', 'fee_pending'),
                (r'\bwaitlisted\b', 'waitlisted'),
            )
            for pattern, state_value in states:
                if re.search(pattern, text, re.I):
                    result['entities']['state'] = state_value
                    break
            if re.search(r'\bpending\b', text, re.I) and not \
                    result['entities'].get('state'):
                result['entities']['state'] = 'pending'
            if re.search(r'without\s+(?:any\s+)?follow[ -]?ups?|'
                         r'need\s+follow[ -]?ups?', text, re.I):
                result['entities']['no_followup'] = True
        if matched == INTENT_FOLLOWUP_LIST:
            result['entities']['date_filter'] = (
                'overdue' if re.search(r'\boverdue\b', text, re.I)
                else 'today' if re.search(r'\btoday\b', text, re.I)
                else 'yesterday' if re.search(r'\byesterday\b', text, re.I)
                else 'all')
            if result['entities']['date_filter'] == 'all' and re.search(
                    r'\b(?:last|this)\s+week\b|\b(?:on\s+)?'
                    r'\d{4}-\d{1,2}-\d{1,2}\b|'
                    r'\b(?:tomorrow|monday|tuesday|wednesday|thursday|'
                    r'friday|saturday|sunday)\b', text, re.I):
                result['entities']['date_filter'] = 'unsupported'
        if matched == INTENT_TIMETABLE_VIEW:
            date_match = re.search(r'\b(today|tomorrow|yesterday)\b',
                                   text, re.I)
            if date_match:
                result['entities']['schedule_date'] = date_match.group(1).lower()
        # Small validated IR: domain/operation/scope are application
        # derived, while filters remain explicit hints for handler-side
        # validation. No LLM value is converted directly to an ORM domain.
        domain = {
            INTENT_ATTENDANCE: 'attendance',
            INTENT_ATTENDANCE_SUMMARY: 'attendance',
            INTENT_FEES: 'fees', INTENT_FEES_SUMMARY: 'fees',
            INTENT_TIMETABLE: 'timetable',
            INTENT_TIMETABLE_VIEW: 'timetable', INTENT_GRADES: 'grading',
            INTENT_PROGRAMS: 'admission',
            INTENT_APPLICANT_LIST: 'admission',
            INTENT_FOLLOWUP_LIST: 'admission',
            INTENT_GRIEVANCE_SUMMARY: 'grievance',
        }.get(matched, 'entity')
        is_aggregate = matched in AGGREGATE_INTENTS
        count_request = bool(re.search(
            r'\b(how\s+many|count|number\s+of)\b', text, re.I))
        if (is_aggregate or matched in (INTENT_APPLICANT_LIST,
                                        INTENT_FOLLOWUP_LIST)) and count_request:
            operation = 'count'
        elif is_aggregate or matched in (INTENT_TIMETABLE_VIEW,
                                          INTENT_APPLICANT_LIST,
                                          INTENT_FOLLOWUP_LIST):
            operation = 'list'
        elif matched == INTENT_PROGRAMS:
            operation = 'search'
        else:
            operation = 'read'
        filters = {}
        if result['entities'].get('program_query'):
            filters['program_query'] = result['entities']['program_query']
        if result['entities'].get('program_level'):
            filters['program_level'] = result['entities']['program_level']
        if result['entities'].get('schedule_date'):
            filters['date'] = result['entities']['schedule_date']
        if result['entities'].get('campus'):
            filters['campus'] = result['entities']['campus']
        if result['entities'].get('state'):
            filters['state'] = result['entities']['state']
        if result['entities'].get('no_followup'):
            filters['no_followup'] = True
        if result['entities'].get('date_filter'):
            filters['date'] = result['entities']['date_filter']
        result_limit = re.search(r'\b(?:first|top|show)\s+(\d{1,2})\b',
                                 text, re.I)
        if result_limit:
            result['entities']['limit'] = min(int(result_limit.group(1)), 10)
            filters['limit'] = result['entities']['limit']
        threshold = re.search(r'\b(?:below|under|less\s+than)\s+(\d{1,3})\s*%',
                              text, re.I)
        if threshold:
            filters['threshold'] = int(threshold.group(1))
            result['entities']['threshold'] = int(threshold.group(1))
        if re.search(r'\boverdue\b', text, re.I) and domain == 'fees':
            filters['overdue'] = True
            result['entities']['overdue_only'] = True
        if domain == 'grievance' and re.search(
                r'\b(open|pending|unresolved)\b', text, re.I):
            filters['open_only'] = True
            result['entities']['open_only'] = True
        result['query'] = {
            'domain': domain, 'operation': operation,
            'scope': ('aggregate' if operation == 'count' else
                      'collection' if is_aggregate or
                      matched == INTENT_TIMETABLE_VIEW or
                      matched in (INTENT_PROGRAMS,
                                  INTENT_APPLICANT_LIST,
                                  INTENT_FOLLOWUP_LIST) else 'record'),
            'entities': {
                key: value for key, value in result['entities'].items()
                if value not in (False, None, '')
            },
            'filters': filters,
            'date_range': ({'relative': filters['date']}
                           if filters.get('date') else {}),
            'sort': {},
            'limit': result['entities'].get('limit'),
            'follow_up': {},
            'confidence': 1.0,
            'ambiguities': [],
        }
        return result

    @api.model
    def supported_intents(self):
        """The fixed Phase 1A allow-list (for tests and the policy gate)."""
        return list(SUPPORTED_INTENTS)
