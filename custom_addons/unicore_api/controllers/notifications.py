from odoo import http
from odoo.http import request

from odoo.addons.unicore_api.controllers.common import (
    _require_scope,
    _safe_call,
    api_error,
    api_response,
    validate_api_key,
)


class UniCoreApiNotifications(http.Controller):

    @http.route('/api/unicore/v1/notifications/send', type='http',
                auth='public', methods=['POST'], csrf=False)
    def send_notification(self, **kwargs):
        return _safe_call(self._send_notification, **kwargs)

    def _send_notification(self, **kwargs):
        api_key = validate_api_key(request)
        if not api_key:
            return api_error('Invalid or missing API key.',
                             'UNAUTHORIZED', 401)
        if not _require_scope(api_key, 'notify'):
            return api_error(
                'Insufficient scope. Required: notify, Actual: %s'
                % api_key.scope, 'FORBIDDEN', 403)
        try:
            data = request.get_json_data()
        except Exception:
            return api_error('Invalid JSON body.', 'INVALID_JSON', 400)
        student_id = data.get('student_id')
        title = data.get('title')
        message = data.get('message')
        notification_type = data.get('type', 'info')
        if not all([student_id, title, message]):
            return api_error(
                'student_id, title, and message are required.',
                'MISSING_FIELDS', 400,
            )
        student = request.env['unicore.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        notification = request.env['unicore.notification.log'].sudo().create({
            'student_id': student_id,
            'message_subject': title,
            'message_body': message,
            'channel': 'inapp',
            'recipient_type': 'student',
            'company_id': api_key.company_id.id,
        })
        return api_response({
            'id': notification.id,
            'title': notification.message_subject,
            'message': notification.message_body,
            'type': 'info',
            'status': 'sent',
        }, code=201)
