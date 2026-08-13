"""
Oacis Student Leave Portal Controller
Provides web routes for students and guardians
to submit, view and manage leave requests via
the self-service portal.
"""
import logging

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class OacisStudentLeavePortal(CustomerPortal):
    """
    Student & Guardian portal routes for leave
    requests. Extends CustomerPortal to add pages
    under /my/oacis/student/leave/
    """

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(
            counters,
        )
        student = self._get_current_student()
        guardian = self._get_current_guardian()
        if student:
            if 'oacis_leave_requests' in counters:
                values['oacis_leave_requests'] = (
                    request.env[
                        'oacis.student.leave.request'
                    ].sudo().search_count([
                        ('student_id', '=', student.id),
                    ])
                )
        if guardian:
            ward_relations = self._get_ward_relations(
                guardian,
            )
            ward_ids = ward_relations.mapped(
                'student_id',
            ).ids
            if 'oacis_leave_requests' in counters:
                values['oacis_leave_requests'] = (
                    request.env[
                        'oacis.student.leave.request'
                    ].sudo().search_count([
                        ('student_id', 'in', ward_ids),
                    ])
                )
        return values

    def _get_current_student(self):
        if request.env.user._is_public():
            return False
        partner = request.env.user.partner_id
        student = (
            request.env['oacis.student']
            .sudo()
            .search([
                ('partner_id', '=', partner.id),
            ], limit=1)
        )
        return student or False

    def _get_current_guardian(self):
        if request.env.user._is_public():
            return False
        partner = request.env.user.partner_id
        guardian = (
            request.env['oacis.guardian']
            .sudo()
            .search([
                ('partner_id', '=', partner.id),
            ], limit=1)
        )
        return guardian or False

    def _student_required(self):
        if request.env.user._is_public():
            return request.redirect('/web/login')
        student = self._get_current_student()
        if not student:
            raise NotFound(
                _('No student record found for '
                  'your account.'),
            )
        return student

    def _guardian_required(self):
        if request.env.user._is_public():
            return request.redirect('/web/login')
        guardian = self._get_current_guardian()
        if not guardian:
            raise NotFound(
                _('No guardian record found for '
                  'your account.'),
            )
        return guardian

    def _get_ward_relations(self, guardian):
        return (
            request.env['oacis.guardian.student.rel']
            .sudo()
            .search([
                ('guardian_id', '=', guardian.id),
                ('is_active_relationship', '=', True),
            ])
        )

    def _get_viewable_leave_requests(self):
        """Determine which leave requests the current
        user can view based on role."""
        LeaveRequest = request.env[
            'oacis.student.leave.request'
        ].sudo()
        student = self._get_current_student()
        guardian = self._get_current_guardian()
        if student:
            return LeaveRequest.search([
                ('student_id', '=', student.id),
            ], order='create_date desc')
        if guardian:
            ward_relations = self._get_ward_relations(
                guardian,
            )
            ward_ids = ward_relations.mapped(
                'student_id',
            ).ids
            return LeaveRequest.search([
                ('student_id', 'in', ward_ids),
            ], order='create_date desc')
        return LeaveRequest.browse()

    # ===================================================
    # ROUTE 1: LEAVE REQUESTS LIST
    # ===================================================

    @http.route(
        '/my/oacis/student/leave',
        type='http',
        auth='user',
        website=True,
    )
    def leave_request_list(self, **kwargs):
        """List all leave requests for the current
        student or guardian's wards."""
        student = self._get_current_student()
        guardian = self._get_current_guardian()
        if not student and not guardian:
            raise NotFound(
                _('No student or guardian record '
                  'found.'),
            )

        leave_requests = self._get_viewable_leave_requests()

        values = {
            'leave_requests': leave_requests,
            'page_name': 'student_leave_requests',
            'student': student,
            'guardian': guardian,
        }
        return request.render(
            'oacis_student_leave'
            '.portal_leave_request_list',
            values,
        )

    # ===================================================
    # ROUTE 2: NEW LEAVE REQUEST FORM
    # ===================================================

    @http.route(
        '/my/oacis/student/leave/new',
        type='http',
        auth='user',
        website=True,
    )
    def leave_request_new(self, **kwargs):
        """Show the form to create a new leave request."""
        student = self._get_current_student()
        guardian = self._get_current_guardian()

        if not student and not guardian:
            raise NotFound(
                _('No student or guardian record '
                  'found.'),
            )

        # Determine available students
        if student:
            available_students = student
        elif guardian:
            ward_relations = self._get_ward_relations(
                guardian,
            )
            available_students = ward_relations.mapped(
                'student_id',
            )
        else:
            available_students = request.env[
                'oacis.student'
            ].browse()

        values = {
            'page_name': 'student_leave_request_new',
            'student': student,
            'guardian': guardian,
            'available_students': available_students,
            'error': kwargs.get('error', ''),
        }
        return request.render(
            'oacis_student_leave'
            '.portal_leave_request_form',
            values,
        )

    # ===================================================
    # ROUTE 3: SUBMIT LEAVE REQUEST (POST)
    # ===================================================

    @http.route(
        '/my/oacis/student/leave/submit',
        type='http',
        auth='user',
        methods=['POST'],
        website=True,
        csrf=True,
    )
    def leave_request_submit(self, **kwargs):
        """Process the submitted leave request form."""
        student = self._get_current_student()
        guardian = self._get_current_guardian()

        if not student and not guardian:
            raise NotFound(
                _('No student or guardian record '
                  'found.'),
            )

        # Extract form data
        student_id = kwargs.get('student_id')
        date_from = kwargs.get('date_from')
        date_to = kwargs.get('date_to')
        reason = kwargs.get('reason')
        doc_name = kwargs.get(
            'supporting_document_name', '',
        )

        if not all([student_id, date_from, date_to,
                    reason]):
            return request.redirect(
                '/my/oacis/student/leave/new'
                '?error=Please+fill+all+required+fields',
            )

        # Find the student record
        target_student = (
            request.env['oacis.student']
            .sudo()
            .browse(int(student_id))
        )
        if not target_student.exists():
            return request.redirect(
                '/my/oacis/student/leave/new'
                '?error=Invalid+student+selected',
            )

        # Check student is not already on leave
        if target_student.student_state == 'on_leave':
            return request.redirect(
                '/my/oacis/student/leave/new'
                '?error=Student+is+already+on+leave',
            )

        # Create the leave request
        try:
            vals = {
                'student_id': target_student.id,
                'date_from': date_from,
                'date_to': date_to,
                'reason': reason,
                'supporting_document_name': doc_name,
                'company_id': (
                    target_student.company_id.id
                ),
                'user_id': request.env.user.id,
            }

            if guardian:
                vals['guardian_id'] = guardian.id
                vals['submitted_by'] = 'guardian'

            leave_request = (
                request.env[
                    'oacis.student.leave.request'
                ]
                .sudo()
                .create(vals)
            )

            # Handle file upload if present
            if request.httprequest.files.get(
                'supporting_document',
            ):
                uploaded = request.httprequest.files[
                    'supporting_document'
                ]
                leave_request.sudo().write({
                    'supporting_document': uploaded.read(),
                    'supporting_document_name': (
                        uploaded.filename
                    ),
                })

            # Auto-submit the request
            leave_request.sudo().action_submit()

            return request.redirect(
                '/my/oacis/student/leave/%d'
                % leave_request.id,
            )

        except (ValidationError, AccessError) as e:
            return request.redirect(
                '/my/oacis/student/leave/new'
                '?error=%s' % str(e),
            )
        except Exception as e:
            _logger.error(
                'Leave request creation failed: %s',
                str(e),
            )
            return request.redirect(
                '/my/oacis/student/leave/new'
                '?error=An+error+occurred+while+'
                'submitting+your+request',
            )

    # ===================================================
    # ROUTE 4: LEAVE REQUEST DETAIL
    # ===================================================

    @http.route(
        '/my/oacis/student/leave/<int:leave_id>',
        type='http',
        auth='user',
        website=True,
    )
    def leave_request_detail(self, leave_id, **kwargs):
        """Show detail of a single leave request."""
        leave_request = (
            request.env[
                'oacis.student.leave.request'
            ]
            .sudo()
            .browse(leave_id)
        )
        if not leave_request.exists():
            raise NotFound(
                _('Leave request not found.'),
            )

        values = {
            'leave_request': leave_request,
            'page_name': 'student_leave_request_detail',
        }
        return request.render(
            'oacis_student_leave'
            '.portal_leave_request_detail',
            values,
        )
