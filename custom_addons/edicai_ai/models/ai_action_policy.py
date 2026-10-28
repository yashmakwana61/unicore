"""Phase 2A — policy gate for the FIRST conversational write action.

``admission.draft_inquiry`` (drafting a new admission inquiry, i.e. an
``edicai.admission.applicant`` record with ``state='inquiry'``) is the
single allow-listed conversational write.  This module is its POLICY
LAYER ONLY — it never executes anything:

    request ──► POLICY GATE (this module, twice: preview + re-confirm)
                ──► pending action (ai_pending_action)
                ──► existing admission business logic (applicant.create)

Design rules carried over from Phases 0/1A/1B:

* Fail-closed: an unavailable flag reader or group check DENIES.
* The LLM can never grant permission; authorization state lives in
  ``ir.config_parameter`` + Odoo groups, never in conversation context.
* ``any-of`` group semantics: matches the ACTUAL backend ACL of
  ``edicai.admission.applicant`` (create/write is granted to registrar,
  manager and admin — see edicai_admission/security/ir.model.access.csv).
  This module therefore deviates deliberately from the all-of group
  loop used by the read-only policy gate (ai_policy.py), which checks
  a single AI-user group.
* NO ``sudo()`` anywhere in this path.
"""

import logging

from odoo import api, models

from odoo.addons.edicai_ai.models.ai_approval import REQUESTER_GROUPS
from odoo.addons.edicai_ai.models.ai_proactive import SURFACE_GROUPS

_logger = logging.getLogger(__name__)

#: Allow-listed conversational write actions (Phase 2A + 2B entities
#: from Phase G2).
from odoo.addons.edicai_ai.models.ai_action_resolve import (
    ACTION_ENTITY_CREATE,
    ACTION_ENTITY_EXECUTE,
    ACTION_ENTITY_UPDATE,
)
ACTION_DRAFT_INQUIRY = 'admission.draft_inquiry'
ACTION_SCHEDULE_FOLLOWUP = 'admission.schedule_followup'

ACTION_ALLOWLIST = (ACTION_DRAFT_INQUIRY, ACTION_SCHEDULE_FOLLOWUP,
                    ACTION_ENTITY_CREATE, ACTION_ENTITY_UPDATE,
                    ACTION_ENTITY_EXECUTE)

#: Phase G2 master flag for the GENERIC entity write surface. The
#: individual ENTITY policy (edicai.ai.entity.policy write_groups) is
#: the data-level gate; this flag is the module-level master switch,
#: default OFF, exactly like the Phase 2A flag.

#: Server-side feature flag. Default OFF: with the flag off, the
#: orchestrator behaves exactly as in Phase 1B (write requests keep
#: hitting the deterministic Phase 1A unsupported reply).
FLAG_ACTION_WRITE = 'edicai_ai.action_write_enabled'
FLAG_ACTION_ENTITY_WRITE = 'edicai_ai.action_entity_write_enabled'
#: Phase G3: the record-ACTION master flag (declared methods only).
FLAG_ACTION_ENTITY_EXECUTE = 'edicai_ai.action_entity_execute_enabled'

#: Phase 5: independent flag for the ONE proactive-intelligence slice
#: (``attendance.shortage.review``).  Default OFF — with it off the
#: proactive router is never consulted and Phases 0–4 stay
#: byte-identical (prompt §22).
FLAG_PROACTIVE = 'edicai_ai.proactive_enabled'

#: Phase 2B: independent rollout flag for the follow-up action, so
#: the FIRST write action's rollout is never reopened by accident.
#: Default OFF — with it off, follow-up requests keep hitting the
#: Phase 1A unsupported reply, byte-identically.
FLAG_ACTION_FOLLOWUP = 'edicai_ai.action_followup_enabled'

#: Phase 3: independent rollout flag for the ONE conversational
#: workflow (admission.prepare_followups).  Default OFF; the workflow
#: additionally requires the follow-up ACTION flag at execution time
#: (existing individual action flags stay respected, prompt §30).
FLAG_WORKFLOW = 'edicai_ai.workflow_enabled'

#: Phase 4: independent rollout flag for the ONE approval-required
#: vertical slice (asset.request.approval).  Default OFF — with it
#: off, approval phrasings are not even detected and Phases 0–3
#: behave byte-identically.
FLAG_APPROVAL = 'edicai_ai.approval_enabled'

