"""JSON-RPC endpoints consumed by the OWL chatbot component.

Phase 0 (Security Foundation) behaviour:

* DB-level owner isolation now also holds — record rules in
  ``security/edicai_ai_record_rules.xml`` restrict chat sessions and
  messages to their owner (controller checks remain as defence in
  depth).
* Durable AI audit events (``edicai.ai.audit.event``) are written for
  conversation lifecycle, throttling, provider calls/errors and
  access denials.  No message content is ever persisted in the audit.
* Provider/ORM exceptions are mapped through
  ``models/ai_error.py`` — users only ever receive deterministic,
  safe category messages; internals stay in the server log.
* A conservative per-user conversation throttle (configurable,
  default 30 turns / 5 min) runs BEFORE any write; it layers on top
  of the existing per-tool hourly rate limits, which are unchanged.
* The orchestrator feature flag (``edicai_ai.orchestrator_enabled``)
  exists in ``models/ai_config.py`` but is deliberately NOT wired
  here — the chat path still uses ``provider.chat(history)`` exactly
  as before Phase 0.

Manual-testing lab (additive, QA only):

* ``/edicai_ai/chat/provider_status`` — safe, non-sensitive active
  provider/model display for the chat header indicator.
* When ``edicai_ai.qa_test_mode`` is ON, every chat response gains a
  compact STRUCTURED ``diagnostics`` object for manual QA (provider,
  model, latency, status, tool, authorization outcome, mutation
  indicator, audit indication, proactive status).  Test mode NEVER
  weakens any gate and NEVER exposes prompts, reasoning or secrets.
* The AI_PROVIDER_CALL / AI_PROVIDER_ERROR audit events carry
  provider/model/latency metadata (no keys) — a lightweight usage
  log on top of the EXISTING audit mechanism.
"""

import logging
import time

from odoo import http
from odoo.http import request

from odoo.addons.edicai_ai.models.ai_error import (
    classify_exception,
    safe_error_payload,
)

_logger = logging.getLogger(__name__)

#: Audit identifier for the LLM provider call in this chat path.
PROVIDER_TOOL_NAME = 'edicai.ai.provider.chat'

#: Audit event types that indicate a business mutation actually
#: executed during a turn (only ever via confirm/approval flows).
_MUTATION_EVENTS = frozenset({
    'ACTION_EXECUTED',
    'WORKFLOW_EXECUTION_STARTED',
})


