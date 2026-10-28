"""Student Portal AI Copilot — scoped JSON endpoint.

Route: POST /my/edicai/student/copilot/ask (type='json', auth='user').

Security:
* Portal-session check via the existing
  ``EdicaiStudentPortal._get_current_student`` helper. Any failure
  returns 403 JSON — never a redirect (redirects break JSON clients
  and can loop).
* Forced own-record scope: ``student_id`` + ``company_id`` are taken
  from the server-side session only. Client-supplied identity keys
  (``student_id``, ``faculty_id``, ``guardian_id``, ``company_id``,
  ``student_ids``, ``uid``) are dropped and logged, never trusted.
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

from .portal_student_controller import EdicaiStudentPortal

_logger = logging.getLogger(__name__)

#: Client-supplied identity keys. Always dropped; scope comes from
#: the portal session, never from the request body.
_DROPPED_KEYS = (
    'student_id', 'student_ids', 'faculty_id', 'guardian_id',
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
    (('payment method', 'upi', 'how paid', 'mode of pay'), 'ask_data.payment_methods'),
    (('fee', 'invoice', 'due', 'outstanding', 'overdue', 'billed', 'receipt'), 'ask_data.fee_collection'),
    (('scholarship', 'net revenue', 'snapshot', 'trend'), 'ask_data.finance_snapshot'),
    (('kpi', 'efficiency', 'collection rate'), 'ask_data.finance_kpi'),
    (('grade', 'mark', 'pass rate', 'fail', 'gpa distribution'), 'ask_data.grades'),
    (('semester result', 'sgpa', 'semester gpa', 'promotion'), 'ask_data.semester_results'),
    (('attend', 'shortage', 'absent'), 'ask_data.attendance'),
    (('enrol', 'admission intake', 'batch', 'cohort', 'cgpa'), 'ask_data.enrollment'),
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


class EdicaiStudentCopilot(http.Controller):
    """Scoped student copilot (own records only)."""

    def _forbidden(self, message):
        return request.make_json_response(
            {'error': message}, status=403,
        )

    @http.route(
        '/my/edicai/student/copilot/ask',
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
        student = EdicaiStudentPortal()._get_current_student()
        if not student:
            return self._forbidden(
                'No student record found for your account.',
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
                'Student copilot: ignored client scope keys %s '
                'for user %s.', dropped, request.env.user.login,
            )
        try:
            capped = max(1, min(int(limit or 50), 100))
        except (TypeError, ValueError):
            capped = 50

        # --- 3. Forced scope (server-side identity only) ---
        tool_name = _resolve_tool(question, intent)
        scoped_params = {
            'question': question,
            'limit': capped,
            'student_id': student.id,
            'student_ids': [student.id],
            'company_id': student.company_id.id
            if getattr(student, 'company_id', False)
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
                'Student copilot denied (tool=%s user=%s): %s',
                tool_name, request.env.user.login, msg,
            )
            return request.make_json_response(
                {'error': msg}, status=status,
            )
        except Exception as exc:  # never leak internals
            _logger.exception('Student copilot failed.')
            return request.make_json_response(
                {'error': 'Copilot request failed.'}, status=500,
            )

        # --- 5. Shape the portal answer ---
        if not isinstance(result, dict):
            return {'answer': str(result), 'sources': [tool_name]}
        label = result.get('label') or result.get('intent') or tool_name
        count = result.get('count', 0)
        answer = '%s: %s row(s) for your own record.' % (label, count)
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
