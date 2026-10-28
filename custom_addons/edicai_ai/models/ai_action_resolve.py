"""Phases 2A/2B — strict action schemas, extraction and resolution helpers.

Everything here is DETERMINISTIC and ADVISORY-input only:

* ``validate_action_entities`` (2A) / ``validate_followup_entities``
  (2B) — schema validation for LLM-proposed entities (unknown fields /
  wrong types / oversizes REJECT the whole proposal; nothing is ever
  repaired by trimming, mirroring the Phase 1B rule).
* ``extract_fields`` / ``extract_followup_fields`` — deterministic
  labeled/regex extraction of what a user actually typed (no LLM on
  the confirm path).
* ``resolve_entities`` / ``resolve_applicant`` — record-rule-respecting
  searches (NO sudo) that turn name hints into candidate/unique
  records. Names are SEARCH HINTS ONLY (prompt §7): zero candidates →
  not found, several → clarify. Never a silent pick.
* ``parse_followup_date`` — deterministic natural-language due-date
  phrase resolution anchored on Odoo's user-local ``today``.
"""

import re
from datetime import date, datetime, timedelta

from odoo import api, fields, models

# ---------------------------------------------------------------------------
# Action contract (strict)
# ---------------------------------------------------------------------------

ACTION_DRAFT_INQUIRY = 'admission.draft_inquiry'

ACTION_SCHEDULE_FOLLOWUP = 'admission.schedule_followup'

ACTION_FIELDS = (
    'name', 'email', 'mobile', 'gender', 'date_of_birth',
    'cycle', 'program', 'campus', 'notes',
)
REQUIRED_FIELDS = (
    'name', 'email', 'mobile', 'gender', 'date_of_birth',
    'cycle', 'program', 'campus',
)

# --- Phase 2B: second (still exactly one) write action -------------
# The canonical business operation is ``activity_schedule`` on
# ``edicai.admission.applicant`` (mail.activity.mixin) with the To-Do
# activity type.  Its real fields are: ``res_id`` (the applicant), a
# DATE ``date_deadline`` (mail.activity stores a day, never a time) and
# a free-text note/summary.  The schema below mirrors exactly that —
# nothing invented.
FOLLOWUP_FIELDS = ('applicant', 'date', 'purpose')

#: Phase G2 — generic entity create/update. The canonical payload is
#: (model, values, record_id); ``values`` itself is validated+coerced
#: JSON by edicai.ai.entity.tools (preview AND confirm time).
ACTION_ENTITY_CREATE = 'entity.create'
ACTION_ENTITY_UPDATE = 'entity.update'
#: Phase G3 — execute ONE code-declared record action (never a free
#: method name: see models/ai_entity_actions.py).
ACTION_ENTITY_EXECUTE = 'entity.execute'
ENTITY_FIELDS = ('model', 'values', 'record_id')
ENTITY_EXECUTE_FIELDS = ('model', 'entity_action', 'record_id', 'params')
FOLLOWUP_REQUIRED_FIELDS = ('applicant', 'date')

_FOLLOWUP_FIELD_LIMITS = {
    'applicant': 120,
    'date': 60,
    'purpose': 200,
}

_FIELD_LIMITS = {
    'name': 120,
    'email': 120,
    'mobile': 15,
    'gender': 10,
    'date_of_birth': 10,
    'cycle': 120,
    'program': 60,
    'campus': 60,
    'notes': 200,
}

_GENDERS = ('male', 'female', 'other', 'prefer_not')

_GENDER_SYNONYMS = {
    'prefer not to say': 'prefer_not',
    'prefer not': 'prefer_not',
    'prefer not say': 'prefer_not',
}

_GENDER_LABELS = {
    'male': 'Male',
    'female': 'Female',
    'other': 'Other',
    'prefer_not': 'Prefer not to say',
}

_EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')

_DOB_FORMATS = (
    '%Y-%m-%d', '%Y/%m/%d',
    '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
    '%d %b %Y', '%d %B %Y',
    '%b %d, %Y', '%B %d, %Y',
)

# ---------------------------------------------------------------------------
# Request detection (edit distance zero: literal phrases only)
# ---------------------------------------------------------------------------

_ACTION_REQUEST_PATTERNS = (
    # "create an admission inquiry", "draft an application", "raise an
    # admission enquiry", "add an applicant"...
    (r'\b(?:raise|log|submit|start|draft|create|add|register|make|open)'
     r'[^.;?!]{0,40}?\b(?:admission\s+)?(?:inquiry|enquiry|application'
     r'|applicant)\b'),
    # "... inquiry/application for/about <program>"
    (r'\b(?:admission\s+)?(?:inquiry|enquiry|application)\s+'
     r'(?:for|about|regarding)\b'),
    # "I want to apply / enquire ..."
    (r'\bi\s+(?:want|would\s+like|wish|need)\s+to\s+'
     r'(?:apply|enquir|inquir|register|admit)'),
    # "apply for <known degree family>"
    (r'\bapply\s+for\s+(?:the\s+)?(?:program|course|admission|'
     r'b\.?tech|b\.?e\b|bba|bca|mba|mca|m\.?tech|b\.?com|b\.?sc|b\.?a\b'
     r'|m\.?sc|m\.?a\b|diploma)'),
    # "admission form"
    r'\b(?:admission|application)\s+form\b',
)

