"""Guardian Portal AI Copilot — scoped JSON endpoint.

Route: POST /my/edicai/guardian/copilot/ask (type='json', auth='user').

Security:
* Portal-session check via the existing
  ``EdicaiGuardianPortal._get_current_guardian`` helper. Any failure
  returns 403 JSON — never a redirect (redirects break JSON clients
  and can loop).
* Forced own-record scope: ``guardian_id`` + active-ward
  ``student_ids`` + ``company_id`` are taken from the server-side
  session only (wards resolved via the existing
  ``_get_ward_relations`` helper, active relationships only).
  Client-supplied identity keys (``guardian_id``, ``student_id``,
  ``student_ids``, ``faculty_id``, ``company_id``, ``uid``) are
  dropped and logged, never trusted. Per-ward permission flags
  (``can_view_academic_records`` / ``can_view_fee_records``) are
  forwarded in params for record-level tools that honor them.
* Execution goes through ``edicai.ai.tool.registry.execute_tool``
  (allow-list + requester-company forcing + audit + per-tool
  per-user hourly rate limit). No sudo, no raw SQL, no cursor use
  in this file — reads run with the portal user's own rights so
  record rules / ACLs stay effective (same pattern as
  ``edicai.fee.copilot`` scope helpers in
  ``edicai_fees/models/ai_tools_fees.py``).
"""

import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from .guardian_portal import EdicaiGuardianPortal

_logger = logging.getLogger(__name__)

#: Client-supplied identity keys. Always dropped; scope comes from
#: the portal session, never from the request body.
_DROPPED_KEYS = (
    'guardian_id', 'student_id', 'student_ids', 'faculty_id',
    'company_id', 'uid', 'user_id', 'partner_id',
)

#: Server-side intent -> registered ask-data tool. The client's
#: ``intent``/``question`` only selects among these names; arbitrary
#: tool names from the client are never executed.
_INTENT_TOOLS = {
    'fee_collection': 'ask_data.fee_collection',
    'payment_methods': 'ask_data.payment_methods',
    'finance_snapshot': 'ask_data.finance_snapshot',
    'finance_kpi': 'ask_data.finance_kpi',
    'grades': 'ask_data.grades',
    'semester_results': 'ask_data.semester_results',
    'attendance': 'ask_data.attendance',
    'enrollment': 'ask_data.enrollment',
}
_DEFAULT_TOOL = 'ask_data.fee_collection'

#: Keyword routing for free-text questions (server-side only).
_KEYWORD_TOOLS = (
    (('fee', 'invoice', 'due', 'outstanding', 'overdue', 'billed', 'receipt'), 'ask_data.fee_collection'),
    (('payment method', 'upi', 'how paid', 'mode of pay'), 'ask_data.payment_methods'),
    (('scholarship', 'net revenue', 'snapshot', 'trend'), 'ask_data.finance_snapshot'),
    (('grade', 'mark', 'pass rate', 'fail', 'result'), 'ask_data.grades'),
    (('semester result', 'sgpa', 'semester gpa', 'promotion'), 'ask_data.semester_results'),
    (('attend', 'shortage', 'absent'), 'ask_data.attendance'),
)


#: Maximum accepted question length (DoS guard: over-long prompts
#: inflate LLM/tool cost and can wedge JSON parsing).
_MAX_QUESTION_LEN = 2000


def _resolve_tool(question, intent):
    """Pick a registered tool name server-side (never from client)."""
    if isinstance(intent, str) and intent in _INTENT_TOOLS:
        return _INTENT_TOOLS[intent]
    text = (question or '').lower()
    for keywords, tool in _KEYWORD_TOOLS:
        if any(kw in text for kw in keywords):
            return tool
    return _DEFAULT_TOOL


class EdicaiGuardianCopilot(http.Controller):
    """Scoped guardian copilot (own wards only)."""

    def _forbidden(self, message):
        return request.make_json_response(
            {'error': message}, status=403,
        )

    @http.route(
        '/my/edicai/guardian/copilot/ask',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def copilot_ask(self, question=None, intent=None, limit=None,
                    **kwargs):
        # --- 1. Portal-session check (no redirects, JSON 403) ---
        if request.env.user._is_public():
            return self._forbidden(
                'Authentication required.',
            )
        portal = EdicaiGuardianPortal()
        guardian = portal._get_current_guardian()
        if not guardian:
            return self._forbidden(
                'No guardian record found for your account.',
            )

        # --- 2. Validate input ---
        question = (question or '').strip()[:_MAX_QUESTION_LEN]
        if not isinstance(intent, str):
            intent = None
        if not question and intent not in _INTENT_TOOLS:
            return request.make_json_response(
                {'error': 'Provide a question.'}, status=400,
            )
        dropped = [k for k in kwargs if k in _DROPPED_KEYS]
        if dropped:
            _logger.warning(
                'Guardian copilot: ignored client scope keys %s '
                'for user %s.', dropped, request.env.user.login,
            )
        try:
            capped = max(1, min(int(limit or 50), 100))
        except (TypeError, ValueError):
            capped = 50

        # --- 3. Forced scope (server-side identity only) ---
        relations = portal._get_ward_relations(guardian)
        ward_ids = sorted({rel.student_id.id for rel in relations
                           if rel.student_id})
        ward_permissions = {
            str(rel.student_id.id): {
                'academic': bool(rel.can_view_academic_records),
                'fees': bool(rel.can_view_fee_records),
            }
            for rel in relations if rel.student_id
        }
        tool_name = _resolve_tool(question, intent)
        scoped_params = {
            'question': question,
            'limit': capped,
            'guardian_id': guardian.id,
            'student_ids': ward_ids,
            'ward_permissions': ward_permissions,
            'company_id': guardian.company_id.id
            if getattr(guardian, 'company_id', False)
            else request.env.company.id,
        }

        # --- 4. Execute via the central registry (rate-limited) ---
        if 'edicai.ai.tool.registry' not in request.env:
            return request.make_json_response(
                {'error': 'AI copilot is not installed.'},
                status=501,
            )
        registry = request.env['edicai.ai.tool.registry']
        try:
            result = registry.execute_tool(tool_name, scoped_params)
        except (AccessError, UserError) as exc:
            msg = str(exc)
            status = 429 if 'rate limit' in msg.lower() else 403
            _logger.info(
                'Guardian copilot denied (tool=%s user=%s): %s',
                tool_name, request.env.user.login, msg,
            )
            return request.make_json_response(
                {'error': msg}, status=status,
            )
        except Exception as exc:  # never leak internals
            _logger.exception('Guardian copilot failed.')
            return request.make_json_response(
                {'error': 'Copilot request failed.'}, status=500,
            )

        # --- 5. Shape the portal answer ---
        if not isinstance(result, dict):
            return {'answer': str(result), 'sources': [tool_name]}
        label = result.get('label') or result.get('intent') or tool_name
        count = result.get('count', 0)
        answer = '%s: %s row(s) for your wards.' % (label, count)
        return {
            'answer': answer,
            'sources': [{
                'tool': tool_name,
                'label': label,
            }],
            'chart': result.get('chart') or False,
            'rows': result.get('rows') or [],
            'count': count,
            'columns': result.get('columns') or [],
        }
