"""Phase 3 — ONE conversational WORKFLOW: ``admission.prepare_followups``.

Phases 2A/2B proved single confirmed writes.  This module proves the
NEXT step — a bounded multi-operation plan composed of ALREADY-PROVEN
actions:

    goal → discovery (read-only) → deterministic plan → validation
         → preview → action-bound confirmation → re-authorization
         → bounded execution of ONE ``admission.schedule_followup``
           action per candidate (the EXISTING Phase 2B path)
         → per-operation verification → accurate result report

Repository-derived candidate rule (NOT invented):
    an ``edicai.admission.applicant`` requires follow-up when it is in a
    NON-TERMINAL admission state (anything from which
    ``ALLOWED_TRANSITIONS`` still has moves — terminal states
    confirmed/rejected/withdrawn are excluded) and it has NO open
    ``mail.activity`` (nothing currently pending on the record).
    Candidates are scoped to the requesting user's company and found
    under the user's OWN record rules; the oldest ones first.

Safety invariants (prompt §2/§12/§18/§20):

* discovery is PURE READ; nothing mutates before confirmation.
* the LLM never chooses records: it may only propose the optional
  ``date`` phrase, ``purpose`` and ``limit`` — all strictly validated;
  record identities come from application discovery alone.
* execution creates a CHILD ``edicai.ai.pending.action`` row (Phase 2B)
  per candidate and runs its ``confirm_and_execute`` — there is NO
  second business implementation of ``admission.schedule_followup``.
* per-operation savepoints keep the transaction usable; one failing
  operation never claims success for others (each operation is fully
  independent, so continuing is demonstrably deterministic-safe).
* idempotency: existing row lock + status re-check; a PARTIAL workflow
  re-confirms by skipping already-verified operations, backed by a
  deterministic already-scheduled re-check on mail.activity.
* re-authorization runs INSIDE ``confirm_and_execute`` (second gate).
* hard limit of 20 operations; never silently truncated — the preview
  states the found-vs-planned counts when more candidates exist.
* FAIL-CLOSED everywhere; NO sudo on business records; record rules
  always applied.
"""

import hashlib
import json
import logging
import re
from datetime import timedelta

import psycopg2

from odoo import _, api, fields, models

