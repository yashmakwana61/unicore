"""Phase 4 — ONE approval-required conversational slice:
``asset.request.approval``.

Phase 3 proved a multi-operation confirmed workflow.  Phase 4 proves
the NEXT boundary — a second, INDEPENDENT human authorization:

    requester preview → requester confirmation → SUBMISSION
        → approval request (server-side authority)
        → APPROVER (a DIFFERENT human) → approve / reject
        → re-authorization → canonical business logic
        → verification → grounded response → audit

Repository-derived slice (NOT invented):

``edicai_asset_request.edicai.asset.request`` is a repository-native
approval workflow:

* module docstring: *"Faculty and staff submit requests; administrators
  review and approve/reject"* — a first-class requester/approver
  separation: ``requested_by`` versus ``approver_id``;
* canonical ``action_submit`` → ``_assign_approver`` assigns the
  designated approver (an institution administrator) SERVER-SIDE;
* ``action_approve`` / ``action_reject`` are the canonical execution
  and rejection paths (pure state flips + chatter — no external side
  effects, safe to test);
* the module's own security: faculty/staff may create only THEIR OWN
  requests (record rule ``requested_by = user.id``), while
  ``edicai_base.group_edicai_admin`` holds full access — the repository's
  deterministic approval authority.

The critical invariant (prompt §5):

    A conversational "yes" from the requester is REQUESTER
    CONFIRMATION.  It may never execute the approval.  Only an
    authorized approver — by actual Odoo group membership, resolved
    server-side, and a DIFFERENT person than the requester — can
    approve.

Safety invariants (mirroring Phases 2/3):

* requester-side LLM understanding is NOT extended — detection and
  extraction are deterministic only; the LLM never invents approvers,
  approvals, hashes or statuses (prompt §19 is conditional on LLM
  usage, and the Phases 1A/1B intents stay untouched).
* the approval request is immutable: canonical serialization +
  SHA-256 hash at each freeze; the write guard blocks material field
  changes after preview; a materially changed underlying request
  FAILS CLOSED.
* approval authority is resolved SERVER-SIDE: admin group membership
  + actor ≠ requester + same company + fresh record-rule
  visibility.  Self-approval and cross-company approval are
  impossible (prompt §21).
* every execution is: row lock (NOWAIT) → status re-check → expiry
  check → RE-AUTHORIZATION → canonical ``action_approve`` executed AS
  THE APPROVER → post-conditions verified.  No LLM call exists on
  this path (prompt §12).
* idempotency: duplicate or concurrent approvals become honest
  replays or fail fast (the lock philosophy proven in Phases 2/3).
* expiry: bounded lifetime (configurable, default 24h) — expired
  approvals fail closed.
* NO sudo anywhere in business execution; record rules always apply.
"""

import hashlib
import json
import logging
import re
from datetime import timedelta

import psycopg2

from odoo import api, fields, models

