r"""Question catalogue — the conversational ERP's phrase matrix.

WHY THIS EXISTS
---------------
The conversational layer used to route on a handful of keywords, so a
perfectly reasonable question like *"how many students have outstanding
fees?"* was answered with *"Which student do you mean?"* — the tools
were per-entity only, and the follow-up (*"just count the number of
students"*) was parsed as a student name.

This module is the single, declarative source of truth for
**"which question phrasings does the ERP answer, and with which tool"**:

* every domain lists the phrasings a real user types (counts, totals,
  lists, per-entity lookups, filters, synonyms, both question orders);
* the intent matcher routes from this catalogue FIRST, so a phrasing
  listed here can never silently regress to a keyword guess;
* the coverage test (``tests/test_ai_question_catalogue.py``) walks
  every entry and asserts that (a) the pattern matches its own real
  example sentence, and (b) that sentence routes to the expected tool —
  and that every allow-listed tool is covered by at least one phrasing.

Adding support for a new phrasing is therefore ONE entry here plus
(optionally) a new tool contract.

The catalogue is data, not behaviour: it contains no secrets, no record
identifiers and no ERP payloads.

Each entry is::

    {
        'domain':  'fees',                    # ERP area
        'intent':  'fees.fee_summary',        # tool that answers it
        'mode':    'aggregate',               # 'single' | 'aggregate'
        'specificity': 'domain',              # 'domain' | 'fallback'
        'phrases': (                           # (pattern, example) pairs
            (r'how\s+many\s+students?...', 'how many students have '
                                          'outstanding fees'),
        ),
    }

``specificity``
    ``domain``   — the phrasing names its domain (fee/attendance/...);
                   these are matched first.
    ``fallback`` — the phrasing is topic-less ("just count the number
                   of students") and only matches when no domain-specific
                   phrasing did.  It answers the CURRENT conversation
                   topic's cohort question (fees is the default).
"""

# ---------------------------------------------------------------------------
# Catalogue entries
# ---------------------------------------------------------------------------