from odoo.addons.edicai_ai.models.ai_action_resolve import (
    ACTION_SCHEDULE_FOLLOWUP,
    parse_followup_date,
)
from odoo.addons.edicai_ai.models.ai_error import (
    AUTHORIZATION_DENIED,
    SAFE_MESSAGES,
    VALIDATION_FAILED,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Workflow contract (strict)
# ---------------------------------------------------------------------------

WORKFLOW_NAME = 'admission.prepare_followups'

#: Understanding-layer alias of the workflow allow-list name.
ACTION_PREPARE_FOLLOWUPS = WORKFLOW_NAME

#: The ONLY optional, strictly typed inputs of this one workflow.  There
#: is deliberately NO ``criteria`` field: the candidate rule is the
#: repository-derived rule above, never user/LLM-selectable.
WORKFLOW_FIELDS = ('date', 'purpose', 'limit')

_WORKFLOW_FIELD_LIMITS = {
    'date': 60,
    'purpose': 200,
}

WORKFLOW_DATE_DEFAULT = 'tomorrow'

#: Present in the repository preview example ("Purpose: Admission
#: follow-up") — the same neutral summary the Phase 2B action uses.
WORKFLOW_PURPOSE_DEFAULT = 'Admission follow-up'

#: Hard maximum of operations per workflow run (prompt §10).  Chosen so
#: a single confirmed turn stays a small, auditable batch.
WORKFLOW_LIMIT_DEFAULT = 20
WORKFLOW_LIMIT_MAX = 20

# ---------------------------------------------------------------------------
# Statuses (mirror the pending action lifecycle; partial = retryable)
# ---------------------------------------------------------------------------

STATUS_DRAFT = 'draft'
STATUS_PREVIEW = 'preview'        # eager preview: created directly there
STATUS_EXECUTED = 'executed'
STATUS_PARTIAL = 'partial'        # mixed / not-yet-committed result
STATUS_CANCELLED = 'cancelled'
STATUS_EXPIRED = 'expired'
STATUS_FAILED = 'failed'          # reserved: kept for schema completeness
STATUS_SUPERSEDED = 'superseded'
#: Phase 12 — the plan's assumptions no longer hold (candidates added,
#: removed or materially changed).  A NEW preview is required.
STATUS_INVALIDATED = 'invalidated'

ACTIVE_STATUSES = (STATUS_DRAFT, STATUS_PREVIEW, STATUS_PARTIAL)
EXPIRABLE_STATUSES = (STATUS_DRAFT, STATUS_PREVIEW)
CONFIRMABLE_STATUSES = (STATUS_PREVIEW, STATUS_PARTIAL)

_TERMINAL_STATUSES = (STATUS_EXECUTED, STATUS_CANCELLED, STATUS_EXPIRED,
                      STATUS_FAILED, STATUS_SUPERSEDED,
                      STATUS_INVALIDATED)

#: Phase 12 — material-change answer (never auto-regenerate).
PLAN_INVALIDATED_TEXT = (
    'The underlying records changed after this preview was created. '
    'I need to generate a new preview before proceeding.')
PLAN_INVALIDATED_REPLY = (
    PLAN_INVALIDATED_TEXT + ' Nothing was changed.')

# ---------------------------------------------------------------------------
# Request detection (literal phrases; literal quote tolerance)
# ---------------------------------------------------------------------------

_WORKFLOW_VERB_ALT = (
    r'prepare|prep|batch|generate|queue|build|process|run')

_WORKFLOW_VERB_CORE = r'(?:' + _WORKFLOW_VERB_ALT + r')'

_WORKFLOW_REQUEST_PATTERNS = (
    # "prepare today's admission follow-ups", "batch the follow-ups"
    r'\b' + _WORKFLOW_VERB_CORE +
    r'\b[^.;?!]{0,60}?\bfollow[-\s]?ups?\b',
    # "find / show applicants who need follow-up"
    r'\b(?:find|show|list|get|give|search|collect|pull|' +
    _WORKFLOW_VERB_ALT + r')\b'
    r'[^.;?!]{0,60}?\b(?:all\s+|the\s+|my\s+)?'
    r'(?:applicants?|inquiries|enquiries|leads)\b'
    r'[^.;?!]{0,80}?\b(?:need(?:s|ed)?|needing)\b'
    r'[^.;?!]{0,60}?\bfollow[-\s]?ups?\b',
    # "applicants who haven't been contacted recently"
    r'\b(?:applicants?|inquiries|enquiries|leads)\b'
    r'[^.;?!]{0,80}?\bhaven.?t\s+been\s+contacted\b'
    r'|\bhaven.?t\s+been\s+contacted\b[^.;?!]{0,80}?'
    r'\b(?:applicants?|inquiries|enquiries|leads)\b',
)

_WORKFLOW_REQUEST_RE = re.compile(
    '|'.join('(?:%s)' % p for p in _WORKFLOW_REQUEST_PATTERNS), re.I)

# Read-only phrasings that must never open the workflow.
_WORKFLOW_NEGATIVE_RE = re.compile(
    r'\bfollow[-\s]?ups?\b[^.;?!]{0,40}\b(?:due|pending|open|overdue'
    r'|status|report|overview|summary|history)\b'
    r'|(?:what(?:\s+is|\s+are|\x27s|\'s))\b[^.;?!]{0,40}\bfollow'
    r'|(?:status|report)\s+of\b[^.;?!]{0,40}\bfollow',
    re.I)

_WORKFLOW_INTENT_RE = re.compile(r'\b' + _WORKFLOW_VERB_CORE + r'\b', re.I)

# Injection probes specific to the workflow surface (prompt §27).  The
# generic Phase 2A probes stay in force; these add workflow-only
# phrasings and are consulted ONLY while the workflow layer is enabled.
_WORKFLOW_ADVERSARIAL_RE = re.compile(
    r'\b(?:execute|do|run)\s+(?:the\s+)?(?:everything|plan|workflow'
    r'|rest|remaining|all)\b'
    r'|do\s+the\s+remaining\s+applicants?\b'
    r'|skip\s+the\s+preview\b'
    r'|continue\s+even\s+if\b'
    r'|\bautomatically\s+(?:continue|proceed|execute)\b'
    r'|in\s+batches\s+automatically',
    re.I)

# "max 5" / "limit 10" / "top 3" / "only 2"
_WORKFLOW_LIMIT_RE = re.compile(
    r'\b(?:limit|max(?:imum)?|top|only|first)\s+(\d{1,2})\b'
    r'|\bfor\s+(\d{1,2})\s+applicants?\b', re.I)


def is_workflow_request(text):
    """Deterministic detection of a PREPARE-FOLLOW-UPS goal."""
    text = str(text or '')
    if not text.strip():
        return False
    if _WORKFLOW_NEGATIVE_RE.search(text) and \
            not _WORKFLOW_INTENT_RE.search(text):
        return False
    return bool(_WORKFLOW_REQUEST_RE.search(text))


def is_workflow_adversarial(text):
    """Workflow-specific injection probe detection (additive)."""
    return bool(_WORKFLOW_ADVERSARIAL_RE.search(str(text or '')))


def validate_workflow_entities(raw):
    """Strict schema validation for workflow entities.

    Same reject-the-whole-proposal semantics as the actions: unknown
    keys (including ``criteria`` and any record hint), wrong types and
    oversizes invalidate the WHOLE proposal; nothing is repaired.
    ``limit`` must already be an INTEGER in 1..WORKFLOW_LIMIT_MAX —
    a string is a schema violation, not something to coerce.
    """
    if not isinstance(raw, dict):
        return {}, False, ['entities']
    invalid = []
    extra = sorted(
        str(key) for key in raw if key not in WORKFLOW_FIELDS)
    if extra:
        return {}, False, extra
    clean = {}
    for field in WORKFLOW_FIELDS:
        value = raw.get(field)
        if value is None or (isinstance(value, str)
                             and not value.strip()):
            continue
        if field == 'limit':
            if isinstance(value, bool) or not isinstance(value, int):
                invalid.append(field)
                continue
            if value < 1 or value > WORKFLOW_LIMIT_MAX:
                invalid.append(field)
                continue
            clean[field] = int(value)
            continue
        if not isinstance(value, str):
            invalid.append(field)
            continue
        value = ' '.join(value.split())[:_WORKFLOW_FIELD_LIMITS[field]]
        if len(str(raw.get(field)).strip()) > _WORKFLOW_FIELD_LIMITS[field]:
            # An oversized raw value is a violation, NEVER trimmed
            # into acceptance.
            invalid.append(field)
            continue
        if field == 'purpose' and \
                re.search(r'[<>]', value):
            # Free text destined for the activity note — keep the same
            # escape-first stance as 2B: no raw angle brackets.
            invalid.append(field)
            continue
        clean[field] = value
    if invalid:
        return {}, False, invalid
    return clean, True, []


def extract_workflow_fields(text):
    """Deterministic extraction of the OPTIONAL workflow inputs.

    Reuses the follow-up date-phrase extractor and purpose/note label
    patterns; applicant hints are deliberately dropped — this workflow
    never takes record identities from the user turn.
    :returns: ``(fields, rest)`` with ``limit`` an int when found.
    """
    from odoo.addons.edicai_ai.models.ai_action_resolve import (
        _FOLLOWUP_LABEL_PATTERNS,
        extract_followup_date_phrase,
    )
    text = str(text or '')
    fields = {}
    rest = text
    phrase, rest = extract_followup_date_phrase(rest)
    if phrase:
        clean, ok, _invalid = validate_workflow_entities({'date': phrase})
        if ok and 'date' in clean:
            fields['date'] = clean['date']
    for field, pattern in _FOLLOWUP_LABEL_PATTERNS.items():
        if field != 'purpose':
            continue
        match = pattern.search(rest)
        if not match:
            continue
        raw_val = match.group('val').strip(' \t"\'')
        clean, ok, _invalid = validate_workflow_entities(
            {'purpose': raw_val})
        if ok and field in clean:
            fields[field] = clean[field]
            rest = rest[:match.start()] + ' ' + rest[match.end():]
    match = _WORKFLOW_LIMIT_RE.search(rest)
    if match:
        requested = match.group(1) or match.group(2)
        clean, ok, _invalid = validate_workflow_entities(
            {'limit': int(requested)})
        if ok and 'limit' in clean:
            fields['limit'] = clean['limit']
            rest = rest[:match.start()] + ' ' + rest[match.end():]
    return fields, rest


def plan_hash(plan):
    """Deterministic SHA-256 over the canonical plan JSON."""
    canonical = json.dumps(plan, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _failure_text(error_code):
    """Deterministic, machine-reason → user-safe phrase map."""
    mapping = {
        'applicant_unreadable':
            'the applicant is no longer accessible to you',
        'UNAUTHORIZED': 'authorization was denied at execution time',
        'ACL_DENIED_AT_EXECUTION':
            'authorization was denied at execution time',
        'VERIFICATION_FAILED':
            'the created follow-up could not be verified',
        'VALIDATION_FAILED':
            'standard business validation rejected the operation',
        'CONCURRENT': 'a concurrent execution held the operation',
        'NOT_FOUND_AT_EXECUTION':
            'the applicant could not be resolved at execution time',
        'RESOLUTION_INCONSISTENT':
            'the applicant could not be resolved at execution time',
        'INTERNAL_ERROR': 'an unexpected error occurred',
    }
    return mapping.get(str(error_code or 'INTERNAL_ERROR'),
                       'an unexpected error occurred')


class EdicaiAIPendingWorkflow(models.Model):
    """Durable, owner-scoped pending WORKFLOW (Phase 3).

    One active workflow per (session, user) — mirror of the Phase 2A
    pending action, extended with a multi-operation canonical plan.
    """

    _name = 'edicai.ai.pending.workflow'
    _description = 'AI Pending Conversational Workflow'
    _order = 'id desc'
    _rec_name = 'ref'

    workflow = fields.Char(
        string='Workflow', required=True, default=WORKFLOW_NAME,
        help='Allow-listed conversational workflow identifier.')
    session_id = fields.Many2one(
        'edicai.ai.chat.session', string='Conversation',
        required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one(
        'res.users', string='Requested by', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Institution', required=True,
        default=lambda self: self.env.company, ondelete='restrict',
        index=True)
    purpose = fields.Char(
        string='Follow-up Purpose (canonical)', default='')
    date_phrase = fields.Char(
        string='Requested Due-Date Phrase', default='')
    limit_count = fields.Integer(
        string='Operation Limit', default=WORKFLOW_LIMIT_DEFAULT)
    total_candidates = fields.Integer(
        string='Candidates Found', default=0)
    more_available = fields.Boolean(
        string='More Candidates Exist', default=False)
    plan_json = fields.Text(string='Workflow Plan (canonical)')
    plan_hash = fields.Char(string='Plan Hash', index=True)
    ref = fields.Char(string='Confirmation Code')
    status = fields.Selection(
        selection=[
            (STATUS_DRAFT, 'Draft'),
            (STATUS_PREVIEW, 'Preview'),
            (STATUS_EXECUTED, 'Executed'),
            (STATUS_PARTIAL, 'Partial'),
            (STATUS_CANCELLED, 'Cancelled'),
            (STATUS_EXPIRED, 'Expired'),
            (STATUS_FAILED, 'Failed'),
            (STATUS_SUPERSEDED, 'Superseded'),
            (STATUS_INVALIDATED, 'Invalidated (records changed)'),
        ],
        default=STATUS_DRAFT, required=True, index=True)
    result_json = fields.Text(
        string='Per-Operation Result Snapshot',
        help='Application-verified result of EVERY planned operation '
             '(deterministic, grounded reply source).')
    failure_reason = fields.Char(
        string='Internal Failure Reason',
        help='Machine reason code only — never user content.')

    # ------------------------------------------------------------------
    # Write guard (mirror of the pending action lifecycle guard)
    # ------------------------------------------------------------------

    def write(self, vals):
        for record in self:
            if record.status in _TERMINAL_STATUSES and any(
                    key in vals for key in
                    ('plan_json', 'status', 'plan_hash')):
                new_status = vals.get('status')
                if not (record.status in _TERMINAL_STATUSES
                        and new_status in _TERMINAL_STATUSES):
                    _logger.warning(
                        'AI pending workflow %s: terminal write '
                        'blocked.', record.id)
                    return True
        return super().write(vals)

    # ------------------------------------------------------------------
    # Canonical plan / results reads (never trust raw JSON)
    # ------------------------------------------------------------------

    def _read_plan(self):
        try:
            data = json.loads(self.plan_json or '{}')
        except (ValueError, TypeError):
            return {}
        if not isinstance(data, dict) or \
                data.get('workflow') != WORKFLOW_NAME or \
                not isinstance(data.get('candidates'), list):
            return {}
        candidates = []
        for op in data['candidates']:
            if not isinstance(op, dict):
                return {}
            if not isinstance(op.get('applicant_id'), int) or \
                    not isinstance(op.get('application_number'), str):
                return {}
            candidates.append({
                'applicant_id': op['applicant_id'],
                'applicant': str(op.get('applicant') or ''),
                'application_number': op['application_number'],
            })
        return {
            'workflow': WORKFLOW_NAME,
            'company_id': data.get('company_id'),
            'date': str(data.get('date') or ''),
            'time': str(data.get('time') or ''),
            'purpose': str(data.get('purpose') or ''),
            'limit': int(data.get('limit') or 0),
            'candidates': candidates,
        }

    def _read_results(self, plan):
        try:
            data = json.loads(self.result_json or '[]')
        except (ValueError, TypeError):
            data = []
        results = data if isinstance(data, list) else []
        # Results are index-bound to the FROZEN plan.
        normalized = []
        for idx, op in enumerate(plan['candidates']):
            entry = results[idx] if idx < len(results) else {}
            if not isinstance(entry, dict):
                entry = {}
            entry.setdefault('applicant_id', op['applicant_id'])
            entry.setdefault('applicant', op['applicant'])
            entry.setdefault('application_number', op['application_number'])
            entry.setdefault('status', 'pending')
            entry.setdefault('error_code', '')
            entry['activity_id'] = int(entry.get('activity_id') or 0)
            normalized.append(entry)
        return normalized

    def _store_results(self, results):
        self.write({'result_json': json.dumps(results, sort_keys=True)})

    # ------------------------------------------------------------------
    # Lookups (owner-scoped, mirror of the pending action)
    # ------------------------------------------------------------------

    @api.model
    def open_active(self, session, user=None):
        """The (at most one) ACTIVE workflow for this session + owner."""
        if session is None:
            return self.env['edicai.ai.pending.workflow']
        user = user or self.env.user
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', user.id),
            ('status', 'in', list(ACTIVE_STATUSES)),
        ], limit=1)

    @api.model
    def find_recent_executed(self, session, user=None, minutes=15):
        """Last fully-executed workflow for idempotent replays."""
        if session is None:
            return self.env['edicai.ai.pending.workflow']
        user = user or self.env.user
        since = fields.Datetime.now() - timedelta(minutes=minutes)
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', user.id),
            ('status', '=', STATUS_EXECUTED),
            ('write_date', '>=', since),
        ], limit=1)

    @api.model
    def find_recent_final(self, session, user=None, minutes=15):
        """Most recent lifecycle-final workflow of this session."""
        if session is None:
            return self.env['edicai.ai.pending.workflow']
        user = user or self.env.user
        since = fields.Datetime.now() - timedelta(minutes=minutes)
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', user.id),
            ('status', 'in', [STATUS_EXPIRED, STATUS_CANCELLED,
                              STATUS_FAILED, STATUS_INVALIDATED]),
            ('write_date', '>=', since),
        ], limit=1)

    @api.model
    def supersede_active(self, session=None, user=None, reason_code=None,
                         row=None):
        """Freeze the ACTIVE workflow of this session (no mutation).

        Used both for cancellation-style transitions (a new ACTION
        taking over) and material plan changes.  Returns True when a
        row was superseded; a business write NEVER happens here.
        """
        Wf = self.env['edicai.ai.pending.workflow']
        row = row or Wf.open_active(session, user)
        if not row:
            return False
        try:
            row.write({'status': STATUS_SUPERSEDED,
                       'failure_reason': reason_code or 'SUPERSEDED'})
        except Exception:
            return False
        Wf._audit_event('WORKFLOW_CANCELLED', conversation=row.session_id,
                        user=row.user_id, decision='deny',
                        reason_code=reason_code or 'SUPERSEDED',
                        metadata={'workflow_id': row.id})
        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @api.model
    def _open_states(self):
        """Non-terminal admission states, DERIVED from the repository
        state machine (never hardcoded business semantics)."""
        try:
            transitions = dict(
                self.env['edicai.admission.applicant'].ALLOWED_TRANSITIONS)
        except Exception:
            # Fail closed: without the repository map, NO candidates.
            _logger.info('AI workflow: state machine unavailable.')
            return ()
        terminal = [state for state, nxt in transitions.items()
                    if not nxt]
        return tuple(sorted(state for state in transitions
                            if state not in terminal))

    @api.model
    def _discovery_domain(self, company):
        states = self._open_states()
        if not states:
            return None
        return [
            ('company_id', '=', company.id),
            ('state', 'in', list(states)),
        ]

    @api.model
    def _discover_candidates(self, company):
        """Pure READ candidate discovery (record rules respected).

        Candidates: open-state applicants of THIS company that have
        NO open ``mail.activity`` — oldest first.  Returns the full
        ordered list (the plan slicing happens later).
        """
        domain = self._discovery_domain(company)
        if domain is None:
            return []
        rows = self.env['edicai.admission.applicant'].search(
            domain, order='create_date asc, id asc')
        if not rows:
            return []
        Activity = self.env['mail.activity']
        open_ids = set(Activity.search([
            ('res_model', '=', 'edicai.admission.applicant'),
            ('res_id', 'in', rows.ids),
        ]).mapped('res_id'))
        return [record for record in rows if record.id not in open_ids]

    @api.model
    def start_workflow(self, session, entities, user=None):
        """Gate → schema → discovery → plan → preview (NO mutation).

        Supersedes any active pending ACTION of this session first
        (one active item per conversation — the workflow takes over).
        Returns the chatbot reply dict.
        """
        user = user or self.env.user
        policy = self.env['edicai.ai.action.policy']
        gate = policy.check_workflow_access(user)
        if not gate['allowed']:
            self._audit_event('WORKFLOW_AUTH_DENIED',
                              conversation=session, user=user,
                              decision='deny',
                              reason_code=gate['reason_code'])
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED])

        clean, ok, _invalid = validate_workflow_entities(entities or {})
        if not ok:
            self._audit_event('INTENT_DETECTED',
                              conversation=session, user=user,
                              decision='deny',
                              reason_code='WORKFLOW_FIELD_INVALID')
            return self._error_reply(
                SAFE_MESSAGES[VALIDATION_FAILED] +
                ' Re-send the request without the invalid values.')

        # One active item per conversation: the workflow supersedes any
        # active pending ACTION row (deterministic takeover, audited).
        Pending = self.env['edicai.ai.pending.action']
        previous = Pending.open_active(session, user)
        if previous:
            previous.write({'status': 'superseded'})
            Pending._audit('ACTION_INVALIDATED', conversation=session,
                           user=user, reason_code='SUPERSEDED_BY_WORKFLOW',
                           metadata={'pending_id': previous.id},
                           tool_name=previous.action)
        row, reply = self.with_user(user)._create_and_preview(
            session, clean, user)
        if reply is not None:
            return reply
        return row.preview_reply()

    def _create_and_preview(self, session, clean, user):
        """Plan construction (read-only) + row creation + preview."""
        date_phrase = clean.get('date') or WORKFLOW_DATE_DEFAULT
        purpose = clean.get('purpose') or WORKFLOW_PURPOSE_DEFAULT
        limit_count = clean.get('limit') or WORKFLOW_LIMIT_DEFAULT
        state, date_iso, time_str = parse_followup_date(
            date_phrase, today=fields.Date.context_today(self))
        if state != 'ok':
            self._audit_event('INTENT_DETECTED', user=user,
                              decision='deny',
                              reason_code='WORKFLOW_DATE_INVALID')
            return None, self._error_reply(
                'That follow-up date is not valid. Use a future date '
                'such as "tomorrow", "Friday" or "2026-12-01" — '
                'nothing was changed.')
        company = self.env.company
        candidates = self._discover_candidates(company)
        total = len(candidates)
        self._audit_event('INTENT_DETECTED', conversation=session,
                          user=user, decision='allow',
                          reason_code='WORKFLOW_REQUESTED',
                          metadata={'workflow': WORKFLOW_NAME,
                                    'candidates': total,
                                    'limit': limit_count})
        if not candidates:
            self._audit_event('INTENT_DETECTED', conversation=session,
                              user=user, decision='deny',
                              reason_code='WORKFLOW_NO_CANDIDATES')
            return None, self._answered_reply(_NO_CANDIDATES_TEXT)
        plan = {
            'workflow': WORKFLOW_NAME,
            'company_id': company.id,
            'date': date_iso,
            'time': time_str or '',
            'purpose': purpose,
            'limit': limit_count,
            'candidates': [
                {
                    'applicant_id': record.id,
                    'applicant': record.display_name,
                    'application_number': record.application_number,
                }
                for record in candidates[:limit_count]
            ],
        }
        Wf = self.env['edicai.ai.pending.workflow'].with_user(user)
        row = Wf.create({
            'workflow': WORKFLOW_NAME,
            'session_id': session.id,
            'user_id': user.id,
            'company_id': company.id,
            'purpose': purpose,
            'date_phrase': date_phrase,
            'limit_count': limit_count,
            'total_candidates': total,
            'more_available': total > min(limit_count,
                                          WORKFLOW_LIMIT_MAX),
            'plan_json': json.dumps(plan, sort_keys=True),
            'status': STATUS_DRAFT,
        })
        Wf._audit_event('WORKFLOW_PROPOSED', conversation=session,
                        user=user, decision='allow',
                        reason_code='PLAN_BUILT',
                        metadata={'workflow_id': row.id,
                                  'candidates': total,
                                  'planned': len(plan['candidates'])})
        row.mark_preview()
        return row, None

    def mark_preview(self):
        """Freeze the plan: hash + confirmation ref (§15)."""
        self.ensure_one()
        digest = plan_hash(self._read_plan())
        self.write({'status': STATUS_PREVIEW,
                    'plan_hash': digest,
                    'ref': digest[:8]})
        self._audit_event('WORKFLOW_PREVIEWED', decision='allow',
                          reason_code='PREVIEW_READY',
                          metadata={'workflow_id': self.id})
        return self

    def cancel(self):
        """User cancellation before execution (§24): no side effect."""
        self.ensure_one()
        if self.status not in ACTIVE_STATUSES:
            return False
        self.write({'status': STATUS_CANCELLED,
                    'failure_reason': 'USER_CANCELLED'})
        self._audit_event('WORKFLOW_CANCELLED', decision='allow',
                          reason_code='USER_CANCELLED',
                          metadata={'workflow_id': self.id})
        return True

    @api.model
    def expire_stale(self, session, timeout_minutes=None):
        """Lazy expiry of active PREVIEW rows (no cron).

        PARTIAL workflows are deliberately NOT expired lazily: some of
        their operations DID run (business records exist), so a stale
        partial must stay recoverable (deterministic re-confirm) or be
        explicitly cancelled — never silently discarded.
        """
        Wf = self.env['edicai.ai.pending.workflow']
        if session is None:
            return Wf.env['edicai.ai.pending.workflow']
        if timeout_minutes is None:
            timeout_minutes = self.env[
                'edicai.ai.action.policy'].get_confirm_timeout_minutes()
        cutoff = fields.Datetime.now() - timedelta(
            minutes=max(0, timeout_minutes))
        stale = Wf.search([
            ('session_id', '=', session.id),
            ('user_id', '=', Wf.env.user.id),
            ('status', 'in', list(EXPIRABLE_STATUSES)),
            ('create_date', '<', cutoff),
        ])
        for row in stale:
            row.write({'status': STATUS_EXPIRED,
                       'failure_reason': 'CONFIRMATION_TIMEOUT'})
            row._audit_event('WORKFLOW_EXPIRED',
                             reason_code='CONFIRMATION_TIMEOUT',
                             metadata={'workflow_id': row.id})
        return Wf.open_active(session, Wf.env.user)

    def _is_expired_now(self):
        """Preview-only expiry check inside the confirmation lock.

        A PARTIAL workflow never expires by time: its earlier verified
        operations are durable business state, and recovery must stay
        available until the user explicitly confirms or cancels.
        """
        if self.status == STATUS_PARTIAL:
            return False
        minutes = self.env[
            'edicai.ai.action.policy'].get_confirm_timeout_minutes()
        cutoff = fields.Datetime.now() - timedelta(minutes=minutes)
        return bool(self.create_date and self.create_date < cutoff)

    # ------------------------------------------------------------------
    # Confirmation + bounded execution (prompt §16–§20)
    # ------------------------------------------------------------------

    def _lock_nowait(self):
        """Row-level lock, fail fast on concurrency (idempotency)."""
        try:
            self.env.cr.execute(
                'SELECT id FROM %s WHERE id = %%s FOR UPDATE NOWAIT'
                % self._table, [self.id])
            return True
        except psycopg2.Error as exc:
            _logger.info(
                'AI pending workflow %s: concurrent confirmation '
                '(%s).', self.id, type(exc).__name__)
            return False

    def _candidate_snapshot(self, record):
        """The material fields frozen into (and re-checked against) a plan."""
        return {
            'applicant_id': record.id,
            'applicant': record.display_name or '',
            'application_number': record.application_number or '',
            'state': record.state,
        }

    def _plan_invalid_reason(self, plan):
        """P0 (BUG-010): compare live assumptions with the frozen plan.

        PREVIEW (nothing ran yet) requires an IDENTICAL discovery result:
        the same candidate count and the same ordered prefix with the
        same identity/material fields.  A candidate added, removed or
        materially changed therefore invalidates the plan.

        PARTIAL (some operations already ran) intentionally re-checks
        only the NOT-yet-succeeded operations: executed ones now carry a
        follow-up activity by design, so a full re-discovery would
        always differ.

        :returns: a machine reason code, or ``None`` when still valid.
        """
        company = self.company_id
        states = self._open_states()
        if not states:
            return 'STATE_MACHINE_UNAVAILABLE'
        results = self._read_results(plan)
        Applicant = self.env['edicai.admission.applicant'] \
            .with_user(self.env.user).with_company(company)
        if self.status == STATUS_PARTIAL:
            for idx, op in enumerate(plan['candidates']):
                if results[idx]['status'] in ('succeeded',
                                              'succeeded_already'):
                    continue
                current = Applicant.search([
                    ('id', '=', op['applicant_id']),
                    ('company_id', '=', company.id),
                    ('state', 'in', list(states)),
                ], limit=1)
                if not current:
                    return 'CANDIDATE_UNAVAILABLE'
                if (current.application_number or '') != \
                        op['application_number'] or \
                        (current.display_name or '') != op['applicant']:
                    return 'CANDIDATE_CHANGED'
            return None
        # PREVIEW — the whole discovery result is part of the plan.
        current = self._discover_candidates(company)
        if len(current) != self.total_candidates:
            return 'CANDIDATE_SET_CHANGED'
        planned = plan['candidates']
        if len(current) < len(planned):
            return 'CANDIDATE_SET_CHANGED'
        for op, record in zip(planned, current[:len(planned)]):
            if record.id != op['applicant_id']:
                return 'CANDIDATE_SET_CHANGED'
            if (record.application_number or '') != \
                    op['application_number'] or \
                    (record.display_name or '') != op['applicant']:
                return 'CANDIDATE_CHANGED'
            if record.state not in states:
                return 'CANDIDATE_CHANGED'
        return None

    def confirm_and_execute(self):
        """Bind-then-execute the EXACT frozen plan, once.

        lock → status/expiry re-check → RE-AUTHORIZE → per operation:
        revalidate visibility → already-scheduled re-check →
        child Phase 2B action execution → record result → finalize.

        The row lock + in-lock status check makes double or concurrent
        confirmations single-effect.  Every guard failure returns
        WITHOUT claiming success.
        """
        self.ensure_one()
        if self.status not in CONFIRMABLE_STATUSES:
            return {'outcome': 'not_confirmable'}
        if not self._lock_nowait():
            self._audit_event('WORKFLOW_DUPLICATE',
                              reason_code='CONCURRENT_CONFIRMATION',
                              metadata={'workflow_id': self.id})
            return {'outcome': 'duplicate_concurrent'}
        # Re-read INSIDE the lock (monotone state check).
        fresh = self.search([('id', '=', self.id)], limit=1)
        if fresh.status not in CONFIRMABLE_STATUSES:
            return {'outcome': 'duplicate', 'row': fresh}
        if fresh._is_expired_now():
            fresh.write({'status': STATUS_EXPIRED,
                         'failure_reason': 'CONFIRMATION_TIMEOUT'})
            fresh._audit_event('WORKFLOW_EXPIRED',
                               reason_code='CONFIRMATION_TIMEOUT',
                               metadata={'workflow_id': fresh.id})
            return {'outcome': 'expired'}
        fresh._audit_event('WORKFLOW_CONFIRMED', decision='allow',
                           reason_code='USER_CONFIRMED',
                           metadata={'workflow_id': fresh.id,
                                     'plan_hash': fresh.plan_hash})
        # Re-authorization (prompt §17 — mandatory second gate).
        gate = self.env[
            'edicai.ai.action.policy'].check_workflow_access(
                user=self.env.user)
        if not gate['allowed']:
            fresh._audit_event('WORKFLOW_AUTH_DENIED',
                               decision='deny',
                               reason_code=gate['reason_code'],
                               metadata={'workflow_id': fresh.id})
            return {'outcome': 'denied',
                    'reason_code': gate['reason_code']}
        if self.env.company.id != fresh.company_id.id:
            fresh._audit_event('WORKFLOW_AUTH_DENIED',
                               decision='deny',
                               reason_code='COMPANY_CHANGED',
                               metadata={'workflow_id': fresh.id})
            return {'outcome': 'denied',
                    'reason_code': 'COMPANY_CHANGED'}
        if self.env.user.id != fresh.user_id.id:
            fresh._audit_event('WORKFLOW_AUTH_DENIED',
                               decision='deny',
                               reason_code='SESSION_OWNER_CHANGED',
                               metadata={'workflow_id': fresh.id})
            return {'outcome': 'denied',
                    'reason_code': 'SESSION_OWNER_CHANGED'}
        # ---- P0 (BUG-010): immutable-plan integrity + assumption check.
        # Re-discover the relevant current state and compare it with the
        # frozen plan BEFORE any child execution.  A changed plan is
        # never auto-regenerated-and-executed; the user must review a
        # fresh preview explicitly.
        plan = fresh._read_plan()
        invalid = False
        if not plan or plan_hash(plan) != fresh.plan_hash:
            invalid = 'PLAN_HASH_MISMATCH'
        else:
            invalid = fresh._plan_invalid_reason(plan)
        if invalid:
            fresh.write({
                'status': STATUS_INVALIDATED,
                'failure_reason': invalid,
            })
            fresh._audit_event(
                'WORKFLOW_INVALIDATED', decision='deny',
                reason_code=invalid,
                metadata={'workflow_id': fresh.id,
                          'plan_hash': fresh.plan_hash})
            return {'outcome': 'invalidated',
                    'reason_code': invalid,
                    'row': fresh}
        return fresh._execute_plan_locked()

    def _execute_plan_locked(self):
        """Run the frozen plan through the EXISTING Phase 2B path.

        One child ``edicai.ai.pending.action`` row (Phase 2B,
        ``admission.schedule_followup``) per candidate — each executed
        with its own full lifecycle (resolution, ACL check, canonical
        activity_schedule, verification).  There is NO second business
        implementation (prompt §18).
        """
        plan = self._read_plan()
        if not plan:
            self._audit_event('WORKFLOW_PARTIAL',
                              reason_code='PLAN_UNREADABLE',
                              metadata={'workflow_id': self.id})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        results = self._read_results(plan)
        total = len(results)
        done_before = sum(
            1 for entry in results
            if entry['status'] in ('succeeded', 'succeeded_already'))
        self._audit_event('WORKFLOW_EXECUTION_STARTED', decision='allow',
                          reason_code='PLAN_LOCKED',
                          metadata={'workflow_id': self.id,
                                    'operations': total,
                                    'already_done': done_before})
        Pending = self.env['edicai.ai.pending.action']
        Activity = self.env['mail.activity']
        todo_id = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        company = self.company_id
        due_date = plan.get('date') or ''
        time_str = plan.get('time') or ''
        purpose = plan.get('purpose') or WORKFLOW_PURPOSE_DEFAULT
        date_payload = due_date + (
            ' at %s' % time_str if time_str else '')
        user = self.env.user
        applicant_model = 'edicai.admission.applicant'
        for idx, op in enumerate(plan['candidates']):
            entry = results[idx]
            if entry['status'] in ('succeeded', 'succeeded_already'):
                continue  # §20: never duplicate verified operations
            entry = dict(entry)
            entry.update({
                'applicant_id': op['applicant_id'],
                'applicant': op['applicant'],
                'application_number': op['application_number'],
                'status': 'failed',
                'error_code': 'INTERNAL_ERROR',
                'activity_id': 0,
            })
            # ---- deterministic revalidation (prompt §16/#17) -------
            # The applicant must STILL be visible to the PLAN's owner
            # and still belong to the plan's company — current record
            # rules, never trust from the preview.
            seen = self.env[applicant_model].with_user(user).with_company(
                    company).search([
                        ('id', '=', op['applicant_id']),
                        ('company_id', '=', company.id),
                    ], limit=1)
            if not seen:
                entry['error_code'] = 'applicant_unreadable'
                results[idx] = entry
                self._store_results(results)
                self._audit_op(idx, entry, executed=False)
                continue
            # ---- already-scheduled re-check (§20 recovery) ---------
            if todo_id:
                existing = Activity.search([
                    ('res_model', '=', applicant_model),
                    ('res_id', '=', op['applicant_id']),
                    ('active', '=', True),
                    ('activity_type_id', '=', todo_id.id),
                    ('user_id', '=', user.id),
                    ('date_deadline', '=', due_date),
                ], limit=1)
                if existing:
                    entry.update({'status': 'succeeded_already',
                                  'activity_id': existing.id,
                                  'error_code': ''})
                    results[idx] = entry
                    self._store_results(results)
                    self._audit_op(
                        idx, entry, executed=False,
                        reason_code='ALREADY_SCHEDULED')
                    continue
            # ---- child Phase 2B action (the ONE mutated path) ------
            child = Pending.with_user(user).with_company(company) \
                .create_pending(
                    self.session_id,
                    {'applicant': op['application_number'],
                     'date': date_payload,
                     'purpose': purpose},
                    user=user, action=ACTION_SCHEDULE_FOLLOWUP,
                    supersede=False)
            child.mark_preview()
            outcome = child.confirm_and_execute()
            self._apply_child_outcome(results, idx, entry, outcome)
            self._store_results(results)
        return self._finalize_plan(results, total)

    def _apply_child_outcome(self, results, idx, entry, outcome):
        """Map the child action outcome to a per-operation status."""
        outcome_state = (outcome or {}).get('outcome', 'error')
        if outcome_state == 'executed':
            verified = outcome.get('verified') or {}
            entry.update({'status': 'succeeded',
                          'error_code': '',
                          'activity_id':
                              int(verified.get('activity_id') or 0)})
        elif outcome_state == 'denied':
            entry['error_code'] = 'UNAUTHORIZED'
            self._audit_event('WORKFLOW_AUTH_DENIED', decision='deny',
                              reason_code=(
                                  outcome or {}).get('reason_code')
                              or 'DENIED_AT_EXECUTION',
                              metadata={'workflow_id': self.id})
        elif outcome_state == 'verification_failed':
            entry['error_code'] = 'VERIFICATION_FAILED'
        elif outcome_state == 'duplicate_concurrent':
            entry['error_code'] = 'CONCURRENT'
        elif outcome_state in ('clarify', 'not_found'):
            entry['error_code'] = 'NOT_FOUND_AT_EXECUTION'
        elif outcome_state in ('missing', 'invalid_date'):
            entry['error_code'] = 'RESOLUTION_INCONSISTENT'
        else:  # error / expired / not_confirmable / unsupported outcome
            entry['error_code'] = str(
                (outcome or {}).get('error_code') or 'INTERNAL_ERROR')
        results[idx] = entry
        self._audit_op(idx, entry,
                       executed=(entry['status'] == 'succeeded'))

    def _audit_op(self, idx, entry, executed, reason_code=None):
        metadata = {
            'workflow_id': self.id,
            'op_index': idx,
            'applicant_id': entry.get('applicant_id'),
            'error_code': entry.get('error_code') or '',
        }
        if executed:
            metadata['activity_id'] = entry.get('activity_id')
            self._audit_event('WORKFLOW_OPERATION_EXECUTED',
                              decision='allow',
                              reason_code=reason_code or 'VERIFIED',
                              metadata=metadata)
        else:
            self._audit_event('WORKFLOW_OPERATION_FAILED',
                              decision='deny',
                              reason_code=reason_code
                              or (entry.get('error_code')
                                  or 'OPERATION_FAILED'),
                              metadata=metadata)

    def _finalize_plan(self, results, total):
        """Accurate partial-failure accounting (prompt §19)."""
        completed = sum(1 for entry in results
                        if entry['status'] == 'succeeded')
        already = sum(1 for entry in results
                      if entry['status'] == 'succeeded_already')
        failed = sum(1 for entry in results
                     if entry['status'] == 'failed')
        metadata = {'workflow_id': self.id,
                    'completed': completed,
                    'already': already,
                    'failed': failed}
        if failed == 0 and (completed + already) == total:
            self.write({'status': STATUS_EXECUTED})
            self._audit_event('WORKFLOW_COMPLETED', decision='allow',
                              reason_code='ALL_OPERATIONS_VERIFIED',
                              metadata=metadata)
            return {'outcome': 'executed', 'row': self}
        if completed + already == 0:
            self.write({'status': STATUS_PARTIAL,
                        'failure_reason': 'NO_OPERATION_SUCCEEDED'})
            self._audit_event('WORKFLOW_PARTIAL', decision='error',
                              reason_code='NO_OPERATION_SUCCEEDED',
                              metadata=metadata)
        else:
            self.write({'status': STATUS_PARTIAL})
            self._audit_event('WORKFLOW_PARTIAL', decision='allow',
                              reason_code='SOME_OPERATIONS_FAILED',
                              metadata=metadata)
        return {'outcome': 'partial', 'row': self}

    # ------------------------------------------------------------------
    # Deterministic reply builders (grounded facts only)
    # ------------------------------------------------------------------

    def preview_reply(self):
        self.ensure_one()
        if self.status not in ACTIVE_STATUSES:
            return self._error_reply(
                'This workflow is no longer active. Nothing was '
                'changed.')
        plan = self._read_plan()
        lines = [
            '%s (%s)' % (_PREVIEW_HEADER, self.ref or 'XXXXXXXX'),
            '',
            _GOAL_LINE,
            '',
            'Candidates found: %d%s' % (
                self.total_candidates,
                ' — I found %d applicants, but this workflow is '
                'limited to %d operations at a time; start a new '
                'request for the rest'
                % (self.total_candidates, self.limit_count)
                if self.more_available else ''),
            '',
            'Operations (%d):' % len(plan['candidates']),
        ]
        due_label = plan['date'] + (
            ' (requested time %s)' % plan['time'] if plan['time'] else '')
        for idx, op in enumerate(plan['candidates']):
            lines.append('%d. %s (%s) — due %s' % (
                idx + 1, op['applicant'], op['application_number'],
                due_label))
            lines.append('    Purpose: %s' % plan['purpose'])
        lines += [
            '',
            'Responsible: you (%s) — Institution: %s' % (
                self.env.user.name, self.company_id.name),
            'Effect: each operation creates ONE To-Do follow-up '
            'activity via the standard Odoo activity mechanism '
            '(admission.schedule_followup).',
            '',
            _NOTHING_CHANGED_LINE,
            '',
            'Confirmation code: %s' % (self.ref or ''),
            _CONFIRM_LINE % (self.ref or 'XXXXXXXX'),
        ]
        return self._answered_reply('\n'.join(lines))

    def status_reply(self, note=None):
        """Deterministic restatement for a stray turn (no mutation)."""
        self.ensure_one()
        if self.status == STATUS_PREVIEW:
            return self.preview_reply()
        if self.status == STATUS_PARTIAL:
            results = self._read_results(self._read_plan())
            lines = [_PARTIAL_TITLE, '']
            lines += self._result_lines(results)
            lines += ['', 'Reply "confirm" to retry ONLY the unfinished '
                         'operations, or "cancel" to discard.']
            if note:
                lines.insert(1, note)
            return self._answered_reply('\n'.join(lines))
        if self.status == STATUS_INVALIDATED:
            return self.compose_invalidated_reply()
        return self.preview_reply()

    def _result_lines(self, results):
        completed = sum(1 for entry in results
                        if entry['status'] == 'succeeded')
        already = sum(1 for entry in results
                      if entry['status'] == 'succeeded_already')
        failed = [entry for entry in results
                  if entry['status'] == 'failed']
        lines = ['Completed: %d · Already scheduled before: %d · '
                 'Failed: %d' % (completed, already, len(failed))]
        for entry in failed:
            lines.append(
                ' — %s (%s): %s.' % (
                    entry['application_number'], entry['applicant'],
                    _failure_text(entry.get('error_code'))))
        return lines

    def compose_result_reply(self, duplicated=False):
        """Final grounded reply from the verified per-op snapshot."""
        self.ensure_one()
        if duplicated:
            self._audit_event('WORKFLOW_DUPLICATE', decision='allow',
                              reason_code='REPEATED_CONFIRMATION',
                              metadata={'workflow_id': self.id})
            return self._answered_reply(
                'Already done — this workflow was already executed. '
                'No operations were repeated.')
        results = self._read_results(self._read_plan())
        failed_count = sum(
            1 for entry in results if entry['status'] == 'failed')
        title = ('Workflow partially executed.'
                 if failed_count else 'Workflow executed.')
        lines = [title]
        lines += self._result_lines(results)
        lines.append('Nothing else was changed.')
        return self._answered_reply('\n'.join(lines))

    def compose_invalidated_reply(self):
        """P0 (BUG-010): honest stale-plan answer — nothing executed."""
        self.ensure_one()
        return self._error_reply(PLAN_INVALIDATED_REPLY)

    # ------------------------------------------------------------------
    # Reply surface + audit helpers (mirrors of the action layer)
    # ------------------------------------------------------------------

    def _answered_reply(self, text):
        return {
            'status': 'answered',
            'reply': text,
            'source_label': False,
            'tool_name': WORKFLOW_NAME,
            'error_code': None,
        }

    def _error_reply(self, text):
        return {
            'status': 'error',
            'reply': text,
            'source_label': False,
            'tool_name': WORKFLOW_NAME,
            'error_code': VALIDATION_FAILED,
        }

    @api.model
    def _audit_event(self, event_type, conversation=None, user=None,
                     decision=None, reason_code=None, detail=None,
                     metadata=None):
        """Best-effort workflow audit (same infra, never raises).

        When called on a ROW record, the conversation and user default
        to the row's own binding (mirrors the pending-action audit).
        """
        if self and self.id:
            conversation = conversation or self.session_id
            user = user or self.user_id
        try:
            return self.env['edicai.ai.audit.event'].log_event(
                event_type,
                tool_name=WORKFLOW_NAME,
                user=user,
                conversation=conversation,
                decision=decision,
                reason_code=reason_code,
                detail=detail,
                metadata=metadata,
            )
        except Exception:
            _logger.exception('AI workflow: audit call failed.')
            return False

    def _audit(self, event_type, **kwargs):
        """Record-context convenience wrapper."""
        kwargs.setdefault('conversation', self.session_id)
        kwargs.setdefault('user', self.user_id)
        return self._audit_event(event_type, **kwargs)