from odoo.addons.edicai_ai.models.ai_action_resolve import (
    _FOLLOWUP_DATE_SPAN_RE,
    parse_followup_date,
)
from odoo.addons.edicai_ai.models.ai_error import (
    SAFE_MESSAGES,
    VALIDATION_FAILED,
)
from odoo.addons.edicai_ai.models.ai_workflow import (
    plan_hash,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Approval contract (strict)
# ---------------------------------------------------------------------------

#: The ONE allow-listed approval kind (prompt §24 — nothing generic).
APPROVAL_KIND = 'asset.request.approval'

#: The canonical underlying model of this ONE slice (verified alive at
#: routing time — never improvised).
UNDERLYING_MODEL = 'edicai.asset.request'

#: Distinguishing token for the target request (the module's own
#: sequence prefix — parsed from the repository, not invented: the
#: ``edicai.asset.request`` sequence emits ``AR/YYYY/NNNN``).
_TARGET_TOKEN_RE = re.compile(r'\bAR/[\w/-]+', re.I)

#: Approver group — the repository's designated approval authority
#: (``_assign_approver`` assigns an admin; the module ACL gives the
#: admin group full authority over asset requests).
APPROVER_GROUP = 'edicai_base.group_edicai_admin'

#: Requester groups — mirrors the module's OWN authority surface:
#: exactly the groups that may CREATE asset requests AND read the
#: required ``edicai.campus`` reference data (faculty may create
#: requests but cannot read campuses at all, so its resolution fails
#: closed — the repository offers no campus-read authority there).
REQUESTER_GROUPS = (
    'edicai_base.group_edicai_manager',
    'edicai_base.group_edicai_admin',
)

#: The ONLY strictly typed inputs of this ONE slice — no IDs, no
#: approver hints, no free-form criteria (prompt §19).
APPROVAL_FIELDS = ('asset_type', 'description', 'reason',
                   'needed_by', 'campus')

#: Required before submission (module-level: ``campus_id``,
#: ``reason`` and ``needed_by_date`` are required; the conversational
#: contract requires ``asset_type`` so the description is never
#: empty).
APPROVAL_REQUIRED_FIELDS = ('asset_type', 'reason', 'needed_by',
                            'campus')

_FIELD_LIMITS = {
    'asset_type': 40,
    'description': 200,
    'reason': 500,
    'needed_by': 60,
    'campus': 100,
}

#: Synonyms over the module's OWN selection values.  Validation always
#: re-checks against the LIVE selection of ``edicai.asset.request`` at
#: resolution time (fail closed when the module is not installed).
_ASSET_TYPE_SYNONYMS = {
    'projector': 'projector',
    'projectors': 'projector',
    'lab equipment': 'lab_equipment',
    'laboratory equipment': 'lab_equipment',
    'computer': 'computer',
    'computers': 'computer',
    'laptop': 'computer',
    'laptops': 'computer',
    'furniture': 'furniture',
    'audio': 'audio_video',
    'audio video': 'audio_video',
    'a/v': 'audio_video',
    'av': 'audio_video',
    'vehicle': 'vehicle',
    'other': 'other',
}

#: Longest-first matching of the synonyms above.
_ASSET_TYPE_ORDERED = sorted(_ASSET_TYPE_SYNONYMS,
                             key=len, reverse=True)

#: Expiry of a PENDING approval (looks like the preview timeout only:
#: human approvers are not expected within minutes).  Deterministic,
#: configurable, consistent with the Phase 2/3 param pattern.
PARAM_APPROVAL_TIMEOUT = 'edicai_ai.approval_timeout_minutes'
DEFAULT_APPROVAL_TIMEOUT_MINUTES = 1440  # 24 hours

# ---------------------------------------------------------------------------
# Statuses (the prompt §4 lifecycle, one row end-to-end)
# ---------------------------------------------------------------------------

STATUS_DRAFT = 'draft'                    # requester still composing
STATUS_PREVIEW = 'preview'                # creation plan frozen
STATUS_PENDING = 'pending'                # PENDING_APPROVAL (submitted)
STATUS_APPROVED = 'approved'              # approver decision recorded
STATUS_EXECUTED = 'executed'              # canonical action verified
STATUS_REJECTED = 'rejected'
STATUS_CANCELLED = 'cancelled'
STATUS_EXPIRED = 'expired'
STATUS_FAILED = 'failed'                  # execution failed honestly
#: Phase 12 (BUG-011) — the underlying request changed materially after
#: submission.  The old approval is dead; a NEW review is required.
STATUS_INVALIDATED = 'invalidated'

STATUS_ACTIVE = (STATUS_DRAFT, STATUS_PREVIEW)
STATUS_TERMINAL = (STATUS_EXECUTED, STATUS_REJECTED, STATUS_CANCELLED,
                   STATUS_EXPIRED, STATUS_FAILED, STATUS_INVALIDATED)

_PENDING_REPLIES = ('pending', STATUS_APPROVED, STATUS_EXECUTED)

# ---------------------------------------------------------------------------
# Texts (deterministic; grounded facts only)
# ---------------------------------------------------------------------------

_NOTHING_CHANGED = 'Nothing has been changed yet.'

_NOTHING_EXECUTED = 'The requested operation has NOT been executed.'

_EXPIRED_TEXT = (
    'This approval request has expired. Nothing was executed.')

_ALREADY_TEXT = (
    'Already done — this approval was already processed and nothing '
    'was executed twice.')

_CANCELLED_TEXT = ('Approval request cancelled. Nothing was approved '
                   'and the underlying asset request has been '
                   'cancelled as well.')

_REJECT_LIMIT = 200

#: Phase 12 (BUG-011) — the material fields that participate in the
#: approval hash.  They are the canonical fields that decide WHAT the
#: approver is approving (identity, owner, institution, campus, asset,
#: quantity, justification, required-by date, designated approver and
#: lifecycle state). Decision actor/timestamps and chatter are non-material.
MATERIAL_REQUEST_FIELDS = (
    'name', 'company_id', 'campus_id', 'requested_by', 'asset_id',
    'asset_type', 'asset_description', 'requested_quantity', 'reason',
    'needed_by_date', 'state', 'approver_id',
)

APPROVAL_INVALIDATED_TEXT = (
    'This approval is no longer valid because the request changed after '
    'it was submitted. A new review is required.')
APPROVAL_INVALIDATED_REPLY = (
    APPROVAL_INVALIDATED_TEXT + ' Nothing was executed.')

# ---------------------------------------------------------------------------
# Detection (deterministic; adversarial-aware)
# ---------------------------------------------------------------------------

#: A NEW asset request for the approval lane.
_APPROVAL_REQUEST_RE = re.compile(
    r'(?:\b(?:raise|file|submit|put\ in|request|create|prepare)\b'
    r'(?:\s+\w+){0,4}\s+'
    r'(?:asset|equipment)\s+request'
    r'|\brequest\s+(?:an?\s+)?(?:projector|laptop|computer|lab\s+'
    r'equipment|furniture|vehicle|audio\s+video|a/v)\b)',
    re.I)

#: Veto: phrasings ABOUT approvals belong to the approver lane (or
#: already-decided questions) — never fresh creations.
_REQUEST_NEGATIVE_RE = re.compile(
    r'\b(approve|approved|approval|reject)\b', re.I)

_APPROVE_RE = re.compile(r'^\s*(?:ok\s+|yes\s+|sure,?\s+)?approve\b'
                         r'(?P<rest>.*)$', re.I)
_REJECT_RE = re.compile(r'^\s*reject\b(?P<rest>.*)$', re.I)
_PENDING_LIST_RE = re.compile(
    r'(?:what|which)\s+approvals?\s+(?:are\s+)?(?:waiting|pending)'
    r'|(?:show|list|view)\s+(?:my\s+|the\s+)?(?:pending\s+|open\s+)?'
    r'(?:asset\s+)?approvals?'
    r'|(?:pending|waiting|open)\s+(?:asset\s+)?(?:approvals?|requests?)',
    re.I)

_REASON_LABEL_RE = re.compile(
    r'reason\s*[:\-]\s*(?P<val>[^;.]{3,500})', re.I)
_DESCRIPTION_LABEL_RE = re.compile(
    r'description\s*[:\-]\s*(?P<val>[^;]{1,200}?)'
    r'(?=\s+reason\b|\s+needed\b|\s+campus\b|[;.]\s*|$)', re.I)
_CAMPUS_HINT_RE = re.compile(
    r'(?:for|at)\s+(?:the\s+)?(?P<hint>[A-Za-z][\w\s]{0,79}?'
    r'\s?campus\b)'
    r'|campus\s*[:\-]\s*(?P<chint>[^;.]{1,100}?)'
    r'(?=\s+(?:reason|needed|description)\b|[;.]\s*|$)',
    re.I)

#: Phase 4 adversarial probes (additive to the Phase 2A list).
_APPROVAL_ADVERSARIAL_RE = re.compile(
    r'skip\s+(?:the\s+)?approval'
    r'|bypass\s+(?:the\s+)?approval'
    r'|without\s+(?:any\s+)?approval'
    r'|self\s?approv'
    r'|approve\s+it\s+myself'
    r'|mark\s+(?:it\s+)?(?:as\s+)?approved'
    r'|pretend\s+(?:it.?s\s+)?approved'
    r'|force\s+(?:the\s+)?approval'
    r'|execute\s+(?:it\s+)?(?:anyway|without)',
    re.I)


def is_approval_request(text):
    """Deterministic detection of a NEW asset request for the lane."""
    text = str(text or '')
    if not text.strip():
        return False
    if not _APPROVAL_REQUEST_RE.search(text):
        return False
    # Mentioning that an asset request *requires approval* is not an
    # instruction to approve an existing request. Keep the veto for actual
    # approve/reject/meta phrasings, but allow this creation grammar.
    requires_approval = bool(re.search(
        r'\b(?:requires?|needs?)\s+(?:prior\s+)?approval\b', text, re.I))
    if _REQUEST_NEGATIVE_RE.search(text) and not requires_approval:
        return False
    return True


def is_approval_adversarial(text):
    return bool(_APPROVAL_ADVERSARIAL_RE.search(str(text or '')))


def classify_admin_intent(text):
    """Deterministic approver-lane classification.

    :returns: ``'approve'`` / ``'reject'`` / ``'list'`` / ``None``.
    """
    text = str(text or '')
    if not text.strip():
        return None
    if _PENDING_LIST_RE.search(text):
        return 'list'
    if _APPROVE_RE.match(text):
        return 'approve'
    if _REJECT_RE.match(text):
        return 'reject'
    return None


def _parse_ref_token(text):
    """Pull the ONLY deterministic address token from a turn.

    Accepts the underlying request reference (``AR/...``) or the
    approval code (8 hex chars).  Returns ``(kind, token)``.
    """
    low = str(text or '')
    token = _TARGET_TOKEN_RE.search(low)
    if token:
        return 'name', token.group(0).strip().rstrip('.,;')
    hexes = re.search(r'\b([0-9a-f]{8})\b', low, re.I)
    if hexes:
        return 'ref', hexes.group(1).lower()
    return None, None


def _parse_reject_reason(rest):
    """Bounded optional rejection reason (labelled form only)."""
    match = _REASON_LABEL_RE.search(str(rest or ''))
    val = ''
    if match:
        val = match.group('val').strip(' \t"\'.,;')
    reason = re.sub(r'\s+', ' ', val)
    if len(reason) > _REJECT_LIMIT:
        return ''  # oversized reasons are ignored, not trimmed
    return reason


def extract_approval_entities(text):
    """Deterministic extraction of this slice's typed inputs.

    Only whitelist synonyms of the module's selection; no free-form
    fields, no record identities.  :returns: ``(fields, rest)`` with
    the remaining text (unused for resolution — no hints are trusted).
    """
    text = str(text or '')
    fields = {}
    # The asset TYPE is searched only in the part BEFORE the labelled
    # fields — a reason like "repair the projector" must never become
    # the requested type (deterministic boundary, no guessing).
    low = text.lower()
    reason_idx = low.find('reason')
    type_zone = text[:reason_idx] if reason_idx > -1 else text
    for synonym in _ASSET_TYPE_ORDERED:
        if re.search(r'\b%s\b' % re.escape(synonym), type_zone, re.I):
            fields['asset_type'] = _ASSET_TYPE_SYNONYMS[synonym]
            break
    match = re.search(r'needed\s+(?:by|on|for)\s+', text, re.I)
    if match:
        span = _FOLLOWUP_DATE_SPAN_RE.search(text[match.end():])
        if span:
            fields['needed_by'] = span.group(0).strip()[:60]
    else:
        span = _FOLLOWUP_DATE_SPAN_RE.search(text)
        if span:
            fields['needed_by'] = span.group(0).strip()[:60]
    match = _REASON_LABEL_RE.search(text)
    if match:
        fields['reason'] = re.sub(
            r'\s+', ' ', re.sub(r'[;]+', ' ', match.group(
                'val'))).strip()[:500]
    match = _DESCRIPTION_LABEL_RE.search(text)
    if match:
        fields['description'] = re.sub(
            r'\s+', ' ', match.group('val')).strip()[:200]
    match = _CAMPUS_HINT_RE.search(text)
    if match:
        hint = match.group('hint') or match.group('chint') or ''
        hint = re.sub(r'\bcampus\b', '', hint, flags=re.I)
        hint = re.sub(r'\s+', ' ', hint).strip(' ,')
        if hint:
            fields['campus'] = hint[:100]
    return fields, text


def validate_approval_entities(raw):
    """Strict schema validation (reject-the-whole-turn semantics)."""
    clean = {}
    invalid = []
    if raw is None:
        return clean, True, invalid
    if not isinstance(raw, dict):
        return {}, False, ['entities']
    extra = set(raw) - set(APPROVAL_FIELDS)
    if extra:
        return {}, False, [
            'unknown_fields:%s' % ','.join(sorted(extra))]
    for field in APPROVAL_FIELDS:
        value = raw.get(field)
        if value is None or (isinstance(value, str)
                             and not value.strip()):
            continue
        if not isinstance(value, str):
            invalid.append(field)
            continue
        value = re.sub(r'\s+', ' ', value).strip()
        if not value:
            continue
        if field == 'asset_type':
            # Deterministic canonicalization; the LIVE selection check
            # happens at resolution (fail closed for unknown types).
            value = value.lower()
        if len(value) > _FIELD_LIMITS[field]:
            invalid.append(field)
            continue
        clean[field] = value
    return clean, not invalid, invalid


def missing_approval_fields(payload):
    """Required fields absent from the payload."""
    return [f for f in APPROVAL_REQUIRED_FIELDS
            if not str((payload or {}).get(f) or '').strip()]


def _asset_selection(env):
    """The LIVE selection of the module field (fail closed)."""
    data = env[UNDERLYING_MODEL].fields_get(
        ['asset_type'], attributes=['selection'])
    return (data.get('asset_type') or {}).get('selection') or []


def _human_type_label(env, value):
    for key, label in _asset_selection(env):
        if key == value:
            return label
    raise ValueError('unknown asset type %r' % (value,))


# ---------------------------------------------------------------------------
# The ONE pending approval row
# ---------------------------------------------------------------------------

class EdicaiAIPendingApproval(models.Model):
    """Durable end-to-end approval row (requester → approver).

    ONE row carries the requester's plan (creation) AND the approver's
    decision surface, bound by SHA-256 hashes at both freezes.
    """

    _name = 'edicai.ai.pending.approval'
    _description = 'AI Pending Human Approval (asset request)'
    _order = 'id desc'
    _rec_name = 'ref'

    kind = fields.Char(
        string='Approval Kind', required=True, default=APPROVAL_KIND,
        index=True,
        help='The ONE allow-listed approval vertical (nothing generic).')
    session_id = fields.Many2one(
        'edicai.ai.chat.session', string='Requester Conversation',
        required=True, ondelete='cascade', index=True)
    requester_id = fields.Many2one(
        'res.users', string='Requested By', required=True,
        ondelete='cascade', index=True,
        help='The person whose confirmation created this request. '
             'NEVER auto-authorized to approve it.')
    company_id = fields.Many2one(
        'res.company', string='Institution', required=True,
        default=lambda self: self.env.company, ondelete='restrict',
        index=True)

    # --- the requester's frozen creation plan --------------------------
    vals_json = fields.Text(
        string='Creation Plan (canonical)',
        help='The exact entity values frozen at preview (hash-bound).')
    plan_json = fields.Text(
        string='Approval Plan (canonical)',
        help='The FROZEN plan of the current stage: creation plan at '
             'preview, approve operation plan after submission.')
    plan_hash = fields.Char(string='Plan Hash', index=True,
                            help='SHA-256 of the current frozen plan.')
    ref = fields.Char(string='Approval Code', index=True,
                      help='First 8 hex chars of the current hash.')

    # --- grounded state (server-side only) -----------------------------
    # NOTE: the underlying request is stored as INTEGER + NAME, NOT a
    # Many2one — edicai_ai does not depend on edicai_asset_request, and
    # the registry must load in databases where it is not installed
    # (the same reason the Phase 3 workflow stores identities in JSON).
    request_res_id = fields.Integer(
        string='Asset Request ID', index=True,
        help='The canonical underlying request (bound at submission).')
    request_name = fields.Char(
        string='Asset Request Reference', default='',
        help='The sequence reference underwriting the target identity.')
    designated_approver_id = fields.Many2one(
        'res.users', string='Designated Approver (canonical)',
        ondelete='restrict',
        help='Assigned by the MODULE itself at submission — '
             'transparency only; authority is re-verified at approval.')
    approved_by_id = fields.Many2one(
        'res.users', string='Decided By', ondelete='restrict')
    decided_on = fields.Datetime(string='Decision Time')
    rejection_reason = fields.Char(string='Rejection Reason (bounded)')

    # --- the frozen entity columns (grounded display) ------------------
    asset_type = fields.Char(string='Asset Type (canonical)', default='')
    description = fields.Char(string='Description (canonical)', default='')
    reason = fields.Char(string='Reason (canonical)', default='')
    needed_by = fields.Char(string='Needed By (canonical ISO date)',
                            default='')
    campus_id = fields.Many2one(
        'edicai.campus', string='Campus', ondelete='restrict')

    status = fields.Selection(
        selection=[
            (STATUS_DRAFT, 'Draft'),
            (STATUS_PREVIEW, 'Preview'),
            (STATUS_PENDING, 'Approval Required'),
            (STATUS_APPROVED, 'Approved'),
            (STATUS_EXECUTED, 'Executed'),
            (STATUS_REJECTED, 'Rejected'),
            (STATUS_CANCELLED, 'Cancelled'),
            (STATUS_EXPIRED, 'Expired'),
            (STATUS_FAILED, 'Failed'),
            (STATUS_INVALIDATED, 'Invalidated (request changed)'),
        ],
        default=STATUS_DRAFT, required=True, index=True)
    result_json = fields.Text(string='Approval Result Snapshot')
    failure_reason = fields.Char(string='Machine Reason Code')

    #: Materially immutable keys (the approval request §7): blocked on
    #: every external write after the row is previewed.  Lifecycle
    #: methods write through the internal flag (see below).
    _IMMUTABLE_KEYS = frozenset((
        'vals_json', 'plan_json', 'plan_hash', 'request_res_id',
        'request_name',
        'asset_type', 'description', 'reason', 'needed_by',
        'campus_id', 'session_id', 'requester_id', 'company_id',
        'kind', 'ref',
    ))
    _RESULT_KEYS = frozenset((
        'status', 'result_json', 'failure_reason',
        'rejection_reason', 'approved_by_id', 'decided_on',
        'designated_approver_id', 'approved_json', 'approval_hash',
    ))

    # ------------------------------------------------------------------
    # Write guard: immutability after preview
    # ------------------------------------------------------------------

    def _lifecycle_write(self, vals):
        """Internal, whitelisted write used ONLY by lifecycle code."""
        return super(EdicaiAIPendingApproval, self.with_context(
            ai_approval_lifecycle=True)).write(vals)

    def write(self, vals):
        for record in self:
            if self.env.context.get('ai_approval_lifecycle'):
                break
            if record.status == STATUS_DRAFT:
                continue
            blocked = [key for key in vals
                       if key in record._IMMUTABLE_KEYS]
            if blocked:
                _logger.warning(
                    'AI pending approval %s: external write of %s at '
                    'status %s blocked (immutable).', record.id,
                    ','.join(blocked), record.status)
                return True
            # A lifecycle-status change stays monotone (no terminal
            # resurrection, no pending→draft).
            new_status = vals.get('status')
            if new_status and new_status != record.status:
                legal = (
                    record.status == STATUS_PREVIEW and new_status
                    in (STATUS_PENDING, STATUS_CANCELLED,
                        STATUS_EXPIRED, STATUS_FAILED)
                    or record.status == STATUS_PENDING and new_status
                    in (STATUS_APPROVED, STATUS_REJECTED,
                        STATUS_CANCELLED, STATUS_EXPIRED,
                        STATUS_FAILED, STATUS_INVALIDATED)
                    or record.status == STATUS_APPROVED and new_status
                    in (STATUS_EXECUTED, STATUS_FAILED,
                        STATUS_CANCELLED)
                    or record.status in STATUS_TERMINAL and False)
                if not legal:
                    _logger.warning(
                        'AI pending approval %s: transition %s → %s '
                        'blocked.', record.id, record.status,
                        new_status)
                    return True
        return super().write(vals)

    # ------------------------------------------------------------------
    # Canonical reads (never trust raw JSON)
    # ------------------------------------------------------------------

    def _read_vals(self):
        """The frozen creation payload (validated on every read)."""
        try:
            data = json.loads(self.vals_json or '{}')
        except Exception:
            _logger.exception('AI approval %s: vals unreadable.',
                              self.id)
            return {}
        return data if isinstance(data, dict) else {}

    def _read_plan(self):
        try:
            data = json.loads(self.plan_json or '{}')
        except Exception:
            _logger.exception('AI approval %s: plan unreadable.',
                              self.id)
            return {}
        return data if isinstance(data, dict) else {}

    def _read_result(self):
        try:
            data = json.loads(self.result_json or '{}')
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _store_result(self, results):
        self._lifecycle_write({'result_json':
                               json.dumps(results, sort_keys=True)})

    @api.model
    def _material_snapshot(self, request):
        """Canonical material snapshot of the underlying asset request.

        Phase 12 (BUG-011): computed with the SAME canonical reader used
        when the approval was submitted.  Only the fields that change
        WHAT is approved participate (see ``MATERIAL_REQUEST_FIELDS``);
        approver bookkeeping and timestamps do not.
        """
        return {
            'request_id': request.id,
            'name': request.name or '',
            'company_id': request.company_id.id or 0,
            'campus_id': request.campus_id.id or 0,
            'requested_by': request.requested_by.id or 0,
            'approver_id': request.approver_id.id or 0,
            'asset_id': request.asset_id.id or 0,
            'asset_type': request.asset_type or '',
            'asset_description': request.asset_description or '',
            'requested_quantity': int(request.requested_quantity or 0),
            'reason': request.reason or '',
            'needed_by_date': (
                fields.Date.to_string(request.needed_by_date)
                if request.needed_by_date else ''),
            'state': request.state or '',
        }

    # ------------------------------------------------------------------
    # Lookups (owner / approver scoped — record rules on top)
    # ------------------------------------------------------------------

    @api.model
    def open_active(self, session, user=None):
        """The (at most one) DRAFT/PREVIEW row for session + owner."""
        if session is None:
            return self.env['edicai.ai.pending.approval']
        user = user or self.env.user
        return self.search([
            ('session_id', '=', session.id),
            ('requester_id', '=', user.id),
            ('status', 'in', list(STATUS_ACTIVE)),
        ], limit=1)

    @api.model
    def pending_for(self, company=None):
        """Grounded PENDING rows of ONE company (list + addressing).

        The APPROVER authority is NOT trusted from this lookup — it is
        re-verified at approval time (§10/§11).  Record rules still
        apply: only visible rows come back.
        """
        company = company or self.env.company
        return self.search([
            ('status', '=', STATUS_PENDING),
            ('company_id', '=', company.id),
        ], order='create_date asc, id asc')

    @api.model
    def find_for_user_session(self, session, user=None):
        """Most recent approval row of (session, requester)."""
        if session is None:
            return self.env['edicai.ai.pending.approval']
        user = user or self.env.user
        return self.search([
            ('session_id', '=', session.id),
            ('requester_id', '=', user.id),
        ], limit=1)

    @api.model
    def find_by_address(self, token_kind, token, company=None):
        """Resolve 'approve|reject <AR/... | 8-hex-code | this>'.

        'this' (bare word) resolves to THE single pending row of the
        company when there is exactly one — deterministic.
        """
        company = company or self.env.company
        Approval = self.env['edicai.ai.pending.approval']
        domain = [
            ('status', '=', STATUS_PENDING),
            ('company_id', '=', company.id),
        ]
        if token_kind == 'ref' and token:
            return Approval.search(domain + [('ref', '=', token)],
                                   limit=1)
        if token_kind == 'name' and token:
            return Approval.search(domain + [
                ('request_name', '=ilike', token)], limit=1)
        if not token_kind:
            rows = Approval.search(domain)
            return rows if len(rows) == 1 else Approval.browse(())
        return Approval.browse(())

    @api.model
    def find_decided_by_address(self, token_kind, token,
                                company=None):
        """Like :meth:`find_by_address` but for DECIDED rows only.

        An executed or rejected row addressed again must replay its
        grounded decision honestly (duplicate-safety surface).
        """
        company = company or self.env.company
        Approval = self.env['edicai.ai.pending.approval']
        domain = [
            ('status', 'in', [STATUS_EXECUTED, STATUS_REJECTED]),
            ('company_id', '=', company.id),
        ]
        if token_kind == 'ref' and token:
            return Approval.search(domain + [('ref', '=', token)],
                                   limit=1)
        if token_kind == 'name' and token:
            return Approval.search(domain + [
                ('request_name', '=ilike', token)], limit=1)
        return Approval.browse(())

    @api.model
    def find_any_by_address(self, token_kind, token, company=None):
        """Address ANY row regardless of status (status answers)."""
        company = company or self.env.company
        Approval = self.env['edicai.ai.pending.approval']
        if token_kind == 'ref' and token:
            return Approval.search([
                ('ref', '=', token),
                ('company_id', '=', company.id)], limit=1)
        if token_kind == 'name' and token:
            return Approval.search([
                ('request_name', '=ilike', token),
                ('company_id', '=', company.id)], limit=1)
        return Approval.browse(())

    # ------------------------------------------------------------------
    # Lazy expiry (bounded lifetime — fail closed)
    # ------------------------------------------------------------------

    def _approval_timeout_minutes(self):
        Approval = self.env['edicai.ai.pending.approval']
        try:
            value = Approval.env['ir.config_parameter'].sudo() \
                .get_param(PARAM_APPROVAL_TIMEOUT,
                           DEFAULT_APPROVAL_TIMEOUT_MINUTES)
            return max(1, int(float(value)))
        except Exception:
            return DEFAULT_APPROVAL_TIMEOUT_MINUTES

    @api.model
    def expire_pending(self, company=None):
        """Expire PENDING approvals older than the approval window.

        Called at the start of a turn (no cron).  Only rows visible in
        the requested company are swept — every session user sweeps
        their own view, deterministic and cheap.
        """
        Approval = self.env['edicai.ai.pending.approval']
        timeout = Approval._approval_timeout_minutes()
        cutoff = fields.Datetime.now() - timedelta(minutes=timeout)
        domain = [
            ('status', '=', STATUS_PENDING),
            ('create_date', '<', cutoff),
        ]
        if company is not None:
            domain.append(('company_id', '=', company.id))
        for row in Approval.search(domain):
            row._lifecycle_write({'status': STATUS_EXPIRED,
                                  'failure_reason':
                                      'APPROVAL_TIMEOUT'})
            row._audit_event(
                'APPROVAL_EXPIRED', decision='deny',
                reason_code='APPROVAL_TIMEOUT',
                metadata={'approval_id': row.id})
        return True

    def _is_expired_now(self):
        cutoff = fields.Datetime.now() - timedelta(
            minutes=self._approval_timeout_minutes())
        return bool(self.create_date and self.create_date < cutoff)

    def _preview_still_valid(self):
        """Preview timeout — same window as the Phase 2/3 previews."""
        minutes = self.env[
            'edicai.ai.action.policy'].get_confirm_timeout_minutes()
        cutoff = fields.Datetime.now() - timedelta(minutes=minutes)
        return bool(self.create_date and self.create_date >= cutoff)

    # ------------------------------------------------------------------
    # Requester lifecycle (compose → preview → confirm)
    # ------------------------------------------------------------------

    @api.model
    def start_request(self, session, payload, user=None):
        """A NEW approval-lane request (draft + immediate advance).

        Supersedes any ACTIVE (draft/preview) row of this session —
        one routable item per conversation (proven rule).
        """
        Approval = self.env['edicai.ai.pending.approval']
        user = user or self.env.user
        previous = self.open_active(session, user)
        if previous:
            previous._lifecycle_write({'status': STATUS_CANCELLED,
                                       'failure_reason':
                                           'SUPERSEDED_BY_NEW_REQUEST'})
            previous._audit_event(
                'APPROVAL_SUPERSEDED', decision='deny',
                reason_code='SUPERSEDED_BY_NEW_REQUEST',
                metadata={'approval_id': previous.id})
        clean, ok, invalid = validate_approval_entities(payload or {})
        if not ok:
            Approval._audit_event(
                'INTENT_DETECTED', conversation=session, user=user,
                decision='deny', reason_code='APPROVAL_FIELD_INVALID',
                metadata={'invalid': ','.join(invalid)})
            return Approval._error_reply(
                SAFE_MESSAGES[VALIDATION_FAILED] +
                ' Re-send the request without the invalid values.')
        row = Approval.create({
            'session_id': session.id,
            'requester_id': user.id,
            'company_id': self.env.company.id,
            'vals_json': json.dumps(clean, sort_keys=True),
        })
        Approval._audit_event(
            'APPROVAL_PROPOSED', conversation=session, user=user,
            decision='allow', reason_code='REQUEST_CREATED',
            metadata={'approval_id': row.id})
        return row.advance()

    def merge_payload(self, payload):
        """Field supply on the DRAFT row (immutable once previewed)."""
        if self.status != STATUS_DRAFT:
            return self, False
        clean, ok, invalid = validate_approval_entities(payload or {})
        if not ok or not clean:
            return self, False
        current = self._read_vals()
        current.update(clean)
        self._lifecycle_write({'vals_json':
                               json.dumps(current, sort_keys=True)})
        return self, True

    def _current_payload(self):
        """Entity view from the frozen columns + unsolved hints."""
        data = self._read_vals()
        payload = dict(data)
        payload.setdefault('asset_type', self.asset_type or '')
        payload.setdefault('description', self.description or '')
        payload.setdefault('reason', self.reason or '')
        payload.setdefault('needed_by', self.needed_by or
                           data.get('needed_by') or '')
        payload.setdefault('campus', data.get('campus') or '')
        return payload

    def advance(self):
        """Resolve → freeze the creation plan → preview (or ask)."""
        self.ensure_one()
        payload = self._current_payload()
        outcome = self.resolve_approval_payload(
            payload, self.company_id)
        state = outcome.get('status')
        if state == 'missing':
            return self._missing_reply(outcome.get('field'))
        if state == 'invalid_date':
            self._audit_event(
                'INTENT_DETECTED', decision='deny',
                reason_code='APPROVAL_DATE_INVALID',
                metadata={'approval_id': self.id})
            return self._error_reply(
                'That needed-by date is not valid. Use a future date '
                'such as "tomorrow", "Friday" or "2026-12-01" — '
                '%s' % _NOTHING_CHANGED)
        if state == 'not_found':
            self._audit_event(
                'INTENT_AMBIGUOUS', decision='deny',
                reason_code='ENTITY_NOT_FOUND:campus',
                metadata={'approval_id': self.id})
            return self._error_reply(
                'The campus "%s" could not be found in your '
                'institution. Please name an existing campus — %s'
                % (payload.get('campus') or '', _NOTHING_CHANGED))
        # 'ok' — freeze the creation plan.
        resolved = outcome['payload']
        plan = {
            'effect': 'create_and_submit_for_approval',
            'res_model': UNDERLYING_MODEL,
            'payload': resolved,
        }
        digest = plan_hash(plan)
        self._lifecycle_write({
            'vals_json': json.dumps(resolved, sort_keys=True),
            'plan_json': json.dumps(plan, sort_keys=True),
            'plan_hash': digest,
            'ref': digest[:8],
            'asset_type': resolved.get('asset_type') or '',
            'description': resolved.get('description') or '',
            'reason': resolved.get('reason') or '',
            'needed_by': resolved.get('needed_by') or '',
            'campus_id': resolved.get('campus_id') or False,
            'status': STATUS_PREVIEW,
        })
        self._audit_event('APPROVAL_PREVIEWED', decision='allow',
                          reason_code='PREVIEW_READY',
                          metadata={'approval_id': self.id,
                                    'plan_hash': digest})
        return self.preview_reply()

    # ------------------------------------------------------------------
    # Requester confirmation → canonical create + submit → approval row
    # ------------------------------------------------------------------

    def _lock_nowait(self):
        """Row-level lock, fail fast on concurrency (same pattern)."""
        try:
            self.env.cr.execute(
                'SELECT id FROM %s WHERE id = %%s FOR UPDATE NOWAIT'
                % self._table, [self.id])
            return True
        except psycopg2.Error as exc:
            _logger.info(
                'AI pending approval %s: concurrent turn (%s).',
                self.id, type(exc).__name__)
            return False

    def confirm_and_submit(self):
        """Requester confirmation → canonical request + submission.

        lock → status re-check → preview expiry → RE-AUTHORIZATION →
        canonical create + ``action_submit`` AS THE REQUESTER (under
        the requester's own record rules) → approval plan frozen →
        status ``pending``.  The APPROVAL itself is NEVER given here.
        """
        self.ensure_one()
        if self.status != STATUS_PREVIEW:
            return {'outcome': 'not_confirmable'}
        if not self._lock_nowait():
            self._audit_event('APPROVAL_DUPLICATE',
                              reason_code='CONCURRENT_TURN',
                              metadata={'approval_id': self.id})
            return {'outcome': 'duplicate_concurrent'}
        fresh = self.search([('id', '=', self.id)], limit=1)
        if fresh.status != STATUS_PREVIEW:
            return {'outcome': 'duplicate', 'row': fresh}
        if not fresh._preview_still_valid():
            return {'outcome': 'expired_preview', 'row': fresh}
        fresh._audit_event('APPROVAL_CONFIRMED', decision='allow',
                           reason_code='REQUESTER_CONFIRMED',
                           metadata={'approval_id': fresh.id,
                                     'plan_hash': fresh.plan_hash})
        # The requester gate re-runs here (second gate).
        gate = self.env['edicai.ai.action.policy'] \
            .check_approval_requester_access(user=self.env.user)
        if not gate['allowed']:
            fresh._audit_event('APPROVAL_AUTH_DENIED', decision='deny',
                               reason_code=gate['reason_code'],
                               metadata={'approval_id': fresh.id})
            return {'outcome': 'denied', 'row': fresh,
                    'reason_code': gate['reason_code']}
        return self._execute_creation(fresh)

    def _execute_creation(self, row):
        """Canonical create + ``action_submit`` AS THE REQUESTER.

        Record rules apply throughout.  On success the approval plan
        (a SECOND hash) freezes and the row goes to ``pending``: a
        waiting human approval is now the ONLY way forward.
        """
        payload = row._read_plan().get('payload') or {}
        Res = self.env[UNDERLYING_MODEL].with_user(
            self.env.user).with_company(row.company_id)
        # Target revalidation (under the requester's rules).
        campus = self.env['edicai.campus'].with_user(
            self.env.user).with_company(row.company_id).search([
                ('id', '=', payload.get('campus_id')),
                ('company_id', '=', row.company_id.id),
            ], limit=1)
        if not campus:
            row._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='CREATE_CAMPUS_UNAVAILABLE',
                metadata={'approval_id': row.id})
            return {'outcome': 'error', 'row': row,
                    'error_code': 'CREATE_CAMPUS_UNAVAILABLE'}
        vals = {
            'campus_id': campus.id,
            'asset_type': payload.get('asset_type') or 'other',
            'asset_description': payload.get('description') or '',
            'reason': payload.get('reason') or '',
            'needed_by_date': payload.get('needed_by') or '',
        }
        try:
            request = Res.create(vals)
        except Exception as exc:
            _logger.info(
                'AI pending approval %s: canonical create rejected '
                '(%s): %s', row.id, type(exc).__name__, exc)
            row._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='CANONICAL_CREATE_REJECTED',
                metadata={'approval_id': row.id,
                          'error_type': type(exc).__name__})
            return {'outcome': 'error', 'row': row,
                    'error_code': 'CANONICAL_CREATE_REJECTED'}
        # Pre-assign the DESIGNATED approver with the module's own
        # search semantics ("first admin, non-share"), expressed with
        # THIS Odoo version's field name.  The module's internal
        # ``_assign_approver`` uses the removed Odoo-17 name
        # (``groups_id`` — a pre-existing incompatibility; the module
        # is unmodifiable) and would crash; with the approver pre-set
        # the canonical ``action_submit`` short-circuits that helper
        # and proceeds untouched.  Approval AUTHORITY remains
        # group-based and is re-verified server-side at decision
        # time — this assignment is bookkeeping, never authority.
        approver = self.env['res.users'].with_user(self.env.user) \
            .search([
                ('group_ids', 'in',
                 self.env.ref('edicai_base.group_edicai_admin').id),
                ('share', '=', False),
            ], limit=1)
        if approver:
            try:
                request.approver_id = approver
            except Exception as exc:
                _logger.info(
                    'AI pending approval %s: approver assignment '
                    'rejected (%s): %s', row.id,
                    type(exc).__name__, exc)
                row._audit_event(
                    'APPROVAL_EXECUTION_FAILED', decision='error',
                    reason_code='CANONICAL_SUBMIT_REJECTED',
                    metadata={'approval_id': row.id,
                              'error_type': type(exc).__name__})
                return {'outcome': 'error', 'row': row,
                        'error_code': 'CANONICAL_SUBMIT_REJECTED'}
        try:
            request.action_submit()
        except Exception as exc:
            _logger.info(
                'AI pending approval %s: canonical submit rejected '
                '(%s): %s', row.id, type(exc).__name__, exc)
            row._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='CANONICAL_SUBMIT_REJECTED',
                metadata={'approval_id': row.id,
                          'error_type': type(exc).__name__})
            return {'outcome': 'error', 'row': row,
                    'error_code': 'CANONICAL_SUBMIT_REJECTED'}
        # ---- freeze the APPROVAL plan (a DIFFERENT hash) -----------
        request = Res.browse(request.id).with_user(
            self.env.user).with_company(row.company_id)
        material_snapshot = self._material_snapshot(request)
        approval_plan = {
            'effect': 'approve',
            'res_model': UNDERLYING_MODEL,
            'request_id': request.id,
            'request_name': request.name,
            'requester_id': row.requester_id.id,
            'company_id': row.company_id.id,
            # Phase 12 (BUG-011): the material target snapshot is part of
            # the frozen approval plan/hash, and is re-read and compared
            # immediately before execution.
            'material': material_snapshot,
            'material_hash': plan_hash(material_snapshot),
            'submitted_on':
                fields.Datetime.to_string(fields.Datetime.now()),
        }
        digest = plan_hash(approval_plan)
        row._lifecycle_write({
            'status': STATUS_PENDING,
            'request_res_id': request.id,
            'request_name': request.name,
            'designated_approver_id': (
                request.approver_id and request.approver_id.id
                or False),
            'plan_json': json.dumps(approval_plan, sort_keys=True),
            'plan_hash': digest,
            'ref': digest[:8],
        })
        row._audit_event('APPROVAL_SUBMITTED', decision='allow',
                         reason_code='WAITING_APPROVAL',
                         metadata={'approval_id': row.id,
                                   'request_id': request.id,
                                   'plan_hash': digest})
        return {'outcome': 'submitted', 'row': row}

    # ------------------------------------------------------------------
    # Approver lifecycle (§11/§12: approval THEN separated execution)
    # ------------------------------------------------------------------

    def _approve_gate(self, actor):
        """The FULL approver gate (server-side, fail closed).

        The approver identity is never trusted from the routing text:
        this gate needs the ACTUAL group, the requester/approver split
        and the SAME-COMPANY rule (prompt §6/§21/§22).
        """
        policy = self.env['edicai.ai.action.policy']
        if not policy.is_approval_enabled():
            return 'APPROVAL_DISABLED'
        if self.requester_id.id == actor.id:
            return 'SELF_APPROVAL'
        try:
            approved = actor.has_group(APPROVER_GROUP)
        except Exception:
            approved = False
        if not approved:
            return 'NOT_AN_APPROVER'
        if self.company_id.id != actor.company_id.id:
            return 'COMPANY_MISMATCH'
        return None

    def approve_and_execute(self, actor=None):
        """Approval decision + canonical execution, fail closed.

        lock → status re-check → authority gate → plan integrity →
        expiry → target validity → canonical ``action_approve`` AS
        THE APPROVER → post-conditions.  NO LLM call anywhere.
        """
        self.ensure_one()
        actor = actor or self.env.user
        if self.status != STATUS_PENDING:
            return {'outcome': 'not_pending'}
        if not self._lock_nowait():
            self._audit_event('APPROVAL_DUPLICATE',
                              reason_code='CONCURRENT_APPROVAL',
                              metadata={'approval_id': self.id})
            return {'outcome': 'duplicate_concurrent',
                    'actor_id': actor.id}
        # ---- decision-time re-checks FIRST (fail closed): an
        # unauthorized actor must get a DENIAL, never a row-state
        # echo — under their own record rules they may not even SEE
        # the row (prompt §11: authority before visibility).
        denial = self._approve_gate(actor)
        if denial:
            self._audit_event(
                'APPROVAL_AUTH_DENIED', decision='deny',
                reason_code=denial,
                metadata={'approval_id': self.id,
                          'actor': actor.id})
            return {'outcome': 'denied', 'row': self,
                    'reason_code': denial}
        Approval = self.env['edicai.ai.pending.approval'] \
            .with_user(actor).with_company(self.company_id)
        fresh = Approval.search([('id', '=', self.id)], limit=1)
        if not fresh or fresh.status != STATUS_PENDING:
            return {'outcome': 'duplicate',
                    'row': fresh or self}
        plan = fresh._read_plan()
        if plan.get('effect') != 'approve' or \
                plan.get('res_model') != UNDERLYING_MODEL:
            fresh._lifecycle_write({'status': STATUS_FAILED,
                                    'failure_reason':
                                        'APPROVAL_HASH_MISMATCH'})
            fresh._audit_event(
                'APPROVAL_AUTH_DENIED', decision='deny',
                reason_code='APPROVAL_HASH_MISMATCH',
                metadata={'approval_id': fresh.id})
            return {'outcome': 'hash_mismatch', 'row': fresh}
        if plan_hash(plan) != fresh.plan_hash:
            fresh._lifecycle_write({'status': STATUS_FAILED,
                                    'failure_reason':
                                        'APPROVAL_HASH_MISMATCH'})
            fresh._audit_event(
                'APPROVAL_AUTH_DENIED', decision='deny',
                reason_code='APPROVAL_HASH_MISMATCH',
                metadata={'approval_id': fresh.id})
            return {'outcome': 'hash_mismatch', 'row': fresh}
        if fresh._is_expired_now():
            fresh._lifecycle_write({'status': STATUS_EXPIRED,
                                    'failure_reason':
                                        'APPROVAL_TIMEOUT'})
            fresh._audit_event('APPROVAL_EXPIRED', decision='deny',
                               reason_code='APPROVAL_TIMEOUT',
                               metadata={'approval_id': fresh.id})
            return {'outcome': 'expired', 'row': fresh}
        return self._execute_approved(fresh, actor)

    @api.model
    def _execute_approved(self, row, actor):
        """The EXECUTION SERVICE — separated from the approval.

        lock (caller) → the target must STILL be visible under the
        APPROVER's own record rules, in the plan's company and
        unprocessed → canonical ``action_approve`` AS THE APPROVER →
        post-conditions verified (prompt §12).
        """
        plan = row._read_plan()
        res_model = plan['res_model']
        Req = self.env[res_model].with_user(actor).with_company(
            row.company_id)
        target = Req.search([
            ('id', '=', plan.get('request_id')),
            ('company_id', '=', row.company_id.id),
        ], limit=1)
        if not target:
            row._lifecycle_write({'status': STATUS_FAILED,
                                  'failure_reason':
                                      'TARGET_UNAVAILABLE'})
            row._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='TARGET_UNAVAILABLE',
                metadata={'approval_id': row.id,
                          'actor': actor.id})
            return {'outcome': 'error', 'row': row,
                    'error_code': 'TARGET_UNAVAILABLE'}
        if target.state != 'submitted':
            # Someone else already processed the request — honest
            # fail-closed answer, no double execution.
            row._lifecycle_write({'status': STATUS_CANCELLED,
                                  'failure_reason':
                                      'TARGET_PROCESSED_ELSEWHERE'})
            row._audit_event(
                'APPROVAL_DUPLICATE', decision='deny',
                reason_code='TARGET_PROCESSED_ELSEWHERE',
                metadata={'approval_id': row.id,
                          'target_state': target.state})
            return {'outcome': 'target_processed', 'row': row,
                    'target_state': target.state}
        # ---- P0 (BUG-011): material-change boundary -----------------
        # Recompute the canonical snapshot from the LIVE target under
        # the current transaction and compare with the snapshot frozen
        # into the approval plan.  A different snapshot means the
        # approver is no longer approving what was submitted.
        frozen = plan.get('material')
        frozen_hash = plan.get('material_hash')
        if not isinstance(frozen, dict) or not frozen or not frozen_hash:
            invalid = 'MATERIAL_SNAPSHOT_MISSING'
        elif (row._material_snapshot(target) != frozen or
              plan_hash(row._material_snapshot(target)) != frozen_hash):
            invalid = 'MATERIAL_SNAPSHOT_CHANGED'
        else:
            invalid = False
        if invalid:
            row._lifecycle_write({'status': STATUS_INVALIDATED,
                                  'failure_reason': invalid})
            row._audit_event(
                'APPROVAL_INVALIDATED', decision='deny',
                reason_code=invalid,
                metadata={'approval_id': row.id,
                          'actor': actor.id,
                          'request_id': target.id})
            return {'outcome': 'invalidated', 'row': row,
                    'reason_code': invalid}
        row._lifecycle_write({'status': STATUS_APPROVED})
        row._audit_event('APPROVAL_APPROVED', decision='allow',
                         reason_code='APPROVER_APPROVED',
                         metadata={'approval_id': row.id,
                                   'approver': actor.id,
                                   'request_id': target.id})
        row._audit_event('APPROVAL_EXECUTION_STARTED', decision='allow',
                         reason_code='CANONICAL_EXECUTE',
                         metadata={'approval_id': row.id})
        try:
            target.action_approve()
        except Exception as exc:
            row._lifecycle_write({'status': STATUS_FAILED,
                                  'failure_reason':
                                      'CANONICAL_APPROVE_FAILED'})
            row._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='CANONICAL_APPROVE_FAILED',
                metadata={'approval_id': row.id,
                          'error_type': type(exc).__name__})
            return {'outcome': 'error', 'row': row,
                    'error_code': 'CANONICAL_APPROVE_FAILED'}
        verified = Req.search([('id', '=', target.id)], limit=1)
        ok = bool(verified) and verified.state == 'approved' and \
            bool(verified.approved_date)
        result = {
            'request_name': plan.get('request_name'),
            'request_id': target.id,
            'approved_by': actor.name,
            'approved_on': fields.Datetime.to_string(
                fields.Datetime.now()),
            'verified': ok,
            'state': verified.state if verified else '',
            'target_state_before': 'submitted',
        }
        row._lifecycle_write({
            'status': STATUS_EXECUTED if ok else STATUS_FAILED,
            'approved_by_id': actor.id,
            'decided_on': fields.Datetime.now(),
            'result_json': json.dumps(result, sort_keys=True),
        })
        if not ok:
            row._audit_event(
                'APPROVAL_VERIFICATION_FAILED', decision='error',
                reason_code='APPROVAL_STATE_UNVERIFIED',
                metadata={'approval_id': row.id})
            return {'outcome': 'verification_failed', 'row': row}
        row._audit_event('APPROVAL_EXECUTED', decision='allow',
                         reason_code='CANONICAL_STATE_VERIFIED',
                         metadata={'approval_id': row.id,
                                   'request_id': target.id})
        return {'outcome': 'executed', 'row': row,
                'result': result}

    def reject_and_execute(self, reason=None, actor=None):
        """Approver rejection — canonical ``action_reject``.

        A bounded optional reason is kept ON THE APPROVAL ROW (the
        module writes its own chatter annotation).  A rejected row is
        terminal — it can never be executed afterwards.
        """
        self.ensure_one()
        actor = actor or self.env.user
        if self.status != STATUS_PENDING:
            return {'outcome': 'not_pending'}
        if not self._lock_nowait():
            self._audit_event('APPROVAL_DUPLICATE',
                              reason_code='CONCURRENT_REJECTION',
                              metadata={'approval_id': self.id})
            return {'outcome': 'duplicate_concurrent',
                    'actor_id': actor.id}
        # Authority BEFORE visibility (see approve_and_execute).
        denial = self._approve_gate(actor)
        if denial:
            self._audit_event(
                'APPROVAL_AUTH_DENIED', decision='deny',
                reason_code=denial,
                metadata={'approval_id': self.id,
                          'actor': actor.id})
            return {'outcome': 'denied', 'row': self,
                    'reason_code': denial}
        Approval = self.env['edicai.ai.pending.approval'] \
            .with_user(actor).with_company(self.company_id)
        fresh = Approval.search([('id', '=', self.id)], limit=1)
        if not fresh or fresh.status != STATUS_PENDING:
            return {'outcome': 'duplicate',
                    'row': fresh or self}
        plan = fresh._read_plan()
        if plan_hash(plan) != fresh.plan_hash:
            fresh._lifecycle_write({'status': STATUS_FAILED,
                                    'failure_reason':
                                        'APPROVAL_HASH_MISMATCH'})
            fresh._audit_event(
                'APPROVAL_AUTH_DENIED', decision='deny',
                reason_code='APPROVAL_HASH_MISMATCH',
                metadata={'approval_id': fresh.id})
            return {'outcome': 'hash_mismatch', 'row': fresh}
        if fresh._is_expired_now():
            fresh._lifecycle_write({'status': STATUS_EXPIRED,
                                    'failure_reason':
                                        'APPROVAL_TIMEOUT'})
            fresh._audit_event('APPROVAL_EXPIRED', decision='deny',
                               reason_code='APPROVAL_TIMEOUT',
                               metadata={'approval_id': fresh.id})
            return {'outcome': 'expired', 'row': fresh}
        Req = self.env[plan['res_model']].with_user(actor) \
            .with_company(fresh.company_id)
        target = Req.search([
            ('id', '=', plan.get('request_id')),
            ('company_id', '=', fresh.company_id.id),
            ('name', '=', plan.get('request_name')),
        ], limit=1)
        if not target:
            fresh._lifecycle_write({'status': STATUS_FAILED,
                                    'failure_reason':
                                        'TARGET_UNAVAILABLE'})
            fresh._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='TARGET_UNAVAILABLE',
                metadata={'approval_id': fresh.id})
            return {'outcome': 'error', 'row': fresh,
                    'error_code': 'TARGET_UNAVAILABLE'}
        if target.state != 'submitted':
            fresh._lifecycle_write({'status': STATUS_CANCELLED,
                                    'failure_reason':
                                        'TARGET_PROCESSED_ELSEWHERE'})
            fresh._audit_event(
                'APPROVAL_DUPLICATE', decision='deny',
                reason_code='TARGET_PROCESSED_ELSEWHERE',
                metadata={'approval_id': fresh.id,
                          'target_state': target.state})
            return {'outcome': 'target_processed', 'row': fresh,
                    'target_state': target.state}
        try:
            target.action_reject()
        except Exception as exc:
            fresh._lifecycle_write({'status': STATUS_FAILED,
                                    'failure_reason':
                                        'CANONICAL_REJECT_FAILED'})
            fresh._audit_event(
                'APPROVAL_EXECUTION_FAILED', decision='error',
                reason_code='CANONICAL_REJECT_FAILED',
                metadata={'approval_id': fresh.id,
                          'error_type': type(exc).__name__})
            return {'outcome': 'error', 'row': fresh,
                    'error_code': 'CANONICAL_REJECT_FAILED'}
        verified = Req.search([('id', '=', target.id)], limit=1)
        ok = bool(verified) and verified.state == 'rejected'
        safe_reason = (str(reason or '').strip())[:_REJECT_LIMIT]
        fresh._lifecycle_write({
            'status': STATUS_REJECTED if ok else STATUS_FAILED,
            'approved_by_id': actor.id,
            'decided_on': fields.Datetime.now(),
            'rejection_reason': safe_reason,
            'result_json': json.dumps({
                'request_name': plan.get('request_name'),
                'rejected_by': actor.name,
                'decided_on': fields.Datetime.to_string(
                    fields.Datetime.now()),
                'state': verified.state if verified else '',
            }, sort_keys=True),
        })
        if not ok:
            fresh._audit_event(
                'APPROVAL_VERIFICATION_FAILED', decision='error',
                reason_code='REJECTION_STATE_UNVERIFIED',
                metadata={'approval_id': fresh.id})
            return {'outcome': 'verification_failed', 'row': fresh}
        fresh._audit_event('APPROVAL_REJECTED', decision='allow',
                           reason_code='APPROVER_REJECTED',
                           metadata={'approval_id': fresh.id,
                                     'actor': actor.id,
                                     'reasoned': bool(safe_reason)})
        return {'outcome': 'rejected', 'row': fresh,
                'reason': safe_reason,
                'rejected_by': actor.name}

    # ------------------------------------------------------------------
    # Requester cancellation (§15)
    # ------------------------------------------------------------------

    def cancel(self):
        """Requester withdrawal (§15) — conversational lane only.

        ``edicai_asset_request`` has NO canonical cancel action (nor a
        cancel button in its views), so the repository semantic for a
        submitted request is: it stays submitted until an authorized
        admin decides on it in the standard interface.  Withdrawal
        therefore:

        * draft/preview → freezes the conversational draft (nothing
          was ever created);
        * pending → freezes the APPROVAL REQUEST only — a withdrawn
          approval can never execute through this lane again — and
          reports the residual business state honestly.  NO business
          cancellation is invented.
        """
        self.ensure_one()
        if self.status in (STATUS_DRAFT, STATUS_PREVIEW):
            self._lifecycle_write({'status': STATUS_CANCELLED,
                                   'failure_reason':
                                       'USER_CANCELLED'})
            self._audit_event('APPROVAL_CANCELLED', decision='deny',
                              reason_code='USER_CANCELLED',
                              metadata={'approval_id': self.id})
            return {'outcome': 'cancelled', 'row': self}
        if self.status != STATUS_PENDING:
            return {'outcome': 'not_cancellable', 'row': self}
        user = self.env.user
        if user.id != self.requester_id.id:
            self._audit_event(
                'APPROVAL_AUTH_DENIED', decision='deny',
                reason_code='NOT_THE_REQUESTER',
                metadata={'approval_id': self.id,
                          'actor': user.id})
            return {'outcome': 'denied', 'row': self,
                    'reason_code': 'NOT_THE_REQUESTER'}
        # Residual business state, read under the requester's rules —
        # reported honestly, NEVER mutated (no invented semantics).
        target_state = ''
        target_name = self.request_name or ''
        if self.request_res_id:
            Req = self.env[UNDERLYING_MODEL].with_user(user) \
                .with_company(self.company_id)
            target = Req.search([('id', '=', self.request_res_id)],
                                limit=1)
            if target:
                target_state = target.state
        self._lifecycle_write({'status': STATUS_CANCELLED,
                               'failure_reason':
                                   'APPROVAL_WITHDRAWN'})
        self._audit_event(
            'APPROVAL_CANCELLED', decision='deny',
            reason_code='APPROVAL_WITHDRAWN',
            metadata={'approval_id': self.id,
                      'request_res_id': self.request_res_id,
                      'request_name': target_name,
                      'target_state': target_state})
        return {'outcome': 'cancelled', 'row': self,
                'request_name': target_name,
                'target_state': target_state}

    # ------------------------------------------------------------------
    # Deterministic resolution (record rules + module data only)
    # ------------------------------------------------------------------

    @api.model
    def resolve_approval_payload(self, payload, company):
        """Resolve the strict payload against repository data.

        ``asset_type`` MUST be one of the module's own selection
        values; the description falls back to the selection label
        (module-compliant — ``action_submit`` accepts a description
        when no specific asset is given); the campus hint resolves
        through the repository resolver; the needed-by phrase
        resolves through the deterministic date parser.
        """
        clean = dict(payload or {})
        selection = _asset_selection(self.env)
        valid = {value for value, _label in selection}
        typ = str(clean.get('asset_type') or '').strip()
        if typ not in valid:
            return {'status': 'missing', 'field': 'asset_type'}
        label = _human_type_label(self.env, typ)
        description = str(clean.get('description') or '').strip() \
            or label
        reason = str(clean.get('reason') or '').strip()
        if not reason:
            return {'status': 'missing', 'field': 'reason'}
        phrase = str(clean.get('needed_by') or '').strip()
        if not phrase:
            return {'status': 'missing', 'field': 'needed_by'}
        state, date_iso, _time_str = parse_followup_date(
            phrase, today=fields.Date.context_today(self))
        if state != 'ok':
            return {'status': 'invalid_date', 'field': 'needed_by'}
        campus_hint = str(clean.get('campus') or '').strip()
        if not campus_hint:
            return {'status': 'missing', 'field': 'campus'}
        Resolve = self.env['edicai.ai.action.resolve']
        campus_state, campus, _candidates = Resolve.resolve_campus(
            campus_hint, company)
        if campus_state != 'ok':
            return {'status': 'not_found', 'field': 'campus'}
        resolved = dict(clean)
        resolved.update({
            'asset_type': typ,
            'description':
                description[:_FIELD_LIMITS['description']],
            'reason': reason,
            'needed_by': date_iso,
            'campus_id': campus.id,
            'campus': campus.campus_display_name or campus.name,
        })
        return {'status': 'ok', 'field': None,
                'payload': resolved}

    # ------------------------------------------------------------------
    # Reply builders — grounded facts; NEVER claim unexecuted success
    # ------------------------------------------------------------------

    def preview_reply(self):
        self.ensure_one()
        data = self._read_plan().get('payload') or {}
        try:
            label = _human_type_label(
                self.env, data.get('asset_type') or 'other')
        except ValueError:
            label = data.get('asset_type') or '?'
        lines = [
            'Submit this asset request for approval?',
            '',
            'Type: %s' % label,
            'Description: %s' % (data.get('description') or label),
            'Reason: %s' % (data.get('reason') or ''),
            'Needed by: %s' % (data.get('needed_by') or ''),
            '',
            'Campus: %s' % (data.get('campus') or ''),
            'Institution: %s' % (self.company_id.name or ''),
            'Requested by: %s' % (self.requester_id.name or ''),
            '',
            'On confirmation the request is created and submitted '
            'through the standard asset request workflow. The '
            'approval itself is reserved to an institution '
            'administrator — you, as requester, cannot approve it.',
            '',
            'Confirmation code: %s' % (self.ref or ''),
            '',
            '%s Reply "confirm %s" to submit this request for '
            'approval, or "cancel" to discard it.'
            % (_NOTHING_CHANGED, self.ref or ''),
        ]
        return self._answered_reply('\n'.join(lines))

    def _missing_reply(self, latest_missing=None):
        missing = missing_approval_fields(self._current_payload())
        labels = {
            'asset_type': 'the equipment type (e.g. projector, '
                          'computer, lab equipment)',
            'reason': 'the reason (label "reason:")',
            'needed_by': 'the needed-by date',
            'campus': 'the campus (e.g. "at Main Campus" or '
                      '"campus: <name>")',
        }
        lines = ['To prepare your asset request, I still need:']
        lines += ['- %s' % labels.get(f, str(f)) for f in missing]
        lines += ['', _NOTHING_CHANGED]
        return self._answered_reply('\n'.join(lines))

    def submitted_reply(self):
        """§8 — the explicit waiting-for-approval message."""
        self.ensure_one()
        try:
            label = _human_type_label(
                self.env, self.asset_type or 'other')
        except ValueError:
            label = self.asset_type or '?'
        if self.designated_approver_id:
            approver = '%s (institution administrator)' % (
                self.designated_approver_id.name or '')
        else:
            approver = 'an institution administrator'
        lines = [
            'Approval required.',
            '',
            'Requested by: %s' % (self.requester_id.name or ''),
            'Action: Asset request approval',
            'Target: Asset request %s' % (self.request_name or ''),
            'Type: %s' % label,
            'Reason: %s' % (self.reason or ''),
            'Needed by: %s' % (self.needed_by or ''),
            '',
            'Approver: %s' % approver,
            '',
            'Status: Waiting for approval.',
            'The request has been submitted for approval. It has '
            'NOT been approved yet — the approval itself is '
            'performed by a human approver, not by this '
            'conversation.',
            '',
            'Approval code: %s' % (self.ref or ''),
        ]
        return self._answered_reply('\n'.join(lines))

    def status_reply(self):
        self.ensure_one()
        if self.status == STATUS_DRAFT:
            return self.advance()
        if self.status == STATUS_PREVIEW:
            return self.preview_reply()
        if self.status == STATUS_PENDING:
            lines = [
                'Status: Waiting for approval.',
                'Target: Asset request %s'
                % (self.request_name or '(unsubmitted)'),
                'Approval code: %s' % (self.ref or ''),
                '',
                _NOTHING_EXECUTED,
            ]
            return self._answered_reply('\n'.join(lines))
        if self.status == STATUS_EXECUTED:
            return self.compose_decision_reply(duplicated=False)
        if self.status == STATUS_REJECTED:
            return self.compose_rejection_reply()
        if self.status == STATUS_EXPIRED:
            return self._error_reply(_EXPIRED_TEXT)
        if self.status == STATUS_INVALIDATED:
            return self.compose_invalidated_reply()
        if self.status == STATUS_CANCELLED:
            return self._answered_reply(_CANCELLED_TEXT)
        return self._error_reply(
            'The approval request is not ready yet (%s). Nothing '
            'was executed.' % self.status.replace('_', ' '))

    def compose_decision_reply(self, duplicated=False):
        """Grounded approval result (or honest duplicate replay)."""
        self.ensure_one()
        result = self._read_result()
        req_name = result.get('request_name') or \
            self.request_name or ''
        approved_by = result.get('approved_by') or \
            (self.approved_by_id and self.approved_by_id.name) or ''
        if duplicated:
            lines = [
                '%s' % _ALREADY_TEXT,
                '',
                'Request %s — approved by %s'
                % (req_name or '(unsubmitted)', approved_by),
                'State: %s' % (result.get('state') or 'approved'),
                'On: %s' % (result.get('approved_on') or ''),
            ]
        else:
            lines = [
                'Done. Request %s has been approved.'
                % (req_name or '(unsubmitted)',),
                '',
                'Approved by: %s' % approved_by,
                'On: %s' % (result.get('approved_on') or ''),
                'State: Approved',
            ]
        return self._answered_reply('\n'.join(lines))

    def compose_invalidated_reply(self):
        """P0 (BUG-011): material change invalidated the approval."""
        self.ensure_one()
        return self._error_reply(APPROVAL_INVALIDATED_REPLY)

    def compose_withdrawn_reply(self, target_state=''):
        """Honest withdrawal answer (residual state documented)."""
        self.ensure_one()
        lines = ['Approval request withdrawn. Nothing was approved '
                 'and nothing was executed by the assistant.']
        if target_state and self.request_name:
            lines += [
                '',
                'Note: the underlying asset request %s remains '
                'submitted in the standard interface (state: "%s") '
                '— no business cancellation was invented.'
                % (self.request_name, target_state),
            ]
        return self._answered_reply('\n'.join(lines))

    def compose_rejection_reply(self, duplicated=False):
        self.ensure_one()
        result = self._read_result()
        req_name = (result.get('request_name')
                    or self.request_name or '')
        lines = ['Request %s has been rejected.' % (req_name or
                                                    '(unsubmitted)')]
        if result.get('rejected_by'):
            lines.append('Rejected by: %s' % result['rejected_by'])
        if self.rejection_reason:
            lines.append('Reason: %s' % self.rejection_reason)
        lines += ['', 'Nothing was executed.']
        return self._answered_reply('\n'.join(lines))

    @api.model
    def pending_list_reply(self):
        """§9 — the approver's grounded pending list (no LLM)."""
        rows = self.pending_for()
        if not rows:
            return self._answered_reply(
                'No pending approvals in your institution at the '
                'moment. Nothing was executed.')
        lines = ['Pending approvals (%d):' % len(rows), '']
        Req = self.env[UNDERLYING_MODEL]
        for row in rows:
            try:
                label = _human_type_label(
                    self.env, row.asset_type or 'other')
            except ValueError:
                label = row.asset_type or '?'
            req_name = row.request_name or '(unsubmitted)'
            lines.append(
                '%s — %s — %s — by %s — needed %s%s' % (
                    row.ref or '?', req_name, label,
                    row.requester_id.name or '?',
                    row.needed_by or '?',
                    (' — %s' % row.reason) if row.reason else ''))
        selection_note = dict(Req._fields['state'].selection).get(
            'approved', 'Approved')
        lines += [
            '',
            'Reply "approve <code>" or "reject <code>" for one of '
            'the entries. An approval executes the standard %s '
            'action under your own authorization.'
            % selection_note.lower(),
        ]
        return self._answered_reply('\n'.join(lines))

    # ------------------------------------------------------------------
    # Reply plumbing (mirrors the proven workflow builders)
    # ------------------------------------------------------------------

    def _answered_reply(self, text):
        return {'status': 'answered', 'reply': text,
                'source_label': False, 'tool_name': APPROVAL_KIND,
                'error_code': ''}

    def _error_reply(self, text):
        return {'status': 'error', 'reply': text,
                'source_label': False, 'tool_name': APPROVAL_KIND,
                'error_code': VALIDATION_FAILED}

    @api.model
    def _audit_event(self, event_type, conversation=None, user=None,
                     decision=None, reason_code=None, detail=None,
                     metadata=None):
        """Best-effort audit on the SAME Phase 0 infra (never raises).

        Called on a ROW record: conversation + user default to the
        row's own binding (like the pending-action `_audit`).
        """
        if self and self.id:
            conversation = conversation or self.session_id
            user = user or self.requester_id
        try:
            return self.env['edicai.ai.audit.event'].log_event(
                event_type,
                tool_name=APPROVAL_KIND,
                user=user,
                conversation=conversation,
                decision=decision,
                reason_code=reason_code,
                detail=detail,
                metadata=metadata,
            )
        except Exception:
            _logger.exception('AI approval: audit call failed.')
            return False

    def _audit(self, event_type, **kwargs):
        return self._audit_event(event_type, **kwargs)