QUESTION_CATALOGUE = (
    {
        'domain': 'fees',
        'intent': 'fees.fee_summary',
        'mode': 'aggregate',
        'specificity': 'domain',
        'phrases': (
            (r'how\s+many\s+students?\s+(?:have|has|are|are\s+there|with)\b.*\bfees?\b',
             'how many students have outstanding fees'),
            (r'how\s+many\s+students?\s+have\s+(?:outstanding|pending|unpaid|due)\b',
             'how many students have pending fees'),
            (r'how\s+many\s+students?\s+owe\b',
             'how many students owe money'),
            (r'how\s+many\s+students?\s+(?:are\s+)?(?:still\s+)?owing\b',
             'how many students are still owing'),
            (r'count\s+(?:the\s+)?students?\s+(?:with|who\s+have|having|that\s+have)\b.*\bfees?\b',
             'count the students with unpaid fees'),
            (r'count\s+(?:the\s+)?students?\s+owing\b',
             'count students owing money'),
            (r'(?:total\s+)?number\s+of\s+students?\s+(?:with|who\s+have|having|that\s+have)\b.*\bfees?\b',
             'total number of students with outstanding fees'),
            (r'(?:total\s+)?number\s+of\s+students?\s+owing\b',
             'number of students owing fees'),
            (r'(?:give|show|tell)\s+me\s+(?:the\s+)?(?:number|count|total)\b.*\bstudents?\b',
             'give me the number of students with dues'),
            (r'(?:all|every)\s+students?.*\bfees?\b',
             'all students fee status'),
            (r'(?:show|list)\s+(?:me\s+)?(?:fee|fees)\s+'
             r'(?:details|status)\s+for\s+(?:all|every)\s+students?\b',
             'show fee details for every student'),
            (r'\bfees?\b.*\bof\s+(?:all|every)\s+students?\b',
             'fees of every student'),
            (r'(?:show|list|which|who)\s+(?:me\s+)?(?:all\s+)?students?\s+'
             r'(?:with|who\s+have|having)\s+(?:outstanding|overdue|unpaid|pending)\s+fees?\b',
             'show me students with outstanding fees'),
            (r'who\s+has\s+(?:overdue|outstanding)\s+fees?\b',
             'who has overdue fees'),
            (r'total\s+outstanding\b',
             'total outstanding amount'),
            (r'how\s+much\s+(?:is|are)\s+outstanding\s+(?:in\s+total|overall)\b',
             'how much is outstanding overall'),
            (r'how\s+many\s+students?\s+are\s+overdue\b',
             'how many students are overdue'),
            (r'summary\s+of\s+(?:all\s+)?(?:students?[\'’]?\s+)?fees?\b',
             'summary of all students fees'),
        ),
    },
    {
        'domain': 'attendance',
        'intent': 'attendance.shortage_summary',
        'mode': 'aggregate',
        'specificity': 'domain',
        'phrases': (
            (r'how\s+many\s+students?\s+(?:have|are|with)\b.*\battendance\b',
             'how many students have low attendance'),
            (r'how\s+many\s+students?\s+are\s+short\s+(?:of|on)\s+attendance\b',
             'how many students are short of attendance'),
            (r'how\s+many\s+students?\s+have\s+low\s+attendance\b',
             'how many students have low attendance'),
            (r'how\s+many\s+students?\s+are\s+below\s+(?:the\s+)?(?:policy|minimum|threshold)\b',
             'how many students are below the policy minimum'),
            (r'count\s+(?:the\s+)?students?\s+(?:with|who\s+have|having)\b.*\battendance\b',
             'count the students with attendance shortage'),
            (r'(?:which|show|list)\s+(?:me\s+)?students?\s+'
             r'(?:have|with|below)\b.*\b(?:attendance\s+)?(?:shortage|low|policy|minimum|threshold|%|percent)',
             'which students have attendance shortage'),
            (r'who\s+is\s+below\s+\d{1,3}\s*%',
             'who is below 75%'),
            (r'(?:total\s+)?number\s+of\s+students?\s+(?:with|who\s+have|having)\b.*\battendance\b',
             'number of students with attendance issues'),
            (r'just\s+count\s+(?:the\s+)?(?:number\s+of\s+)?students?\b.*\battendance\b',
             'just count the number of students with attendance issues'),
            (r'count\s+(?:them|all|everyone|everybody)\b.*\battendance\b',
             'count them all for attendance'),
            (r'attendance\s+shortage\s+(?:summary|overview|report)\b',
             'attendance shortage summary'),
            (r'(?:show|list)\s+(?:the\s+)?attendance\s+'
             r'(?:problems?|shortages?)\b',
             'show attendance problems'),
            (r'summary\s+of\s+(?:all\s+)?attendance\b',
             'summary of all attendance'),
        ),
    },
    {
        'domain': 'fees',
        'intent': 'fees.fee_summary',
        'mode': 'aggregate',
        'specificity': 'fallback',
        'phrases': (
            (r'just\s+count\s+(?:the\s+)?(?:number\s+of\s+)?students?\b',
             'just count the number of student'),
            (r'count\s+(?:them|all|everyone|everybody)\b',
             'count them all'),
            (r'how\s+many\s+of\s+(?:them|all|my\s+students?)\b',
             'how many of them have dues'),
        ),
    },
    {
        'domain': 'fees',
        'intent': 'fees.fee_status',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'\bmy\s+(?:fee|fees)\s+status\b', 'what is my fee status'),
            (r'\bmy\s+outstanding\b', 'my outstanding amount'),
            (r'how\s+much\s+do\s+i\s+owe\b', 'how much do i owe'),
            (r'how\s+much\s+(?:do\s+i\s+owe|are\s+my\s+fees|fees?\s+do\s+i\s+owe)\b',
             'how much are my fees'),
            (r'\bfees?\s+(?:of|for)\s+[A-Z]', 'fees of Aarav Patel'),
            (r'\boutstanding\s+(?:fees?\s+)?(?:of|for)\s+[A-Z]',
             'outstanding fees of Aarav Patel'),
            (r'\bfees?\s+of\s+[A-Z]', 'fees of Aarav Patel'),
            (r'how\s+much\s+(?:is|are)\s+(?:left|remaining|due)\b',
             'how much is left'),
            (r'do\s+i\s+have\s+(?:any\s+)?(?:pending\s+|outstanding\s+)?fees?\b',
             'do i have any pending fees'),
            (r'have\s+i\s+paid\s+(?:all|everything|my\s+fees)\b',
             'have i paid all my fees'),
            (r'fee\s+(?:status|summary)\s+(?:of|for)\s+[A-Z]',
             'fee status of Aarav Patel'),
        ),
    },
    {
        'domain': 'attendance',
        'intent': 'attendance.shortage_report',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'\bmy\s+attendance\b', 'what is my attendance'),
            (r'how\s+(?:is|are)\s+my\s+attendance\b', 'how is my attendance'),
            (r'how\s+many\s+classes\s+\w*\s*(?:have\s+)?i\s+missed',
             'how many classes have i missed'),
            (r'am\s+i\s+short\s+(?:on|of)\b', 'am i short on attendance'),
            (r'attendance\s+(?:of|for)\s+[A-Z]', 'attendance of Aarav Patel'),
            (r'\bshortage\b', 'is there a shortage'),
        ),
    },
    {
        'domain': 'grades',
        'intent': 'grading.grade_summary',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'\bmy\s+(?:grades?|marks?|cgpa|gpa|results?)\b', 'what are my grades'),
            (r'how\s+are\s+my\s+grades\b', 'how are my grades'),
            (r'what\s+are\s+my\s+marks\b', 'what are my marks'),
            (r'my\s+academic\s+(?:standing|performance)\b',
             'my academic standing'),
            (r'academic\s+(?:results?|performance)\s+(?:of|for)\s+[A-Z]',
             'academic results of Aarav Patel'),
            (r'\bsemester\s+result\b', 'my semester result'),
        ),
    },
    {
        'domain': 'timetable',
        'intent': 'timetable.view',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'\bmy\s+timetable\b', 'show my timetable'),
            (r'\b(?:show|what\s+is|what.s)\b.*\b(?:schedule|timetable)\b',
             'what is my timetable today'),
            (r'\bwhat\s+classes\s+do\s+i\s+have\b',
             'what classes do i have today'),
            (r'\bshow\s+(?:today.s|tomorrow.s|yesterday.s)?\s*classes\b',
             "show today's classes"),
        ),
    },
    {
        'domain': 'timetable',
        'intent': 'timetable.clash_check',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'\btimetable\s+clashes?\b', 'any timetable clashes'),
            (r'\bclashes?\b', 'are there clashes'),
            (r'\bconflicts?\b', 'show conflicts'),
            (r'double[\s-]booked\b', 'am i double booked'),
            (r'any\s+scheduling\s+problems?\b', 'any scheduling problems'),
            (r'(?:show|check)\s+(?:me\s+)?scheduling\s+problems?\b',
             'check scheduling problems'),
            (r'are\s+there\s+any\s+(?:clashes|conflicts)\b',
             'are there any clashes'),
            (r'clash\s+check\b', 'run a clash check'),
        ),
    },
    {
        'domain': 'admission',
        'intent': 'admission.followup_list',
        'mode': 'aggregate',
        'specificity': 'domain',
        'phrases': (
            (r'(?:show|list)\s+(?:me\s+)?(?:today.s\s+)?'
             r'(?:pending\s+)?follow[ -]?ups?'
             r'(?:\s+due\s+today)?\b',
             "show today's pending follow-ups"),
            (r'how\s+many\s+follow[ -]?ups?\s+'
             r'(?:are\s+)?(?:due\s+today|pending\s+today)\b',
             'how many follow-ups are due today'),
            (r'how\s+many\s+follow[ -]?ups?\s+(?:are\s+)?overdue\b',
             'how many follow-ups are overdue'),
            (r'which\s+applicants?\s+have\s+overdue\s+follow[ -]?ups?\b',
             'which applicants have overdue follow-ups'),
        ),
    },
    {
        'domain': 'grievance',
        'intent': 'grievance.summary',
        'mode': 'aggregate',
        'specificity': 'domain',
        'phrases': (
            (r'(?:summari[sz]e|summary\s+of)\s+(?:the\s+)?'
             r'(?:grievances?|complaints?)\b',
             'summarize grievance volume by category'),
            (r'how\s+many\s+(?:grievances?|complaints?)\b',
             'how many grievances are open'),
            (r'(?:show|list)\s+(?:the\s+)?grievances?\s+by\s+category\b',
             'show grievances by category'),
        ),
    },
    {
        'domain': 'admission',
        'intent': 'admission.applicant_list',
        'mode': 'aggregate',
        'specificity': 'domain',
        'phrases': (
            (r'how\s+many\s+applicants?\s+(?:are\s+)?'
             r'(?:currently\s+)?in\s+'
             r'(?:the\s+)?inquiry\s+stage\b',
             'how many applicants are in inquiry stage'),
            (r'how\s+many\s+applicants?\s+(?:are\s+)?pending\b',
             'how many applicants are pending'),
            (r'(?:show|list|which)\s+(?:me\s+)?applicants?\s+'
             r'(?:without\s+(?:any\s+)?follow[ -]?ups?|'
             r'who\s+need\s+follow[ -]?ups?)',
             'show applicants without follow-ups'),
            (r'(?:show|list)\s+(?:me\s+)?[A-Za-z][A-Za-z0-9.&/-]{1,24}'
             r'\s+applicants?\b', 'show B.Com applicants'),
        ),
    },
    {
        'domain': 'admission',
        'intent': 'admission.program_search',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'what\s+can\s+i\s+(?:study|apply\s+for)\b', 'what can i study'),
            (r'courses?\s+available\s+for\s+admission\b',
             'courses available for admission'),
            (r'programs?\s+open\s+for\s+admission\b',
             'programs open for admission'),
            (r'\bprograms?\s+(?:are\s+)?offered\b', 'what programs are offered'),
            (r'\bdegrees?\s+(?:are\s+)?offered\b', 'which degrees are offered'),
            (r'list\s+(?:the\s+)?(?:programs?|degrees?|courses?)\b',
             'list the programs'),
        ),
    },
    # Generic entity layer (Phase G4): DISCOVERY ONLY. The two intents
    # are self-describing (no NL→filter mapping needed) and grant-checked
    # at execution. ``entity.search`` stays deliberately OFF this
    # catalogue: its model/filter parameters arrive only as a validated
    # LLM proposal (fail-closed), never as a keyword guess.
    {
        'domain': 'meta',
        'intent': 'entity.list_actions',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'what\s+actions\s+(?:can|could|does)\s+(?:the\s+)?'
             r'(?:ai|assistant|erp)\s+(?:perform|do|run|support|have)\b',
             'what actions can the AI perform on records'),
            (r'which\s+record\s+actions\s+(?:are|were)\s+available\b',
             'which record actions are available'),
            (r'list\s+the\s+record\s+actions\b',
             'list the record actions'),
        ),
    },
    {
        'domain': 'meta',
        'intent': 'entity.list_models',
        'mode': 'single',
        'specificity': 'domain',
        'phrases': (
            (r'what\s+(?:information|data)\s+can\s+(?:you|i|we|the\s+ai)\s+'
             r'(?:access|see|query|fetch|read|ask\s+about)\b',
             'what information can you access'),
            (r'which\s+entities\s+can\s+(?:you|i|we)\s+(?:access|query|'
             r'search|ask\s+about)\b',
             'which entities can you query'),
            (r'what\s+data\s+can\s+i\s+ask\s+about\b',
             'what data can i ask about'),
        ),
    },
)