_ACTION_REQUEST_RE = re.compile(
    '|'.join('(?:%s)' % p for p in _ACTION_REQUEST_PATTERNS), re.I)

# Generic request noise removed BEFORE hint matching: leftover text
# like "create a new admission inquiry about physics" must hint
# "physics", not the whole sentence.
_HINT_NOISE_RE = re.compile(
    r'\b(?:create|draft|start|open|make|add|raise|log|register|submit'
    r'|help|new|about|for|regarding|admission|enquiry|inquiry|enquire'
    r'|inquire|application|applicant|form|please|college|study'
    r'|program|course|want|wish|need|like|would|could|can|you|me|i'
    r'|to|a|an|the|my|friend|up|sign|apply|and|of|do|setup|set)\b',
    re.I)

# Read-only phrasings that would otherwise collide with the write
# detection above (Phase 1A program search surface).
_ACTION_REQUEST_NEGATIVE_RE = re.compile(
    r'what\s+can\s+i\s+(?:study|apply\s+for)'
    r'|courses?\s+available\s+for\s+admission'
    r'|programs?\s+open\s+for\s+admission'
    r'|(?:status|track)\s+of\s+(?:my\s+)?(?:application|inquiry)'
    r'|(?:what\s+is\s+)?(?:the\s+)?status\s+(?:of|for)\s+'
    r'(?:the\s+)?(?:application|inquiry|applicant)\b'
    r'|my\s+(?:application|inquiry)\s+status',
    re.I)

# Write-specific injection probes (Phase 1A already refuses these when
# the action flag is OFF; once writes exist they must be refused here
# too, BEFORE any preview/confirm logic can look at them).
_ACTION_ADVERSARIAL_PATTERNS = re.compile(
    r'ignore\s+(?:the\s+)?confirmation'
    r'|skip\s+(?:the\s+)?confirmation'
    r'|without\s+(?:the\s+)?(?:confirmation|preview)'
    r'|don.t\s+show\s+(?:me\s+)?(?:the\s+)?preview'
    r'|execute\s+(?:the\s+)?action\s+without'
    r'|create\s+it\s+without'
    r'|pretend\s+i\s+(?:already\s+)?(?:have\s+)?confirmed'
    r'|pretend\s+i\s+already\s+(?:said\s+)?yes'
    r'|administrators?\s+(?:have\s+|has\s+)?approved'
    r'|(?:the\s+)?admin\s+(?:said\s+|approved)',
    re.I)

# ---------------------------------------------------------------------------
# Phase 2B — follow-up request detection (literal phrases only)
# ---------------------------------------------------------------------------

_FOLLOWUP_REQUEST_PATTERNS = (
    # "schedule a follow-up", "set a follow up", "book a follow-up"
    (r'\b(?:schedule|set|book|create|add|plan|arrange|put)\b'
     r'[^.;?!]{0,30}?\bfollow[-\s]?ups?\b'),
    # "follow up with <applicant>" / "follow-up for ..."
    (r'\bfollow[-\s]?ups?\b[^.;?!]{0,60}?\b(?:with|for|to)\b'),
    # "remind the admission team to follow up ..."
    (r'\bremind\b[^.;?!]{0,60}?\bfollow[-\s]?up'),
)

_FOLLOWUP_REQUEST_RE = re.compile(
    '|'.join('(?:%s)' % p for p in _FOLLOWUP_REQUEST_PATTERNS), re.I)

# Read-only phrasings that must never open the follow-up write flow.
_FOLLOWUP_NEGATIVE_RE = re.compile(
    r'(?:show|list|see|tell|which|what|any|whose|who|where|when\b)'
    r'[^.;?!]{0,40}?\bfollow[-\s]?ups?\b'
    r'|follow[-\s]?ups?\b[^.;?!]{0,40}\b(?:due|pending|open|overdue|'
    r'status|list|scheduled)'
    r'|(?:my|the|his|her|their)\s+follow[-\s]?ups?\b',
    re.I)

# Generic request noise for follow-ups: remove scheduling verbs and
# dialogue filler so leftover segments can hint the APPLICANT.
_FOLLOWUP_NOISE_RE = re.compile(
    r'\b(?:schedule|scheduled|set|book|create|add|plan|arrange|put'
    r'|remind|reminds|reminder|follow|ups?|up|help|please|team'
    r'|admission|applicant|about|with|for|regarding|to|a|an|the|my'
    r'|our|i|you|me|we|us|at|on|by|tomorrow|today|want|wish|need|like'
    r'|would|could|can|and|of|do|next|this)\b',
    re.I)


