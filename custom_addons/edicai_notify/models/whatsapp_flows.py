"""
Edicai WhatsApp Interactive Flows.

Pure flow builders returning Meta WhatsApp Business Cloud API
payloads, plus thin ``edicai.whatsapp.flows`` helpers that hand
delivery to the notify engine (``edicai.notification.engine``).

Rule: nothing in this module performs HTTP itself. Builders return
plain dicts shaped for ``POST {api_url}/{phone_number_id}/messages``;
the ``send_*`` / ``request_*`` model methods deliver the *text* part
through ``Engine._send_whatsapp`` and record the interactive payload
in the notification log. A future engine patch can POST ``payload``
directly to enable native buttons without touching callers.

Flows
-----
1. fee_reminder      — amount + due date + pay-link CTA button.
2. attendance_alert  — attendance % + sessions + view CTA button.
3. result_published  — letter grade + view CTA button.
4. leave_decision    — approve / reject for guardian/faculty
                      approvers via signed magic-link URLs.

Meta API limitation: an ``interactive`` message carries at most ONE
``cta_url`` button. The leave flow therefore ships the primary action
(Approve) as the CTA button and embeds the secondary (Reject) URL in
the body text. ``build_leave_reject_followup_payload`` builds an
optional second message with Reject as the CTA button.

Signed approval tokens
----------------------
``v1.<leave_id>.<action>.<kind>.<ts>.<sig>`` where ``sig`` is
HMAC-SHA256 over the first five segments with a per-database secret
stored in ``ir.config_parameter`` (``edicai_notify.whatsapp_signing_secret``,
auto-generated on first use). Tokens expire 48h after issue and are
verified with :func:`hmac.compare_digest`. Replay is neutralised by
the leave state machine: only ``submitted`` requests are actionable,
so a reused token resolves to an already-decided request.
"""

import hashlib
import hmac
import logging
import secrets
import time

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# -----------------------------------------------------------
# Token constants (module level so they are unit-testable
# without an Odoo environment).
# -----------------------------------------------------------

TOKEN_VERSION = 'v1'
TOKEN_TTL_SECONDS = 48 * 3600  # 48h expiry for approval tokens
APPROVAL_ACTIONS = ('approve', 'reject')
APPROVER_KINDS = ('guardian', 'faculty')
_SIGNING_SECRET_PARAM = 'edicai_notify.whatsapp_signing_secret'

# Meta WhatsApp template names bound to each flow. The matching
# ``edicai.notification.template`` records live in
# data/whatsapp_flow_templates.xml; the template *body* carries the
# human text (with {variables}) and the builders below attach the
# button definitions, because the template model has no button
# schema of its own.
FLOW_META_TEMPLATE_NAMES = {
    'fee_reminder': 'edicai_fee_reminder_pay_cta',
    'attendance_alert': 'edicai_attendance_alert_view_cta',
    'result_published': 'edicai_result_published_view_cta',
    'leave_decision': 'edicai_leave_approval_dual_cta',
}


# -----------------------------------------------------------
# Pure helpers (no self.env — safe to import in plain tests).
# -----------------------------------------------------------

def _clean_mobile(to_mobile):
    """Normalise a recipient number the same way the engine does."""
    clean = ''.join(
        c for c in (to_mobile or '') if c.isdigit() or c == '+'
    )
    return clean[1:] if clean.startswith('+') else clean


def _cta_url_payload(to_mobile, body_text, button_text, url):
    """Single CTA-URL interactive payload (Meta ``interactive``)."""
    return {
        'messaging_product': 'whatsapp',
        'to': _clean_mobile(to_mobile),
        'type': 'interactive',
        'interactive': {
            'type': 'cta_url',
            'body': {'text': body_text},
            'action': {
                'name': 'cta_url',
                'parameters': {
                    'display_text': button_text,
                    'url': url,
                },
            },
        },
    }


def build_fee_reminder_payload(to_mobile, body_text, pay_url,
                               button_text='Pay Now'):
    """Fee reminder: amount + due date text with a pay-link button."""
    return _cta_url_payload(to_mobile, body_text, button_text, pay_url)


def build_attendance_alert_payload(to_mobile, body_text, view_url,
                                   button_text='View Attendance'):
    """Attendance alert: % + sessions text with a view button."""
    return _cta_url_payload(to_mobile, body_text, button_text, view_url)