#: Aggregate phrasings are matched before the per-entity ones: a cohort
#: question must never be read as a student-name question.
AGGREGATE_INTENTS = tuple(
    entry['intent'] for entry in QUESTION_CATALOGUE
    if entry['mode'] == 'aggregate'
)

#: Every intent the catalogue routes to (used by the coverage test).
CATALOGUE_INTENTS = tuple(
    sorted({entry['intent'] for entry in QUESTION_CATALOGUE})
)

#: Matcher order: aggregate+domain, aggregate+fallback, then per-entity.
#: (A domain-specific phrasing always beats a topic-less fallback.)
CATALOGUE_PATTERNS = tuple(
    (entry['intent'], tuple(pattern for pattern, _sample in entry['phrases']))
    for entry in sorted(
        QUESTION_CATALOGUE,
        key=lambda e: (
            0 if (e['mode'] == 'aggregate'
                  and e.get('specificity') == 'domain') else
            1 if e['mode'] == 'aggregate' else
            2
        ),
    )
)

#: (pattern, example sentence) pairs — the examples double as the
#: regression corpus of the coverage test.
CATALOGUE_EXAMPLES = tuple(
    (entry['intent'], pattern, sample)
    for entry in QUESTION_CATALOGUE
    for pattern, sample in entry['phrases']
)