def is_followup_request(text):
    """Deterministic detection of a follow-up scheduling request."""
    text = str(text or '')
    if not text.strip():
        return False
    if _FOLLOWUP_NEGATIVE_RE.search(text):
        return False
    return bool(_FOLLOWUP_REQUEST_RE.search(text))


# ---------------------------------------------------------------------------
# Phase 2B — deterministic date/time phrase resolution
# ---------------------------------------------------------------------------

_FOLLOWUP_DATE_CORE = (
    r'(?:\d{4}-\d{1,2}-\d{1,2}'
    r'|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}'
    r'|day\s+after\s+tomorrow'
    r'|tomorrow'
    r'|today'
    r'|(?:next\s+|this\s+|on\s+|by\s+)?'
    r'(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b'
    r')'
)
_FOLLOWUP_TIME_CORE = (
    r'(?:\b(?:at|by)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?'
    r'|\b\d{1,2}:\d{2}\b)'
)
_FOLLOWUP_DATE_SPAN_RE = re.compile(
    _FOLLOWUP_DATE_CORE +
    r'(?:\s+' + _FOLLOWUP_TIME_CORE + r')?', re.I)

_FOLLOWUP_TIME_RE = re.compile(
    r'(?:\b(?:at|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
    r'|\b(\d{1,2}):(\d{2})\b)', re.I)

_WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}

_FOLLOWUP_MAX_DAYS_AHEAD = 365

_FOLLOWUP_DATE_FORMATS = (
    '%Y-%m-%d', '%Y/%m/%d',
    '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
)


def parse_followup_date(phrase, today=None):
    """Deterministically resolve a natural-language due DATE phrase.

    The canonical business field (``mail.activity.date_deadline``)
    stores a DAY, never a time.  A requested time-of-day, when the user
    supplied one, is returned as a normalized ``HH:MM`` string so the
    layer can store it deterministically in the activity note — it is
    NEVER used to invent a datetime the model cannot hold.

    Deterministic rules (documented, no LLM involvement):
    * ``today`` / ``tomorrow`` / ``day after tomorrow`` — anchored on
      the caller's ``today`` (Odoo ``fields.Date.context_today``, i.e.
      the requesting user's timezone).
    * a bare weekday resolves to the NEXT occurrence strictly after
      today (``this X`` is the same; ``next X`` is that occurrence
      one week later).
    * explicit dates: ISO ``YYYY-MM-DD`` or day-first ``DD-MM-YYYY``
      (also ``/`` and ``.`` separators).
    * the date must be in the future and at most 365 days ahead.
    * an explicit 24h clock time or ``at hh[:mm] [am|pm]`` normalizes
      to ``HH:MM``; nonsense times invalidate the phrase.

    :returns: ``(state, iso, time_str)`` with state ``'ok'`` /
        ``'invalid'`` / ``'missing'``; ``iso`` is ``YYYY-MM-DD``.
    """
    if not phrase or not isinstance(phrase, str):
        return 'missing', None, None
    text = re.sub(r'\s+', ' ', phrase.strip())
    if not text:
        return 'missing', None, None

    # ---- date part ---------------------------------------------------
    date_iso = None
    match = re.search(
        r'\b(\d{4}-\d{1,2}-\d{1,2})\b', text)
    if match:
        try:
            part = datetime.strptime(match.group(1), '%Y-%m-%d').date()
        except ValueError:
            part = None
        date_iso = part
    if date_iso is None:
        match = re.search(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b', text)
        if match:
            try:
                part = date(
                    int(match.group(3)), int(match.group(2)),
                    int(match.group(1)))
            except ValueError:
                part = None
            date_iso = part
    if date_iso is None:
        low = text.lower()
        anchor = today or date.today()
        match = re.search(r'\b(today|tomorrow|day after tomorrow)\b', low)
        if match:
            if match.group(1) == 'today':
                date_iso = anchor
            elif match.group(1) == 'tomorrow':
                date_iso = anchor + timedelta(days=1)
            else:
                date_iso = anchor + timedelta(days=2)
        else:
            match = re.search(
                r'\b(next\s+|this\s+|on\s+)?'
                r'(monday|tuesday|wednesday|thursday|friday|saturday'
                r'|sunday)\b', low)
            if not match:
                return 'invalid', None, None
            target = _WEEKDAYS[match.group(2)]
            ahead = (target - anchor.weekday()) % 7
            if ahead == 0:
                # Next occurrence strictly after today.
                ahead = 7
            date_iso = anchor + timedelta(days=ahead)
            if (match.group(1) or '').strip() == 'next':
                date_iso = date_iso + timedelta(days=7)
    if date_iso is None:
        return 'invalid', None, None

    # Sanity window: a follow-up deadline is always future-bounded.
    anchor = today or date.today()
    if date_iso <= anchor or \
            date_iso > anchor + timedelta(days=_FOLLOWUP_MAX_DAYS_AHEAD):
        return 'invalid', None, None

    # ---- optional time-of-day (normalized, stored as note text) ------
    time_str = None
    match = _FOLLOWUP_TIME_RE.search(text)
    if match:
        if match.group(1):
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            meridiem = (match.group(3) or '').lower()
            if meridiem == 'am' and hour == 12:
                hour = 0
            elif meridiem == 'pm' and hour != 12:
                hour += 12
            if meridiem in ('am', 'pm') and hour > 23:
                return 'invalid', None, None
            if not meridiem and hour > 23:
                return 'invalid', None, None
        else:
            hour = int(match.group(4))
            minute = int(match.group(5))
        if minute > 59:
            return 'invalid', None, None
        time_str = '%02d:%02d' % (hour, minute)
    return 'ok', date_iso.isoformat(), time_str


def validate_followup_entities(raw):
    """Strict schema validation for LLM-proposed follow-up entities.

    Same reject-the-whole-proposal semantics as the Phase 2A action:
    unknown keys, non-string values and oversizes REJECT the offending
    field(s). Dates are NOT parsed here — natural-language phrases are
    resolved deterministically at resolution time (they depend on the
    requesting user's timezone anchor).
    """
    clean = {}
    invalid = []
    if raw is None:
        return clean, True, invalid
    if not isinstance(raw, dict):
        return {}, False, ['entities']
    extra = set(raw) - set(FOLLOWUP_FIELDS)
    if extra:
        return {}, False, [
            'unknown_fields:%s' % ','.join(sorted(extra))]
    for field in FOLLOWUP_FIELDS:
        value = raw.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if not isinstance(value, str):
            invalid.append(field)
            continue
        value = re.sub(r'\s+', ' ', value.strip())
        if not value:
            continue
        if len(value) > _FOLLOWUP_FIELD_LIMITS[field]:
            # No trimming: oversized values invalidate the field.
            invalid.append(field)
            continue
        if field == 'date':
            # A draft must not retain an impossible explicit calendar
            # date. Relative language remains timezone-anchored and is
            # resolved by parse_followup_date at the server boundary.
            explicit = re.search(
                r'\b(\d{4}-\d{1,2}-\d{1,2}|'
                r'\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b', value)
            if explicit:
                token = explicit.group(1)
                formats = ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y',
                           '%d.%m.%Y')
                valid_calendar_date = False
                for fmt in formats:
                    try:
                        datetime.strptime(token, fmt)
                        valid_calendar_date = True
                        break
                    except ValueError:
                        continue
                if not valid_calendar_date:
                    invalid.append(field)
                    continue
        clean[field] = value
    return clean, not invalid, invalid


