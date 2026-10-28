"""Durable AI audit trail — Phase 0 (Security Foundation).

``edicai.ai.audit.event`` records WHAT happened, WHO caused it, WHEN, and
whether it was allowed or denied.  It stores NO conversation content and
NO raw provider/tool payloads by default: only small, redacted, derived
metadata (counts, statuses, content lengths) may be persisted in
``metadata_json``.

Writes go through :meth:`EdicaiAIAuditEvent.log_event`, which is
best-effort (an audit failure must never crash a user request) and uses
``sudo`` internally — audit logging is *not* an AI execution path, and
audit rows must be recordable regardless of the actor's own model
access.  Reads are restricted to AI Manager / administrator within the
record's company by ACL + record rules
(``security/edicai_ai_record_rules.xml``).
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: Durable event categories.  Phase 0 surface + Phase 1A additive
#: INTENT_* lifecycle events.  Keep additive-only.
EVENT_TYPES = (
    'CHAT_CREATED',
    'CHAT_SESSION_DELETED',
    'CHAT_SESSION_RENAMED',
    'CHAT_ACCESS_DENIED',
    'CHAT_MESSAGE_SENT',
    'INTENT_DETECTED',
    'INTENT_UNKNOWN',
    'INTENT_UNSUPPORTED',
    'INTENT_AMBIGUOUS',
    # Phase 1B — LLM-understanding lifecycle (additive).
    'LLM_UNDERSTANDING',
    'LLM_COMPOSE',
    'TOOL_EXECUTED',
    'TOOL_DENIED',
    'TOOL_ERROR',
    'RATE_LIMITED',
    'AI_PROVIDER_CALL',
    'AI_PROVIDER_ERROR',
    'AUTHORIZATION_DENIED',
    'INTERNAL_ERROR',
    # Phase 2A — first confirmed write action lifecycle (additive).
    'ACTION_PREVIEW_CREATED',
    'ACTION_CONFIRMED',
    'ACTION_AUTHORIZATION_DENIED',
    'ACTION_EXECUTED',
    'ACTION_VERIFIED',
    'ACTION_DUPLICATE',
    'ACTION_ERROR',
    'ACTION_CANCELLED',
    'ACTION_EXPIRED',
    'ACTION_INVALIDATED',
    # Phase 3 — the one conversational workflow (additive).
    'WORKFLOW_PROPOSED',
    'WORKFLOW_PREVIEWED',
    'WORKFLOW_AUTH_DENIED',
    'WORKFLOW_CONFIRMED',
    'WORKFLOW_EXECUTION_STARTED',
    'WORKFLOW_OPERATION_EXECUTED',
    'WORKFLOW_OPERATION_FAILED',
    'WORKFLOW_COMPLETED',
    'WORKFLOW_PARTIAL',
    'WORKFLOW_DUPLICATE',
    'WORKFLOW_CANCELLED',
    'WORKFLOW_EXPIRED',
    'WORKFLOW_INVALIDATED',
    # Phase 4 — the ONE approval-required slice (additive).
    'APPROVAL_PROPOSED',
    'APPROVAL_PREVIEWED',
    'APPROVAL_SUBMITTED',
    'APPROVAL_CONFIRMED',
    'APPROVAL_AUTH_DENIED',
    'APPROVAL_APPROVED',
    'APPROVAL_REJECTED',
    'APPROVAL_CANCELLED',
    'APPROVAL_EXPIRED',
    'APPROVAL_EXECUTION_STARTED',
    'APPROVAL_EXECUTED',
    'APPROVAL_EXECUTION_FAILED',
    'APPROVAL_VERIFICATION_FAILED',
    'APPROVAL_DUPLICATE',
    'APPROVAL_SUPERSEDED',
    'APPROVAL_INVALIDATED',
    # Phase 12 — validated, bounded query context.
    'QUERY_FILTER_REJECTED',
    'QUERY_CONTEXT_EXPLAINED',
    # Phase 5 — proactive-intelligence slice (additive, informational
    # surface lifecycle; the insight NEVER mutates business records).
    'PROACTIVE_SIGNAL_DETECTED',
    'PROACTIVE_SIGNAL_SURFACED',
    'PROACTIVE_SIGNAL_EXPLAINED',
    'PROACTIVE_SIGNAL_DISMISSED',
    'PROACTIVE_SIGNAL_RESOLVED',
)

_DECISION_BY_EVENT = {
    'CHAT_ACCESS_DENIED': 'deny',
    'INTENT_UNSUPPORTED': 'deny',
    'TOOL_DENIED': 'deny',
    'RATE_LIMITED': 'deny',
    'AUTHORIZATION_DENIED': 'deny',
    'AI_PROVIDER_ERROR': 'error',
    'TOOL_ERROR': 'error',
    'INTERNAL_ERROR': 'error',
    # Phase 2A — action lifecycle defaults (additive).
    'ACTION_AUTHORIZATION_DENIED': 'deny',
    'ACTION_ERROR': 'error',
    'ACTION_INVALIDATED': 'deny',
    # Phase 3 — workflow lifecycle defaults (additive).
    'WORKFLOW_AUTH_DENIED': 'deny',
    'WORKFLOW_OPERATION_FAILED': 'deny',
    'WORKFLOW_CANCELLED': 'deny',
    'WORKFLOW_INVALIDATED': 'deny',
    # Phase 4 — approval lifecycle defaults (additive).
    'APPROVAL_AUTH_DENIED': 'deny',
    'APPROVAL_REJECTED': 'deny',
    'APPROVAL_CANCELLED': 'deny',
    'APPROVAL_EXPIRED': 'deny',
    'APPROVAL_DUPLICATE': 'deny',
    'APPROVAL_SUPERSEDED': 'deny',
    'APPROVAL_INVALIDATED': 'deny',
    'QUERY_FILTER_REJECTED': 'deny',
    'QUERY_CONTEXT_EXPLAINED': 'allow',
    'APPROVAL_EXECUTION_FAILED': 'error',
    'APPROVAL_VERIFICATION_FAILED': 'error',
    # Phase 5 — proactive lifecycle defaults (additive; detections and
    # dismissals are decision-relevant, explanations informational).
    'PROACTIVE_SIGNAL_DISMISSED': 'deny',
    'PROACTIVE_SIGNAL_SURFACED': 'allow',
    'PROACTIVE_SIGNAL_EXPLAINED': 'allow',
    'PROACTIVE_SIGNAL_RESOLVED': 'allow',
}


class EdicaiAIAuditEvent(models.Model):
    _name = 'edicai.ai.audit.event'
    _description = 'AI Audit Event'
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Event',
        required=True,
        index=True,
    )
    event_type = fields.Selection(
        selection=[(t, t.replace('_', ' ').title()) for t in EVENT_TYPES],
        string='Event Type',
        required=True,
        index=True,
    )
    decision = fields.Selection(
        selection=[
            ('allow', 'Allowed'),
            ('deny', 'Denied'),
            ('error', 'Error'),
        ],
        string='Decision',
        index=True,
    )
    reason_code = fields.Char(
        string='Reason Code',
        index=True,
        help='Machine reason: the error category or the gate that '
             'produced the decision (e.g. CONVERSATION_THROTTLE).',
    )
    tool_name = fields.Char(
        string='Tool',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Actor',
        index=True,
        ondelete='set null',
    )
    conversation_id = fields.Many2one(
        'edicai.ai.chat.session',
        string='Conversation',
        index=True,
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        index=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    detail = fields.Text(
        string='Detail',
        help='Short, non-sensitive technical detail '
             '(no payloads, no message content).',
    )
    metadata_json = fields.Json(
        string='Metadata',
        help='Small redacted structured metadata. Never prompts, '
             'message content or secrets.',
    )

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    @api.model
    def log_event(self, event_type, name=None, tool_name=None, user=None,
                  conversation=None, decision=None, reason_code=None,
                  detail=None, metadata=None, company=None):
        """Best-effort durable audit write.  NEVER raises.

        :param event_type: one of :data:`EVENT_TYPES`.
        :param tool_name: optional tool/provider identifier.
        :param user: actor record (defaults to env.user).
        :param conversation: ``edicai.ai.chat.session`` record or None.
        :param decision: 'allow' / 'deny' / 'error'.
        :param detail: short non-sensitive technical detail.
        :param metadata: already-redacted dict (no content, no secrets).
        :returns: True when persisted, False otherwise.
        """
        try:
            if event_type not in EVENT_TYPES:
                _logger.warning(
                    'AI audit: unknown event_type %r logged as '
                    'INTERNAL_ERROR.', event_type)
                event_type = 'INTERNAL_ERROR'
            actor = user or self.env.user
            vals = {
                'name': (name or '%s%s' % (
                    event_type,
                    (' — %s' % tool_name) if tool_name else '',
                ))[:200],
                'event_type': event_type,
                'decision': decision or _DECISION_BY_EVENT.get(event_type),
                'reason_code': (reason_code or None),
                'tool_name': tool_name or None,
                'user_id': actor.id,
                'conversation_id': conversation.id if conversation else None,
                'company_id': (company or self.env.company).id,
                'detail': (detail or None),
                'metadata_json': metadata or None,
            }
            self.sudo().create(vals)
            return True
        except Exception:
            _logger.exception(
                'AI audit: failed to persist %s event (ignored so a '
                'audit failure can never crash a request).', event_type)
            return False
