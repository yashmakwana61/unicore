from odoo import http
from odoo.http import request

from odoo.addons.unicore_api.controllers.common import (
    _check_body_size,
    _require_scope,
    _safe_call,
    _validate_int_param,
    _validate_str_param,
    api_error,
    api_response,
    validate_api_key,
)

VALID_STUDENT_STATES = [
    'enrolled', 'active', 'graduated',
    'dropped', 'suspended', 'alumni',
]


class UniCoreApiStudents(http.Controller):

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

    @http.route('/api/unicore/v1/students', type='http', auth='public',
                methods=['GET'], csrf=False)
    def list_students(self, **kwargs):
        return _safe_call(self._list_students, **kwargs)

    def _list_students(self, **kwargs):
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
        campus_id, err = _validate_int_param(
            kwargs.get('campus_id'), 'campus_id')
        if err:
            return err
        student_state, err = _validate_str_param(
            kwargs.get('student_state'), 'student_state',
            allowed_values=VALID_STUDENT_STATES)
        if err:
            return err
        offset, err = _validate_int_param(
            kwargs.get('offset', 0), 'offset', min_val=0)
        if err:
            return err
        offset = offset or 0
        limit, err = _validate_int_param(
            kwargs.get('limit', 20), 'limit', min_val=1, max_val=100)
        if err:
            return err
        limit = limit or 20

        search_val, err = _validate_str_param(
            kwargs.get('search'), 'search', max_length=200)
        if err:
            return err

        domain = [('active', '=', True)]
        if campus_id:
            domain.append(('campus_id', '=', campus_id))
        if program_id:
            domain.append(('program_id', '=', program_id))
        if student_state:
            domain.append(('student_state', '=', student_state))
        if search_val:
            domain.append(
                '|', ('name', 'ilike', search_val),
                ('student_id_number', 'ilike', search_val),
            )

        students = request.env['unicore.student'].sudo().search(
            domain, offset=offset, limit=limit, order='name',
        )
        total = request.env['unicore.student'].sudo().search_count(domain)
        return api_response(
            [{
                'id': s.id,
                'student_number': s.student_id_number,
                'name': s.name,
                'email': s.email,
                'phone': s.phone,
                'campus': s.campus_id.name if s.campus_id else None,
                'program': s.program_id.name if s.program_id else None,
                'status': s.student_state,
            } for s in students],
            meta={
                'total': total,
                'offset': offset,
                'limit': limit,
            },
        )

    @http.route('/api/unicore/v1/students/<int:student_id>',
                type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_student(self, student_id, **kwargs):
        return _safe_call(self._get_student, student_id, **kwargs)

    def _get_student(self, student_id, **kwargs):
        api_key, err = self._require_auth_read()
        if err:
            return err
        student = request.env['unicore.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        return api_response({
            'id': student.id,
            'student_number': student.student_id_number,
            'name': student.name,
            'email': student.email,
            'phone': student.phone,
            'mobile': student.mobile,
            'gender': student.gender,
            'date_of_birth': student.date_of_birth.isoformat()
                             if student.date_of_birth else None,
            'campus': {
                'id': student.campus_id.id,
                'name': student.campus_id.name,
            } if student.campus_id else None,
            'program': {
                'id': student.program_id.id,
                'name': student.program_id.name,
            } if student.program_id else None,
            'status': student.student_state,
            'active': student.active,
        })

    @http.route('/api/unicore/v1/students/<int:student_id>/enrollments',
                type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_student_enrollments(self, student_id, **kwargs):
        return _safe_call(self._get_student_enrollments, student_id, **kwargs)

    def _get_student_enrollments(self, student_id, **kwargs):
        api_key, err = self._require_auth_read()
        if err:
            return err
        student = request.env['unicore.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        enrollments = request.env['unicore.enrollment'].sudo().search([
            ('student_id', '=', student_id),
        ])
        return api_response([{
            'id': e.id,
            'batch': e.batch_id.name if e.batch_id else None,
            'semester': e.semester_id.name if e.semester_id else None,
            'program': e.program_id.name if e.program_id else None,
            'enrollment_date': e.enrollment_date.isoformat()
                               if e.enrollment_date else None,
            'status': e.enrollment_state,
        } for e in enrollments])

    @http.route('/api/unicore/v1/students/<int:student_id>/attendance',
                type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_student_attendance(self, student_id, **kwargs):
        return _safe_call(self._get_student_attendance, student_id, **kwargs)

    def _get_student_attendance(self, student_id, **kwargs):
        api_key, err = self._require_auth_read()
        if err:
            return err
        student = request.env['unicore.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        records = request.env['unicore.attendance.record'].sudo().search([
            ('student_id', '=', student_id),
        ], limit=200)
        return api_response([{
            'id': r.id,
            'date': r.session_date.isoformat()
                    if r.session_date else None,
            'status': r.status,
            'session': r.session_id.name if r.session_id else None,
            'course': r.course_id.name if r.course_id else None,
        } for r in records])

    @http.route('/api/unicore/v1/students/<int:student_id>/grades',
                type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_student_grades(self, student_id, **kwargs):
        return _safe_call(self._get_student_grades, student_id, **kwargs)

    def _get_student_grades(self, student_id, **kwargs):
        api_key, err = self._require_auth_read()
        if err:
            return err
        student = request.env['unicore.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        grades = request.env['unicore.grade.entry'].sudo().search([
            ('student_id', '=', student_id),
        ])
        return api_response([{
            'id': g.id,
            'course': g.course_id.name if g.course_id else None,
            'grade': g.letter_grade,
            'score': g.total_marks_obtained,
            'semester': g.semester_id.name if g.semester_id else None,
            'status': g.entry_state,
        } for g in grades])

    @http.route('/api/unicore/v1/students/<int:student_id>/fees',
                type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_student_fees(self, student_id, **kwargs):
        return _safe_call(self._get_student_fees, student_id, **kwargs)

    def _get_student_fees(self, student_id, **kwargs):
        api_key, err = self._require_auth_read()
        if err:
            return err
        student = request.env['unicore.student'].sudo().browse(student_id)
        if not student.exists():
            return api_error('Student not found.', 'NOT_FOUND', 404)
        fees = request.env['unicore.fee.invoice'].sudo().search([
            ('student_id', '=', student_id),
        ])
        total_outstanding = sum(f.amount_outstanding for f in fees)
        return api_response(
            [{
                'id': f.id,
                'fee_type': f.line_ids[0].fee_type if f.line_ids else None,
                'amount': f.total_amount,
                'paid_amount': f.amount_paid,
                'balance': f.amount_outstanding,
                'due_date': f.due_date.isoformat() if f.due_date else None,
                'status': f.invoice_state,
            } for f in fees],
            meta={'total_outstanding': total_outstanding},
        )