def missing_followup_fields(payload):
    """Fields of the follow-up REQUIRED set absent from ``payload``."""
    return [f for f in FOLLOWUP_REQUIRED_FIELDS
            if not (payload or {}).get(f)]




_GENDER_RE = re.compile(
    r'\b(prefer\s+not\s+to\s+say|prefer\s+not|female|male|other)\b', re.I)

_PHONE_RE = re.compile(
    r'(?<![\d])(\+\d[\d\- ]{8,22}?\d|\d[\d\- ]{9,22}?\d)(?![\d])')


def _normalized_indian_mobile(value):
    """Normalize supported Indian mobile spellings for LOOKUP only."""
    digits = re.sub(r'\D', '', str(value or ''))
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in '6789':
        return False
    return digits

_DOB_PATTERNS = (
    # labeled variants are tried first via the label machinery
    re.compile(r'\b(\d{4}-\d{1,2}-\d{1,2})\b'),                       # ISO
    re.compile(r'\b(\d{1,2}-\d{1,2}-\d{4})\b'),                       # d-m-y
    re.compile(r'\b(\d{1,2}/\d{1,2}/\d{4})\b'),                       # d/m/y
    re.compile(r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep'
                    r'|Oct|Nov|Dec)[a-z]*\.?,?\s+\d{4})\b', re.I),
    re.compile(r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
                    r'[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b', re.I),
)

_NAME_RE = re.compile(
    r'\b([A-Z][a-zA-Z]{1,19}(?:\s+[A-Z][a-zA-Z]{1,19}){1,3})\b')