class EdicaiAIController(http.Controller):
    """JSON-RPC endpoints consumed by the OWL chatbot component."""

    # ------------------------------------------------------------------
    # Internal helpers (audit / safe errors)
    # ------------------------------------------------------------------

    def _audit(self, event_type, **kwargs):
        """Best-effort durable audit write (never raises)."""
        return request.env['edicai.ai.audit.event'].log_event(
            event_type, **kwargs)

    def _safe_error(self, error_code):
        """Deterministic, safe error payload for chat endpoints."""
        payload = safe_error_payload(error_code)
        return {'error': payload['error'], 'error_code': payload['error_code']}

    # ------------------------------------------------------------------
    # Manual-testing lab: provider indicator + turn diagnostics
    # ------------------------------------------------------------------

    def _qa_test_mode(self):
        try:
            return request.env[
                'edicai.ai.config'].is_qa_test_mode_enabled()
        except Exception:  # noqa: BLE001 — diagnostics must never break
            return False

    def _provider_display(self):
        """Safe display info for the chat UI (never an API key)."""
        try:
            return request.env[
                'edicai.ai.provider'].get_active_provider_display()
        except Exception:  # noqa: BLE001
            return {'provider': 'unknown', 'provider_label': 'Unknown',
                    'model': '', 'available': False}

    def _turn_diagnostics(self, started, result, session=None, error=False):
        """Structured turn diagnostics for MANUAL QA.

        Only safe, structured metadata: no prompts, no hidden model
        reasoning, no chain-of-thought, no secrets.  Computed from
        response shapes and the user's OWN audit trail.
        """
        provider_display = self._provider_display()
        diag = {
            'provider': provider_display.get('provider_label'),
            'model': provider_display.get('model'),
            'session_id': session.id if session is not None else None,
            'status': 'error' if error else 'unknown',
            'tool_name': '',
            'error_code': '',
            'authorization': 'UNKNOWN',
            'mutation': 'NO',
            'proactive_status': '',
            'audit_created': True,   # CHAT_MESSAGE_SENT is always written
            'request_at': time.strftime('%Y-%m-%d %H:%M:%S',
                                        time.localtime(started)),
            'response_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'latency_ms': int((time.time() - started) * 1000),
        }
        if isinstance(result, dict):
            diag.update({
                'status': result.get('status', diag['status']),
                'tool_name': result.get('tool_name') or '',
                'error_code': result.get('error_code') or '',
            })
            if result.get('error_code') == 'AUTHORIZATION_DENIED':
                diag['authorization'] = 'DENIED'
            elif result.get('status') == 'answered':
                diag['authorization'] = 'ALLOWED'
        try:
            audit = request.env['edicai.ai.audit.event']
            mutated = audit.search_count([
                ('create_date', '>=', time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(started))),
                ('event_type', 'in', list(_MUTATION_EVENTS)),
            ])
            diag['mutation'] = 'YES (confirmed action)' if mutated else 'NO'
        except Exception:  # noqa: BLE001 — audit read may be restricted
            diag['mutation'] = 'UNKNOWN'
        try:
            if request.env['edicai.ai.action.policy'].is_proactive_enabled():
                Insight = request.env['edicai.ai.proactive.insight']
                row = Insight.search([
                    ('user_id', '=', request.env.uid)], limit=1)
                diag['proactive_status'] = row.status if row else 'none'
        except Exception:  # noqa: BLE001
            pass
        return diag

    # ------------------------------------------------------------------
    # Provider status endpoint (safe, keyless)
    # ------------------------------------------------------------------

    @http.route('/edicai_ai/chat/provider_status', type='json', auth='user')
    def provider_status(self):
        """Safe, non-sensitive active-provider indicator data."""
        display = self._provider_display()
        return {
            'provider_label': display.get('provider_label', 'Unknown'),
            'model': display.get('model', ''),
            'available': bool(display.get('available')),
            'test_mode': self._qa_test_mode(),
        }

    # ------------------------------------------------------------------
    # Starter prompts (safe: static public labels, no secrets)
    # ------------------------------------------------------------------

    STARTER_PROMPTS = [
        {'label': 'Show my fee status', 'prompt': 'Show my fee status'},
        {'label': 'Check my attendance', 'prompt': 'Check my attendance'},
        {'label': 'Any timetable clashes?',
         'prompt': 'Are there any timetable clashes?'},
        {'label': 'List admission programs',
         'prompt': 'List admission programs'},
    ]

    @http.route('/edicai_ai/chat/prompts', type='json', auth='user')
    def chat_prompts(self):
        """Starter suggestions for the chatbot panel. Static public list —
        contains no user data or provider internals."""
        return [{'label': p['label'], 'prompt': p['prompt'],
                 'icon': 'fa-comment-o'} for p in self.STARTER_PROMPTS]

    # ------------------------------------------------------------------
    # Chat session endpoints
    # ------------------------------------------------------------------

    @http.route('/edicai_ai/chat/sessions', type='json', auth='user')
    def get_sessions(self, query=None, limit=200):
        """Return the chat sessions of the current user.

        ``query`` filters on the title (case-insensitive) so the
        workspace sidebar can search; ``limit`` is capped so a large
        history can never turn into an unbounded response.
        """
        try:
            limit = max(1, min(int(limit), 500))
        except (TypeError, ValueError):
            limit = 200
        domain = [('user_id', '=', request.env.user.id)]
        query = (query or '').strip()
        if query:
            domain += [('title', 'ilike', query)]
        sessions = request.env['edicai.ai.chat.session'].search(
            domain, order='write_date desc, id desc', limit=limit)
        return [
            {
                'id': s.id,
                'title': s.title,
                'write_date': s.write_date.isoformat() if s.write_date else '',
                'create_date': s.create_date.isoformat() if s.create_date else '',
                'message_count': len(s.message_ids),
            }
            for s in sessions
        ]

    @http.route('/edicai_ai/chat/rename_session', type='json', auth='user')
    def rename_session(self, session_id, title):
        """Rename a chat session (owner only, fail-closed).

        The session is fetched through the OWNER record rule, so a
        foreign session is simply not found — the endpoint never
        reveals whether it exists.
        """
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return self._safe_error('RECORD_NOT_FOUND')
        title = (title or '').strip()
        if not title:
            return self._safe_error('VALIDATION_FAILED')
        if len(title) > 120:
            title = title[:120]
        session = request.env['edicai.ai.chat.session'].search(
            [('id', '=', session_id)], limit=1)
        if not session:
            return self._safe_error('RECORD_NOT_FOUND')
        session.write({'title': title})
        self._audit('CHAT_SESSION_RENAMED', conversation=session)
        return {'success': True, 'id': session.id, 'title': session.title}

    @http.route('/edicai_ai/chat/new_session', type='json', auth='user')
    def new_session(self):
        """Create a new chat session and return its id."""
        session = request.env['edicai.ai.chat.session'].create({
            'user_id': request.env.user.id,
        })
        self._audit('CHAT_CREATED', conversation=session)
        return {'id': session.id, 'title': session.title}

    @http.route('/edicai_ai/chat/messages', type='json', auth='user')
    def get_messages(self, session_id):
        """Return all messages for a given session.

        Record rules guarantee only the owner's messages are ever
        returned, even for a foreign ``session_id``.
        """
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return self._safe_error('RECORD_NOT_FOUND')
        messages = request.env['edicai.ai.chat.message'].search([
            ('session_id', '=', session_id),
            ('session_id.user_id', '=', request.env.user.id),
        ], order='sequence, id')
        return [
            {
                'id': m.id,
                'role': m.role,
                'content': m.content,
                'source': m.source_tool or '',
            }
            for m in messages
        ]

    @http.route('/edicai_ai/chat/send', type='json', auth='user')
    def send_message(self, session_id, message):
        """Send a user message and get an AI reply.

        Persists both the user message and the assistant reply in the
        database, then returns the assistant reply.  Phase 0 adds:
        throttle → audit → sanitised error handling.  The LLM path is
        unchanged (``provider.chat``) — the orchestrator is Phase 1.
        Manual-testing lab: with test mode ON the response carries a
        safe structured ``diagnostics`` object for QA.
        """
        started = time.time()
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            self._audit('CHAT_ACCESS_DENIED', reason_code='RECORD_NOT_FOUND')
            return self._safe_error('RECORD_NOT_FOUND')
        env = request.env
        Session = env['edicai.ai.chat.session']
        Message = env['edicai.ai.chat.message']
        provider = env['edicai.ai.provider']
        provider_display = self._provider_display()

        # Ownership check via a RULE-CHECKED search: a foreign or
        # nonexistent id yields an empty recordset, so we reach the same
        # safe path — never a raw AccessError from a rule-checked read.
        # (Also enforced at DB level by the record rules.)
        session = Session.search([('id', '=', session_id)], limit=1)
        if not session:
            # Never distinguish "not found" from "not yours".
            self._audit(
                'CHAT_ACCESS_DENIED',
                reason_code='RECORD_NOT_FOUND_OR_NOT_OWNER')
            return self._safe_error('RECORD_NOT_FOUND')

        # Conversation throttle (Phase 0) — BEFORE any message write.
        allowed, throttle_info = env['edicai.ai.config'].\
            check_conversation_throttle()
        if not allowed:
            self._audit(
                'RATE_LIMITED',
                conversation=session,
                decision='deny',
                reason_code='CONVERSATION_THROTTLE',
                metadata={
                    'limit': throttle_info.get('turns'),
                    'window_minutes': throttle_info.get('window_minutes'),
                    'used': throttle_info.get('used'),
                })
            return self._safe_error('RATE_LIMITED')

        # Determine next sequence
        last_seq = 0
        if session.message_ids:
            last_seq = max(session.message_ids.mapped('sequence'))

        # Persist user message
        Message.create({
            'session_id': session_id,
            'role': 'user',
            'content': message,
            'sequence': last_seq + 10,
        })

        # Auto-title on first message
        if len(session.message_ids) <= 1:
            Session._auto_title(session_id, message)

        # Audit: a turn happened.  Content is NEVER stored — only its
        # letter count.
        self._audit(
            'CHAT_MESSAGE_SENT',
            conversation=session,
            metadata={'content_chars': len(str(message or ''))},
        )

        # Phase 1A: the orchestrator branch is strictly behind the
        # ``edicai_ai.orchestrator_enabled`` flag.  With the flag OFF the
        # legacy provider chat path below behaves EXACTLY as in Phase 0.
        if env['edicai.ai.config'].is_orchestrator_enabled():
            return self._send_with_orchestrator(
                env, session, message, last_seq, started, )

        # Build conversation history for the API
        history = [
            {'role': m.role, 'content': m.content}
            for m in session.message_ids.sorted('sequence')
        ]

        provider_meta = {
            'provider': provider_display.get('provider'),
            'model': provider_display.get('model'),
        }
        self._audit(
            'AI_PROVIDER_CALL',
            tool_name=PROVIDER_TOOL_NAME,
            conversation=session,
            metadata=provider_meta,
        )
        try:
            reply = provider.chat(history)
        except Exception as exc:
            _logger.exception('Edicai AI chat error')
            error_code, safe_text = classify_exception(exc)
            # Detail stays server-side AND sanitised: exception CLASS
            # only — exception messages can embed payloads.
            self._audit(
                'AI_PROVIDER_ERROR',
                tool_name=PROVIDER_TOOL_NAME,
                conversation=session,
                decision='error',
                reason_code=error_code,
                detail=type(exc).__name__,
                metadata=dict(provider_meta,
                              latency_ms=int((time.time() - started)
                                             * 1000)),
            )
            # Same response shape as before; safe text only.
            response = {
                'reply': '⚠️ %s' % safe_text,
                'error_code': error_code,
                'session_title': session.title,
            }
            if self._qa_test_mode():
                response['diagnostics'] = self._turn_diagnostics(
                    started, response, session=session, error=True)
            return response

        # Persist assistant reply
        Message.create({
            'session_id': session_id,
            'role': 'assistant',
            'content': reply,
            'sequence': last_seq + 20,
        })

        response = {
            'reply': reply,
            'session_title': session.title,
        }
        if self._qa_test_mode():
            response['diagnostics'] = self._turn_diagnostics(
                started, {'status': 'answered',
                          'tool_name': PROVIDER_TOOL_NAME},
                session=session)
        return response

    # ------------------------------------------------------------------
    # Phase 1A — grounded read-only orchestrator path (flag-protected)
    # ------------------------------------------------------------------

    def _send_with_orchestrator(self, env, session, message, last_seq,
                                started=None):
        """Handle one turn through the grounded read-only orchestrator.

        The orchestrator NEVER calls the provider; intent detection is
        deterministic and replies are composed from tool results by
        fixed templates.  All its individual decision outcomes are
        audited by the orchestrator itself; this wrapper only handles
        unexpected infrastructure failures and message persistence.

        Response shape is unchanged (``reply``/``session_title``) and
        gains the additive ``source`` citation label for the chat UI.
        """
        Message = env['edicai.ai.chat.message']
        try:
            result = env['edicai.ai.orchestrator'].answer_turn(
                message, session=session)
        except Exception as exc:  # noqa: BLE001 — sanitised below
            _logger.exception('Edicai AI orchestrator failure')
            self._audit(
                'INTERNAL_ERROR',
                conversation=session,
                decision='error',
                reason_code='ORCHESTRATOR_FAILURE',
                detail=type(exc).__name__,
            )
            payload = safe_error_payload('INTERNAL_ERROR')
            response = {
                'reply': '⚠️ %s' % payload['error'],
                'error_code': payload['error_code'],
                'session_title': session.title,
                'source': '',
            }
            if self._qa_test_mode():
                response['diagnostics'] = self._turn_diagnostics(
                    started or time.time(), response, session=session,
                    error=True)
            return response

        # Persist the assistant reply with its citation reference
        # (additive ``source_tool`` column; never set on user messages).
        Message.create({
            'session_id': session.id,
            'role': 'assistant',
            'content': result['reply'],
            'sequence': last_seq + 20,
            'source_tool': result.get('source_label') or None,
        })

        if result.get('error_code'):
            # SAFE taxonomy errors keep the historical error-payload
            # shape so the frontend can treat them uniformly.
            response = {
                'reply': result['reply'],
                'error_code': result['error_code'],
                'session_title': session.title,
                'source': '',
            }
        else:
            response = {
                'reply': result['reply'],
                'session_title': session.title,
                'source': result.get('source_label') or '',
            }
        response['status'] = result.get('status') or 'answered'
        response['tool_name'] = result.get('tool_name') or ''
        if self._qa_test_mode():
            response['diagnostics'] = self._turn_diagnostics(
                started or time.time(), response, session=session)
        return response

    @http.route('/edicai_ai/chat/delete_session', type='json', auth='user')
    def delete_session(self, session_id):
        """Archive (soft-delete) a chat session."""
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return self._safe_error('RECORD_NOT_FOUND')
        # Rule-checked search: foreign sessions are simply not found.
        session = request.env['edicai.ai.chat.session'].search(
            [('id', '=', session_id)], limit=1)
        if session:
            session.write({'active': False})
            self._audit('CHAT_SESSION_DELETED', conversation=session)
        return {'success': True}