#: Bounded lifetime of a PENDING approval (minutes), configurable.
PARAM_APPROVAL_TIMEOUT = 'edicai_ai.approval_timeout_minutes'
DEFAULT_APPROVAL_TIMEOUT_MINUTES = 1440  # 24 hours

#: Confirmation timeout (minutes) for pending actions, configurable.
PARAM_ACTION_TIMEOUT = 'edicai_ai.action_confirm_timeout_minutes'
DEFAULT_ACTION_TIMEOUT_MINUTES = 15

#: any-of groups matching the applicant-create backend ACL.
WRITE_GROUPS = (
    'edicai_base.group_edicai_registrar',
    'edicai_base.group_edicai_manager',
    'edicai_base.group_edicai_admin',
)


class EdicaiAIActionPolicy(models.AbstractModel):
    """Write-action allow-list, flag + any-of group gate (Phase 2A)."""

    _name = 'edicai.ai.action.policy'
    _description = 'AI Action Policy (conversational write gate)'

    # ------------------------------------------------------------------
    # Flag helpers (mirrors ai_config.py patterns; additive)
    # ------------------------------------------------------------------

    @api.model
    def is_action_write_enabled(self):
        """Phase 2A: the conversational write layer master flag.

        Default OFF — with the flag off ``answer_turn`` must behave
        byte-identically to Phase 1B (this module is not even entered).
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_ACTION_WRITE, default='False')
        except Exception:
            # Fail closed: an unreadable flag must never open writes.
            _logger.exception(
                'AI action policy: flag read failed (failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def is_followup_enabled(self):
        """Phase 2B: independent flag for the follow-up action.

        Default OFF — with it off the follow-up action cannot even be
        half-armed: requests fall through to Phase 1A unchanged.
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_ACTION_FOLLOWUP, default='False')
        except Exception:
            _logger.exception(
                'AI action policy: follow-up flag read failed '
                '(failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    def is_any_action_enabled(self):
        """True when ANY allow-listed write action is enabled."""
        return self.is_action_write_enabled() or self.is_followup_enabled()

    @api.model
    def is_workflow_enabled(self):
        """Phase 3: independent flag for the one workflow.

        Default OFF — with it off the workflow layer is not even
        entered (byte-identical Phases 0/1A/1B/2A/2B behaviour).
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_WORKFLOW, default='False')
        except Exception:
            _logger.exception(
                'AI action policy: workflow flag read failed '
                '(failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def is_any_gate_enabled(self):
        """True when ANY write path (action, workflow or entity) is on.

        Byte-identical to ``is_any_action_enabled`` whenever the
        workflow, approval AND entity flags are off (the entity flag
        is default OFF, so Phases 0-4 behaviour is unchanged until a
        manager deliberately opens the generic entity surface).
        """
        return self.is_any_action_enabled() or self.is_workflow_enabled() \
            or self.is_approval_enabled() or self.is_entity_write_enabled() \
            or self.is_entity_execute_enabled()

    @api.model
    def is_approval_enabled(self):
        """Phase 4: independent flag for the ONE approval slice.

        Default OFF — with it off, approval phrasings are not even
        detected (byte-identical Phase 0–3 behaviour).
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_APPROVAL, default='False')
        except Exception:
            _logger.exception(
                'AI action policy: approval flag read failed '
                '(failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def is_entity_write_enabled(self):
        """Phase G2: master flag for GENERIC entity create/update.

        Default OFF. Entity-level grants live in
        ``edicai.ai.entity.policy.write_groups`` (also deny-by-default);
        BOTH switch and per-entity grant must be open for an execution
        to proceed (defense in depth).
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_ACTION_ENTITY_WRITE, default='False')
        except Exception:
            _logger.exception(
                'AI action policy: entity write flag read failed '
                '(failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def is_entity_execute_enabled(self):
        """Phase G3: master flag for declared record ACTIONS.

        Default OFF and INDEPENDENT of the G2 write flag: executing a
        business method is a different risk than writing a field, so a
        deployment can open (or close) either surface on its own.
        Entity-level grants live in
        ``edicai.ai.entity.policy.execute_groups`` plus the action row's
        ``allowed_groups`` — all three must be open.
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_ACTION_ENTITY_EXECUTE, default='False')
        except Exception:
            _logger.exception(
                'AI action policy: entity execute flag read failed '
                '(failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def get_confirm_timeout_minutes(self):
        """Pending-action expiry window, floored at 1 minute."""
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                PARAM_ACTION_TIMEOUT, default=DEFAULT_ACTION_TIMEOUT_MINUTES)
            return max(1, int(float(value)))
        except (TypeError, ValueError):
            return DEFAULT_ACTION_TIMEOUT_MINUTES
        except Exception:
            _logger.exception(
                'AI action policy: timeout read failed (using default).')
            return DEFAULT_ACTION_TIMEOUT_MINUTES

    # ------------------------------------------------------------------
    # The gate (runs TWICE in the lifecycle: before preview and again
    # immediately before execution — prompt §14 re-authorization)
    # ------------------------------------------------------------------

    @api.model
    def check_write_access(self, action, user=None):
        """Authorize one conversational write action.

        :returns: ``{'allowed': bool, 'reason_code': str}`` — never
            raises, never reads conversation context/LLM output.
        """
        user = user or self.env.user
        if action not in ACTION_ALLOWLIST:
            return {'allowed': False,
                    'reason_code': 'NOT_IN_ACTION_ALLOWLIST'}
        # Per-action flag: disabling ONE action never re-arms the
        # other (Phase 2B rollout isolation, prompt §22).
        if action == ACTION_DRAFT_INQUIRY and \
                not self.is_action_write_enabled():
            return {'allowed': False, 'reason_code': 'ACTION_WRITE_DISABLED'}
        if action == ACTION_SCHEDULE_FOLLOWUP and \
                not self.is_followup_enabled():
            return {'allowed': False,
                    'reason_code': 'ACTION_WRITE_DISABLED'}
        if action in (ACTION_ENTITY_CREATE, ACTION_ENTITY_UPDATE,
                      ACTION_ENTITY_EXECUTE):
            # Canonical + entity-policy validation already ran at
            # PREVIEW time and will run again inside the executor;
            # here: master flag + the AI-user grant. The DATA grants
            # (write_groups / execute_groups + the action row) are
            # re-verified at execution time by the entity tools.
            if action == ACTION_ENTITY_EXECUTE:
                if not self.is_entity_execute_enabled():
                    return {'allowed': False,
                            'reason_code': 'ENTITY_EXECUTE_DISABLED'}
            elif not self.is_entity_write_enabled():
                return {'allowed': False,
                        'reason_code': 'ENTITY_WRITE_DISABLED'}
            has_user = False
            try:
                has_user = user.has_group(
                    'edicai_ai.group_edicai_ai_user')
            except Exception:
                _logger.exception(
                    'AI action policy: entity user check failed '
                    'for %s (denying).', user.login)
            if has_user:
                return {'allowed': True, 'reason_code': 'OK'}
            return {'allowed': False,
                    'reason_code': 'GROUP_GATE:edicai_ai_user'}
        # any-of semantics (matches the backend ACL): a user holding ANY
        # of the write groups may use the action. Fail-closed per group:
        # a broken ``has_group`` counts as a missing group.
        for group in WRITE_GROUPS:
            try:
                if user.has_group(group):
                    return {'allowed': True, 'reason_code': 'OK'}
            except Exception:
                _logger.exception(
                    'AI action policy: group check failed for %s '
                    '(denying).', group)
        return {'allowed': False,
                'reason_code': 'GROUP_GATE:any_of:%s' % ','.join(
                    g.rsplit('.', 1)[-1] for g in WRITE_GROUPS)}

    @api.model
    def check_approval_requester_access(self, user=None):
        """Authorize the REQUESTER side of the ONE approval slice.

        Exactly the module's own asset-request CREATE authority that
        can also READ the required campus reference (manager / admin
        per ``edicai_asset_request`` ACL + ``edicai.campus`` ACL),
        gated by the Phase 4 flag.  Fails closed per check.
        The APPROVER authority is a DIFFERENT gate (enforced on the
        approval row at decision time) — a requester is never an
        approver by this gate.
        """
        user = user or self.env.user
        if not self.is_approval_enabled():
            return {'allowed': False, 'reason_code':
                        'APPROVAL_DISABLED'}
        for group in REQUESTER_GROUPS:
            try:
                if user.has_group(group):
                    return {'allowed': True, 'reason_code': 'OK'}
            except Exception:
                _logger.exception(
                    'AI action policy: requester group check failed '
                    'for %s (denying).', group)
        return {'allowed': False,
                'reason_code': 'GROUP_GATE:any_of:facultymgradmin'}

    @api.model
    def get_approval_timeout_minutes(self):
        """Pending-APPROVAL lifetime, floored at 1 minute."""
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                PARAM_APPROVAL_TIMEOUT,
                DEFAULT_APPROVAL_TIMEOUT_MINUTES)
            return max(1, int(float(value)))
        except (TypeError, ValueError):
            return DEFAULT_APPROVAL_TIMEOUT_MINUTES
        except Exception:
            _logger.exception(
                'AI action policy: approval timeout read failed '
                '(using default).')
            return DEFAULT_APPROVAL_TIMEOUT_MINUTES

    @api.model
    def check_approval_approver_access(self, user=None):
        """Authorize the APPROVER lane commands (list/approve/reject).

        This is only the ROUTING precondition: the approval flag plus
        the actual approver group (``edicai_base.group_edicai_admin`` —
        the repository's designated authority, see
        ``ai_approval.APPROVER_GROUP``).  The FULL per-row gate —
        admin group re-check, actor ≠ requester, same company, target
        visibility, hash integrity — is re-verified at DECISION time
        on the approval row itself (prompt §10/§11).
        """
        user = user or self.env.user
        if not self.is_approval_enabled():
            return {'allowed': False, 'reason_code':
                        'APPROVAL_DISABLED'}
        try:
            if user.has_group('edicai_base.group_edicai_admin'):
                return {'allowed': True, 'reason_code': 'OK'}
        except Exception:
            _logger.exception(
                'AI action policy: approver group check failed '
                '(denying).')
        return {'allowed': False, 'reason_code': 'NOT_AN_APPROVER'}

    @api.model
    def is_proactive_enabled(self):
        """Phase 5: independent flag for the ONE proactive slice.

        Default OFF — with it off the proactive router is never
        consulted (byte-identical Phases 0–4 behaviour).
        """
        try:
            value = self.env['ir.config_parameter'].sudo().get_param(
                FLAG_PROACTIVE, default='False')
        except Exception:
            _logger.exception(
                'AI action policy: proactive flag read failed '
                '(failing closed).')
            return False
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @api.model
    def check_proactive_access(self, user=None):
        """Authorize the ONE proactive slice for a user.

        Authority is identical to the repository itself: the user
        must hold one of the groups that can READ the underlying
        attendance records (faculty / registrar / manager / admin per
        ``edicai_attendance`` ACLs).  The actual EVIDENCE visibility is
        then narrowed further by the record rules at detection time
        — faculty see only their own sessions' rows.  Fails closed
        per group (a broken ``has_group`` counts as missing).
        """
        user = user or self.env.user
        if not self.is_proactive_enabled():
            return {'allowed': False, 'reason_code': 'PROACTIVE_DISABLED'}
        for group in SURFACE_GROUPS:
            try:
                if user.has_group(group):
                    return {'allowed': True, 'reason_code': 'OK'}
            except Exception:
                _logger.exception(
                    'AI action policy: proactive group check failed '
                    'for %s (denying).', group)
        return {'allowed': False,
                'reason_code': 'GROUP_GATE:any_of:%s' % ','.join(
                    g.rsplit('.', 1)[-1] for g in SURFACE_GROUPS)}

    @api.model
    def check_workflow_access(self, user=None):
        """Authorize the Phase 3 workflow (its own double gate).

        The workflow composes ALREADY-AUTHORIZED action primitives, so
        it requires: the workflow flag, the follow-up ACTION flag (its
        execution target — existing individual flags stay respected)
        and the same any-of group pattern.  Fails closed per check.
        """
        user = user or self.env.user
        if not self.is_workflow_enabled():
            return {'allowed': False, 'reason_code': 'WORKFLOW_DISABLED'}
        if not self.is_followup_enabled():
            return {'allowed': False,
                    'reason_code': 'ACTION_WRITE_DISABLED'}
        for group in WRITE_GROUPS:
            try:
                if user.has_group(group):
                    return {'allowed': True, 'reason_code': 'OK'}
            except Exception:
                _logger.exception(
                    'AI action policy: workflow group check failed for '
                    '%s (denying).', group)
        return {'allowed': False,
                'reason_code': 'GROUP_GATE:any_of:%s' % ','.join(
                    g.rsplit('.', 1)[-1] for g in WRITE_GROUPS)}