def build_result_published_payload(to_mobile, body_text, view_url,
                                   button_text='View Result'):
    """Result published: letter/grade text with a view button."""
    return _cta_url_payload(to_mobile, body_text, button_text, view_url)


def build_leave_decision_payload(to_mobile, body_text, approve_url,
                                 reject_url, approve_text='Approve Leave'):
    """Leave approval request for guardian/faculty approvers.

    Meta allows only one ``cta_url`` button per message, so Approve
    rides as the CTA button while the Reject magic link stays in the
    body text (callers must append it). Use
    ``build_leave_reject_followup_payload`` for a Reject-first
    variant.
    """
    payload = _cta_url_payload(
        to_mobile, body_text, approve_text, approve_url,
    )
    payload['reject_url'] = reject_url
    return payload


def build_leave_reject_followup_payload(to_mobile, body_text, reject_url,
                                        reject_text='Reject Leave'):
    """Optional second message with Reject as the CTA button."""
    return _cta_url_payload(to_mobile, body_text, reject_text, reject_url)


def pack_approval_token(secret, leave_id, action, kind, ts=None):
    """Create a signed approval token string.

    :param secret: HMAC signing secret (never empty).
    :param leave_id: ``edicai.student.leave.request`` id (positive int).
    :param action: ``approve`` or ``reject``.
    :param kind: ``guardian`` or ``faculty``.
    :param ts: unix timestamp (defaults to now); injectable for tests.
    """
    if not secret:
        raise ValueError('Signing secret is required.')
    leave_id = int(leave_id)
    if leave_id <= 0:
        raise ValueError('leave_id must be a positive integer.')
    if action not in APPROVAL_ACTIONS:
        raise ValueError('Unknown approval action: %r.' % (action,))
    if kind not in APPROVER_KINDS:
        raise ValueError('Unknown approver kind: %r.' % (kind,))
    stamp = str(int(ts if ts is not None else time.time()))
    core = '.'.join(
        [TOKEN_VERSION, str(leave_id), action, kind, stamp],
    )
    sig = hmac.new(
        secret.encode('utf-8'), core.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return '%s.%s' % (core, sig)


def verify_approval_token(secret, token, now_ts=None,
                           ttl=TOKEN_TTL_SECONDS):
    """Verify a signed approval token.

    :return: ``(True, info_dict)`` or ``(False, error_code)`` where
        info has ``leave_id``, ``action``, ``kind``, ``ts``.
        Comparison uses :func:`hmac.compare_digest`.
    """
    if not secret or not token:
        return False, 'missing_token'
    parts = str(token or '').strip().split('.')
    if len(parts) != 6 or parts[0] != TOKEN_VERSION:
        return False, 'bad_format'
    _ver, leave_s, action, kind, stamp_s, sig = parts
    try:
        leave_id = int(leave_s)
        stamp = int(stamp_s)
    except (TypeError, ValueError):
        return False, 'bad_format'
    if leave_id <= 0:
        return False, 'bad_format'
    if action not in APPROVAL_ACTIONS:
        return False, 'bad_action'
    if kind not in APPROVER_KINDS:
        return False, 'bad_kind'
    core = '.'.join([TOKEN_VERSION, str(leave_id), action, kind, str(stamp)])
    expected = hmac.new(
        secret.encode('utf-8'), core.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, 'bad_signature'
    now = int(now_ts if now_ts is not None else time.time())
    if stamp > now + 300:
        return False, 'token_from_future'
    if now - stamp > int(ttl):
        return False, 'token_expired'
    return True, {
        'leave_id': leave_id,
        'action': action,
        'kind': kind,
        'ts': stamp,
    }


class EdicaiWhatsappFlows(models.AbstractModel):
    """Flow builders + engine handoff for WhatsApp interactivity."""

    _name = 'edicai.whatsapp.flows'
    _description = 'WhatsApp Interactive Flow Builders'

    # --------------------------------------------------
    # Signing secret + token API (env-bound wrappers).
    # --------------------------------------------------

    @api.model
    def _signing_secret(self):
        """Per-database HMAC secret, auto-generated once via sudo."""
        params = self.env['ir.config_parameter'].sudo()
        secret = (params.get_param(_SIGNING_SECRET_PARAM) or '').strip()
        if not secret:
            secret = secrets.token_urlsafe(48)
            params.set_param(_SIGNING_SECRET_PARAM, secret)
            _logger.info(
                'Generated new WhatsApp signing secret.',
            )
        return secret

    @api.model
    def sign_leave_token(self, leave_request, action,
                         approver_kind='guardian'):
        """Mint a 48h approval token for an existing leave request."""
        return pack_approval_token(
            self._signing_secret(),
            int(leave_request.id if hasattr(
                leave_request, 'id') else leave_request),
            action,
            approver_kind,
        )

    @api.model
    def verify_leave_token(self, token):
        """Verify a token; returns ``(ok, info_or_error)``."""
        return verify_approval_token(self._signing_secret(), token)

    @api.model
    def _base_url(self):
        return (
            self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url',
            ) or ''
        ).rstrip('/')

    @api.model
    def approval_url(self, leave_id, action, approver_kind,
                     token=None):
        """Public callback URL carrying the signed action token."""
        token = token or pack_approval_token(
            self._signing_secret(), int(leave_id), action,
            approver_kind,
        )
        return '%s/notify/whatsapp/leave/%s/%s?token=%s' % (
            self._base_url(), int(leave_id), action, token,
        )

    # --------------------------------------------------
    # Engine handoff (never requests.post here).
    # --------------------------------------------------

    @api.model
    def _hand_to_engine(self, to_mobile, company_id, text_body,
                        trigger_event, template_id=None,
                        student_id=None, guardian_id=None,
                        recipient_type=None, extra_log_body=''):
        """Send text via the engine; stash the interactive payload
        (with button URLs) in the notification log for audit."""
        engine = self.env['edicai.notification.engine']
        success, msg_id = engine._send_whatsapp(
            to_mobile=to_mobile,
            message_body=text_body,
            company_id=company_id,
        )
        engine._log_notification(
            channel='whatsapp',
            trigger_event=trigger_event,
            company_id=company_id,
            status='sent' if success else 'failed',
            recipient_mobile=to_mobile,
            message_body=(text_body + extra_log_body)[:2000],
            student_id=student_id,
            guardian_id=guardian_id,
            template_id=template_id,
            whatsapp_message_id=msg_id if success else None,
            error_message=None if success else str(msg_id),
            recipient_type=recipient_type,
        )
        return success, msg_id

    @api.model
    def _render_flow_text(self, trigger_event, company_id, variables,
                          fallback_body):
        """Render the flow template body; fall back to formatted text
        when no template row exists for this company yet."""
        try:
            template = self.env[
                'edicai.notification.engine'
            ]._get_template(trigger_event, 'whatsapp', company_id)
        except Exception:
            template = False
        if template:
            try:
                rendered = template.render_template(dict(variables))
                if rendered.get('whatsapp_body'):
                    return rendered['whatsapp_body'], template.id
            except Exception as e:
                _logger.warning(
                    'WhatsApp flow template render failed: %s',
                    str(e),
                )
        try:
            return fallback_body.format(**variables), None
        except KeyError:
            return fallback_body, None

    # --------------------------------------------------
    # Flow 1: fee reminder (amount + due + pay-link button).
    # --------------------------------------------------

    @api.model
    def send_fee_reminder(self, invoice, to_mobile=None):
        """Build + hand a fee-reminder flow to the engine.

        Pay-link resolution: ``edicai.payment`` helper
        ``get_online_payment_portal_url()`` when the module is
        installed (guarded by ``hasattr`` — ``edicai_notify`` does
        not depend on it), else the student portal URL.
        """
        student = invoice.student_id
        company_id = invoice.company_id.id or self.env.company.id
        portal_url = '%s/my/edicai/student' % self._base_url()
        pay_url = False
        try:
            if hasattr(invoice, 'get_online_payment_portal_url'):
                pay_url = invoice.get_online_payment_portal_url()
        except Exception as e:
            _logger.warning(
                'Pay-link lookup failed for invoice %s: %s',
                invoice.id, str(e),
            )
        pay_url = pay_url or portal_url
        variables = {
            'student_name': student.display_name,
            'amount': str(round(invoice.amount_outstanding or 0.0, 2)),
            'due_date': str(invoice.due_date or ''),
            'invoice_number': invoice.invoice_number or '',
            'portal_url': portal_url,
            'pay_url': pay_url,
            'institution_name': invoice.company_id.name or '',
        }
        fallback = (
            'Fee Reminder — {institution_name}\n\n'
            'Dear {student_name},\n\n'
            'Your fee payment of Rs.{amount} is due on {due_date}.\n'
            'Invoice: {invoice_number}\n\n'
            'Pay online: {pay_url}'
        )
        text, template_id = self._render_flow_text(
            'fee_overdue', company_id, variables, fallback,
        )
        to_mobile = to_mobile or student.mobile
        payload = build_fee_reminder_payload(to_mobile, text, pay_url)
        ok, msg_id = self._hand_to_engine(
            to_mobile, company_id, text, 'fee_overdue',
            template_id=template_id, student_id=student.id,
            recipient_type='student',
            extra_log_body='\n[button: Pay Now -> %s]' % pay_url,
        )
        return {
            'ok': ok, 'message_id': msg_id if ok else None,
            'error': None if ok else str(msg_id),
            'to': _clean_mobile(to_mobile), 'payload': payload,
            'pay_url': pay_url,
        }

    # --------------------------------------------------
    # Flow 2: attendance alert (pct + sessions + view btn).
    # --------------------------------------------------

    @api.model
    def send_attendance_alert(self, record, to_mobile=None,
                              sessions_attended='', total_sessions='',
                              view_path='/my/edicai/student'):
        """Build + hand an attendance-shortage flow to the engine."""
        student = record.student_id
        company_id = (
            record.company_id.id if getattr(
                record, 'company_id', False)
            else (student.company_id.id if student else
                  self.env.company.id)
        )
        sessions_attended = sessions_attended or getattr(
            record, 'sessions_attended', '') or ''
        total_sessions = total_sessions or getattr(
            record, 'total_sessions', '') or ''
        sessions_summary = (
            '%s/%s sessions attended' % (
                sessions_attended, total_sessions)
            if sessions_attended or total_sessions else ''
        )
        view_url = '%s%s' % (self._base_url(), view_path)
        try:
            pct = round(float(
                record.cumulative_attendance_percentage or 0.0), 1)
        except (TypeError, ValueError):
            pct = 0.0
        variables = {
            'student_name': student.display_name if student else '',
            'course_name': (
                record.course_id.display_name
                if getattr(record, 'course_id', False) else ''
            ),
            'attendance': str(pct),
            'minimum_required': '75',
            'sessions_attended': str(sessions_attended),
            'total_sessions': str(total_sessions),
            'sessions_summary': sessions_summary,
            'portal_url': view_url,
            'institution_name': self.env.company.name or '',
        }
        fallback = (
            'Attendance Alert — {institution_name}\n\n'
            'Dear {student_name},\n\n'
            'Your attendance in {course_name} is {attendance}% '
            '(minimum: {minimum_required}%).\n'
            '{sessions_summary}\n\n'
            'View details: {portal_url}'
        )
        text, template_id = self._render_flow_text(
            'attendance_warning', company_id, variables, fallback,
        )
        to_mobile = to_mobile or (student.mobile if student else None)
        payload = build_attendance_alert_payload(
            to_mobile, text, view_url,
        )
        ok, msg_id = self._hand_to_engine(
            to_mobile, company_id, text, 'attendance_warning',
            template_id=template_id,
            student_id=student.id if student else None,
            recipient_type='student',
            extra_log_body='\n[button: View Attendance -> %s]'
            % view_url,
        )
        return {
            'ok': ok, 'message_id': msg_id if ok else None,
            'error': None if ok else str(msg_id),
            'to': _clean_mobile(to_mobile), 'payload': payload,
        }

    # --------------------------------------------------
    # Flow 3: result published (letter/grade + view btn).
    # --------------------------------------------------

    @api.model
    def send_result_published(self, grade_entry, to_mobile=None,
                              view_path='/my/edicai/student'):
        """Build + hand a result-published flow to the engine."""
        student = grade_entry.student_id
        company_id = (
            grade_entry.company_id.id if getattr(
                grade_entry, 'company_id', False)
            else (student.company_id.id if student else
                  self.env.company.id)
        )
        view_url = '%s%s' % (self._base_url(), view_path)
        variables = {
            'student_name': student.display_name if student else '',
            'course_name': (
                grade_entry.course_id.display_name
                if getattr(grade_entry, 'course_id', False) else ''
            ),
            'grade': grade_entry.letter_grade or '',
            'portal_url': view_url,
            'institution_name': self.env.company.name or '',
        }
        fallback = (
            'Results Published — {institution_name}\n\n'
            'Dear {student_name},\n\n'
            'Results for {course_name} are published. '
            'Your grade: {grade}\n\n'
            'View details: {portal_url}'
        )
        text, template_id = self._render_flow_text(
            'result_published', company_id, variables, fallback,
        )
        to_mobile = to_mobile or (student.mobile if student else None)
        payload = build_result_published_payload(
            to_mobile, text, view_url,
        )
        ok, msg_id = self._hand_to_engine(
            to_mobile, company_id, text, 'result_published',
            template_id=template_id,
            student_id=student.id if student else None,
            recipient_type='student',
            extra_log_body='\n[button: View Result -> %s]' % view_url,
        )
        return {
            'ok': ok, 'message_id': msg_id if ok else None,
            'error': None if ok else str(msg_id),
            'to': _clean_mobile(to_mobile), 'payload': payload,
        }

    # --------------------------------------------------
    # Flow 4: leave decision (approve/reject URLs for the
    # guardian/faculty approver; maps back to the existing
    # action_approve / action_reject on
    # edicai.student.leave.request).
    # --------------------------------------------------

    @api.model
    def request_leave_approval(self, leave_request, to_mobile=None,
                               approver_kind='guardian'):
        """Send the approver a WhatsApp approval request with signed
        Approve/Reject magic links (48h expiry).

        The callback route verifies the token and calls the existing
        ``action_approve`` / ``action_reject`` — no new state machine.
        Only ``submitted`` requests produce links.
        """
        if approver_kind not in APPROVER_KINDS:
            raise ValueError(
                'approver_kind must be guardian or faculty.',
            )
        if leave_request.state != 'submitted':
            return {
                'ok': False,
                'error': 'leave_not_submitted',
                'to': None,
                'payload': None,
            }
        company_id = (
            leave_request.company_id.id or self.env.company.id
        )
        if not to_mobile and approver_kind == 'guardian':
            guardian = leave_request.guardian_id
            to_mobile = (
                (guardian.whatsapp_number or guardian.mobile)
                if guardian else None
            )
        approve_token = self.sign_leave_token(
            leave_request, 'approve', approver_kind,
        )
        reject_token = self.sign_leave_token(
            leave_request, 'reject', approver_kind,
        )
        approve_url = self.approval_url(
            leave_request.id, 'approve', approver_kind,
            token=approve_token,
        )
        reject_url = self.approval_url(
            leave_request.id, 'reject', approver_kind,
            token=reject_token,
        )
        student = leave_request.student_id
        variables = {
            'approver_name': '',
            'student_name': (
                student.display_name if student else ''
            ),
            'request_reference': leave_request.name or '',
            'date_from': str(leave_request.date_from or ''),
            'date_to': str(leave_request.date_to or ''),
            'reason': leave_request.reason or '',
            'approve_url': approve_url,
            'reject_url': reject_url,
            'institution_name': leave_request.company_id.name or '',
        }
        fallback = (
            'Leave Approval Request — {institution_name}\n\n'
            'Student: {student_name}\n'
            'Request: {request_reference}\n'
            'Dates: {date_from} to {date_to}\n'
            'Reason: {reason}\n\n'
            'Tap to APPROVE: {approve_url}\n'
            'Tap to REJECT: {reject_url}\n\n'
            'Links expire in 48 hours.'
        )
        text, template_id = self._render_flow_text(
            'custom', company_id, variables, fallback,
        )
        payload = build_leave_decision_payload(
            to_mobile, text, approve_url, reject_url,
        )
        ok, msg_id = self._hand_to_engine(
            to_mobile, company_id, text, 'custom',
            template_id=template_id,
            student_id=student.id if student else None,
            guardian_id=(
                leave_request.guardian_id.id
                if leave_request.guardian_id else None
            ),
            recipient_type=approver_kind,
            extra_log_body=(
                '\n[button: Approve Leave -> %s]'
                '\n[link: Reject -> %s]'
            ) % (approve_url, reject_url),
        )
        return {
            'ok': ok, 'message_id': msg_id if ok else None,
            'error': None if ok else str(msg_id),
            'to': _clean_mobile(to_mobile), 'payload': payload,
            'approve_url': approve_url, 'reject_url': reject_url,
        }
