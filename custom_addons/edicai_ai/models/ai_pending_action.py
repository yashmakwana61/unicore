"""Phases 2A/2B — pending-action state for confirmed conversational writes.

``edicai.ai.pending.action`` is the SMALLEST durable state that can bind
"yes" to ONE exact write — ``admission.draft_inquiry`` (Phase 2A) or
``admission.schedule_followup`` (Phase 2B) — per prompt §10–12:

* one row per declarative draft per conversation (owner-scoped);
* canonical payload + deterministic SHA-256 ``action_hash`` + short
  ``ref`` code computed at preview time;
* lifecycle ``draft → preview → executed / cancelled / expired /
  failed / superseded`` — execution is possible ONLY from ``preview``;
* confirmation is action-bound (row id + ref + status), never
  "whatever the assistant last said";
* material payload change AFTER a preview SUPERSEDES the old row — a
  confirmation of the old row can never execute the new payload;
* idempotency: ``SELECT … FOR UPDATE NOWAIT`` row lock + in-lock
  status re-check (double / concurrent confirmations mutate once);
* re-authorization runs INSIDE ``confirm_and_execute`` (second gate,
  prompt §14); resolution and duplicate checks re-run under the
  CURRENT record rules at confirm time;
* execution goes through the CANONICAL business path
  (``edicai.admission.applicant.create`` with ``state='inquiry'``) as
  the requesting user — no sudo, no bespoke ORM writes;
* post-execution verification re-reads the record through record
  rules and every material field IS validated before any success is
  reported (prompt §19).

No generic action engine: every method is purpose-built for this one
action while staying structurally reusable later.
"""

import hashlib
import json
import logging
from datetime import timedelta

import psycopg2

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html_escape

from odoo.addons.edicai_ai.models.ai_action_resolve import (
    ACTION_DRAFT_INQUIRY,
    ACTION_SCHEDULE_FOLLOWUP,
    ACTION_FIELDS,
    FOLLOWUP_FIELDS,
    validate_action_entities,
    validate_followup_entities,
)
from odoo.addons.edicai_ai.models.ai_action_resolve import (
    ACTION_ENTITY_CREATE,
    ACTION_ENTITY_EXECUTE,
    ACTION_ENTITY_UPDATE,
    ENTITY_EXECUTE_FIELDS,
    ENTITY_FIELDS,
)
from odoo.addons.edicai_ai.models.ai_entity_actions import (
    action_spec,
    run_action,
    validate_action_params,
)

_logger = logging.getLogger(__name__)

STATUS_DRAFT = 'draft'          # collecting fields
STATUS_PREVIEW = 'preview'      # awaiting confirmation (executable)
STATUS_EXECUTED = 'executed'
STATUS_CANCELLED = 'cancelled'
STATUS_EXPIRED = 'expired'
STATUS_FAILED = 'failed'
STATUS_SUPERSEDED = 'superseded'

ACTIVE_STATUSES = (STATUS_DRAFT, STATUS_PREVIEW)

_EXECUTABLE_STATUS = (STATUS_PREVIEW,)

#: Phase G2/G3 — generic entity actions share this lifecycle entirely.
_ENTITY_ACTIONS = (ACTION_ENTITY_CREATE, ACTION_ENTITY_UPDATE,
                   ACTION_ENTITY_EXECUTE)


def _fields_by_action(action):
    """The strict canonical field tuple of one allow-listed action."""
    if action == ACTION_ENTITY_EXECUTE:
        return ENTITY_EXECUTE_FIELDS
    if action in _ENTITY_ACTIONS:
        return ENTITY_FIELDS
    return ACTION_FIELDS if action == ACTION_DRAFT_INQUIRY \
        else FOLLOWUP_FIELDS


def canonical_action_payload(action, payload):
    """Canonical, strictly-typed payload dict for ONE action."""
    clean = {}
    for field in _fields_by_action(action):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            clean[field] = value.strip()
        elif field in ('values', 'params') and isinstance(value, dict):
            # entity actions (G2/G3): the coerced value/param dict is
            # part of the canonical payload; keep it JSON-stable for
            # hashing.
            try:
                clean[field] = json.loads(
                    json.dumps(value, sort_keys=True, default=str))
            except Exception:
                clean[field] = {}
        elif field == 'record_id' and isinstance(value, int) and not \
                isinstance(value, bool) and value > 0:
            clean[field] = value
    return clean


def canonical_payload(payload):
    """Canonical draft-inquiry payload (Phase 2A, byte-identical)."""
    return canonical_action_payload(ACTION_DRAFT_INQUIRY, payload)


