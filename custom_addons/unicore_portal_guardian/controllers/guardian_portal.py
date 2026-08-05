from datetime import date

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import (
    CustomerPortal, pager as portal_pager
)
from werkzeug.exceptions import NotFound


class UniCoreGuardianPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(
            counters
        )
        guardian = self._get_current_guardian()
        if guardian:
            wards = self._get_ward_relations(guardian)
            if 'unicore_wards' in counters:
                values['unicore_wards'] = len(wards)
        return values

    def _get_current_guardian(self):
        partner = request.env.user.partner_id
        guardian = (
            request.env['unicore.guardian']
            .sudo()
            .search([
                ('partner_id', '=', partner.id),
            ], limit=1)
        )
        return guardian

    def _guardian_required(self):
        if request.env.user._is_public():
            return request.redirect('/web/login')
        guardian = self._get_current_guardian()
        if not guardian:
            raise NotFound(
                _('No guardian record found for '
                  'your account.')
            )
        return guardian

    def _get_ward_relations(self, guardian):
        return request.env[
            'unicore.guardian.student.rel'
        ].sudo().search([
            ('guardian_id', '=', guardian.id),
            ('is_active_relationship', '=', True),
        ])

    def _check_permission(self, relation, perm_field):
        if not relation:
            return False
        return bool(getattr(relation, perm_field, False))

    @http.route(
        '/my/unicore/guardian',
        type='http',
        auth='user',
        website=True,
    )
    def guardian_dashboard(self, **kwargs):
        guardian = self._guardian_required()
        if not isinstance(
            guardian,
            request.env['unicore.guardian'].__class__
        ):
            return guardian

        ward_relations = self._get_ward_relations(guardian)

        ward_data = []
        for rel in ward_relations:
            student = rel.student_id
            acr = rel.can_view_academic_records
            fee = rel.can_view_fee_records

            shortage_count = 0
            pending_fees = 0.0
            if acr:
                shortage_records = request.env[
                    'unicore.attendance.record'
                ].sudo().search([
                    ('student_id', '=', student.id),
                    ('shortage_alert', '=', True),
                ])
                shortage_count = len(shortage_records)
            if fee:
                fee_invoices = request.env[
                    'unicore.fee.invoice'
                ].sudo().search([
                    ('student_id', '=', student.id),
                    ('amount_outstanding', '>', 0),
                    ('invoice_state', 'not in',
                     ['cancelled', 'paid']),
                ])
                pending_fees = sum(
                    i.amount_outstanding
                    for i in fee_invoices
                )

            ward_data.append({
                'relation': rel,
                'student': student,
                'can_view_academic': acr,
                'can_view_fees': fee,
                'shortage_count': shortage_count,
                'pending_fees': pending_fees,
            })

        values = {
            'guardian': guardian,
            'ward_data': ward_data,
            'ward_count': len(ward_data),
            'page_name': 'guardian_dashboard',
        }
        return request.render(
            'unicore_portal_guardian'
            '.portal_guardian_dashboard',
            values,
        )

    @http.route(
        '/my/unicore/guardian/attendance/<int:student_id>',
        type='http',
        auth='user',
        website=True,
    )
    def guardian_ward_attendance(self, student_id,
                                  **kwargs):
        guardian = self._guardian_required()
        if not isinstance(
            guardian,
            request.env['unicore.guardian'].__class__
        ):
            return guardian

        Student = request.env['unicore.student'].sudo()
        student = Student.browse(student_id)
        if not student.exists():
            raise NotFound(_('Student not found.'))

        relation = request.env[
            'unicore.guardian.student.rel'
        ].sudo().search([
            ('guardian_id', '=', guardian.id),
            ('student_id', '=', student.id),
            ('is_active_relationship', '=', True),
        ], limit=1)
        if not relation:
            raise NotFound(
                _('No active ward relationship found.')
            )
        if not self._check_permission(
            relation, 'can_view_academic_records'
        ):
            return request.render(
                'unicore_portal_guardian'
                '.portal_guardian_no_permission',
                {
                    'guardian': guardian,
                    'student': student,
                    'page_name': 'guardian_attendance',
                },
            )

        AttRecord = request.env[
            'unicore.attendance.record'
        ].sudo()
        att_records = AttRecord.search([
            ('student_id', '=', student.id),
        ], order='course_id, semester_id desc')

        seen = set()
        unique_records = []
        for rec in att_records:
            key = (rec.course_id.id, rec.semester_id.id)
            if key not in seen:
                seen.add(key)
                unique_records.append(rec)

        values = {
            'guardian': guardian,
            'student': student,
            'attendance_records': unique_records,
            'shortage_records': [
                r for r in unique_records
                if r.shortage_alert
            ],
            'page_name': 'guardian_attendance',
        }
        return request.render(
            'unicore_portal_guardian'
            '.portal_guardian_ward_attendance',
            values,
        )

    @http.route(
        '/my/unicore/guardian/academic/<int:student_id>',
        type='http',
        auth='user',
        website=True,
    )
    def guardian_ward_academic(self, student_id,
                                **kwargs):
        guardian = self._guardian_required()
        if not isinstance(
            guardian,
            request.env['unicore.guardian'].__class__
        ):
            return guardian

        Student = request.env['unicore.student'].sudo()
        student = Student.browse(student_id)
        if not student.exists():
            raise NotFound(_('Student not found.'))

        relation = request.env[
            'unicore.guardian.student.rel'
        ].sudo().search([
            ('guardian_id', '=', guardian.id),
            ('student_id', '=', student.id),
            ('is_active_relationship', '=', True),
        ], limit=1)
        if not relation:
            raise NotFound(
                _('No active ward relationship found.')
            )
        if not self._check_permission(
            relation, 'can_view_academic_records'
        ):
            return request.render(
                'unicore_portal_guardian'
                '.portal_guardian_no_permission',
                {
                    'guardian': guardian,
                    'student': student,
                    'page_name': 'guardian_academic',
                },
            )

        GradeEntry = request.env[
            'unicore.grade.entry'
        ].sudo()
        SemesterResult = request.env[
            'unicore.semester.result'
        ].sudo()

        grade_entries = GradeEntry.search([
            ('student_id', '=', student.id),
            ('entry_state', 'in',
             ['published', 'locked']),
        ], order='semester_id desc')

        semester_results = SemesterResult.search([
            ('student_id', '=', student.id),
            ('is_published', '=', True),
        ], order='semester_id desc')

        values = {
            'guardian': guardian,
            'student': student,
            'grade_entries': grade_entries,
            'semester_results': semester_results,
            'page_name': 'guardian_academic',
        }
        return request.render(
            'unicore_portal_guardian'
            '.portal_guardian_ward_academic',
            values,
        )

    @http.route(
        '/my/unicore/guardian/fees/<int:student_id>',
        type='http',
        auth='user',
        website=True,
    )
    def guardian_ward_fees(self, student_id, **kwargs):
        guardian = self._guardian_required()
        if not isinstance(
            guardian,
            request.env['unicore.guardian'].__class__
        ):
            return guardian

        Student = request.env['unicore.student'].sudo()
        student = Student.browse(student_id)
        if not student.exists():
            raise NotFound(_('Student not found.'))

        relation = request.env[
            'unicore.guardian.student.rel'
        ].sudo().search([
            ('guardian_id', '=', guardian.id),
            ('student_id', '=', student.id),
            ('is_active_relationship', '=', True),
        ], limit=1)
        if not relation:
            raise NotFound(
                _('No active ward relationship found.')
            )
        if not self._check_permission(
            relation, 'can_view_fee_records'
        ):
            return request.render(
                'unicore_portal_guardian'
                '.portal_guardian_no_permission',
                {
                    'guardian': guardian,
                    'student': student,
                    'page_name': 'guardian_fees',
                },
            )

        Invoice = request.env['unicore.fee.invoice'].sudo()
        invoices = Invoice.search([
            ('student_id', '=', student.id),
            ('invoice_state', '!=', 'cancelled'),
        ], order='invoice_date desc')

        values = {
            'guardian': guardian,
            'student': student,
            'invoices': invoices,
            'total_outstanding': sum(
                i.amount_outstanding for i in invoices
            ),
            'total_paid': sum(
                i.amount_paid for i in invoices
            ),
            'page_name': 'guardian_fees',
        }
        return request.render(
            'unicore_portal_guardian'
            '.portal_guardian_ward_fees',
            values,
        )

    @http.route(
        '/my/unicore/guardian/exams',
        type='http',
        auth='user',
        website=True,
    )
    def guardian_exams(self, **kwargs):
        guardian = self._guardian_required()
        if not isinstance(
            guardian,
            request.env['unicore.guardian'].__class__
        ):
            return guardian

        ward_relations = self._get_ward_relations(guardian)

        ward_exam_data = []
        for rel in ward_relations:
            if not self._check_permission(
                rel, 'can_view_academic_records'
            ):
                continue

            student = rel.student_id
            HallTicket = request.env[
                'unicore.exam.hall.ticket'
            ].sudo()
            tickets = HallTicket.search([
                ('student_id', '=', student.id),
                ('ticket_state', 'not in', ['cancelled']),
            ], order='exam_date desc')

            ExamSchedule = request.env[
                'unicore.exam.schedule'
            ].sudo()
            upcoming_schedules = ExamSchedule.search([
                ('course_id', 'in', (
                    request.env['unicore.enrollment']
                    .sudo()
                    .search([
                        ('student_id', '=', student.id),
                        ('enrollment_state', 'in',
                         ['registered']),
                    ])
                    .mapped('course_id.id')
                )),
                ('exam_state', 'not in',
                 ['completed', 'cancelled']),
            ], order='exam_date asc')

            ward_exam_data.append({
                'student': student,
                'relation': rel,
                'tickets': tickets,
                'upcoming_schedules': upcoming_schedules,
            })

        values = {
            'guardian': guardian,
            'ward_exam_data': ward_exam_data,
            'page_name': 'guardian_exams',
        }
        return request.render(
            'unicore_portal_guardian'
            '.portal_guardian_exams',
            values,
        )

    # ===================================================
    # ROUTE: MY NOTICES
    # ===================================================

    @http.route(
        '/my/unicore/guardian/notices',
        type='http',
        auth='user',
        website=True,
    )
    def guardian_notices(self, page=1, date_begin=None, date_end=None, **kwargs):
        guardian = self._guardian_required()
        if not isinstance(
            guardian,
            request.env['unicore.guardian'].__class__
        ):
            return guardian

        Notice = request.env['unicore.notice'].sudo()
        notices = Notice.search([
            ('publisher_id', '!=', False),
        ], order='pinned desc, publish_date desc')

        today = date.today()
        notices = notices.filtered(
            lambda n: not n.expiry_date or n.expiry_date >= today
        )

        campus_ids = set()
        for rel in self._get_student_wards(guardian):
            if rel.student_id.campus_id:
                campus_ids.add(rel.student_id.campus_id.id)
        campus_ids = list(campus_ids)

        notices = notices.filtered(
            lambda n: n.audience == 'all'
            or (n.audience == 'guardians')
            or (n.audience == 'specific'
                and any(c.id in campus_ids for c in n.campus_ids))
        )

        notice_count = len(notices)
        pager = portal_pager(
            url='/my/unicore/guardian/notices',
            total=notice_count,
            page=page,
            step=20,
        )
        notices = notices[(pager['offset']):(pager['offset'] + pager['step'])]

        values = {
            'guardian': guardian,
            'notices': notices,
            'page_name': 'guardian_notices',
            'pager': pager,
            'date_begin': date_begin,
            'date_end': date_end,
        }
        return request.render(
            'unicore_notice_board.portal_guardian_notices',
            values,
        )
