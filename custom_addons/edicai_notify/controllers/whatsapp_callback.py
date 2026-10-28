"""Edicai Notify — WhatsApp approval callback.

Public magic-link endpoint for guardian/faculty leave approvers.
Auth is the signed token ONLY: no session login is required or
accepted. Tokens are HMAC-signed, 48h-expiry bearer credentials
(see models/whatsapp_flows.py); a token authorises exactly one
(leave_id, action) pair and replays are neutralised because only
``submitted`` requests are actionable.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title></head>
<body style="font-family: Arial, sans-serif; max-width: 560px; \
margin: 40px auto; padding: 0 16px;">
<h2 style="color: {color};">{heading}</h2>
<p>{message}</p>
<p style="color: #888; font-size: 12px;">Edicai ERP — WhatsApp approval \
link. Links expire 48 hours after issue and work only once per \
leave decision.</p>
</body></html>"""


class WhatsappApprovalController(http.Controller):
    """auth='public' + token check only — never session auth."""

    @http.route(
        '/notify/whatsapp/leave/<int:leave_id>/<string:action>',
        type='http', auth='public', methods=['GET'], csrf=False,
    )
    def whatsapp_leave_decision(self, leave_id, action, token=None,
                                **kw):
        Flows = request.env['edicai.whatsapp.flows'].sudo()

        def page(title, heading, message, color='#2c3e50'):
            return _PAGE.format(
                title=title, heading=heading, message=message,
                color=color,
            )

        if action not in ('approve', 'reject'):
            return page(
                'Link invalid', 'Link invalid or expired',
                'This approval link is invalid or has expired '
                '(links last 48 hours). Please open the leave '
                'request in the portal instead.',
                color='#e74c3c',
            )

        ok, info = Flows.verify_leave_token(token)
        if not ok:
            _logger.warning(
                'WhatsApp approval rejected (%s) for leave %s.',
                info, leave_id,
            )
            return page(
                'Link invalid', 'Link invalid or expired',
                'This approval link is invalid or has expired '
                '(links last 48 hours). Please open the leave '
                'request in the portal instead.',
                color='#e74c3c',
            )
        if info['leave_id'] != int(leave_id) or info['action'] != action:
            return page(
                'Link mismatch', 'Link does not match',
                'This link does not match the requested leave '
                'decision. Please use the exact link from '
                'WhatsApp.',
                color='#e74c3c',
            )

        Leave = request.env['edicai.student.leave.request'].sudo()
        leave = Leave.browse(int(leave_id))
        if not leave.exists():
            return page(
                'Not found', 'Leave request not found',
                'The leave request no longer exists.',
                color='#e74c3c',
            )
        if leave.state != 'submitted':
            return page(
                'Already decided',
                'Leave %s is already %s' % (
                    leave.name or leave_id, leave.state),
                'No further action is possible via this link. '
                'The decision has already been recorded.',
            )

        try:
            if action == 'approve':
                leave.action_approve()
            elif action == 'reject':
                leave.action_reject()
            else:
                return page(
                    'Link invalid', 'Link invalid or expired',
                    'This approval link is invalid or has expired '
                    '(links last 48 hours). Please open the leave '
                    'request in the portal instead.',
                    color='#e74c3c',
                )
        except Exception:
            _logger.warning(
                'WhatsApp approval action failed for leave %s.',
                leave_id,
            )
            return page(
                'Action failed', 'Decision could not be recorded',
                'The decision could not be recorded. '
                'Please decide from the portal.',
                color='#e74c3c',
            )

        try:
            leave.message_post(
                body='Leave %s via WhatsApp magic link '
                     '(%s approver, token verified).' % (
                         'approved' if action == 'approve'
                         else 'rejected', info['kind']),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        except Exception:
            pass
        _logger.info(
            'Leave %s %s via WhatsApp link (%s).',
            leave_id, action, info['kind'],
        )
        if action == 'approve':
            return page(
                'Leave approved',
                'Leave %s approved' % (leave.name or ''),
                'The student has been notified. Thank you.',
                color='#27ae60',
            )
        return page(
            'Leave not approved',
            'Leave %s marked not approved' % (leave.name or ''),
            'The student has been notified. Thank you.',
            color='#e67e22',
        )
