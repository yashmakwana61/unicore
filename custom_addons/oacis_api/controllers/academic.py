from odoo import fields, http
from odoo.http import request

from odoo.addons.oacis_api.controllers.common import (
    _check_body_size,
    _require_scope,
    _safe_call,
    _validate_int_param,
    api_error,
    api_response,
    validate_api_key,
)


class OacisApiAcademic(http.Controller):

    def _require_auth_read(self):
        api_key = validate_api_key(request)
        if not api_key:
            return None, api_error('Invalid or missing API key.',
                                   'UNAUTHORIZED', 401)
        if not _require_scope(api_key, 'read'):
            return None, api_error(
                'Insufficient scope. Required: read, Actual: %s'
                % api_key.scope, 'FORBIDDEN', 403)
        return api_key, None

    @http.route('/api/oacis/v1/programs', type='http', auth='public',
                methods=['GET'], csrf=False)
    def list_programs(self, **kwargs):
        return _safe_call(self._list_programs, **kwargs)

    def _list_programs(self, **kwargs):
        err = _check_body_size()
        if err:
            return err
        api_key, err = self._require_auth_read()
        if err:
            return err
        campus_id, err = _validate_int_param(
            kwargs.get('campus_id'), 'campus_id')
        if err:
            return err
        domain = [('active', '=', True)]
        if campus_id:
            domain.append(('campus_ids', '=', campus_id))
        programs = request.env['oacis.program'].sudo().search(
            domain, order='name',
        )
        return api_response([{
            'id': p.id,
            'name': p.name,
            'code': p.code,
            'level': p.program_type,
            'duration_years': p.duration_years,
            'campus': p.campus_ids[0].name if p.campus_ids else None,
        } for p in programs])

    @http.route('/api/oacis/v1/semesters/current', type='http',
                auth='public', methods=['GET'], csrf=False)
    def get_current_semester(self, **kwargs):
        return _safe_call(self._get_current_semester, **kwargs)

    def _get_current_semester(self, **kwargs):
        err = _check_body_size()
        if err:
            return err
        api_key, err = self._require_auth_read()
        if err:
            return err
        today = fields.Date.context_today(request)
        semester = request.env['oacis.semester'].sudo().search([
            ('date_start', '<=', today),
            ('date_end', '>=', today),
            ('active', '=', True),
        ], limit=1, order='date_start desc')
        if not semester:
            return api_error('No current semester found.',
                             'NOT_FOUND', 404)
        return api_response({
            'id': semester.id,
            'name': semester.name,
            'code': semester.code,
            'start_date': semester.start_date.isoformat(),
            'end_date': semester.end_date.isoformat(),
            'status': semester.semester_state,
        })

    @http.route('/api/oacis/v1/courses', type='http', auth='public',
                methods=['GET'], csrf=False)
    def list_courses(self, **kwargs):
        return _safe_call(self._list_courses, **kwargs)

    def _list_courses(self, **kwargs):
        err = _check_body_size()
        if err:
            return err
        api_key, err = self._require_auth_read()
        if err:
            return err
        program_id, err = _validate_int_param(
            kwargs.get('program_id'), 'program_id')
        if err:
            return err
        domain = [('course_state', '=', 'active')]
        if program_id:
            domain.append(('id', 'in',
                request.env['oacis.course.offering'].sudo().search([
                    ('program_id', '=', program_id),
                ]).mapped('course_id.id')))
        courses = request.env['oacis.course'].sudo().search(
            domain, order='name',
        )
        return api_response([{
            'id': c.id,
            'name': c.name,
            'code': c.code,
            'credits': c.credit_hours,
            'program': None,
        } for c in courses])
