from odoo import http
from odoo.http import request

from odoo.addons.edicai_api.controllers.common import (
    _check_body_size,
    _require_scope,
    _safe_call,
    _validate_int_param,
    _validate_str_param,
    api_error,
    api_response,
    validate_api_key,
)


class EdicaiApiNotifications(http.Controller):

    @http.route('/api/edicai/v1/notifications/send', type='http',
                auth='public', methods=['POST'], csrf=False)
    def send_notification(self, **kwargs):
        return _safe_call(self._send_notification, **kwargs)

    def _send_notification(self, **kwargs):
        err = _check_body_size()
        if err:
            return err
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
        if not isinstance(data, dict):
            return api_error('Invalid JSON body.', 'INVALID_JSON', 400)
        student_id, err = _validate_int_param(
            data.get('student_id'), 'student_id')
        if err:
            return err
        if not student_id:
            return api_error(
                'student_id, title, and message are required.',
                'MISSING_FIELDS', 400,
            )
        title, err = _validate_str_param(
            data.get('title'), 'title', max_length=200)
        if err:
            return err
        message, err = _validate_str_param(
            data.get('message'), 'message', max_length=2000)
        if err:
            return err
        notification_type = data.get('type', 'info')
        if not all([student_id, title, message]):
            return api_error(
                'student_id, title, and message are required.',
                'MISSING_FIELDS', 400,
            )
        student = request.env['edicai.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        if api_key.company_id and student.company_id.id != api_key.company_id.id:
            return api_error('Student not found.', 'NOT_FOUND', 404)
        notification = request.env['edicai.notification.log'].sudo().create({
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