_LABEL_PATTERNS = {
    'name': re.compile(
        r'\b(?:full\s+name|applicant\s+name|name)\s*[:\-]\s*'
        r'(?P<val>[^\n;,]{1,120})', re.I),
    'email': re.compile(
        r'\be-?mail(?:\s+is\s+|\s*[:\-]\s*)'
        r'(?P<val>[^\s\n;,]{1,120})', re.I),
    'mobile': re.compile(
        r'\b(?:mobile|phone|contact)(?:\s*(?:no\.?|number))?'
        r'(?:\s+is\s+|\s*[:\-]\s*)'
        r'(?P<val>\+?[\d][\d\- ()]{6,20}\d)', re.I),
    'gender': re.compile(
        r'\bgender(?:\s+is\s+|\s*[:\-]\s*)(?P<val>[^\n;,]{1,30})',
        re.I),
    'date_of_birth': re.compile(
        r'\b(?:d\.?o\.?b\.?|date\s+of\s+birth|birth\s+date|born'
        r'(?:\s+on)?)(?:\s+is\s+|\s*[:\-]?\s*)(?P<val>[^\n;,]{1,40})',
        re.I),
    'cycle': re.compile(
        r'\b(?:admission\s+)?cycle(?:\s+is\s+|\s*[:\-]\s*)'
        r'(?P<val>[^\n;,]{1,120})', re.I),
    'program': re.compile(
        r'\b(?:program(?:me)?|course)(?:\s+is\s+|\s*[:\-]\s*)'
        r'(?P<val>[^\n;,]{1,60})', re.I),
    'campus': re.compile(
        r'\bcampus(?:\s+is\s+|\s*[:\-]\s*)(?P<val>[^\n;,]{1,60})',
        re.I),
    'notes': re.compile(
        r'\b(?:notes?|remarks?|message)(?:\s+is\s+|\s*[:\-]\s*)'
        r'(?P<val>[^\n]{1,200})', re.I),
}

_IGNORED_NAME_PAIRS = re.compile(
    r'^(?:Test Campus|Admission|Inquiry|Application)\b', re.I)


def parse_dob(value):
    """Parse a date-of-birth string; return ISO 'YYYY-MM-DD' or None.

    Deterministic formats only (see _DOB_FORMATS); the date must be in
    the past and not older than 1900.
    """
    if not value or not isinstance(value, str):
        return None
    value = re.sub(r'\s+', ' ', value.strip())
    for fmt in _DOB_FORMATS:
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        today = date.today()
        if parsed_date >= today or parsed_date.year < 1900:
            return None
        return parsed_date.isoformat()
    return None


def validate_action_entities(raw):
    """Validate an action-proposal entity dict (LLM or extracted).

    :returns: ``(clean, ok, invalid)`` where ``clean`` maps canonical
        field → cleaned string. Unknown keys, non-string values,
        oversizes and unparseable e-mail/gender/date values REJECT the
        offending fields (``ok=False``) — never repaired by trimming.
    """
    clean = {}
    invalid = []
    if raw is None:
        return clean, True, invalid
    if not isinstance(raw, dict):
        return {}, False, ['entities']
    extra = set(raw) - set(ACTION_FIELDS)
    if extra:
        # Smuggled fields (ids, ctx, sudo, method hints...) reject the
        # WHOLE proposal — prompt §5.
        return {}, False, ['unknown_fields:%s' % ','.join(sorted(extra))]
    for field in ACTION_FIELDS:
        value = raw.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if not isinstance(value, str):
            invalid.append(field)
            continue
        value = re.sub(r'\s+', ' ', value.strip())
        if not value:
            continue
        if field == 'gender':
            # Synonyms normalize FIRST ('prefer not to say' →
            # 'prefer_not', 10 chars) so the raw phrase is never
            # measured against the canonical value's length limit.
            value = _GENDER_SYNONYMS.get(
                value.lower(), value.lower())
            if value not in _GENDERS:
                invalid.append(field)
                continue
        elif len(value) > _FIELD_LIMITS[field]:
            # No trimming: oversized values invalidate the field.
            invalid.append(field)
            continue
        if field == 'email':
            if not _EMAIL_RE.match(value):
                invalid.append(field)
                continue
            value = value.lower()
        elif field == 'date_of_birth':
            iso = parse_dob(value)
            if not iso:
                invalid.append(field)
                continue
            value = iso
        elif field == 'mobile':
            if len(value.replace(' ', '')) > _FIELD_LIMITS[field]:
                invalid.append(field)
                continue
        clean[field] = value
    return clean, not invalid, invalid


def is_action_request(text):
    """Deterministic, grammar-level detection of a draft-inquiry
    request (read-only phrasings are excluded explicitly)."""
    text = str(text or '')
    if not text.strip():
        return False
    if _ACTION_REQUEST_NEGATIVE_RE.search(text):
        return False
    return bool(_ACTION_REQUEST_RE.search(text))


def is_action_adversarial(text):
    """Write-specific adversarial probe (confirmation fakers etc.)."""
    return bool(_ACTION_ADVERSARIAL_PATTERNS.search(str(text or '')))


