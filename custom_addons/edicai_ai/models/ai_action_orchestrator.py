"""Phases 2A/2B — conversational write-action turn handling.

TWO actions, ONE preview each, ONE confirmation, ONE execution
(``admission.draft_inquiry`` and ``admission.schedule_followup``).
This module intercepts turns BEFORE the Phase 1A grammar only when the
write layer is explicitly enabled:

    handle_turn(text, session)
        ├─ flags OFF ................► None  (byte-identical Phase 1B)
        ├─ adversarial probe ........► refuse (never mutate)
        ├─ policy gate DENIED .......► refuse (no LLM involved)
        ├─ confirmation of pending ..► execute pending action (locked)
        ├─ cancellation of pending ..► cancel (no effect on DB records)
        ├─ field supply to draft ....► merge → preview or ask-again
        ├─ new inquiry request ......► extract → merge → preview/ask
        └─ none of the above ........► None  (grammar handles the turn)

The reply surface stays the plain chatbot: confirmation is a USER TEXT
turn through the EXISTING ``/edicai_ai/chat/send`` route — no new
endpoint, no client-side trust (backend is authoritative, prompt §30).

No LLM call happens on the confirm path (prompt §32): the assistant
executes the already-validated pending action.
"""

import logging
import re

from odoo import api, models

from odoo.addons.edicai_ai.models.ai_action_resolve import (
    ACTION_DRAFT_INQUIRY,
    ACTION_SCHEDULE_FOLLOWUP,
    ACTION_ENTITY_CREATE,
    ACTION_ENTITY_EXECUTE,
    ACTION_ENTITY_UPDATE,
    _GENDER_LABELS,
    extract_followup_fields,
    is_action_adversarial,
    is_action_request,
    is_followup_request,
    missing_fields,
    validate_followup_entities,
)
from odoo.addons.edicai_ai.models.ai_workflow import (
    WORKFLOW_NAME,
    _CANCELLED_TEXT as _WF_CANCELLED_TEXT,
    _DENIED_TEXT as _WF_DENIED_TEXT,
    _EXPIRED_TEXT as _WF_EXPIRED_TEXT,
    extract_workflow_fields,
    is_workflow_adversarial,
    is_workflow_request,
    validate_workflow_entities,
)
from odoo.addons.edicai_ai.models.ai_approval import (
    APPROVAL_KIND as _AP_KIND,
    _CANCELLED_TEXT as _AP_CANCELLED_TEXT,
    _EXPIRED_TEXT as _AP_EXPIRED_TEXT,
    _parse_ref_token as _parse_ap_token,
    _parse_reject_reason as _parse_ap_reason,
    STATUS_EXECUTED as _AP_EXECUTED,
    STATUS_PENDING as _AP_PENDING,
    STATUS_REJECTED as _AP_REJECTED,
    STATUS_TERMINAL as _AP_TERMINAL,
    STATUS_EXECUTED,
    STATUS_REJECTED,
    classify_admin_intent,
    extract_approval_entities,
    is_approval_adversarial,
    is_approval_request,
    validate_approval_entities,
)
from odoo.addons.edicai_ai.models.ai_intent import (
    UNSUPPORTED_REPLY,
    _ADVERSARIAL_PHRASES,
)
from odoo.addons.edicai_ai.models.ai_error import (
    AUTHORIZATION_DENIED,
    INTERNAL_ERROR,
    RECORD_NOT_FOUND,
    SAFE_MESSAGES,
    VALIDATION_FAILED,
)

_logger = logging.getLogger(__name__)

STATUS_ANSWERED = 'answered'
STATUS_CLARIFY = 'clarify'
STATUS_ERROR = 'error'

#: Strict confirmation allow-list — "yes" binds to the ONE confirmation
#: code shown in the preview, never to "whatever was said last" (§11).
CONFIRM_WORDS = frozenset((
    'yes', 'y', 'yes, create it', 'confirm', 'confirm it',
    'create it', 'go ahead', 'ok create it', 'yes please',
))
CANCEL_WORDS = frozenset((
    'no', 'cancel', 'cancel it', 'no thanks', 'discard',
    "don't create", 'do not create', 'stop', 'forget it',
))

_REF_CONFIRM_RE = r'^(?:yes|confirm|confirm it)\s+([0-9a-f]{8})$'

_REF_CODE_LABEL = 'Admission Inquiry'

_PREVIEW_HEADER = 'Create admission inquiry?'

_PREVIEW_HEADER_FOLLOWUP = 'Schedule follow-up?'

_NOTHING_CREATED_LINE = 'Nothing has been created yet.'

_NOTHING_CHANGED_LINE = 'Nothing has been changed yet.'

_CONFIRM_INSTRUCTIONS = (
    'Reply "%s" / "yes %s" to create it, or "cancel" to discard it.'
)

_CONFIRM_INSTRUCTIONS_FOLLOWUP = (
    'Reply "%s" / "yes %s" to schedule it, or "cancel" to discard it.'
)

_CANCELLED_TEXT = (
    'Cancelled. Nothing was created. You can start a new request '
    'any time.')

_CANCELLED_TEXT_FOLLOWUP = (
    'Cancelled. Nothing was scheduled. You can start a new request '
    'any time.')

_FOLLOWUP_FIELD_LABELS = {
    'applicant': 'which applicant (name, e-mail, mobile or '
                 'application number)',
    'date': 'when (e.g. "tomorrow", "Friday", "2026-10-21", '
            'optionally "at 11 AM")',
    'purpose': 'note (optional)',
}

_FOLLOWUP_SUPPLY_FORMAT = (
    'Reply in the form:  applicant: …  ·  when: …  ·  '
    '(note/purpose: …)')

_MISSING_FIELD_LABELS = {
    'name': 'full name',
    'email': 'e-mail address',
    'mobile': 'mobile number',
    'gender': 'gender (male / female / other / prefer not to say)',
    'date_of_birth': 'date of birth (YYYY-MM-DD)',
    'cycle': 'admission cycle',
    'program': 'program',
    'campus': 'campus',
}

_REPLY_SUPPLY_FORMAT = (
    'Reply in the form:  name: …  ·  email: …  ·  mobile: …  ·  '
    'gender: …  ·  date of birth: YYYY-MM-DD  ·  cycle: …  ·  '
    'program: …  ·  campus: …'
)


_REF_CONFIRM = re.compile(_REF_CONFIRM_RE)