# Reply texts (deterministic, grounded).

_PREVIEW_HEADER = 'Admission follow-up plan'

_GOAL_LINE = (
    'Goal: schedule one To-Do follow-up for every open admission '
    'applicant that has no open activity.')

_NOTHING_CHANGED_LINE = 'Nothing has been changed yet.'

_CONFIRM_LINE = (
    'Reply "confirm" / "yes %s" to execute this exact plan, or '
    '"cancel" to discard it.')

_PARTIAL_TITLE = 'Workflow status: partially executed.'

_NO_CANDIDATES_TEXT = (
    'No admission applicants currently need a follow-up '
    '(open applicants without an open activity). Nothing was changed.')

_EXPIRED_TEXT = (
    'This workflow preview has expired. Nothing was changed.')

_CANCELLED_TEXT = 'Workflow cancelled. Nothing was changed.'

_DENIED_TEXT = 'Workflow authorization was denied. Nothing was changed.'


class EdicaiAIWorkflowReplay(models.AbstractModel):
    """Deterministic replay / expiry helpers for the action router.

    Kept SEPARATE from the workflow model so the router's boxed
    branches stay small and byte-identical when the workflow flag is
    off.
    """

    _name = 'edicai.ai.workflow.replay'
    _description = 'AI Workflow Replay Hook (deterministic)'

    @api.model
    def replay_terminal_turn(self, session, user=None):
        """One just-finished workflow: duplicate / expiry answers."""
        Wf = self.env['edicai.ai.pending.workflow']
        user = user or self.env.user
        done = Wf.find_recent_executed(session, user)
        if done:
            return done.compose_result_reply(duplicated=True)
        final = Wf.find_recent_final(session, user)
        if final and final.status == STATUS_EXPIRED:
            return final._answered_reply(_EXPIRED_TEXT)
        return None