def extract_fields(text):
    """Deterministic field extraction from one user turn.

    Labeled values (``email: x@y.z``) win; generic patterns cover the
    assistant-directed free-form reply. Returns a VALIDATED fields
    dict (subset of ACTION_FIELDS).
    """
    text = str(text or '')
    if len(text) > 2000:
        text = text[:2000]
    fields = {}
    rest = text
    # 1 — labeled values first (they are explicit; consume their spans)
    for field, pattern in _LABEL_PATTERNS.items():
        if field in fields:
            continue
        match = pattern.search(rest)
        if not match:
            continue
        raw_val = match.group('val').strip(' \t"\'')
        clean, ok, _invalid = validate_action_entities({field: raw_val})
        if ok and field in clean:
            fields[field] = clean[field]
            rest = rest[:match.start()] + ' ' + rest[match.end():]
    # 2 — date of birth (unlabeled); consume before phone so date
    #     digits are never read as a mobile number.
    if 'date_of_birth' not in fields:
        for pattern in _DOB_PATTERNS:
            match = pattern.search(rest)
            if match:
                iso = parse_dob(match.group(1))
                if iso:
                    fields['date_of_birth'] = iso
                    rest = rest[:match.start()] + ' ' + rest[match.end():]
                    break
    # 3 — e-mail (unlabeled)
    if 'email' not in fields:
        match = re.search(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
                          rest)
        if match:
            clean, ok, _invalid = validate_action_entities(
                {'email': match.group(0)})
            if ok and 'email' in clean:
                fields['email'] = clean['email']
                rest = rest[:match.start()] + ' ' + rest[match.end():]
    # 4 — gender (unlabeled)
    if 'gender' not in fields:
        match = _GENDER_RE.search(rest)
        if match:
            clean, ok, _invalid = validate_action_entities(
                {'gender': match.group(1)})
            if ok and 'gender' in clean:
                fields['gender'] = clean['gender']
                rest = rest[:match.start()] + ' ' + rest[match.end():]
    # 5 — mobile (unlabeled); needs >= 10 digits (or a leading +) so a
    #     plain year is never mistaken for a phone.
    if 'mobile' not in fields:
        match = _PHONE_RE.search(rest)
        if match:
            candidate = match.group(1).strip()
            digits = len(re.sub(r'\D', '', candidate))
            if digits >= 10 or candidate.startswith('+'):
                clean, ok, _invalid = validate_action_entities(
                    {'mobile': re.sub(r'\s+', ' ', candidate)})
                if ok and 'mobile' in clean:
                    fields['mobile'] = clean['mobile']
                    rest = rest[:match.start()] + ' ' + rest[match.end():]
    # 6 — name (unlabeled): 2–4 capitalized words only.
    if 'name' not in fields:
        match = _NAME_RE.search(rest)
        if match and not _IGNORED_NAME_PAIRS.match(match.group(1)):
            clean, ok, _invalid = validate_action_entities(
                {'name': match.group(1)})
            if ok and 'name' in clean:
                fields['name'] = clean['name']
                rest = rest[:match.start()] + ' ' + rest[match.end():]
    return fields, rest


_FOLLOWUP_LABEL_PATTERNS = {
    'applicant': re.compile(
        r'\b(?:applicant(?:\s+name)?|about|with|contact)\s*[:\-]\s*'
        r'(?P<val>[^\n;,]{1,120})', re.I),
    'purpose': re.compile(
        r'\b(?:purpose|reason|note|notes|remarks|message|summary)'
        r'\s*[:\-]\s*(?P<val>[^\n]{1,200})', re.I),
}


def extract_followup_date_phrase(text):
    """Pull the literal date+time span out of a turn (first match).

    :returns: ``(phrase, remaining_text)``; the phrase is the matched
        span verbatim (e.g. ``'tomorrow at 11 AM'``), so it can be
        stored in the canonical payload and re-resolved later.
    """
    match = _FOLLOWUP_DATE_SPAN_RE.search(str(text or ''))
    if not match:
        return None, str(text or '')
    phrase = match.group(0).strip()
    remaining = text[:match.start()] + ' ' + text[match.end():]
    return phrase, remaining