class EdicaiAIActionOrchestrator(models.AbstractModel):
    """Turn router for the single conversational write action."""

    _name = 'edicai.ai.action.orchestrator'
    _description = 'AI Action Orchestrator (preview → confirm lifecycle)'

    # ------------------------------------------------------------------
    # Entry child of answer_turn (additive FIRST branch)
    # ------------------------------------------------------------------

    @api.model
    def handle_turn(self, text, session=None):
        """Return a chatbot response dict, or ``None`` to let the
        Phase 1A/1B orchestrator handle the turn unchanged.

        Phase 5 wrapper: the Phase 2–4 lanes run FIRST (via
        ``_handle_turn``); only when they leave the turn untouched
        AND the proactive flag is explicitly ON may the ONE
        proactive slice (``attendance.shortage.review``) answer it.
        With the flag OFF this function is byte-identical to
        Phase 4's ``handle_turn`` (prompt §22)."""
        primary = self._handle_turn(text, session)
        if primary is not None:
            return primary
        try:
            if not self.env[
                    'edicai.ai.action.policy'].is_proactive_enabled():
                return None
            return self.env['edicai.ai.proactive'].handle_turn(
                text, session) or None
        except Exception:
            # The proactive layer is strictly additive: ANY failure
            # falls through to Phase 1A/1B unchanged.
            _logger.exception(
                'AI action orchestrator: proactive turn handling '
                'failed (ignored).')
            return None

    def _handle_turn(self, text, session=None):
        """Phase 2–4 deterministic lanes (unchanged Phase 4 body)."""
        text = str(text or '').strip()
        policy = self.env['edicai.ai.action.policy']
        if not policy.is_any_gate_enabled():
            return None
        if session is None:
            # The write lifecycle requires a durable session; without
            # one the turn falls through to Phase 1A (unsupported).
            return None
        if 'edicai.admission.applicant' not in self.env or \
                'mail.activity' not in self.env:
            # The admission/mail applications are not installed in
            # THIS database: the Phase 2A/2B actions cannot exist —
            # never improvise. The Phase G2 GENERIC entity lane does
            # not depend on the admission app (its scope is the
            # entity policy), so it stays reachable where the generic
            # tools are installed.
            if not ((policy.is_entity_write_enabled()
                     or policy.is_entity_execute_enabled())
                    and 'edicai.ai.entity.tools' in self.env):
                _logger.info(
                    'AI action orchestrator: admission/module unavailable '
                    '(turn ignored).')
                return None
        Pending = self.env['edicai.ai.pending.action']
        Resolve = self.env['edicai.ai.action.resolve']

        row = Pending.expire_stale(session) or None
        detected = self._detect_action(text)
        # Per-action rollout isolation (prompt §22): an action whose
        # OWN flag is off must behave exactly as before — the request
        # falls through to the Phase 1A grammar/unsupported reply.
        if detected == ACTION_DRAFT_INQUIRY and \
                not policy.is_action_write_enabled():
            detected = None
        elif detected == ACTION_SCHEDULE_FOLLOWUP and \
                not policy.is_followup_enabled():
            detected = None
        adversarial = self._is_adversarial(text)

        # ---- Phase 3 (additive, gated): the ONE workflow ----------
        # With the workflow flag OFF every workflow branch below is
        # inert and the flow above + below is byte-identical to 2B.
        Wf = None
        wrow = None
        detected_wf = False
        wf_enabled = policy.is_workflow_enabled() and \
            'edicai.ai.pending.workflow' in self.env
        if wf_enabled:
            Wf = self.env['edicai.ai.pending.workflow']
            wrow = (self.env['edicai.ai.pending.workflow'].expire_stale(
                session) or None)
            detected_wf = is_workflow_request(text)
        # ---- Phase 4 (additive, gated): the ONE approval lane -----
        # With the approval flag OFF this block is inert and the flow
        # stays byte-identical to Phases 0–3.
        Approval = None
        arow = None
        detected_ap = None
        ap_token = None
        ap_token_kind = None
        adversarial_ap = False
        ap_context = False
        ap_enabled = policy.is_approval_enabled() and \
            'edicai.ai.pending.approval' in self.env and \
            'edicai.asset.request' in self.env
        if ap_enabled:
            Approval = self.env['edicai.ai.pending.approval']
            Approval.expire_pending()
            arow = Approval.open_active(session) or None
            detected_ap = classify_admin_intent(text) or (
                'create' if is_approval_request(text) else None)
            if detected_ap in ('approve', 'reject'):
                ap_token_kind, ap_token = _parse_ap_token(text)
            adversarial_ap = is_approval_adversarial(text)
            # A pending approval of THIS session is durable context:
            # injections about it must hit the refusal, never the
            # approval lane (prompt §21).
            ap_context = bool(arow)
            if not ap_context and not detected_ap:
                apex = Approval.find_for_user_session(session)
                ap_context = bool(apex and apex.status
                                  == _AP_PENDING)
        if (adversarial or (wf_enabled and is_workflow_adversarial(
                text)) or (ap_enabled and adversarial_ap)) and (
                detected or detected_wf or row or wrow or arow or
                detected_ap or (ap_enabled and ap_context)):
            self._audit('INTENT_UNSUPPORTED',
                        conversation=session,
                        decision='deny',
                        reason_code='WRITE_OR_ADVERSARIAL_REQUEST',
                        metadata={'action': (wrow and wrow.workflow)
                                  or (row and row.action)
                                  or detected or ACTION_DRAFT_INQUIRY})
            return self._error_reply(UNSUPPORTED_REPLY)

        if not row:
            # ---- Phase 4: an ACTIVE approval row (requester) ------
            if arow:
                return self._approval_turn(
                    text, arow, detected, detected_wf,
                    detected_ap, session)
            # ---- Phase 3: an ACTIVE workflow owns this turn -------
            if wrow:
                return self._workflow_turn(text, wrow, detected,
                                           detected_wf, session)
            # Phase 3 (additive, gated): WORKFLOW duplicate / expiry
            # answers FIRST, with RECENCY — the most recently finished
            # execution candidate wins the bare confirmation word, so
            # a later single ACTION replay still behaves as before.
            if wf_enabled and (detected_wf or
                               self._is_confirmation_word(text)):
                wdone = Wf.find_recent_executed(session)
                wfinal = Wf.find_recent_final(session)
                adone = Pending.find_recent_executed(session)
                # Workflow children execute BEFORE the plan finalize
                # write, so they are never more recent than the
                # workflow itself; a single action executed afterwards
                # is — and keeps its own legacy replay (2B parity).
                if wdone and (not adone or
                              adone.write_date <= wdone.write_date):
                    return wdone.compose_result_reply(duplicated=True)
                if (wfinal and wfinal.status == 'expired' and
                        (not adone or
                         adone.write_date <= wfinal.write_date)):
                    return self._error_reply(_WF_EXPIRED_TEXT)
            # Idempotent replay of a JUST-executed action under this
            # session (prompt §15/#13: duplicate confirmation must not
            # create a second record; it returns the verified result).
            if detected or self._is_confirmation_word(text):
                done = Pending.find_recent_executed(session)
                if done and detected in (None, done.action):
                    self._audit('ACTION_DUPLICATE',
                                conversation=session,
                                reason_code='REPEATED_CONFIRMATION',
                                metadata={'pending_id': done.id})
                    return self._executed_reply(done._read_result(),
                                                duplicated=True,
                                                action=done.action)
                # A just-expired action must answer with the safe
                # "expired" message (prompt §13), not fall through to
                # the grammar's generic refusal.
                final = Pending.find_recent_final(session)
                if final and final.status == 'expired':
                    return self._error_reply(
                        'This pending action has expired. Please submit '
                        'the request again — nothing was created.')
            # ---- Phase 4 (additive, gated): the approval lane ------
            if ap_enabled and detected_ap in ('approve', 'reject'):
                own_pending = Approval.find_for_user_session(session)
                if own_pending and own_pending.status == _AP_PENDING:
                    self._audit(
                        'APPROVAL_AUTH_DENIED', conversation=session,
                        decision='deny', reason_code='REQUESTER_CANNOT_DECIDE',
                        metadata={'approval_id': own_pending.id},
                        tool_name=_AP_KIND)
                    return self._error_reply(
                        'You cannot approve or reject your own request. An '
                        'independent authorized approver must review it.')
            if ap_enabled and detected_ap in ('list', 'approve',
                                              'reject'):
                return self._approval_approver_turn(
                    text, detected_ap, session,
                    ap_token_kind, ap_token)
            if ap_enabled and detected_ap == 'create':
                return self._approval_start(text, session)
            # A resolved approval row owns stray turns of its session:
            # a PENDING approval answers every undetected turn with
            # its grounded status (waiting) — and 'cancel' withdraws
            # it; other rows answer a bare confirmation word only.
            # Requester 'yes' is NEVER a second execution nor an
            # approval (§8).
            if ap_enabled and not detected_ap:
                arecent = Approval.find_for_user_session(session)
                if arecent and arecent.status == _AP_PENDING:
                    low_can = text.strip().lower()
                    if low_can in CANCEL_WORDS:
                        outcome = arecent.cancel()
                        return self._finalize_approval(outcome,
                                                       'cancel')
                    return arecent.status_reply()
                if arecent and self._is_confirmation_word(text):
                    return arecent.status_reply()
            # ---- Phase 3 (additive, gated): start the workflow.
            # Workflow detection runs BEFORE the action start so goal
            # phrasings ("prepare follow-ups for everyone") are not
            # swallowed by the Phase 2B "…for…" action pattern.
            if wf_enabled and detected_wf:
                return Wf.start_workflow(session, dict(
                    extract_workflow_fields(text)[0]))
            if detected:
                return self._start_request(text, session, detected)
            return None

        # ---- An active pending action exists for this session ----
        # Phase 3 (additive, gated): a workflow GOAL material-change
        # (§15) supersedes the pending action and takes over.
        if wf_enabled and detected_wf:
            return Wf.start_workflow(session, dict(
                extract_workflow_fields(text)[0]))
        # ---- Phase 4 (additive, gated): approval interplay --------
        if ap_enabled and detected_ap in ('list', 'approve', 'reject'):
            # The approver lane never touches the pending action.
            return self._approval_approver_turn(
                text, detected_ap, session, ap_token_kind, ap_token)
        if ap_enabled and detected_ap == 'create':
            # A NEW approval request is a material change (§15): the
            # pending action is superseded (audited in the takeover).
            return self._approval_start(text, session)
        gate = policy.check_write_access(row.action)
        if not gate['allowed']:
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        conversation=session,
                        reason_code=gate['reason_code'])
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED])

        # A DIFFERENT allow-listed action was requested while one is
        # active: it becomes a brand-new request — the common
        # ``create_pending`` path supersedes the old row itself.
        if detected and detected != row.action:
            return self._start_request(text, session, detected)

        low = text.strip().lower()
        ref_match = _REF_CONFIRM.match(low)
        if (low in CONFIRM_WORDS or ref_match):
            if row.status != 'preview':
                return self._status_reply(row, note=(
                    'The action is not ready to confirm yet.'))
            if ref_match and ref_match.group(1) != (row.ref or ''):
                self._audit('ACTION_CONFIRMED',
                            conversation=session,
                            decision='deny',
                            reason_code='CONFIRMATION_CODE_MISMATCH',
                            metadata={'pending_id': row.id})
                return self._error_reply(
                    'That confirmation code does not match the pending '
                    'action.')
            outcome = row.confirm_and_execute()
            return self._finalize_execution(outcome, session, row)
        if low in CANCEL_WORDS:
            cancelled = row.cancel()
            if not cancelled:
                return self._status_reply(row)
            return self._answered_reply(
                _CANCELLED_TEXT_FOLLOWUP
                if row.action == ACTION_SCHEDULE_FOLLOWUP
                else _CANCELLED_TEXT)
        # Otherwise the turn may be field supply / modification.
        return self._merge_and_advance(row, text, session)

    # ------------------------------------------------------------------
    # Phase 3 — the ONE workflow (additive turn helpers, all gated)
    # ------------------------------------------------------------------

    def _workflow_turn(self, text, wrow, detected, detected_wf, session):
        """Route a turn while an ACTIVE workflow owns this session.

        Confirmation is deterministic (lock → re-authorize → execute
        the frozen plan); a stray turn NEVER touches the plan.
        """
        policy = self.env['edicai.ai.action.policy']
        Wf = self.env['edicai.ai.pending.workflow']
        # A NEW workflow request = material change: fresh plan → new
        # preview → new confirmation (never "execute what we said").
        # Checked BEFORE the action detectors so broad Phase 2B
        # phrasings ("follow-ups with/for…") never swallow a goal.
        if detected_wf:
            Wf.supersede_active(row=wrow,
                                reason_code='MATERIALLY_CHANGED')
            return Wf.start_workflow(session, dict(
                extract_workflow_fields(text)[0]))
        # An allow-listed ACTION request is a material change (§15):
        # supersede the frozen plan, start the action normally.
        if detected:
            Wf.supersede_active(row=wrow,
                                reason_code='SUPERSEDED_BY_ACTION')
            return self._start_request(text, session, detected)
        gate = policy.check_workflow_access()
        if not gate['allowed']:
            self._audit('WORKFLOW_AUTH_DENIED',
                        conversation=session,
                        decision='deny',
                        reason_code=gate['reason_code'],
                        tool_name=WORKFLOW_NAME)
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=WORKFLOW_NAME)
        low = text.strip().lower()
        ref_match = _REF_CONFIRM.match(low)
        if (low in CONFIRM_WORDS or ref_match):
            if wrow.status not in ('preview', 'partial'):
                return wrow.status_reply(note=(
                    'The workflow is not ready to confirm yet.'))
            if ref_match and ref_match.group(1) != (wrow.ref or ''):
                self._audit('WORKFLOW_CONFIRMED',
                            conversation=session,
                            decision='deny',
                            reason_code='CONFIRMATION_CODE_MISMATCH',
                            metadata={'workflow_id': wrow.id},
                            tool_name=WORKFLOW_NAME)
                return self._error_reply(
                    'That confirmation code does not match the pending '
                    'workflow.')
            outcome = wrow.confirm_and_execute()
            return self._finalize_workflow(outcome, session, wrow)
        if low in CANCEL_WORDS:
            cancelled = wrow.cancel()
            if not cancelled:
                return wrow.status_reply()
            self._audit('WORKFLOW_CANCELLED',
                        conversation=session,
                        decision='allow',
                        reason_code='USER_CANCELLED',
                        metadata={'workflow_id': wrow.id},
                        tool_name=WORKFLOW_NAME)
            return self._answered_reply(
                _WF_CANCELLED_TEXT, action=WORKFLOW_NAME)
        # Anything else: deterministic status restatement only.
        return wrow.status_reply()

    def _finalize_workflow(self, outcome, session, wrow):
        """Turn the workflow execution outcome into one chat reply."""
        outcome = outcome or {}
        outcome_state = outcome.get('outcome')
        if outcome_state in ('executed', 'partial'):
            row = outcome.get('row') or wrow
            return row.compose_result_reply()
        if outcome_state == 'duplicate':
            row = outcome.get('row') or wrow
            if row.status == 'executed':
                return row.compose_result_reply(duplicated=True)
            return row.status_reply()
        if outcome_state == 'duplicate_concurrent':
            self._audit('WORKFLOW_DUPLICATE',
                        conversation=session,
                        reason_code='CONCURRENT_CONFIRMATION',
                        tool_name=WORKFLOW_NAME)
            return self._error_reply(
                'A confirmation of this workflow is already in '
                'progress. Nothing was duplicated.')
        if outcome_state == 'expired':
            return self._error_reply(
                'This workflow preview has expired. Nothing was '
                'changed.')
        if outcome_state == 'invalidated':
            row = outcome.get('row') or wrow
            return row.compose_invalidated_reply()
        if outcome_state == 'denied':
            return self._error_reply(
                _WF_DENIED_TEXT, action=WORKFLOW_NAME)
        return wrow.status_reply()

    @api.model
    def handle_llm_proposal(self, text, entities, session=None,
                            action=None):
        """LLM-assisted interpretation (only for paraphrases the
        deterministic detection missed). Entry from the Phase 1B
        understanding outcome ``{'status': 'action', ...}``."""
        action = action or ACTION_DRAFT_INQUIRY
        policy = self.env['edicai.ai.action.policy']
        if session is None:
            return None
        # ---- Phase 3 (additive, gated): workflow proposals ----------
        # The LLM may only PROPOSE the goal; discovery, plan,
        # authorization and execution stay fully application-driven.
        if action == WORKFLOW_NAME:
            if not policy.is_workflow_enabled() or \
                    'edicai.ai.pending.workflow' not in self.env or \
                    'edicai.admission.applicant' not in self.env:
                return None
            gate = policy.check_workflow_access()
            if not gate['allowed']:
                self._audit('WORKFLOW_AUTH_DENIED',
                            conversation=session,
                            decision='deny',
                            reason_code=gate['reason_code'],
                            tool_name=WORKFLOW_NAME)
                return self._error_reply(
                    SAFE_MESSAGES[AUTHORIZATION_DENIED],
                    action=WORKFLOW_NAME)
            clean, ok, invalid = validate_workflow_entities(entities)
            if not ok:
                self._audit('INTENT_DETECTED',
                            conversation=session,
                            decision='deny',
                            reason_code='ACTION_PROPOSAL_INVALID',
                            metadata={'invalid': ','.join(invalid),
                                      'action': WORKFLOW_NAME})
                return self._error_reply(
                    SAFE_MESSAGES[VALIDATION_FAILED],
                    action=WORKFLOW_NAME)
            # LLM proposals NEVER breach the single-active-item rule.
            if self.env['edicai.ai.pending.action'].open_active(session) \
                    or self.env[
                        'edicai.ai.pending.workflow'].open_active(session):
                return None
            return self.env['edicai.ai.pending.workflow'].start_workflow(
                session, clean)
        # Per-action flag semantics kept identical to Phase 2A: with
        # the action's flag off the proposal is opportunistically
        # ignored and the grammar owns the turn.
        if action == ACTION_DRAFT_INQUIRY and \
                not policy.is_action_write_enabled():
            return None
        if action == ACTION_SCHEDULE_FOLLOWUP and \
                not policy.is_followup_enabled():
            return None
        if 'edicai.admission.applicant' not in self.env or \
                'mail.activity' not in self.env:
            return None
        gate = policy.check_write_access(action)
        if not gate['allowed']:
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        conversation=session,
                        reason_code=gate['reason_code'],
                        tool_name=action)
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=action)
        Pending = self.env['edicai.ai.pending.action']
        clean, ok, invalid = self._validate_entities(entities, action)
        if not ok:
            self._audit('INTENT_DETECTED',
                        conversation=session,
                        decision='deny',
                        reason_code='ACTION_PROPOSAL_INVALID',
                        metadata={'invalid': ','.join(invalid),
                                  'action': action})
            return self._error_reply(SAFE_MESSAGES[VALIDATION_FAILED],
                                     action=action)
        row = Pending.open_active(session)
        if row:
            # A pending action is already active: LLM proposals NEVER
            # merge into it — the explicit user turn flow governs.
            return None
        row = Pending.create_pending(session, clean, action=action)
        return self._advance_row(row, session)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_confirmation_word(text):
        low = str(text or '').strip().lower()
        return bool(low in CONFIRM_WORDS or _REF_CONFIRM.match(low))

    @api.model
    def _detect_action(self, text):
        """Deterministic action routing (Phase 2A detector FIRST, so
        its behaviour is unchanged even for mixed phrasings)."""
        if is_action_request(text):
            return ACTION_DRAFT_INQUIRY
        if is_followup_request(text):
            return ACTION_SCHEDULE_FOLLOWUP
        return None

    @api.model
    def _is_adversarial(self, text):
        if is_action_adversarial(text):
            return True
        low = str(text or '').lower()
        return any(phrase in low for phrase in _ADVERSARIAL_PHRASES)

    @api.model
    def _validate_entities(self, raw, action=ACTION_DRAFT_INQUIRY):
        if action == ACTION_SCHEDULE_FOLLOWUP:
            return validate_followup_entities(raw)
        from odoo.addons.edicai_ai.models.ai_action_resolve import (
            validate_action_entities)
        return validate_action_entities(raw)

    def _start_request(self, text, session, action=ACTION_DRAFT_INQUIRY):
        """A brand-new write request (no active pending)."""
        policy = self.env['edicai.ai.action.policy']
        gate = policy.check_write_access(action)
        if not gate['allowed']:
            self._audit('ACTION_AUTHORIZATION_DENIED',
                        conversation=session,
                        reason_code=gate['reason_code'],
                        tool_name=action)
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=action)
        Resolve = self.env['edicai.ai.action.resolve']
        if action == ACTION_SCHEDULE_FOLLOWUP:
            fields, _rest = extract_followup_fields(text)
            clean, ok, invalid = self._validate_entities(fields, action)
            if not ok:
                self._audit('INTENT_DETECTED',
                            conversation=session,
                            decision='deny',
                            reason_code='ACTION_FIELD_INVALID',
                            metadata={'invalid': ','.join(invalid),
                                      'action': action})
                return self._error_reply(SAFE_MESSAGES[VALIDATION_FAILED],
                                         action=action)
            Pending = self.env['edicai.ai.pending.action']
            row = Pending.create_pending(session, clean, action=action)
            self._audit('INTENT_DETECTED',
                        conversation=session,
                        decision='allow',
                        reason_code='WRITE_ACTION_REQUESTED',
                        metadata={'action': action,
                                  'pending_id': row.id})
            return self._advance_row(row, session)
        fields, rest, invalid = Resolve.extract_and_validate(text)
        if invalid:
            self._audit('INTENT_DETECTED',
                        conversation=session,
                        decision='deny',
                        reason_code='ACTION_FIELD_INVALID',
                        metadata={'invalid': ','.join(invalid)})
            return self._error_reply(SAFE_MESSAGES[VALIDATION_FAILED])
        hints = Resolve.match_hint_fields(rest, fields)
        fields.update({k: v for k, v in hints.items()
                       if k not in fields})
        Pending = self.env['edicai.ai.pending.action']
        row = Pending.create_pending(session, fields)
        self._audit('INTENT_DETECTED',
                    conversation=session,
                    decision='allow',
                    reason_code='WRITE_ACTION_REQUESTED',
                    metadata={'action': ACTION_DRAFT_INQUIRY,
                              'pending_id': row.id})
        return self._advance_row(row, session)

    def _merge_and_advance(self, row, text, session):
        """Field supply / modification path for an active pending row."""
        Resolve = self.env['edicai.ai.action.resolve']
        if row.action == ACTION_SCHEDULE_FOLLOWUP:
            fields, _rest = extract_followup_fields(text)
            clean, ok, invalid = self._validate_entities(
                fields, row.action)
            if not ok:
                self._audit('INTENT_DETECTED',
                            conversation=session,
                            decision='deny',
                            reason_code='ACTION_FIELD_INVALID',
                            metadata={'invalid': ','.join(invalid),
                                      'action': row.action,
                                      'pending_id': row.id})
                return self._error_reply(
                    SAFE_MESSAGES[VALIDATION_FAILED] +
                    ' Re-send the corrected values for: %s.' %
                    ', '.join(invalid), action=row.action)
            if clean:
                row, _changed, _superseded = row.merge_fields(clean)
                return self._advance_row(row, session)
            # Nothing extractable: restate the current stage so a
            # stray turn can NEVER silently mutate or re-preview.
            return self._status_reply(row)
        fields, rest, invalid = Resolve.extract_and_validate(text)
        if invalid:
            self._audit('INTENT_DETECTED',
                        conversation=session,
                        decision='deny',
                        reason_code='ACTION_FIELD_INVALID',
                        metadata={'invalid': ','.join(invalid),
                                  'pending_id': row.id})
            return self._error_reply(
                SAFE_MESSAGES[VALIDATION_FAILED] +
                ' Re-send the corrected values for: %s.' %
                ', '.join(invalid))
        if fields:
            fields = dict(fields)
        hints = Resolve.match_hint_fields(rest, row._read_payload())
        fields.update({k: v for k, v in hints.items()
                       if k not in fields})
        superseded = False
        if fields:
            row, _changed, superseded = row.merge_fields(fields)
            return self._advance_row(row, session)
        # Nothing extractable: restate the current stage so a stray
        # turn can NEVER silently mutate or re-preview the action.
        return self._status_reply(row)

    def _status_reply(self, row, note=None):
        if row.status == 'preview':
            return self._preview_reply(row)
        if row.action == ACTION_SCHEDULE_FOLLOWUP:
            return self._followup_missing_reply(
                row, note=note or 'The follow-up is not ready to '
                                  'confirm yet.')
        return self._ask_missing(row, note=note or (
            'The inquiry is not ready to confirm yet.'))

    def _advance_row(self, row, session):
        """Resolution + preview generation for one pending row."""
        Resolve = self.env['edicai.ai.action.resolve']
        payload = row._read_payload()
        if row.action == ACTION_SCHEDULE_FOLLOWUP:
            outcome = Resolve.resolve_followup(payload)
            if outcome['status'] == 'missing':
                return self._followup_missing_reply(row)
            if outcome['status'] == 'invalid_date':
                self._audit('INTENT_DETECTED',
                            conversation=session,
                            decision='deny',
                            reason_code='FOLLOWUP_DATE_INVALID',
                            metadata={'pending_id': row.id})
                return self._followup_invalid_date_reply(row)
            if outcome['status'] == 'clarify':
                return self._ask_clarify(row, outcome['field'],
                                         outcome['candidates'],
                                         session, action=row.action)
            if outcome['status'] == 'not_found':
                self._audit('INTENT_AMBIGUOUS',
                            conversation=session,
                            decision='deny',
                            reason_code='ENTITY_NOT_FOUND:%s'
                            % outcome['field'],
                            metadata={'pending_id': row.id})
                return self._not_found_reply(row, outcome['field'],
                                             action=row.action)
            result = row.mark_preview()
            return self._preview_reply(result)
        outcome = Resolve.resolve_entities(payload)
        if outcome['status'] == 'missing':
            return self._ask_missing(row)
        if outcome['status'] == 'clarify':
            return self._ask_clarify(row, outcome['field'],
                                     outcome['candidates'], session)
        if outcome['status'] == 'not_found':
            self._audit('INTENT_AMBIGUOUS',
                        conversation=session,
                        decision='deny',
                        reason_code='ENTITY_NOT_FOUND:%s'
                        % outcome['field'],
                        metadata={'pending_id': row.id})
            return self._not_found_reply(row, outcome['field'])
        result = row.mark_preview()
        return self._preview_reply(result)

    # ------------------------------------------------------------------
    # Reply builders (deterministic; grounded facts only)
    # ------------------------------------------------------------------

    def _preview_reply(self, row):
        if row.action == ACTION_SCHEDULE_FOLLOWUP:
            return self._followup_preview_reply(row)
        payload = row._read_payload()
        # Show RESOLVED entity display names (preview must present the
        # exact ERP entities the confirmation will use).
        Resolve = self.env['edicai.ai.action.resolve']
        resolved = {}
        outcome = Resolve.resolve_entities(payload)
        if outcome['status'] == 'ok':
            resolved = {
                key: rec.display_name
                for key, rec in outcome['resolved'].items()}
        payload = dict(payload, **{k: v for k, v in resolved.items()
                                   if v})
        lines = [_PREVIEW_HEADER, '']
        label_map = (
            ('program', 'Program'), ('campus', 'Campus'),
            ('cycle', 'Cycle'),
        )
        lines += ['%s: %s' % (title, payload.get(key, '—'))
                  for key, title in label_map]
        lines.append('Applicant: %s' % payload.get('name', '—'))
        lines.append('Contact: %s · %s' % (
            payload.get('email', '—'), payload.get('mobile', '—')))
        lines.append('Gender: %s · Born: %s' % (
            _GENDER_LABELS.get(payload.get('gender'), '—'),
            payload.get('date_of_birth', '—')))
        if payload.get('notes'):
            lines.append('Notes: %s' % payload['notes'])
        lines += ['', _NOTHING_CREATED_LINE, '',
                  'Confirmation code: %s' % (row.ref or '')]
        lines.append(_CONFIRM_INSTRUCTIONS % (
            'confirm', row.ref or 'XXXXXXXX'))
        return {
            'status': STATUS_ANSWERED,
            'reply': '\n'.join(lines),
            'source_label': False,
            'tool_name': ACTION_DRAFT_INQUIRY,
            'error_code': None,
        }

    def _followup_preview_reply(self, row):
        """Deterministic preview for the follow-up action."""
        payload = row._read_payload()
        Resolve = self.env['edicai.ai.action.resolve']
        outcome = Resolve.resolve_followup(payload)
        if outcome.get('status') != 'ok':  # pragma: no cover — guarded
            return self._status_reply(row)
        applicant = outcome['applicant']
        date_iso = outcome['date_iso']
        time_str = outcome.get('time')
        from datetime import date as _date, datetime as _datetime
        when_text = _date.fromisoformat(
            date_iso).strftime('%A, %d %B %Y')
        if time_str:
            when_text = '%s (%s)' % (
                when_text,
                _datetime(2000, 1, 1,
                           int(time_str[:2]),
                           int(time_str[3:5]),
                ).strftime('%I:%M %p').lstrip('0'))
        lines = [_PREVIEW_HEADER_FOLLOWUP, '']
        lines.append('Applicant: %s' % applicant.display_name)
        if applicant.application_number:
            lines.append('Application No.: %s'
                         % applicant.application_number)
        lines.append('When: %s' % when_text)
        lines.append('Purpose: %s' % (payload.get('purpose') or '—'))
        lines.append('Responsible: %s · Institution: %s'
                     % (self.env.user.name, self.env.company.name))
        if applicant.campus_id:
            lines.append('Campus: %s' % applicant.campus_id.display_name)
        lines.append('Effect: a To-Do follow-up activity will be '
                     'added to this applicant, due on the above day.')
        lines += ['', _NOTHING_CHANGED_LINE, '',
                  'Confirmation code: %s' % (row.ref or '')]
        lines.append(_CONFIRM_INSTRUCTIONS_FOLLOWUP % (
            'confirm', row.ref or 'XXXXXXXX'))
        return {
            'status': STATUS_ANSWERED,
            'reply': '\n'.join(lines),
            'source_label': False,
            'tool_name': ACTION_SCHEDULE_FOLLOWUP,
            'error_code': None,
        }

    def _followup_missing_reply(self, row, note=None):
        payload = row._read_payload()
        lines = []
        if note:
            lines.append(note)
            lines.append('')
        received = [key for key in
                    ('applicant', 'date', 'purpose')
                    if payload.get(key)]
        if received:
            lines.append('Received so far: %s.' % ', '.join(received))
            lines.append('')
        from odoo.addons.edicai_ai.models.ai_action_resolve import (
            missing_followup_fields)
        missing = missing_followup_fields(payload)
        lines.append('To schedule the follow-up I still need:')
        lines += ['%d) %s' % (idx + 1, _FOLLOWUP_FIELD_LABELS[f])
                  for idx, f in enumerate(missing)]
        lines += ['', _FOLLOWUP_SUPPLY_FORMAT,
                  'Reply "cancel" to discard this request.']
        return {
            'status': STATUS_ANSWERED,
            'reply': '\n'.join(lines),
            'source_label': False,
            'tool_name': ACTION_SCHEDULE_FOLLOWUP,
            'error_code': None,
        }

    def _followup_invalid_date_reply(self, row, note=None):
        lines = []
        if note:
            lines.append(note)
        lines += [
            'That date or time could not be understood.',
            '',
            'Reply the when in a clear form like "tomorrow", '
            '"Friday", "2026-10-21", optionally with a time such as '
            '"at 11 AM".',
            'Note: the follow-up is stored with a due DAY — a time '
            'of day is kept as a note on the activity.',
            'Reply "cancel" to discard this request.']
        return {
            'status': STATUS_ANSWERED,
            'reply': '\n'.join(lines),
            'source_label': False,
            'tool_name': ACTION_SCHEDULE_FOLLOWUP,
            'error_code': None,
        }

    def _ask_missing(self, row, note=None):
        payload = row._read_payload()
        missing = missing_fields(payload)
        lines = []
        if note:
            lines.append(note)
            lines.append('')
        if payload:
            names = [key for key in
                     ('name', 'email', 'mobile', 'gender',
                      'date_of_birth', 'cycle', 'program', 'campus')
                     if payload.get(key)]
            if names:
                lines.append('Received so far: %s.' % ', '.join(names))
                lines.append('')
        if missing:
            lines.append('To draft the admission inquiry I still need:')
            numbered = [
                '%d) %s' % (idx + 1, _MISSING_FIELD_LABELS[f])
                for idx, f in enumerate(missing)]
            lines += numbered
            lines.append('')
            lines.append(_REPLY_SUPPLY_FORMAT)
        else:  # pragma: no cover — missing implies the branch above
            lines.append(
                'Say "confirm" to create the inquiry as shown, or '
                '"cancel" to discard it.')
        lines.append('Reply "cancel" to discard this request.')
        return {
            'status': STATUS_ANSWERED,
            'reply': '\n'.join(lines),
            'source_label': False,
            'tool_name': ACTION_DRAFT_INQUIRY,
            'error_code': None,
        }

    def _ask_clarify(self, row, field, candidates, session,
                     action=ACTION_DRAFT_INQUIRY):
        self._audit('INTENT_AMBIGUOUS',
                    conversation=session,
                    decision='allow',
                    reason_code='ENTITY_AMBIGUOUS:%s' % field,
                    metadata={'pending_id': row.id,
                              'candidate_count': len(candidates)})
        label = self._field_label(action, field)
        text = (
            'Which %s do you mean? Candidates: %s.\n'
            'Reply the exact %s name (e.g. "%s").'
            % (label, ', '.join(candidates), label,
               (candidates[0] if candidates else label)))
        return {
            'status': STATUS_CLARIFY,
            'reply': text,
            'source_label': False,
            'tool_name': action,
            'error_code': None,
        }

    def _field_label(self, action, field):
        if action == ACTION_SCHEDULE_FOLLOWUP or \
                field in _FOLLOWUP_FIELD_LABELS:
            return _FOLLOWUP_FIELD_LABELS.get(field, field)
        return _MISSING_FIELD_LABELS.get(field, field)

    def _not_found_reply(self, row, field, action=ACTION_DRAFT_INQUIRY):
        label = self._field_label(action, field)
        if action == ACTION_SCHEDULE_FOLLOWUP:
            return {
                'status': STATUS_ERROR,
                'reply': (
                    'That %s could not be found in this institution. '
                    'Reference the corrected %s, or "cancel" to '
                    'discard.'
                    % (label, label)),
                'source_label': False,
                'tool_name': action,
                'error_code': RECORD_NOT_FOUND,
            }
        return {
            'status': STATUS_ERROR,
            'reply': (
                'That %s could not be found in this institution. '
                'Reply the corrected %s, or "cancel" to discard.'
                % (label, label)),
            'source_label': False,
            'tool_name': ACTION_DRAFT_INQUIRY,
            'error_code': RECORD_NOT_FOUND,
        }

    def _finalize_execution(self, outcome, session, row):
        kind = outcome.get('outcome')
        if kind == 'executed':
            return self._executed_reply(outcome.get('verified') or {},
                                        duplicated=False,
                                        action=row.action)
        if kind == 'duplicate_concurrent':
            return self._answered_reply(
                'This confirmation was already being processed. '
                'Nothing was duplicated.', action=row.action)
        if kind == 'duplicate':
            fresh = outcome.get('row')
            return self._executed_reply(
                fresh._read_result() if fresh else {},
                duplicated=True, action=row.action)
        if kind == 'expired':
            return self._error_reply(
                'This pending action has expired. Please submit the '
                'request again — nothing was created.', action=row.action)
        if kind == 'denied':
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=row.action)
        if kind == 'missing':
            return self._status_reply(row)
        if kind == 'invalid_date':
            return self._followup_invalid_date_reply(row)
        if kind == 'clarify':
            return self._ask_clarify(row, outcome['field'],
                                     outcome['candidates'], session,
                                     action=row.action)
        if kind == 'not_found':
            return self._not_found_reply(row, outcome['field'],
                                         action=row.action)
        if kind == 'duplicate_existing':
            return self._duplicate_existing_reply(
                outcome.get('verified') or {})
        if kind == 'verification_failed':
            return self._error_reply(
                'The requested change could not be verified as '
                'applied — nothing is reported as done.',
                action=row.action)
        code = outcome.get('error_code') or VALIDATION_FAILED
        if code == VALIDATION_FAILED:
            return self._error_reply(
                SAFE_MESSAGES[VALIDATION_FAILED] +
                ' Nothing was %s. Re-send the details to try again, '
                'or "cancel" to discard.' % (
                    'scheduled' if row.action ==
                    ACTION_SCHEDULE_FOLLOWUP else 'created'),
                action=row.action)
        return self._error_reply(SAFE_MESSAGES.get(
            code, SAFE_MESSAGES[INTERNAL_ERROR]), action=row.action)

    def _executed_reply(self, verified, duplicated=False,
                        action=ACTION_DRAFT_INQUIRY):
        """Grounded ONLY in the verified execution result (§16/#22)."""
        lines = []
        if duplicated:
            lines.append(
                'Already done — this confirmation was already '
                'processed and nothing was duplicated.')
        elif action == ACTION_SCHEDULE_FOLLOWUP:
            lines.append('Done. The follow-up has been scheduled.')
        elif action in (ACTION_ENTITY_CREATE, ACTION_ENTITY_UPDATE):
            what = verified.get('model_label') or 'record'
            verb = 'created' if action == ACTION_ENTITY_CREATE \
                else 'updated'
            lines.append('Done. %s %s.' % (what, verb))
        elif action == ACTION_ENTITY_EXECUTE:
            label = verified.get('action_label') or 'Action'
            if verified.get('changed') is False:
                lines.append(
                    'Nothing to do — the record was already in that '
                    'state (%s).' % label)
            else:
                lines.append('Done. %s.' % label)
        else:
            lines.append('Done. Your admission inquiry has been '
                         'created.')
        lines.append('')
        if action in (ACTION_ENTITY_CREATE, ACTION_ENTITY_UPDATE,
                      ACTION_ENTITY_EXECUTE):
            if verified.get('id'):
                lines.append('Record ID: %s' % verified['id'])
            if verified.get('name'):
                lines.append('Name: %s' % verified['name'])
        elif action == ACTION_SCHEDULE_FOLLOWUP:
            if verified.get('applicant'):
                lines.append('Applicant: %s' % verified['applicant'])
            if verified.get('application_number'):
                lines.append('Application No.: %s'
                             % verified['application_number'])
            when = verified.get('date') or ''
            if when:
                from datetime import date as _date
                when = _date.fromisoformat(when).strftime(
                    '%A, %d %B %Y')
            if verified.get('time'):
                when = '%s at %s' % (when, verified['time'])
            if when:
                lines.append('When: %s' % when)
            if verified.get('purpose'):
                lines.append('Purpose: %s' % verified['purpose'])
        else:
            if verified.get('program'):
                lines.append('Program: %s' % verified['program'])
            if verified.get('campus'):
                lines.append('Campus: %s' % verified['campus'])
            if verified.get('cycle'):
                lines.append('Cycle: %s' % verified['cycle'])
            if verified.get('name'):
                lines.append('Applicant: %s' % verified['name'])
            if verified.get('application_number'):
                lines.append('Application No.: %s'
                             % verified['application_number'])
        reply = '\n'.join(lines)
        return {
            'status': STATUS_ANSWERED,
            'reply': reply,
            'source_label': False,
            'tool_name': action,
            'error_code': None,
        }

    def _duplicate_existing_reply(self, verified):
        number = verified.get('application_number') \
            if verified else False
        lines = ['An application with this e-mail, program and cycle '
                 'already exists in this institution.',
                 '', 'Program: %s' % (verified.get('program') or '—'),
                 'Cycle: %s' % (verified.get('cycle') or '—')]
        if number:
            lines.append('Existing Application No.: %s' % number)
        lines += ['', 'Nothing was created.']
        return {
            'status': STATUS_ANSWERED,
            'reply': '\n'.join(lines),
            'source_label': False,
            'tool_name': ACTION_DRAFT_INQUIRY,
            'error_code': VALIDATION_FAILED,
        }

    def _answered_reply(self, text, action=ACTION_DRAFT_INQUIRY):
        return {
            'status': STATUS_ANSWERED,
            'reply': text,
            'source_label': False,
            'tool_name': action,
            'error_code': None,
        }

    def _error_reply(self, text, action=ACTION_DRAFT_INQUIRY):
        return {
            'status': STATUS_ERROR,
            'reply': '⚠️ %s' % text
            if not text.startswith('⚠️') else text,
            'source_label': False,
            'tool_name': action,
            'error_code': VALIDATION_FAILED,
        }

    # ------------------------------------------------------------------
    # Phase 4 — the ONE approval lane (additive turn helpers, gated)
    # ------------------------------------------------------------------

    def _approval_start(self, text, session):
        """A NEW approval-lane request (gate → schema → draft)."""
        policy = self.env['edicai.ai.action.policy']
        Approval = self.env['edicai.ai.pending.approval']
        gate = policy.check_approval_requester_access()
        if not gate['allowed']:
            self._audit('APPROVAL_AUTH_DENIED',
                        conversation=session,
                        decision='deny',
                        reason_code=gate['reason_code'],
                        tool_name=_AP_KIND)
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=_AP_KIND)
        # One active item per conversation: a NEW request supersedes
        # any active pending ACTION row (the Phase 3 takeover pattern).
        Pending = self.env['edicai.ai.pending.action']
        previous = Pending.open_active(session)
        if previous:
            previous.write({'status': 'superseded'})
            Pending._audit('ACTION_INVALIDATED', conversation=session,
                           reason_code='SUPERSEDED_BY_APPROVAL',
                           metadata={'pending_id': previous.id},
                           tool_name=previous.action)
        fields, _rest = extract_approval_entities(text)
        clean, ok, invalid = validate_approval_entities(fields)
        if not ok:
            self._audit('INTENT_DETECTED',
                        conversation=session,
                        decision='deny',
                        reason_code='APPROVAL_FIELD_INVALID',
                        metadata={'invalid': ','.join(invalid)},
                        tool_name=_AP_KIND)
            return self._error_reply(
                SAFE_MESSAGES[VALIDATION_FAILED] +
                ' Re-send the request without the invalid values.',
                action=_AP_KIND)
        return Approval.start_request(session, clean)

    def _approval_turn(self, text, arow, detected, detected_wf,
                       detected_ap, session):
        """Route a turn while an ACTIVE approval row (requester side)
        owns this session — mirror of ``_workflow_turn``."""
        policy = self.env['edicai.ai.action.policy']
        # A NEW approval request = material change: fresh plan → new
        # preview (start supersedes the active row, audited).
        if detected_ap == 'create':
            return self._approval_start(text, session)
        # An allow-listed ACTION request is a material change (§15).
        if detected:
            arow._lifecycle_write({'status': 'cancelled',
                                   'failure_reason':
                                       'SUPERSEDED_BY_ACTION'})
            arow._audit_event('APPROVAL_SUPERSEDED', decision='deny',
                              reason_code='SUPERSEDED_BY_ACTION',
                              metadata={'approval_id': arow.id})
            return self._start_request(text, session, detected)
        # A WORKFLOW goal is a material change (§15).
        if detected_wf:
            arow._lifecycle_write({'status': 'cancelled',
                                   'failure_reason':
                                       'SUPERSEDED_BY_WORKFLOW'})
            arow._audit_event('APPROVAL_SUPERSEDED', decision='deny',
                              reason_code='SUPERSEDED_BY_WORKFLOW',
                              metadata={'approval_id': arow.id})
            Wf = self.env['edicai.ai.pending.workflow']
            return Wf.start_workflow(session, dict(
                extract_workflow_fields(text)[0]))
        if detected_ap in ('approve', 'reject'):
            self._audit('APPROVAL_AUTH_DENIED', conversation=session,
                        decision='deny', reason_code='REQUESTER_CANNOT_DECIDE',
                        metadata={'approval_id': arow.id},
                        tool_name=_AP_KIND)
            return self._error_reply(
                'You cannot approve or reject your own request. An '
                'independent authorized approver must review it.')
        gate = policy.check_approval_requester_access()
        if not gate['allowed']:
            self._audit('APPROVAL_AUTH_DENIED', conversation=session,
                        decision='deny',
                        reason_code=gate['reason_code'],
                        tool_name=_AP_KIND)
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=_AP_KIND)
        low = text.strip().lower()
        ref_match = _REF_CONFIRM.match(low)
        if low in CONFIRM_WORDS or ref_match:
            if ref_match and ref_match.group(1) != (arow.ref or ''):
                self._audit('APPROVAL_CONFIRMED',
                            conversation=session,
                            decision='deny',
                            reason_code='CONFIRMATION_CODE_MISMATCH',
                            metadata={'approval_id': arow.id},
                            tool_name=_AP_KIND)
                return self._error_reply(
                    'That confirmation code does not match the '
                    'pending asset request.')
            if arow.status != 'preview':
                return arow.status_reply()
            outcome = arow.confirm_and_submit()
            return self._finalize_approval(outcome, 'submit')
        if low in CANCEL_WORDS:
            outcome = arow.cancel()
            return self._finalize_approval(outcome, 'cancel')
        # Otherwise the turn may be field supply / status.
        return self._approval_merge(arow, text, session)

    def _approval_merge(self, arow, text, session):
        """Field supply on the DRAFT approval row (deterministic)."""
        fields, _rest = extract_approval_entities(text)
        if not fields:
            return arow.status_reply()
        clean, ok, invalid = validate_approval_entities(fields)
        if not ok:
            self._audit('INTENT_DETECTED', conversation=session,
                        decision='deny',
                        reason_code='APPROVAL_FIELD_INVALID',
                        metadata={'approval_id': arow.id,
                                  'invalid': ','.join(invalid)},
                        tool_name=_AP_KIND)
            return self._error_reply(
                SAFE_MESSAGES[VALIDATION_FAILED] +
                ' Re-send the values without the invalid ones.',
                action=_AP_KIND)
        _row, merged = arow.merge_payload(clean)
        if not merged:
            return arow.status_reply()
        return arow.advance()

    def _approval_approver_turn(self, text, intent, session,
                                token_kind=None, token=None):
        """The approver lane: list / approve / reject (§9–§12).

        Approval authority is NEVER taken from the text: the routing
        gate (flag + admin group) runs here, and the FULL decision
        gate re-runs on the row at execution time.
        """
        policy = self.env['edicai.ai.action.policy']
        Approval = self.env['edicai.ai.pending.approval']
        if intent == 'list':
            # Grounded pending list — record rules decide visibility.
            return Approval.pending_list_reply()
        row = Approval.find_by_address(token_kind, token)
        if row and row.requester_id.id == self.env.user.id:
            # §8: a requester addressing their OWN approval is
            # answered with its honest status — a self-approval
            # through the lane is impossible (fail closed, even for
            # an admin: approval ≠ requester).
            return row.status_reply()
        gate = policy.check_approval_approver_access()
        if not gate['allowed']:
            self._audit('APPROVAL_AUTH_DENIED', conversation=session,
                        decision='deny',
                        reason_code=gate['reason_code'],
                        tool_name=_AP_KIND)
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=_AP_KIND)
        if not row and intent in ('approve', 'reject'):
            # The token may name an ALREADY-DECIDED approval: replay
            # its grounded decision honestly (never a second run).
            decided = Approval.find_decided_by_address(token_kind,
                                                       token)
            if decided:
                if decided.status == STATUS_EXECUTED:
                    return decided.compose_decision_reply(
                        duplicated=True)
                if decided.status == STATUS_REJECTED:
                    return decided.compose_rejection_reply()
                return decided.status_reply()
            any_row = Approval.find_any_by_address(token_kind,
                                                   token)
            if any_row:
                return any_row.status_reply()
        if not row:
            # Deterministic clarification: the grounded pending list
            # (or the honest "nothing pending" answer).
            return Approval.pending_list_reply()
        if intent == 'approve':
            outcome = row.approve_and_execute()
            return self._finalize_approval(outcome, 'approve')
        reason = _parse_ap_reason(text)
        outcome = row.reject_and_execute(reason)
        return self._finalize_approval(outcome, 'reject')

    def _finalize_approval(self, outcome, phase):
        """Map a lifecycle outcome to its grounded reply (§17: no
        false success; duplicates replay honestly)."""
        state = outcome.get('outcome')
        row = outcome.get('row')
        if state == 'submitted':
            return row.submitted_reply()
        if state == 'executed':
            return row.compose_decision_reply()
        if state == 'rejected':
            return row.compose_rejection_reply()
        if state == 'cancelled':
            return row.compose_withdrawn_reply(
                outcome.get('target_state') or '')
        if state in ('duplicate', 'duplicate_concurrent'):
            if phase == 'approve':
                return row.compose_decision_reply(duplicated=True)
            if phase == 'reject':
                return row.compose_rejection_reply()
            return row.status_reply()
        if state in ('not_pending', 'not_confirmable',
                     'not_cancellable'):
            if row and row.id:
                return row.status_reply()
            return self._error_reply(
                'The asset request is not ready for that. Nothing '
                'was executed.', action=_AP_KIND)
        if state == 'expired':
            return row._error_reply(_AP_EXPIRED_TEXT)
        if state == 'expired_preview':
            return row._error_reply(
                'This asset request preview has expired. Please send '
                'the request again — nothing was created.')
        if state == 'hash_mismatch':
            return row._error_reply(
                'This approval request no longer matches its frozen '
                'plan. Nothing was executed; send a new request.')
        if state == 'invalidated':
            return row.compose_invalidated_reply()
        if state == 'denied':
            reason = outcome.get('reason_code') or ''
            if reason == 'SELF_APPROVAL':
                return row._error_reply(
                    'A requester cannot approve their own request. '
                    'Approval is reserved to an institution '
                    'administrator other than the requester. Nothing '
                    'was executed.')
            if reason == 'COMPANY_MISMATCH':
                return row._error_reply(
                    'This approval belongs to another institution. '
                    'Nothing was executed.')
            return self._error_reply(
                SAFE_MESSAGES[AUTHORIZATION_DENIED], action=_AP_KIND)
        if state == 'target_processed':
            return row._error_reply(
                'The asset request %s has already been processed '
                '(state: %s). Nothing was executed by this approval '
                'lane.' % (row.request_id.name or '',
                           outcome.get('target_state') or 'unknown'))
        # 'error' and anything unexpected — an honest failure (§17).
        return row._error_reply(
            'The approval could not be executed: the canonical '
            'business rules rejected it. Nothing was executed.') \
            if row and row.id else self._error_reply(
                'The approval could not be executed. Nothing was '
                'executed.', action=_AP_KIND)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    @api.model
    def _audit(self, event_type, conversation=None, decision=None,
               reason_code=None, detail=None, metadata=None,
               tool_name=None):
        """Best-effort audit mirroring ai_orchestrator._audit."""
        try:
            return self.env['edicai.ai.audit.event'].log_event(
                event_type,
                tool_name=tool_name or ACTION_DRAFT_INQUIRY,
                conversation=conversation,
                decision=decision,
                reason_code=reason_code,
                detail=detail,
                metadata=metadata,
            )
        except Exception:
            _logger.exception('AI action orchestrator: audit failed.')
            return False