def payload_action_hash(action, payload):
    """Deterministic hash of the canonical payload of ONE action."""
    canonical = json.dumps(
        canonical_action_payload(action, payload), sort_keys=True,
        separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


class EdicaiAIPendingAction(models.Model):
    """Durable, owner-scoped pending write action (Phase 2A)."""

    _name = 'edicai.ai.pending.action'
    _description = 'AI Pending Conversational Action'
    _order = 'id desc'
    _rec_name = 'ref'

    action = fields.Char(
        string='Action', required=True, default=ACTION_DRAFT_INQUIRY,
        help='Allow-listed conversational write action identifier.')
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
    payload_json = fields.Text(string='Action Payload (canonical)')
    action_hash = fields.Char(string='Action Hash', index=True)
    ref = fields.Char(string='Confirmation Code')
    status = fields.Selection(
        selection=[
            (STATUS_DRAFT, 'Draft'),
            (STATUS_PREVIEW, 'Preview'),
            (STATUS_EXECUTED, 'Executed'),
            (STATUS_CANCELLED, 'Cancelled'),
            (STATUS_EXPIRED, 'Expired'),
            (STATUS_FAILED, 'Failed'),
            (STATUS_SUPERSEDED, 'Superseded'),
        ],
        default=STATUS_DRAFT, required=True, index=True)
    executed_on = fields.Datetime(string='Executed On')
    result_res_model = fields.Char(string='Created Record Model')
    result_res_id = fields.Integer(string='Created Record Id')
    result_application_number = fields.Char(
        string='Created Application No.')
    failure_reason = fields.Char(
        string='Internal Failure Reason',
        help='Machine reason code only — never user content.')
    result_json = fields.Text(
        string='Verified Result Snapshot',
        help='Application-verified execution result (follow-up '
             'action); the grounded reply reads ONLY from here.')

    # ------------------------------------------------------------------
    # Payload plumbing
    # ------------------------------------------------------------------

    def _read_result(self):
        """Grounded verified-result snapshot for reply composition.

        Reads the ACTUAL created record through record rules; falls
        back to the stored result fields when the record is not
        readable. Never invents facts.
        """
        payload = self._read_payload()
        record = self.env['edicai.admission.applicant'].search(
            [('id', '=', self.result_res_id)], limit=1
        ) if self.result_res_id else None
        if self.action == ACTION_SCHEDULE_FOLLOWUP:
            snapshot = self._read_result_snapshot()
            applicant = self.env['edicai.admission.applicant'].search(
                [('id', '=', snapshot.get('applicant_id'))], limit=1
            ) if snapshot.get('applicant_id') else None
            return {
                'applicant':
                    snapshot.get('applicant')
                    or (applicant.display_name if applicant else False),
                'application_number':
                    self.result_application_number or (
                        applicant.application_number if applicant
                        else False),
                'date': snapshot.get('date') or False,
                'time': snapshot.get('time') or False,
                'purpose': snapshot.get('purpose') or False,
                'activity_id':
                    self.result_res_id if self.result_res_id else False,
            }
        return {
            'application_number':
                self.result_application_number
                or (record.application_number if record else False),
            'name': payload.get('name')
            or (record.name if record else False),
            'program': (record.program_id.display_name if record else False)
            or payload.get('program'),
            'campus': (record.campus_id.display_name if record else False)
            or payload.get('campus'),
            'cycle': (record.cycle_id.display_name if record else False)
            or payload.get('cycle'),
            'applicant_id': record.id if record else False,
        }

    def _read_payload(self):
        try:
            data = json.loads(self.payload_json or '{}')
        except (ValueError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        # Sanitize defensively: only canonical fields of THIS action
        # survive.
        if self.action in _ENTITY_ACTIONS:
            return canonical_action_payload(self.action, data)
        if self.action == ACTION_SCHEDULE_FOLLOWUP:
            clean, ok, _invalid = validate_followup_entities(data)
        else:
            clean, ok, _invalid = validate_action_entities(data)
        return clean if ok else {}

    def _read_result_snapshot(self):
        try:
            data = json.loads(self.result_json or '{}')
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def write(self, vals):  # lifecycle write guard
        for record in self:
            if record._origin_status_done() and any(
                    key in vals for key in
                    ('payload_json', 'status', 'action_hash')):
                if not self._check_allowed_redo(record, vals):
                    _logger.warning(
                        'AI pending action %s: terminal write blocked.',
                        record.id)
                    return True
        return super().write(vals)

    def _origin_status_done(self):
        try:
            return self.status not in ACTIVE_STATUSES
        except Exception:
            return False

    @staticmethod
    def _check_allowed_redo(record, vals):
        """Terminal rows may only move WITHIN terminal statuses."""
        new_status = vals.get('status')
        if new_status is None:
            return False
        terminal = {STATUS_EXECUTED, STATUS_CANCELLED, STATUS_EXPIRED,
                    STATUS_FAILED, STATUS_SUPERSEDED}
        return record.status in terminal and new_status in terminal

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    @api.model
    def open_active(self, session, user=None):
        """The (at most one) active row for this session + owner."""
        if session is None:
            return self.env['edicai.ai.pending.action']
        user = user or self.env.user
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', user.id),
            ('status', 'in', list(ACTIVE_STATUSES)),
        ], limit=1)

    @api.model
    def find_recent_executed(self, session, user=None, minutes=15):
        """Last executed row of this session, for idempotent replays."""
        if session is None:
            return self.env['edicai.ai.pending.action']
        user = user or self.env.user
        since = fields.Datetime.now() - timedelta(minutes=minutes)
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', user.id),
            ('status', '=', STATUS_EXECUTED),
            ('executed_on', '>=', since),
        ], limit=1)

    @api.model
    def find_recent_final(self, session, user=None, minutes=15):
        """Most recent lifecycle-final row of this session.

        Used to answer confirmations of a JUST-expired action with the
        safe expired message instead of a generic refusal. Terminal
        rows are frozen, so the lookup is read-only and never revives
        anything.
        """
        if session is None:
            return self.env['edicai.ai.pending.action']
        user = user or self.env.user
        since = fields.Datetime.now() - timedelta(minutes=minutes)
        # write_date: expiry TRANSITIONS re-stamp the row, while
        # create_date may be far in the past for backdated long drafts.
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', user.id),
            ('status', 'in', [STATUS_EXPIRED, STATUS_CANCELLED,
                              STATUS_FAILED]),
            ('write_date', '>=', since),
        ], limit=1)

    @api.model
    def _validate_payload_for(self, payload, action):
        """Strict validation of a payload for ONE explicit action."""
        if action in _ENTITY_ACTIONS:
            # Entity payloads were validated + COERCED by the
            # edicai.ai.entity.tools validators BEFORE staging (write
            # grants, writable fields, types, required). The executor
            # re-runs the SAME validation — nothing extra here.
            return canonical_action_payload(action, payload), True, []
        if action == ACTION_SCHEDULE_FOLLOWUP:
            return validate_followup_entities(payload)
        return validate_action_entities(payload)

    @api.model
    def create_pending(self, session, payload, user=None, action=None,
                       supersede=True):
        """Start (or restart) the one active draft for this session.

        ``supersede=False`` (Phase 3) creates a WORKFLOW-CHILD action
        row WITHOUT touching the session's active row: bounded plan
        execution must not clobber conversational state.  The default
        keeps Phase 2A/2B behaviour byte-identical.
        """
        user = user or self.env.user
        Pending = self.env['edicai.ai.pending.action']
        previous = Pending.open_active(session, user)
        if previous and supersede:
            previous.write({'status': STATUS_SUPERSEDED})
            Pending._audit(
                'ACTION_INVALIDATED', conversation=session, user=user,
                reason_code='PREVIEW_MATERIALLY_CHANGED',
                metadata={'pending_id': previous.id,
                          'pending_status': STATUS_SUPERSEDED})
        clean, ok, _invalid = self._validate_payload_for(
            payload or {}, action or ACTION_DRAFT_INQUIRY)
        if not ok:
            clean = {}
        if session is None:
            return Pending
        return Pending.create({
            'action': action or ACTION_DRAFT_INQUIRY,
            'session_id': session.id,
            'user_id': user.id,
            'company_id': self.env.company.id,
            'payload_json': json.dumps(clean, sort_keys=True),
            'status': STATUS_DRAFT,
        })

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @api.model
    def expire_stale(self, session, timeout_minutes=None):
        """Expire active rows older than the configured window.

        Lazy expiry (no cron): executed on every action turn and before
        every confirmation. Returns the surviving active row or None.
        """
        Pending = self.env['edicai.ai.pending.action']
        if timeout_minutes is None:
            timeout_minutes = self.env[
                'edicai.ai.action.policy'].get_confirm_timeout_minutes()
        cutoff = fields.Datetime.now() - timedelta(
            minutes=max(0, timeout_minutes))
        stale = Pending.search([
            ('session_id', '=', session.id),
            ('user_id', '=', Pending.env.user.id),
            ('status', 'in', list(ACTIVE_STATUSES)),
            ('create_date', '<', cutoff),
        ])
        for row in stale:
            row.write({'status': STATUS_EXPIRED,
                       'failure_reason': 'CONFIRMATION_TIMEOUT'})
            row._audit('ACTION_EXPIRED', reason_code='CONFIRMATION_TIMEOUT')
        return Pending.open_active(session, Pending.env.user)

    def merge_fields(self, new_fields):
        """Merge validated fields into the payload.

        :returns: ``(row, changed_keys, superseded)``. A material
            change to a PREVIEW row invalidates it (supersede) and
            returns the NEW draft row — the old confirmation can never
            execute modified data (prompt §12).
        """
        self.ensure_one()
        payload = self._read_payload()
        old = dict(payload)
        payload.update(canonical_action_payload(
            self.action, new_fields or {}))
        changed = [key for key in payload
                   if old.get(key) != payload.get(key)]
        if not changed:
            return self, [], False
        if self.status == STATUS_PREVIEW:
            # Immutability: the previewed action is frozen. Material
            # change ⇒ supersede + fresh draft (new preview required).
            new_row = self.env['edicai.ai.pending.action'].create({
                'action': self.action,
                'session_id': self.session_id.id,
                'user_id': self.user_id.id,
                'company_id': self.company_id.id,
                'payload_json': json.dumps(payload, sort_keys=True),
                'status': STATUS_DRAFT,
            })
            self.write({'status': STATUS_SUPERSEDED,
                        'failure_reason': 'MATERIALLY_CHANGED'})
            self._audit('ACTION_INVALIDATED',
                        reason_code='CONFIRMED_ACTION_MODIFIED',
                        metadata={'pending_id': new_row.id,
                                  'changed': sorted(changed)})
            return new_row, changed, True
        self.write({'payload_json': json.dumps(payload, sort_keys=True)})
        return self, changed, False

    def mark_preview(self):
        """Promote to the single confirmable (executable) state.

        Computes the action hash + confirmation ref over the canonical
        payload at THIS point in time.
        """
        self.ensure_one()
        digest = payload_action_hash(self.action, self._read_payload())
        self.write({'status': STATUS_PREVIEW,
                    'action_hash': digest,
                    'ref': digest[:8]})
        self._audit('ACTION_PREVIEW_CREATED',
                    decision='allow',
                    reason_code='PREVIEW_READY',
                    metadata={
                        'pending_id': self.id,
                        'action': self.action,
                        'fields': sorted(canonical_action_payload(
                            self.action, self._read_payload())),
                    })
        return self

    def cancel(self):
        """User cancellation before execution (prompt §23)."""
        self.ensure_one()
        if self.status not in ACTIVE_STATUSES:
            return False
        self.write({'status': STATUS_CANCELLED,
                    'failure_reason': 'USER_CANCELLED'})
        self._audit('ACTION_CANCELLED', decision='allow',
                    reason_code='USER_CANCELLED')
        return True

    # ------------------------------------------------------------------
    # Execution (the ONE mutation path)
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
                'AI pending action %s: concurrent confirmation '
                '(%s).', self.id, type(exc).__name__)
            return False

    def confirm_and_execute(self):
        """Bind-then-execute the pending action exactly once.

        Full sequence (prompt §2 lifecycle):
            lock → status/expiry re-check → RE-AUTHORIZE
            → re-resolve entities → duplicate pre-check
            → ``applicant.create(state='inquiry')``
            → verification re-read → status transition → return.

        The row lock + in-lock status check makes double or concurrent
        confirmations single-effect (prompt §15/#24). Every guard
        failure returns WITHOUT claiming success.

        :returns: outcome dict, see module docstring of the caller.
        """
        self.ensure_one()
        if self.status != STATUS_PREVIEW:
            return {'outcome': 'not_confirmable'}
        if not self._lock_nowait():
            # Another transaction holds the row: it will perform the
            # exact one mutation; this is a duplicate confirmation.
            self._audit('ACTION_DUPLICATE',
                        reason_code='CONCURRENT_CONFIRMATION')
            return {'outcome': 'duplicate_concurrent'}
        # Re-read INSIDE the lock (monotone state check).
        fresh = self.search([('id', '=', self.id)], limit=1)
        if fresh.status != STATUS_PREVIEW:
            return {'outcome': 'duplicate',
                    'session': fresh.session_id,
                    'row': fresh}
        if fresh._is_expired_now():
            fresh.write({'status': STATUS_EXPIRED,
                         'failure_reason': 'CONFIRMATION_TIMEOUT'})
            fresh._audit('ACTION_EXPIRED',
                         reason_code='CONFIRMATION_TIMEOUT')
            return {'outcome': 'expired'}
        fresh._audit('ACTION_CONFIRMED', decision='allow',
                     reason_code='USER_CONFIRMED',
                     metadata={'pending_id': fresh.id,
                               'action_hash': fresh.action_hash})
        # Re-authorization (prompt §14 — mandatory second gate).
        policy = self.env['edicai.ai.action.policy']
        gate = policy.check_write_access(fresh.action)
        if not gate['allowed']:
            fresh._audit('ACTION_AUTHORIZATION_DENIED',
                         reason_code=gate['reason_code'])
            return {'outcome': 'denied',
                    'reason_code': gate['reason_code']}
        # Expiry re-check AFTER re-read (fresh create_date).
        return fresh._execute_locked()

    def _is_expired_now(self):
        minutes = self.env[
            'edicai.ai.action.policy'].get_confirm_timeout_minutes()
        cutoff = fields.Datetime.now() - timedelta(minutes=minutes)
        return bool(self.create_date and self.create_date < cutoff)

    def _execute_locked(self):
        """Run the business logic now that the row is locked and
        re-authorized. Dispatches on the allow-listed action — there
        is NO generic engine: each action keeps its own canonical,
        purpose-built execution."""
        if self.action == ACTION_DRAFT_INQUIRY:
            return self._execute_draft_inquiry_locked()
        if self.action == ACTION_SCHEDULE_FOLLOWUP:
            return self._execute_followup_locked()
        if self.action == ACTION_ENTITY_EXECUTE:
            return self._execute_entity_action_locked()
        if self.action in _ENTITY_ACTIONS:
            return self._execute_entity_locked()
        self._audit('ACTION_ERROR', reason_code='UNKNOWN_ACTION')
        return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}

    # ------------------------------------------------------------------
    # Phase G2 — generic entity create/update (locked execution)
    # ------------------------------------------------------------------

    def _execute_entity_locked(self):
        """Generic entity write, executed exactly once, locked.

        The SAME validators that staged the proposal run AGAIN here
        (preview ≠ execution: grants, row caps and even installed
        models may have changed between the two moments). Every write
        runs as the CONFIRMING user — no sudo, record rules and ACLs
        re-enforced by the ORM at write time.
        """
        payload = self._read_payload()
        model = payload.get('model')
        values = payload.get('values') or {}
        EntityTools = self.env['edicai.ai.entity.tools']
        op = 'create' if self.action == ACTION_ENTITY_CREATE \
            else 'update'
        # Authorization FIRST (reason-coded): the row stays PREVIEW so
        # a later re-grant can retry — nothing succeeded, nothing
        # silently failed.
        auth = EntityTools.authorize_entity_mutation(model, op)
        if not auth['ok']:
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code=auth['reason_code'])
            return {'outcome': 'denied',
                    'reason_code': auth['reason_code']}
        try:
            clean = EntityTools.validate_mutation_values(
                model, values, op)
        except UserError:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_POLICY_REJECT'})
            self._audit('ACTION_ERROR',
                        reason_code='ENTITY_POLICY_REJECT',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'VALIDATION_FAILED'}
        if model not in self.env:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_MODEL_UNAVAILABLE'})
            self._audit('ACTION_ERROR', reason_code='CREATE_FAILED',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        model_env = self.env[model]
        Company = self.company_id or self.env.company
        company_id = Company.id if Company else False

        record = False
        try:
            with self.env.cr.savepoint():
                if op == 'create':
                    vals = dict(clean)
                    if company_id and 'company_id' in model_env._fields:
                        vals['company_id'] = company_id
                    record = model_env.create(vals)
                else:
                    record = model_env.browse(payload.get('record_id'))
                    if not record.exists():
                        raise UserError('record vanished')
                    record.write(clean)
        except AccessError as exc:
            # No sudo will ever hide an ACL denial: refuse, never write
            # (mirrors the Phase 2A draft-inquiry guarantee).
            _logger.info(
                'AI pending action %s: entity write denied by ACL (%s).',
                self.id, type(exc).__name__)
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code='ACL_DENIED_AT_EXECUTION')
            return {'outcome': 'denied',
                    'reason_code': 'ACL_DENIED_AT_EXECUTION'}
        except (ValidationError, UserError) as exc:
            _logger.info(
                'AI pending action %s: entity write rejected (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_DRAFT,
                        'failure_reason': 'VALIDATION_FAILED'})
            self._audit('ACTION_ERROR', reason_code='VALIDATION_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'VALIDATION_FAILED'}
        except psycopg2.IntegrityError:
            _logger.info(
                'AI pending action %s: entity write failed (DB).',
                self.id)
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_WRITE_INTEGRITY'})
            self._audit('ACTION_ERROR',
                        reason_code='ENTITY_WRITE_INTEGRITY',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        except Exception as exc:  # noqa: BLE001 — classified, not leaked
            _logger.info(
                'AI pending action %s: entity write failed (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_WRITE_FAILED'})
            self._audit('ACTION_ERROR', reason_code='ENTITY_WRITE_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}

        return self._verify_entity_write(model, record, clean)

    def _verify_entity_write(self, model, record, clean):
        """Verification re-read (prompt §19): never assume success."""
        self.env.flush_all()
        try:
            seen = self.env[model].search([('id', '=', record.id)])
        except Exception:
            seen = record
        problems = []
        target = seen[0] if seen else record
        verified = {
            'id': record.id,
            'model': model,
            'name': target.display_name,
        }
        try:
            label = self.env['edicai.ai.entity.policy'].policy_for(
                model, 'read').label
        except Exception:
            label = False
        if label:
            verified['model_label'] = label
        else:
            verified['model_label'] = model
        if not seen:
            # A record rule may legitimately hide the row from this
            # caller at verify time; the row itself was written by
            # this caller under ACL — verify against it directly.
            seen_record = record
        else:
            seen_record = seen[0]
        if 'company_id' in self.env[model]._fields and \
                seen_record.company_id.id != self.company_id.id:
            problems.append('company_mismatch')
        for field, value in clean.items():
            try:
                stored = getattr(seen_record, field)
            except Exception:
                continue
            if isinstance(stored, models.BaseModel):
                stored = stored.id or False
            if isinstance(stored, float) or isinstance(value, float):
                if abs(float(stored or 0.0) - float(value or 0.0)) \
                        > 1e-6:
                    problems.append('field_mismatch:%s' % field)
            elif str(stored) != str(value):
                problems.append('field_mismatch:%s' % field)
        verified['written'] = sorted(clean)
        if problems:
            _logger.info(
                'AI pending action %s: entity verify failed (%s).',
                self.id, ', '.join(problems))
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'VERIFY_FAILED'})
            self._audit('ACTION_ERROR', reason_code='VERIFY_FAILED',
                        metadata={'pending_id': self.id,
                                  'problems': problems[:3]})
            return {'outcome': 'error', 'error_code': 'VERIFY_FAILED'}
        self.write({
            'status': STATUS_EXECUTED,
            'executed_on': fields.Datetime.now(),
            'result_res_model': model,
            'result_res_id': record.id,
            'result_json': json.dumps(verified, sort_keys=True),
        })
        self._audit('ACTION_EXECUTED',
                    reason_code='ENTITY_%s' % (
                        'CREATE' if self.action == ACTION_ENTITY_CREATE
                        else 'UPDATE'),
                    metadata={'pending_id': self.id,
                              'record_id': record.id})
        return {
            'outcome': 'executed',
            'verified': verified,
            'session': self.session_id,
            'row': self,
        }

    # ------------------------------------------------------------------
    # Phase G3 — generic entity ACTION (locked execution)
    # ------------------------------------------------------------------

    def _execute_entity_action_locked(self):
        """Run ONE code-declared record action, exactly once, locked.

        Same doctrine as the G2 write path: authorization is re-decided
        here (flag + entity execute grant + action row + code registry),
        the record is re-checked under the CONFIRMING user's ACL and
        record rules, the ERP method does the writing (no sudo, no
        invented field writes), and the outcome is verified by
        re-reading the declared state column.
        """
        payload = self._read_payload()
        model = payload.get('model')
        action = payload.get('entity_action')
        record_id = payload.get('record_id')
        EntityTools = self.env['edicai.ai.entity.tools']
        auth = EntityTools.authorize_entity_execute(model, action)
        if not auth['ok']:
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code=auth['reason_code'])
            return {'outcome': 'denied',
                    'reason_code': auth['reason_code']}
        spec = action_spec(model, action)
        try:
            clean = validate_action_params(spec, payload.get('params'))
        except UserError:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_POLICY_REJECT'})
            self._audit('ACTION_ERROR',
                        reason_code='ENTITY_POLICY_REJECT',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'VALIDATION_FAILED'}
        if model not in self.env:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_MODEL_UNAVAILABLE'})
            self._audit('ACTION_ERROR', reason_code='CREATE_FAILED',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        if isinstance(record_id, bool) or not isinstance(
                record_id, int) or record_id <= 0:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_POLICY_REJECT'})
            self._audit('ACTION_ERROR',
                        reason_code='ENTITY_POLICY_REJECT',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'VALIDATION_FAILED'}
        record = self.env[model].browse(record_id)
        try:
            record.check_access('read')
        except Exception:
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code='ACL_DENIED_AT_EXECUTION')
            return {'outcome': 'denied',
                    'reason_code': 'ACL_DENIED_AT_EXECUTION'}
        if not record.exists():
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_ACTION_RECORD_MISSING'})
            self._audit('ACTION_ERROR',
                        reason_code='ENTITY_ACTION_RECORD_MISSING',
                        metadata={'pending_id': self.id})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        company = self.company_id or self.env.company
        if 'company_id' in self.env[model]._fields and \
                record.company_id != company:
            # Multi-tenant isolation is server-owned: a row from
            # another company is NEVER acted upon.
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code='ENTITY_COMPANY_MISMATCH')
            return {'outcome': 'denied',
                    'reason_code': 'ENTITY_COMPANY_MISMATCH'}
        facts = {}
        try:
            # Savepoint keeps the transaction usable for the audit
            # write after a business rejection.
            with self.env.cr.savepoint():
                facts = run_action(record, spec, clean)
        except AccessError as exc:
            # No sudo will ever hide an ACL denial.
            _logger.info(
                'AI pending action %s: entity action denied by ACL '
                '(%s).', self.id, type(exc).__name__)
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code='ACL_DENIED_AT_EXECUTION')
            return {'outcome': 'denied',
                    'reason_code': 'ACL_DENIED_AT_EXECUTION'}
        except (ValidationError, UserError) as exc:
            # Business rejection (e.g. "only active applications can be
            # moved to waitlist"): the user can correct and retry.
            _logger.info(
                'AI pending action %s: entity action rejected (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_DRAFT,
                        'failure_reason': 'VALIDATION_FAILED'})
            self._audit('ACTION_ERROR', reason_code='VALIDATION_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'VALIDATION_FAILED'}
        except Exception as exc:  # noqa: BLE001 — classified, not leaked
            _logger.info(
                'AI pending action %s: entity action failed (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ENTITY_ACTION_FAILED'})
            self._audit('ACTION_ERROR', reason_code='ENTITY_ACTION_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        return self._verify_entity_action(
            model, record, action, spec, facts)

    def _verify_entity_action(self, model, record, action, spec, facts):
        """Verification re-read (prompt §19): never assume success."""
        self.env.flush_all()
        try:
            seen = self.env[model].search([('id', '=', record.id)])
        except Exception:
            seen = record
        target = seen[0] if seen else record
        state_field = spec['state_field']
        expected = spec['state_value']
        observed = getattr(target, state_field)
        try:
            # Label only (never a grant): the execute-only policy has
            # no read op, so policy_for() would return nothing here.
            label = self.env['edicai.ai.entity.policy'].search([
                ('model_ref', '=', model)], limit=1).label
        except Exception:
            label = False
        row = self.env['edicai.ai.entity.action'].search([
            ('model_ref', '=', model), ('action', '=', action)], limit=1)
        verified = {
            'id': record.id,
            'model': model,
            'name': target.display_name,
            'model_label': label or model,
            'action_label': row.label or spec['label'],
            'state_field': state_field,
            'state_before': facts.get('before'),
            'state_after': observed,
            'changed': bool(facts.get('changed')),
        }
        if observed != expected:
            _logger.info(
                'AI pending action %s: entity action verify failed '
                '(%s=%r, expected %r).', self.id, state_field,
                observed, expected)
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'VERIFY_FAILED'})
            self._audit('ACTION_ERROR', reason_code='VERIFY_FAILED',
                        metadata={'pending_id': self.id,
                                  'state_field': state_field})
            return {'outcome': 'error', 'error_code': 'VERIFY_FAILED'}
        self.write({
            'status': STATUS_EXECUTED,
            'executed_on': fields.Datetime.now(),
            'result_res_model': model,
            'result_res_id': record.id,
            'result_json': json.dumps(verified, sort_keys=True),
        })
        self._audit('ACTION_EXECUTED', reason_code='ENTITY_EXECUTE',
                    metadata={'pending_id': self.id,
                              'record_id': record.id,
                              'action': action})
        return {
            'outcome': 'executed',
            'verified': verified,
            'session': self.session_id,
            'row': self,
        }

    def _execute_draft_inquiry_locked(self):
        """Run the business logic now that the row is locked and
        re-authorized. Called ONLY from confirm_and_execute."""
        payload = self._read_payload()
        company = self.env.company
        Resolve = self.env['edicai.ai.action.resolve']
        outcome = Resolve.resolve_entities(payload, company)
        if outcome['status'] == 'missing':
            # Something disappeared (defensive; preview required the
            # fields) — downgrade so the user can re-supply.
            self.write({'status': STATUS_DRAFT,
                        'failure_reason': 'MISSING_FIELDS_AT_CONFIRM'})
            return {'outcome': 'missing',
                    'missing': outcome['missing']}
        if outcome['status'] == 'clarify':
            return {'outcome': 'clarify', 'field': outcome['field'],
                    'candidates': outcome['candidates']}
        if outcome['status'] == 'not_found':
            return {'outcome': 'not_found', 'field': outcome['field']}
        resolved = outcome['resolved']

        # Duplicate pre-check (friendly, deterministic — the DB
        # constraint alone would surface a raw IntegrityError).
        Applicant = self.env['edicai.admission.applicant']
        existing = Applicant.search([
            ('company_id', '=', company.id),
            ('cycle_id', '=', resolved['cycle'].id),
            ('program_id', '=', resolved['program'].id),
            ('email', '=', payload.get('email', '').lower()),
        ], limit=1)
        if existing:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'DUPLICATE_APPLICATION'})
            self._audit(
                'ACTION_DUPLICATE', reason_code='EXISTING_APPLICATION',
                metadata={'pending_id': self.id,
                          'existing_applicant_id': existing.id,
                          'existing_application_number':
                              existing.application_number})
            return {
                'outcome': 'duplicate_existing',
                'verified': {
                    'application_number': existing.application_number,
                    'name': existing.name,
                    'program': resolved['program'].display_name,
                    'campus': resolved['campus'].display_name,
                    'cycle': resolved['cycle'].display_name,
                    'applicant_id': existing.id,
                },
            }

        vals = {
            'name': payload['name'],
            'email': payload['email'],
            'mobile': payload['mobile'],
            'gender': payload['gender'],
            'date_of_birth': payload['date_of_birth'],
            'cycle_id': resolved['cycle'].id,
            'program_id': resolved['program'].id,
            'campus_id': resolved['campus'].id,
            'state': 'inquiry',
            'company_id': company.id,
        }
        if payload.get('notes'):
            vals['notes'] = payload['notes']
        try:
            # Savepoint keeps the transaction usable for the audit
            # write after a constraint failure.
            with self.env.cr.savepoint():
                applicant = Applicant.create(vals)
        except psycopg2.IntegrityError:
            # Unique constraint fired (duplicate application). The
            # friendly pre-check above normally catches this first;
            # this is the hard guarantee underneath it.
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'DUPLICATE_APPLICATION'})
            self._audit('ACTION_DUPLICATE',
                        reason_code='DB_UNIQUE_CONSTRAINT')
            return {
                'outcome': 'duplicate_existing',
                'verified': {
                    'application_number': False,
                    'name': payload.get('name'),
                    'program': resolved['program'].display_name,
                    'campus': resolved['campus'].display_name,
                    'cycle': resolved['cycle'].display_name,
                    'applicant_id': False,
                },
            }
        except AccessError as exc:
            # No sudo will ever hide an ACL denial (prompt §18): the
            # gate said YES but Odoo says NO — refuse, never create.
            _logger.info(
                'AI pending action %s: create denied by ACL (%s).',
                self.id, type(exc).__name__)
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code='ACL_DENIED_AT_EXECUTION')
            return {'outcome': 'denied',
                    'reason_code': 'ACL_DENIED_AT_EXECUTION'}
        except (ValidationError, UserError) as exc:
            # Business validation (e.g. grade-batch programs require a
            # grade level): user can correct inputs — keep draft.
            _logger.info(
                'AI pending action %s: create rejected (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_DRAFT,
                        'failure_reason': 'VALIDATION_FAILED'})
            self._audit('ACTION_ERROR', reason_code='VALIDATION_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'VALIDATION_FAILED'}
        except Exception as exc:  # noqa: BLE001 — classified, not leaked
            _logger.info(
                'AI pending action %s: create failed (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'CREATE_FAILED'})
            self._audit('ACTION_ERROR', reason_code='CREATE_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        return self._verify_created(applicant, payload, resolved)

    def _verify_created(self, applicant, payload, resolved):
        """Verification re-read (prompt §19): never assume success."""
        self.env.flush_all()
        seen = self.env['edicai.admission.applicant'].search(
            [('id', '=', applicant.id)])
        problems = []
        if not seen:
            problems.append('missing_record')
            record = applicant
        else:
            record = seen[0]
            company = self.env.company
            if record.company_id.id != company.id:
                problems.append('company_mismatch')
            if record.program_id.id != resolved['program'].id:
                problems.append('program_mismatch')
            if record.campus_id.id != resolved['campus'].id:
                problems.append('campus_mismatch')
            if record.cycle_id.id != resolved['cycle'].id:
                problems.append('cycle_mismatch')
            if record.state != 'inquiry':
                problems.append('state_mismatch')
            if not record.application_number or \
                    record.application_number == 'New':
                problems.append('missing_sequence')
            duplicates = self.env['edicai.admission.applicant'].search([
                ('company_id', '=', company.id),
                ('cycle_id', '=', resolved['cycle'].id),
                ('program_id', '=', resolved['program'].id),
                ('email', '=', record.email.lower()),
            ])
            if len(duplicates) > 1:
                problems.append('unexpected_duplicate')
        if problems:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'VERIFICATION_FAILED'})
            self._audit('ACTION_ERROR',
                        reason_code='VERIFICATION_FAILED',
                        metadata={'pending_id': self.id,
                                  'problems': problems})
            return {'outcome': 'verification_failed',
                    'error_code': 'INTERNAL_ERROR'}
        self.write({
            'status': STATUS_EXECUTED,
            'executed_on': fields.Datetime.now(),
            'result_res_model': 'edicai.admission.applicant',
            'result_res_id': record.id,
            'result_application_number': record.application_number,
        })
        self._audit('ACTION_EXECUTED', decision='allow',
                    reason_code='CREATE_OK',
                    metadata={'pending_id': self.id,
                              'applicant_id': record.id},
                    tool_name=self.action)
        self._audit('ACTION_VERIFIED', decision='allow',
                    reason_code='VERIFIED',
                    metadata={'pending_id': self.id,
                              'applicant_id': record.id})
        return {
            'outcome': 'executed',
            'verified': {
                'application_number': record.application_number,
                'name': record.name,
                'program': resolved['program'].display_name,
                'campus': resolved['campus'].display_name,
                'cycle': resolved['cycle'].display_name,
                'applicant_id': record.id,
            },
        }

    def _execute_followup_locked(self):
        """Phase 2B canonical mutation for ``admission.schedule_followup``.

        Verbatim reuse of the EXISTING Odoo business method
        ``mail.activity.mixin.activity_schedule`` with the To-Do
        activity type (the same mechanism the leave workflow uses):
        the applicant record itself carries the mixin, so the activity
        is created on the applicant by the applicant record — with the
        requesting user's own env (NO sudo) and the standard
        ``mail.activity`` ACL + the create-side "+ write right on the
        related document" access check ([C] from mail/models/
        mail_activity.py).
        """
        payload = self._read_payload()
        company = self.env.company
        Resolve = self.env['edicai.ai.action.resolve']
        outcome = Resolve.resolve_followup(payload, company)
        if outcome['status'] == 'missing':
            self.write({'status': STATUS_DRAFT,
                        'failure_reason': 'MISSING_FIELDS_AT_CONFIRM'})
            return {'outcome': 'missing',
                    'missing': outcome['missing']}
        if outcome['status'] == 'invalid_date':
            return {'outcome': 'invalid_date'}
        if outcome['status'] == 'clarify':
            return {'outcome': 'clarify', 'field': outcome['field'],
                    'candidates': outcome['candidates']}
        if outcome['status'] == 'not_found':
            return {'outcome': 'not_found', 'field': outcome['field']}
        applicant = outcome['applicant']
        due_date = fields.Date.to_date(outcome['date_iso'])
        time_str = outcome.get('time')

        purpose = payload.get('purpose') or ''
        note_parts = []
        if purpose:
            note_parts.append('Purpose: %s' % html_escape(purpose))
        if time_str:
            note_parts.append('Requested time: %s' % time_str)
        try:
            # Savepoint keeps the transaction usable for the audit
            # write after a failure.
            with self.env.cr.savepoint():
                activity = applicant.activity_schedule(
                        act_type_xmlid='mail.mail_activity_data_todo',
                        date_deadline=due_date,
                        summary=_('Admission follow-up'),
                        note='<br/>'.join(note_parts) or '',
                        user_id=self.env.user.id,
                    )
        except AccessError as exc:
            # No sudo will ever hide an ACL denial: the gate said YES
            # but Odoo says NO — refuse, never create.
            _logger.info(
                'AI pending action %s: follow-up denied by ACL (%s).',
                self.id, type(exc).__name__)
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        reason_code='ACL_DENIED_AT_EXECUTION')
            return {'outcome': 'denied',
                    'reason_code': 'ACL_DENIED_AT_EXECUTION'}
        except (ValidationError, UserError) as exc:
            _logger.info(
                'AI pending action %s: follow-up rejected (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_DRAFT,
                        'failure_reason': 'VALIDATION_FAILED'})
            self._audit('ACTION_ERROR', reason_code='VALIDATION_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error',
                    'error_code': 'VALIDATION_FAILED'}
        except Exception as exc:  # noqa: BLE001 — classified, not leaked
            _logger.info(
                'AI pending action %s: follow-up failed (%s).',
                self.id, type(exc).__name__)
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'ACTIVITY_CREATE_FAILED'})
            self._audit('ACTION_ERROR',
                        reason_code='ACTIVITY_CREATE_FAILED',
                        metadata={'pending_id': self.id,
                                  'exception_type': type(exc).__name__})
            return {'outcome': 'error', 'error_code': 'INTERNAL_ERROR'}
        return self._verify_followup(
            applicant, activity, due_date, time_str, purpose)

    def _verify_followup(self, applicant, activity, due_date,
                         time_str, purpose):
        """Verification re-read (prompt §15): never assume success."""
        self.env.flush_all()
        todo_id = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        problems = []
        seen = self.env['mail.activity'].search(
            [('id', '=', activity.id)]) if activity.id else None
        if not seen:
            problems.append('missing_record')
            record = activity
        else:
            record = seen[0]
            if record.res_model != 'edicai.admission.applicant':
                problems.append('model_mismatch')
            if record.res_id != applicant.id:
                problems.append('applicant_mismatch')
            if record.user_id.id != self.env.user.id:
                problems.append('user_mismatch')
            if record.date_deadline != due_date:
                problems.append('date_mismatch')
            if not record.active:
                problems.append('cancelled_activity')
            if todo_id and record.activity_type_id.id != todo_id.id:
                problems.append('type_mismatch')
        # The applicant itself must still exist under the requesting
        # user's record rules.
        seen_applicant = self.env['edicai.admission.applicant'].search(
            [('id', '=', applicant.id)])
        if not seen_applicant:
            problems.append('applicant_unreadable')
        if problems:
            self.write({'status': STATUS_FAILED,
                        'failure_reason': 'VERIFICATION_FAILED'})
            self._audit('ACTION_ERROR',
                        reason_code='VERIFICATION_FAILED',
                        metadata={'pending_id': self.id,
                                  'problems': problems})
            return {'outcome': 'verification_failed',
                    'error_code': 'INTERNAL_ERROR'}
        verified = {
            'applicant': applicant.display_name,
            'application_number': applicant.application_number,
            'date': fields.Date.to_string(due_date),
            'time': time_str or '',
            'purpose': purpose or '',
            'applicant_id': applicant.id,
            'activity_id': record.id,
        }
        self.write({
            'status': STATUS_EXECUTED,
            'executed_on': fields.Datetime.now(),
            'result_res_model': 'mail.activity',
            'result_res_id': record.id,
            'result_application_number': applicant.application_number,
            'result_json': json.dumps(verified, sort_keys=True),
        })
        self._audit('ACTION_EXECUTED', decision='allow',
                    reason_code='ACTIVITY_CREATED',
                    metadata={'pending_id': self.id,
                              'activity_id': record.id,
                              'applicant_id': applicant.id},
                    tool_name=self.action)
        self._audit('ACTION_VERIFIED', decision='allow',
                    reason_code='VERIFIED',
                    metadata={'pending_id': self.id,
                              'activity_id': record.id,
                              'applicant_id': applicant.id},
                    tool_name=self.action)
        return {'outcome': 'executed', 'verified': verified}

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    @api.model
    def _audit(self, event_type, conversation=None, user=None,
               decision=None, reason_code=None, detail=None,
               metadata=None, tool_name=None):
        """Best-effort lifecycle audit (never raises)."""
        action_ref = tool_name or ACTION_DRAFT_INQUIRY
        if self and self.id:  # record context (not a bare model call)
            conversation = conversation or self.session_id
            action_ref = tool_name or self.action or ACTION_DRAFT_INQUIRY
        try:
            return self.env['edicai.ai.audit.event'].log_event(
                event_type,
                tool_name=action_ref,
                user=user,
                conversation=conversation,
                decision=decision,
                reason_code=reason_code,
                detail=detail,
                metadata=metadata,
            )
        except Exception:
            _logger.exception('AI pending action: audit call failed.')
            return False