def extract_followup_fields(text):
    """Deterministic follow-up field extraction from one user turn.

    Order matters: explicit date words are consumed FIRST so they are
    never mistaken for an applicant name, then labeled values, then
    e-mail / phone / capitalized-name hints for the applicant.
    :returns: ``(fields, rest)`` — fields already schema-validated.
    """
    text = str(text or '')
    if len(text) > 2000:
        text = text[:2000]
    fields = {}
    rest = text

    # 1 — the date/time span (consumed before everything else)
    phrase, rest = extract_followup_date_phrase(rest)
    if phrase:
        clean, ok, _invalid = validate_followup_entities({'date': phrase})
        if ok and 'date' in clean:
            fields['date'] = clean['date']

    # 2 — labeled applicant / purpose values (explicit spans first)
    for field, pattern in _FOLLOWUP_LABEL_PATTERNS.items():
        if field in fields:
            continue
        match = pattern.search(rest)
        if not match:
            continue
        raw_val = match.group('val').strip(' \t"\'')
        clean, ok, _invalid = validate_followup_entities({field: raw_val})
        if ok and field in clean:
            fields[field] = clean[field]
            rest = rest[:match.start()] + ' ' + rest[match.end():]

    # 3 — e-mail hint for the applicant
    if 'applicant' not in fields:
        match = re.search(
            r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', rest)
        if match:
            clean, ok, _invalid = validate_followup_entities(
                {'applicant': match.group(0)})
            if ok and 'applicant' in clean:
                fields['applicant'] = clean['applicant']
                rest = rest[:match.start()] + ' ' + rest[match.end():]

    # 4 — mobile hint (>= 10 digits) for the applicant
    if 'applicant' not in fields:
        match = _PHONE_RE.search(rest)
        if match:
            candidate = match.group(1).strip()
            digits = len(re.sub(r'\D', '', candidate))
            if digits >= 10 or candidate.startswith('+'):
                clean, ok, _invalid = validate_followup_entities(
                    {'applicant': re.sub(r'\s+', ' ', candidate)})
                if ok and 'applicant' in clean:
                    fields['applicant'] = clean['applicant']
                    rest = rest[:match.start()] + ' ' + rest[match.end():]

    # 5 — capitalized full name hint for the applicant
    if 'applicant' not in fields:
        match = _NAME_RE.search(rest)
        if match and not _IGNORED_NAME_PAIRS.match(match.group(1)):
            clean, ok, _invalid = validate_followup_entities(
                {'applicant': match.group(1)})
            if ok and 'applicant' in clean:
                fields['applicant'] = clean['applicant']
                rest = rest[:match.start()] + ' ' + rest[match.end():]
    return fields, rest


def missing_fields(payload):
    """Fields of the REQUIRED set absent from ``payload``."""
    return [f for f in REQUIRED_FIELDS if not payload.get(f)]


class EdicaiAIActionResolve(models.AbstractModel):
    """Deterministic entity resolution for the draft-inquiry action."""

    _name = 'edicai.ai.action.resolve'
    _description = 'AI Action Resolution (strict, no sudo)'

    # ------------------------------------------------------------------
    # Per-field resolution (record rules respected; env of the caller)
    # ------------------------------------------------------------------

    @api.model
    def resolve_program(self, hint, company):
        """Program names are search hints: unique → record, otherwise
        (0 / several) the caller must not guess."""
        hint = str(hint or '').strip()
        if not hint:
            return 'missing', self.env['edicai.program'], []
        Program = self.env['edicai.program']
        matches = Program.search([
            ('company_id', '=', company.id),
            ('program_state', '=', 'active'),
            ('code', '=', hint.upper()),
        ])
        if len(matches) != 1:
            matches = Program.search([
                ('company_id', '=', company.id),
                ('program_state', '=', 'active'),
                ('name', 'ilike', hint),
            ])
        return self._verdict(matches)

    @api.model
    def resolve_campus(self, hint, company):
        hint = str(hint or '').strip()
        if not hint:
            return 'missing', self.env['edicai.campus'], []
        Campus = self.env['edicai.campus']
        matches = Campus.search([
            ('company_id', '=', company.id),
            ('code', '=', hint.upper()),
        ])
        if len(matches) != 1:
            matches = Campus.search([
                ('company_id', '=', company.id),
                ('name', 'ilike', hint),
            ])
        return self._verdict(matches)

    @api.model
    def resolve_cycle(self, hint, company):
        hint = str(hint or '').strip()
        if not hint:
            return 'missing', self.env['edicai.admission.cycle'], []
        Cycle = self.env['edicai.admission.cycle']
        matches = Cycle.search([
            ('company_id', '=', company.id),
            ('state', '=', 'active'),
            ('code', '=', hint),
        ])
        if len(matches) != 1:
            matches = Cycle.search([
                ('company_id', '=', company.id),
                ('state', '=', 'active'),
                ('name', 'ilike', hint),
            ])
        return self._verdict(matches)

    @api.model
    def match_hint_fields(self, text, payload=None):
        """Try to fill MISSING action fields from leftover turn text.

        Each comma/line-separated segment of the leftover text is a
        SEARCH HINT for program / campus / cycle (prompt §7): it is
        merged ONLY when the field is still missing AND the hint
        resolves UNIQUELY under record rules. Ambiguous hints are
        never merged — the clarify loop asks the user instead.
        """
        payload = payload or {}
        import re as _re
        hints = {}
        cleaned = _HINT_NOISE_RE.sub(' ', str(text or ''))
        segments = [
            seg.strip(' \t.;.-·—') for seg in
            _re.split(r'[,\n;]', cleaned)]
        resolvers = {
            'program': (self.resolve_program, 60),
            'campus': (self.resolve_campus, 60),
            'cycle': (self.resolve_cycle, 120),
        }
        company = self.env.company
        for kind, (resolver, limit) in resolvers.items():
            if payload.get(kind):
                continue
            for seg in segments:
                if len(seg) < 3 or len(seg) > limit:
                    continue
                if not _re.search(r'[A-Za-z0-9]', seg):
                    continue
                status, _rec, _names = resolver(seg, company)
                if status == 'ok':
                    hints[kind] = seg
                    break
        return hints

    @api.model
    def resolve_applicant(self, hint, company):
        """Applicant names are SEARCH HINTS: unique → record,
        otherwise (0 / several) the caller must never guess.

        Search order: e-mail → mobile → application number → name,
        all scoped to the requesting user's company and existing
        record rules (the company-isolation rule on the applicant
        applies automatically — NO sudo).
        """
        hint = str(hint or '').strip()
        if not hint:
            return 'missing', self.env['edicai.admission.applicant'], []
        Applicant = self.env['edicai.admission.applicant']
        if _EMAIL_RE.match(hint):
            matches = Applicant.search([
                ('company_id', '=', company.id),
                ('email', '=', hint.strip().lower()),
            ])
            if len(matches) == 1:
                return self._verdict(matches)
        digits = _normalized_indian_mobile(hint)
        if digits:
            # Stored values and conversational input may use different
            # country-code/separator formats. Compare normalized digits
            # only after a company- and rule-scoped ORM search.
            candidates = Applicant.search([
                ('company_id', '=', company.id),
                ('mobile', '!=', False),
            ], limit=5001)
            matches = candidates.filtered(
                lambda applicant: _normalized_indian_mobile(
                    applicant.mobile) == digits)
            if len(matches) == 1:
                return self._verdict(matches)
            if len(matches) > 1:
                return self._verdict(matches)
        # Backward-compatible exact lookup for legacy stored values that
        # are not valid Indian mobiles. New values remain schema-validated;
        # this branch only compares an explicit user hint to existing data.
        matches = Applicant.search([
            ('company_id', '=', company.id),
            ('mobile', '=ilike', hint),
        ])
        if matches:
            return self._verdict(matches)
        matches = Applicant.search([
            ('company_id', '=', company.id),
            ('application_number', '=', hint),
        ])
        if len(matches) != 1:
            matches = Applicant.search([
                ('company_id', '=', company.id),
                '|', '|',
                ('name', 'ilike', hint),
                ('middle_name', 'ilike', hint),
                ('last_name', 'ilike', hint),
            ], limit=501)
        return self._verdict(matches)

    @api.model
    def resolve_followup(self, payload, company=None):
        """Resolve the full required set for a follow-up payload.

        :returns: one of
            ``{'status': 'ok', 'applicant': rec,
               'date_iso': 'YYYY-MM-DD', 'time': 'HH:MM'|None}``
            ``{'status': 'missing', 'missing': [...], 'invalid': []}``
            ``{'status': 'clarify', 'field', 'candidates'}``
            ``{'status': 'not_found', 'field'}``
        """
        payload = payload or {}
        missing = missing_followup_fields(payload)
        if missing:
            return {'status': 'missing', 'missing': missing}
        status, applicant, candidates = self.resolve_applicant(
            payload.get('applicant'), company or self.env.company)
        if status == 'ambiguous':
            return {'status': 'clarify', 'field': 'applicant',
                    'candidates': candidates}
        if status == 'not_found':
            return {'status': 'not_found', 'field': 'applicant'}
        if status == 'missing':
            return {'status': 'missing', 'missing': ['applicant']}
        # Anchored on Odoo's user-local ``today`` — the existing
        # timezone behaviour of the mail.activity mixin, never a
        # parallel system.
        state, date_iso, time_str = parse_followup_date(
            payload.get('date'),
            today=fields.Date.context_today(self))
        if state == 'missing':
            return {'status': 'missing', 'missing': ['date']}
        if state != 'ok':
            return {'status': 'invalid_date', 'field': 'date'}
        return {'status': 'ok', 'applicant': applicant,
                'date_iso': date_iso, 'time': time_str or None}

    @api.model
    def _verdict(self, matches):
        if len(matches) == 1:
            return 'ok', matches[0], []
        if not matches:
            return 'not_found', matches, []
        names = []
        for rec in matches[:5]:
            if rec.display_name not in names:
                names.append(rec.display_name)
        return 'ambiguous', matches, names

    @api.model
    def resolve_entities(self, payload, company=None):
        """Resolve the full required set for one payload.

        :returns: one of
            ``{'status': 'ok', 'resolved': {...records...}}``
            ``{'status': 'missing', 'missing': [...]}``
            ``{'status': 'clarify', 'field', 'candidates'}``
            ``{'status': 'not_found', 'field'}``
        """
        company = company or self.env.company
        missing = missing_fields(payload or {})
        if missing:
            return {'status': 'missing', 'missing': missing}
        resolved = {}
        for field, resolver in (
                ('program', self.resolve_program),
                ('campus', self.resolve_campus),
                ('cycle', self.resolve_cycle)):
            status, record, candidates = resolver(payload.get(field), company)
            if status == 'ok':
                resolved[field] = record
                continue
            if status == 'missing':
                return {'status': 'missing',
                        'missing': list(missing) or [field]}
            if status == 'ambiguous':
                return {'status': 'clarify', 'field': field,
                        'candidates': candidates}
            return {'status': 'not_found', 'field': field}
        return {'status': 'ok', 'resolved': resolved}

    @api.model
    def extract_and_validate(self, text):
        """Convenience: extraction + validation in one call.

        :returns: ``(fields, rest, invalid)``.
        """
        fields, rest = extract_fields(text)
        clean, ok, invalid = validate_action_entities(fields)
        if not ok:
            return {}, rest, invalid
        return clean, rest, []
