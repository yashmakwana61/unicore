"""
UniCore Student Portal Controller
Provides web routes for the student self-service
portal. All routes require portal user login and
restrict data to the currently logged-in student.
"""

import logging
from datetime import date, datetime

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)


class UniCoreStudentPortal(CustomerPortal):
    """
    Student portal controller. Extends CustomerPortal
    to add UniCore student pages under /my/unicore/
    """

    def _prepare_home_portal_values(self, counters):
        """
        Add UniCore student counters to the portal
        home page (My Home). Extends the parent method.
        """
        values = super()._prepare_home_portal_values(
            counters,
        )
        student = self._get_current_student()
        if student:
            if 'unicore_courses' in counters:
                values['unicore_courses'] = (
                    request.env['unicore.enrollment']
                    .sudo()
                    .search_count([
                        ('student_id', '=', student.id),
                        ('enrollment_state', '=',
                         'registered'),
                    ])
                )
            if 'unicore_assignments' in counters:
                offerings = self.env[
                    'unicore.enrollment'
                ].sudo().search([
                    ('student_id', '=', student.id),
                    ('enrollment_state', '=', 'registered'),
                ]).mapped('course_offering_id')
                values['unicore_assignments'] = (
                    request.env['unicore.assignment']
                    .sudo()
                    .search_count([
                        ('course_offering_id', 'in',
                         offerings.ids),
                        ('assignment_state', '=',
                         'published'),
                    ])
                )
            if 'unicore_invoices' in counters:
                values['unicore_invoices'] = (
                    request.env['unicore.fee.invoice']
                    .sudo()
                    .search_count([
                        ('student_id', '=', student.id),
                        ('invoice_state', 'not in',
                         ['cancelled']),
                    ])
                )
        return values

    def _get_current_student(self):
        """
        Find the unicore.student record linked to
        the currently logged-in portal user.
        Returns False if not found.
        """
        if request.env.user._is_public():
            return False
        partner = request.env.user.partner_id
        student = request.env['unicore.student'].sudo().search([
            ('partner_id', '=', partner.id),
        ], limit=1)
        return student or False

    def _student_required(self):
        """
        Ensure current user is a linked student.
        Raises NotFound if not authenticated or
        no student record found.
        """
        if request.env.user._is_public():
            return request.redirect('/web/login')
        student = self._get_current_student()
        if not student:
            raise NotFound(
                _('No student record found for '
                  'your account.'),
            )
        return student

    # ===================================================
    # ROUTE 1: STUDENT DASHBOARD
    # ===================================================

    @http.route(
        '/my/unicore/student',
        type='http',
        auth='user',
        website=True,
    )
    def student_dashboard(self, **kwargs):
        """
        Main student portal dashboard.
        Shows: profile summary, current semester
        enrollment count, CGPA, attendance summary,
        fee outstanding and recent results.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

        Enrollment = request.env['unicore.enrollment'].sudo()
        AttRecord = request.env[
            'unicore.attendance.record'
        ].sudo()
        Invoice = request.env['unicore.fee.invoice'].sudo()

        # Current semester enrollments
        current_enrollments = Enrollment.search([
            ('student_id', '=', student.id),
            ('enrollment_state', '=', 'registered'),
            ('semester_id', '=',
             student.current_semester_id.id
             if student.current_semester_id else False),
        ])

        # Attendance shortage alerts
        shortage_records = AttRecord.search([
            ('student_id', '=', student.id),
            ('shortage_alert', '=', True),
        ])

        # Outstanding fees
        outstanding_invoices = Invoice.search([
            ('student_id', '=', student.id),
            ('amount_outstanding', '>', 0),
            ('invoice_state', 'not in',
             ['cancelled', 'paid']),
        ])

        values = {
            'student': student,
            'current_enrollments': current_enrollments,
            'enrollment_count': len(current_enrollments),
            'shortage_count': len(shortage_records),
            'outstanding_amount': sum(
                i.amount_outstanding
                for i in outstanding_invoices
            ),
            'outstanding_invoice_count': len(
                outstanding_invoices,
            ),
            'page_name': 'student_dashboard',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_dashboard',
            values,
        )

    # ===================================================
    # ROUTE 2: MY COURSES (current enrollments)
    # ===================================================

    @http.route(
        '/my/unicore/student/courses',
        type='http',
        auth='user',
        website=True,
    )
    def student_courses(self, **kwargs):
        """
        List of all current semester enrolled courses
        with timetable and instructor info.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

        Enrollment = request.env['unicore.enrollment'].sudo()
        TimetableEntry = request.env[
            'unicore.timetable.entry'
        ].sudo()

        enrollments = Enrollment.search([
            ('student_id', '=', student.id),
            ('enrollment_state', 'in',
             ['registered', 'completed']),
        ], order='semester_id desc')

        # Build timetable data per offering
        timetable_map = {}
        for enr in enrollments:
            if enr.course_offering_id:
                entries = TimetableEntry.search([
                    ('course_offering_id', '=',
                     enr.course_offering_id.id),
                    ('entry_state', '=', 'confirmed'),
                ])
                timetable_map[enr.id] = entries

        values = {
            'student': student,
            'enrollments': enrollments,
            'timetable_map': timetable_map,
            'page_name': 'student_courses',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_courses',
            values,
        )

    # ===================================================
    # ROUTE 3: MY ATTENDANCE
    # ===================================================

    @http.route(
        '/my/unicore/student/attendance',
        type='http',
        auth='user',
        website=True,
    )
    def student_attendance(self, **kwargs):
        """
        Per-course attendance summary with shortage
        and warning alerts highlighted.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

        AttRecord = request.env[
            'unicore.attendance.record'
        ].sudo()

        # Get unique per-course records (latest)
        att_records = AttRecord.search([
            ('student_id', '=', student.id),
        ], order='course_id, semester_id desc')

        # Deduplicate: one record per course per sem
        seen = set()
        unique_records = []
        for rec in att_records:
            key = (rec.course_id.id, rec.semester_id.id)
            if key not in seen:
                seen.add(key)
                unique_records.append(rec)

        values = {
            'student': student,
            'attendance_records': unique_records,
            'shortage_records': [
                r for r in unique_records
                if r.shortage_alert
            ],
            'warning_records': [
                r for r in unique_records
                if r.warning_alert and not r.shortage_alert
            ],
            'page_name': 'student_attendance',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_attendance',
            values,
        )

    # ===================================================
    # ROUTE 4: MY EXAM HALL TICKETS
    # ===================================================

    @http.route(
        '/my/unicore/student/exams',
        type='http',
        auth='user',
        website=True,
    )
    def student_exams(self, **kwargs):
        """
        Hall tickets and upcoming exam schedule for
        the current student.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

        HallTicket = request.env[
            'unicore.exam.hall.ticket'
        ].sudo()

        tickets = HallTicket.search([
            ('student_id', '=', student.id),
            ('ticket_state', 'not in', ['cancelled']),
        ], order='exam_date desc')

        upcoming = tickets.filtered(
            lambda t: t.ticket_state in
            ('draft', 'approved'),
        )
        past = tickets.filtered(
            lambda t: t.ticket_state in
            ('used',),
        )

        values = {
            'student': student,
            'all_tickets': tickets,
            'upcoming_tickets': upcoming,
            'past_tickets': past,
            'page_name': 'student_exams',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_exams',
            values,
        )

    # ===================================================
    # ROUTE 5: MY RESULTS
    # ===================================================

    @http.route(
        '/my/unicore/student/results',
        type='http',
        auth='user',
        website=True,
    )
    def student_results(self, **kwargs):
        """
        Published grade entries and semester results
        for the current student.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

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
            'student': student,
            'grade_entries': grade_entries,
            'semester_results': semester_results,
            'page_name': 'student_results',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_results',
            values,
        )

    # ===================================================
    # ROUTE 6: MY FEES
    # ===================================================

    @http.route(
        '/my/unicore/student/fees',
        type='http',
        auth='user',
        website=True,
    )
    def student_fees(self, **kwargs):
        """
        Fee invoices and payment history.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

        Invoice = request.env['unicore.fee.invoice'].sudo()

        invoices = Invoice.search([
            ('student_id', '=', student.id),
            ('invoice_state', '!=', 'cancelled'),
        ], order='invoice_date desc')

        values = {
            'student': student,
            'invoices': invoices,
            'total_outstanding': sum(
                i.amount_outstanding for i in invoices
            ),
            'total_paid': sum(
                i.amount_paid for i in invoices
            ),
            'page_name': 'student_fees',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_fees',
            values,
        )

    # ===================================================
    # ROUTE 7: MY SCHOLARSHIPS
    # ===================================================

    @http.route(
        '/my/unicore/student/scholarships',
        type='http',
        auth='user',
        website=True,
    )
    def student_scholarships(self, **kwargs):
        """
        Scholarship applications and award status.
        """
        student = self._student_required()
        if not isinstance(student,
                          request.env['unicore.student']
                          .__class__):
            return student

        Application = request.env[
            'unicore.scholarship.application'
        ].sudo()

        applications = Application.search([
            ('student_id', '=', student.id),
        ], order='application_date desc')

        values = {
            'student': student,
            'applications': applications,
            'approved_apps': applications.filtered(
                lambda a: a.application_state == 'approved',
            ),
            'page_name': 'student_scholarships',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_scholarships',
            values,
        )

    # ===================================================
    # ROUTE: MY NOTICES
    # ===================================================

    @http.route(
        '/my/unicore/student/notices',
        type='http',
        auth='user',
        website=True,
    )
    def student_notices(self, page=1, date_begin=None, date_end=None, **kwargs):
        student = self._student_required()
        if not isinstance(
            student,
            request.env['unicore.student'].__class__,
        ):
            return student

        Notice = request.env['unicore.notice'].sudo()
        notices = Notice.search([
            ('publisher_id', '!=', False),
        ], order='pinned desc, publish_date desc')

        today = date.today()
        notices = notices.filtered(
            lambda n: not n.expiry_date or n.expiry_date >= today,
        )

        student_campus_ids = student.campus_id.ids if student else []
        student_program_ids = (
            [student.program_id.id]
            if student and student.program_id else []
        )
        notices = notices.filtered(
            lambda n: n.audience == 'all'
            or (n.audience == 'students')
            or (n.audience == 'specific'
                and (
                    any(c.id in student_campus_ids for c in n.campus_ids)
                    or any(p.id in student_program_ids for p in n.program_ids)
                )),
        )

        notice_count = len(notices)
        pager = portal_pager(
            url='/my/unicore/student/notices',
            total=notice_count,
            page=page,
            step=20,
        )
        notices = notices[(pager['offset']):(pager['offset'] + pager['step'])]

        values = {
            'student': student,
            'notices': notices,
            'page_name': 'student_notices',
            'pager': pager,
            'date_begin': date_begin,
            'date_end': date_end,
        }
        return request.render(
            'unicore_notice_board.portal_student_notices',
            values,
        )

    # ===================================================
    # ROUTE: MY ASSIGNMENTS (list)
    # ===================================================

    def _get_student_offerings(self, student):
        """
        Return the course offerings the student is currently
        registered for (published assignments only matter here,
        but we list all active offerings).
        """
        Enrollment = request.env['unicore.enrollment'].sudo()
        enrollments = Enrollment.search([
            ('student_id', '=', student.id),
            ('enrollment_state', '=', 'registered'),
        ])
        return enrollments.mapped('course_offering_id')

    @http.route(
        '/my/unicore/student/assignments',
        type='http',
        auth='user',
        website=True,
    )
    def student_assignments(self, **kwargs):
        """
        List all published/closed assignments for the courses
        the student is enrolled in, with submission status.
        """
        student = self._student_required()
        if not isinstance(
            student,
            request.env['unicore.student'].__class__,
        ):
            return student

        offerings = self._get_student_offerings(student)
        offering_ids = offerings.ids

        Assignment = request.env['unicore.assignment'].sudo()
        Submission = request.env[
            'unicore.assignment.submission'
        ].sudo()

        assignments = Assignment.search([
            ('course_offering_id', 'in', offering_ids),
            ('assignment_state', 'in',
             ['published', 'closed']),
        ], order='due_date')

        # Build submission map: assignment_id -> submission
        submission_map = {}
        for assignment in assignments:
            sub = Submission.search([
                ('assignment_id', '=', assignment.id),
                ('student_id', '=', student.id),
            ], limit=1)
            submission_map[assignment.id] = sub or False

        now = datetime.now()
        overdue_ids = {
            a.id for a in assignments
            if a.due_datetime and now > a.due_datetime
            and a.assignment_state != 'closed'
        }

        values = {
            'student': student,
            'assignments': assignments,
            'submission_map': submission_map,
            'overdue_ids': overdue_ids,
            'published_assignments': assignments.filtered(
                lambda a: a.assignment_state == 'published',
            ),
            'closed_assignments': assignments.filtered(
                lambda a: a.assignment_state == 'closed',
            ),
            'page_name': 'student_assignments',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_assignments',
            values,
        )

    # ===================================================
    # ROUTE: ASSIGNMENT DETAIL (view + submit)
    # ===================================================

    @http.route(
        '/my/unicore/student/assignments/'
        '<int:assignment_id>',
        type='http',
        auth='user',
        website=True,
    )
    def student_assignment_detail(self, assignment_id,
                                   **kwargs):
        """
        Detail page for one assignment. Shows description,
        rubric and the student's submission (or the submit
        form if not yet submitted).
        """
        student = self._student_required()
        if not isinstance(
            student,
            request.env['unicore.student'].__class__,
        ):
            return student

        Assignment = request.env['unicore.assignment'].sudo()
        assignment = Assignment.browse(assignment_id)
        if not assignment.exists():
            raise NotFound()

        offerings = self._get_student_offerings(student)
        if assignment.course_offering_id.id not in offerings.ids:
            raise AccessError(
                _('You are not enrolled in this course.'),
            )

        Submission = request.env[
            'unicore.assignment.submission'
        ].sudo()
        submission = Submission.search([
            ('assignment_id', '=', assignment.id),
            ('student_id', '=', student.id),
        ], limit=1)

        now = datetime.now()
        can_submit = (
            assignment.assignment_state == 'published'
            and (not submission or submission.state
                 in ('draft', 'returned'))
            and (assignment.due_datetime is None
                 or now <= assignment.due_datetime
                 or assignment.is_late_submission_allowed)
        )

        values = {
            'student': student,
            'assignment': assignment,
            'submission': submission or False,
            'can_submit': can_submit,
            'is_overdue': bool(
                assignment.due_datetime
                and now > assignment.due_datetime,
            ),
            'page_name': 'student_assignment_detail',
        }
        return request.render(
            'unicore_portal_student'
            '.portal_student_assignment_detail',
            values,
        )

    # ===================================================
    # ROUTE: SUBMIT ASSIGNMENT (POST)
    # ===================================================

    @http.route(
        '/my/unicore/student/assignments/'
        '<int:assignment_id>/submit',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def student_assignment_submit(self, assignment_id,
                                   **kwargs):
        """
        Handle the assignment submission form. Creates the
        submission (or updates a draft) with the uploaded file
        and submits it.
        """
        student = self._student_required()
        if not isinstance(
            student,
            request.env['unicore.student'].__class__,
        ):
            return student

        Assignment = request.env['unicore.assignment'].sudo()
        assignment = Assignment.browse(assignment_id)
        if not assignment.exists():
            raise NotFound()

        offerings = self._get_student_offerings(student)
        if assignment.course_offering_id.id not in offerings.ids:
            raise AccessError(
                _('You are not enrolled in this course.'),
            )
        if assignment.assignment_state != 'published':
            raise AccessError(
                _('This assignment is not open for submissions.'),
            )

        Submission = request.env[
            'unicore.assignment.submission'
        ].sudo()
        submission = Submission.search([
            ('assignment_id', '=', assignment.id),
            ('student_id', '=', student.id),
        ], limit=1)

        # Handle file upload (multipart) following the
        # established UniCore portal upload pattern.
        submission_file = False
        filename = ''
        if request.httprequest.files.get('submission_file'):
            uploaded = request.httprequest.files['submission_file']
            submission_file = uploaded.read()
            filename = uploaded.filename or ''

        notes = kwargs.get('submission_text') or ''

        if not submission_file and not notes:
            raise UserError(_(
                'Please attach a file or write notes before '
                'submitting.',
            ))

        now = datetime.now()
        due_dt = assignment.due_datetime
        is_late = bool(due_dt and now > due_dt)

        vals = {
            'assignment_id': assignment.id,
            'student_id': student.id,
            'submission_text': notes,
            'submission_date': now,
            'state': 'late' if is_late else 'submitted',
        }
        if submission_file:
            vals['submission_file'] = submission_file
            vals['submission_filename'] = filename

        if submission:
            was_submitted = submission.state in ('submitted', 'late')
            submission.write(vals)
            if not was_submitted:
                submission.attempt_count = (
                    submission.attempt_count + 1
                )
            submission.state = 'late' if is_late else 'submitted'
        else:
            Submission.create(vals)

        # Notify the faculty member
        try:
            assignment._notify_faculty(
                submission or Submission.search([
                    ('assignment_id', '=', assignment.id),
                    ('student_id', '=', student.id),
                ], limit=1),
            )
        except Exception as e:
            _logger.error('Faculty notify failed: %s', str(e))

        return request.redirect(
            '/my/unicore/student/assignments/%d'
            % assignment.id,
        )
