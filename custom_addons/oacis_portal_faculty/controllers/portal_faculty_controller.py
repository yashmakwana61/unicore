"""
UniCore Faculty Portal Controller
Provides web routes for the faculty self-service
portal. Routes restrict data to courses taught by
the currently logged-in faculty member.
Faculty can write attendance and submit grades.
"""

import json
import logging
from datetime import date, datetime

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class UniCoreFacultyPortal(CustomerPortal):
    """
    Faculty portal controller extending CustomerPortal.
    Adds UniCore faculty pages under /my/unicore/faculty/
    """

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(
            counters,
        )
        faculty = self._get_current_faculty()
        if faculty:
            if 'unicore_faculty_courses' in counters:
                values['unicore_faculty_courses'] = (
                    request.env['unicore.course.offering']
                    .sudo()
                    .search_count([
                        ('faculty_member_id', '=',
                         faculty.id),
                        ('offering_state', 'in',
                         ['open', 'ongoing']),
                    ])
                )
            if 'unicore_faculty_assignments' in counters:
                values['unicore_faculty_assignments'] = (
                    request.env['unicore.assignment']
                    .sudo()
                    .search_count([
                        ('faculty_member_id', '=',
                         faculty.id),
                        ('assignment_state', '=',
                         'published'),
                    ])
                )
        return values

    def _get_current_faculty(self):
        """
        Find unicore.faculty.member linked to current user
        via partner_id. Works for both internal users
        and portal users.
        """
        partner = request.env.user.partner_id
        faculty = (
            request.env['unicore.faculty.member']
            .sudo()
            .search([
                ('partner_id', '=', partner.id),
            ], limit=1)
        )
        return faculty

    def _faculty_required(self):
        """
        Ensure current user has a linked faculty record.
        Returns faculty record or raises NotFound.
        """
        faculty = self._get_current_faculty()
        if not faculty:
            raise NotFound(
                _('No faculty record found for '
                  'your account.'),
            )
        return faculty

    def _get_faculty_offerings(self, faculty):
        """
        Return active course offerings for the faculty.
        """
        return (
            request.env['unicore.course.offering']
            .sudo()
            .search([
                ('faculty_member_id', '=', faculty.id),
                ('offering_state', 'in',
                 ['open', 'ongoing']),
            ])
        )

    # ===================================================
    # ROUTE 1: FACULTY DASHBOARD
    # ===================================================

    @http.route(
        '/my/unicore/faculty',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_dashboard(self, **kwargs):
        """
        Faculty portal dashboard showing:
        - Today's classes from timetable
        - Pending grade entries to submit
        - Open attendance sessions to mark
        - Upcoming exams as invigilator
        """
        faculty = self._faculty_required()

        from datetime import date
        today = date.today()
        today_weekday = str(today.weekday())

        offerings = self._get_faculty_offerings(faculty)
        offering_ids = offerings.ids

        # Today's timetable entries
        TimetableEntry = request.env[
            'unicore.timetable.entry'
        ].sudo()
        todays_classes = TimetableEntry.search([
            ('course_offering_id', 'in', offering_ids),
            ('day_of_week', '=', today_weekday),
            ('entry_state', '=', 'confirmed'),
        ])

        # Open attendance sessions to mark
        Session = request.env[
            'unicore.attendance.session'
        ].sudo()
        open_sessions = Session.search([
            ('timetable_entry_id.course_offering_id',
             'in', offering_ids),
            ('session_state', '=', 'open'),
        ])

        # Grade entries pending submission
        GradeEntry = request.env[
            'unicore.grade.entry'
        ].sudo()
        pending_grades = GradeEntry.search([
            ('course_offering_id', 'in', offering_ids),
            ('entry_state', '=', 'draft'),
        ])

        # Upcoming exams as invigilator
        ExamSchedule = request.env[
            'unicore.exam.schedule'
        ].sudo()
        upcoming_exams = ExamSchedule.search([
            '|',
            ('invigilator_ids', 'in', [faculty.id]),
            ('chief_invigilator_id', '=', faculty.id),
            ('exam_date', '>=', str(today)),
            ('exam_state', 'not in',
             ['completed', 'cancelled']),
        ])

        values = {
            'faculty': faculty,
            'offerings': offerings,
            'offering_count': len(offerings),
            'todays_classes': todays_classes,
            'open_sessions': open_sessions,
            'open_session_count': len(open_sessions),
            'pending_grades': pending_grades,
            'pending_grade_count': len(pending_grades),
            'upcoming_exams': upcoming_exams,
            'today': today,
            'page_name': 'faculty_dashboard',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_dashboard',
            values,
        )

    # ===================================================
    # ROUTE 2: MY SCHEDULE
    # ===================================================

    @http.route(
        '/my/unicore/faculty/schedule',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_schedule(self, **kwargs):
        """
        Weekly timetable view for the faculty member.
        Groups entries by day for display.
        """
        faculty = self._faculty_required()

        TimetableEntry = request.env[
            'unicore.timetable.entry'
        ].sudo()
        entries = TimetableEntry.search([
            ('instructor_id', '=', faculty.id),
            ('entry_state', '=', 'confirmed'),
        ], order='day_of_week, time_slot_id')

        # Group by day
        days = {
            '0': {'name': 'Monday', 'entries': []},
            '1': {'name': 'Tuesday', 'entries': []},
            '2': {'name': 'Wednesday', 'entries': []},
            '3': {'name': 'Thursday', 'entries': []},
            '4': {'name': 'Friday', 'entries': []},
            '5': {'name': 'Saturday', 'entries': []},
        }
        for entry in entries:
            day_key = entry.day_of_week
            if day_key in days:
                days[day_key]['entries'].append(entry)

        values = {
            'faculty': faculty,
            'days': days,
            'all_entries': entries,
            'page_name': 'faculty_schedule',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_schedule',
            values,
        )

    # ===================================================
    # ROUTE 3: MY COURSES (student list per course)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/courses',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_courses(self, **kwargs):
        """
        List of courses the faculty teaches with
        enrolled student count and progress.
        """
        faculty = self._faculty_required()

        offerings = self._get_faculty_offerings(faculty)

        # For each offering get enrollment + grade stats
        course_data = []
        Enrollment = request.env['unicore.enrollment'].sudo()
        GradeEntry = request.env['unicore.grade.entry'].sudo()

        for offering in offerings:
            enrollments = Enrollment.search([
                ('course_offering_id', '=', offering.id),
                ('enrollment_state', '=', 'registered'),
            ])
            grades = GradeEntry.search([
                ('course_offering_id', '=', offering.id),
            ])
            submitted = grades.filtered(
                lambda g: g.entry_state == 'submitted',
            )
            shortage_count = len(enrollments.filtered(
                lambda e: any(
                    r.shortage_alert
                    for r in request.env[
                        'unicore.attendance.record'
                    ].sudo().search([
                        ('student_id', '=', e.student_id.id),
                        ('course_offering_id', '=', offering.id),
                    ])
                ),
            ))
            course_data.append({
                'offering': offering,
                'enrollments': enrollments,
                'enrolled_count': len(enrollments),
                'grades_submitted': len(submitted),
                'grades_total': len(grades),
                'shortage_count': shortage_count,
            })

        values = {
            'faculty': faculty,
            'course_data': course_data,
            'page_name': 'faculty_courses',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_courses',
            values,
        )

    # ===================================================
    # ROUTE 4: COURSE DETAIL (students in one course)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/courses/<int:offering_id>',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_course_detail(self, offering_id,
                               **kwargs):
        """
        Detail view for a single course offering.
        Shows enrolled students with attendance and
        current grade status.
        """
        faculty = self._faculty_required()

        Offering = request.env[
            'unicore.course.offering'
        ].sudo()
        offering = Offering.browse(offering_id)

        if not offering.exists():
            raise NotFound()
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Enrollment = request.env[
            'unicore.enrollment'
        ].sudo()
        enrollments = Enrollment.search([
            ('course_offering_id', '=', offering.id),
        ], order='student_id')

        AttRecord = request.env[
            'unicore.attendance.record'
        ].sudo()
        GradeEntry = request.env[
            'unicore.grade.entry'
        ].sudo()

        # Build per-student data
        student_data = []
        for enr in enrollments:
            att_records = AttRecord.search([
                ('student_id', '=', enr.student_id.id),
                ('course_offering_id', '=', offering.id),
            ], limit=1)
            grade = GradeEntry.search([
                ('enrollment_id', '=', enr.id),
            ], limit=1)
            att_pct = (
                att_records[0]
                .cumulative_attendance_percentage
                if att_records else 0.0
            )
            shortage = (
                att_records[0].shortage_alert
                if att_records else False
            )
            student_data.append({
                'enrollment': enr,
                'student': enr.student_id,
                'attendance_pct': att_pct,
                'shortage_alert': shortage,
                'grade': grade,
                'grade_state': (
                    grade.entry_state if grade else 'none'
                ),
                'internal_marks': (
                    grade.internal_marks if grade else 0.0
                ),
                'letter_grade': (
                    grade.letter_grade if grade else '-'
                ),
            })

        # Open sessions for this offering
        Session = request.env[
            'unicore.attendance.session'
        ].sudo()
        open_sessions = Session.search([
            ('timetable_entry_id.course_offering_id',
             '=', offering.id),
            ('session_state', '=', 'open'),
        ])

        values = {
            'faculty': faculty,
            'offering': offering,
            'student_data': student_data,
            'open_sessions': open_sessions,
            'page_name': 'faculty_course_detail',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_course_detail',
            values,
        )

    # ===================================================
    # ROUTE 5: ATTENDANCE MARKING (GET -- show form)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/attendance/'
        '<int:session_id>',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_attendance_session(self, session_id,
                                    **kwargs):
        """
        Show attendance marking form for an open session.
        Faculty can mark present/absent/late for each
        enrolled student.
        """
        faculty = self._faculty_required()

        Session = request.env[
            'unicore.attendance.session'
        ].sudo()
        session = Session.browse(session_id)

        if not session.exists():
            raise NotFound()
        if session.session_state != 'open':
            return request.render(
                'unicore_portal_faculty'
                '.portal_faculty_session_closed',
                {
                    'faculty': faculty,
                    'session': session,
                    'page_name': 'faculty_attendance',
                },
            )

        # Verify faculty owns this session
        offering = (
            session.timetable_entry_id
            .course_offering_id
        )
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You are not the instructor for '
                  'this session.'),
            )

        AttRecord = request.env[
            'unicore.attendance.record'
        ].sudo()
        records = AttRecord.search([
            ('session_id', '=', session.id),
        ], order='student_id')

        # Build student list with existing status
        Enrollment = request.env[
            'unicore.enrollment'
        ].sudo()
        enrollments = Enrollment.search([
            ('course_offering_id', '=', offering.id),
            ('enrollment_state', '=', 'registered'),
        ], order='student_id')

        att_map = {
            r.student_id.id: r for r in records
        }

        values = {
            'faculty': faculty,
            'session': session,
            'offering': offering,
            'enrollments': enrollments,
            'att_map': att_map,
            'page_name': 'faculty_attendance',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_attendance_form',
            values,
        )

    # ===================================================
    # ROUTE 6: ATTENDANCE MARKING (POST -- save)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/attendance/'
        '<int:session_id>/save',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def faculty_attendance_save(self, session_id,
                                 **kwargs):
        """
        Process attendance form submission.
        Creates or updates attendance records.
        """
        faculty = self._faculty_required()

        Session = request.env[
            'unicore.attendance.session'
        ].sudo()
        session = Session.browse(session_id)

        if not session.exists():
            raise NotFound()
        if session.session_state != 'open':
            return request.redirect(
                '/my/unicore/faculty',
            )

        offering = (
            session.timetable_entry_id
            .course_offering_id
        )
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You are not the instructor for '
                  'this session.'),
            )

        AttRecord = request.env[
            'unicore.attendance.record'
        ].sudo()
        Enrollment = request.env[
            'unicore.enrollment'
        ].sudo()

        enrollments = Enrollment.search([
            ('course_offering_id', '=', offering.id),
            ('enrollment_state', '=', 'registered'),
        ])

        for enr in enrollments:
            student_id = enr.student_id.id
            status_key = 'status_%d' % student_id
            late_key = 'late_%d' % student_id
            status = kwargs.get(status_key, 'absent')
            late_minutes = int(
                kwargs.get(late_key, 0) or 0,
            )

            existing = AttRecord.search([
                ('session_id', '=', session.id),
                ('student_id', '=', student_id),
            ], limit=1)

            if existing:
                existing.write({
                    'status': status,
                    'late_minutes': (
                        late_minutes
                        if status == 'late' else 0
                    ),
                })
            else:
                AttRecord.create({
                    'session_id': session.id,
                    'student_id': student_id,
                    'enrollment_id': enr.id,
                    'status': status,
                    'late_minutes': (
                        late_minutes
                        if status == 'late' else 0
                    ),
                })

        return request.redirect(
            '/my/unicore/faculty/courses/%d'
            % offering.id,
        )

    # ===================================================
    # ROUTE 7: GRADE ENTRY (GET -- show form)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/grades/'
        '<int:offering_id>',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_grade_entry(self, offering_id,
                             **kwargs):
        """
        Grade entry form for all students in one course.
        Faculty can enter internal marks and remarks.
        """
        faculty = self._faculty_required()

        Offering = request.env[
            'unicore.course.offering'
        ].sudo()
        offering = Offering.browse(offering_id)

        if not offering.exists():
            raise NotFound()
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Enrollment = request.env[
            'unicore.enrollment'
        ].sudo()
        GradeEntry = request.env[
            'unicore.grade.entry'
        ].sudo()

        enrollments = Enrollment.search([
            ('course_offering_id', '=', offering.id),
            ('enrollment_state', '=', 'registered'),
        ], order='student_id')

        grade_map = {}
        for enr in enrollments:
            grade = GradeEntry.search([
                ('enrollment_id', '=', enr.id),
            ], limit=1)
            grade_map[enr.id] = grade

        values = {
            'faculty': faculty,
            'offering': offering,
            'enrollments': enrollments,
            'grade_map': grade_map,
            'page_name': 'faculty_grades',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_grade_form',
            values,
        )

    # ===================================================
    # ROUTE 8: GRADE ENTRY (POST -- save)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/grades/'
        '<int:offering_id>/save',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def faculty_grade_save(self, offering_id,
                            **kwargs):
        """
        Save grade entries submitted via faculty portal.
        Creates or updates grade records.
        Faculty can save as draft or submit directly.
        """
        faculty = self._faculty_required()

        Offering = request.env[
            'unicore.course.offering'
        ].sudo()
        offering = Offering.browse(offering_id)

        if not offering.exists():
            raise NotFound()
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Enrollment = request.env[
            'unicore.enrollment'
        ].sudo()
        GradeEntry = request.env[
            'unicore.grade.entry'
        ].sudo()

        enrollments = Enrollment.search([
            ('course_offering_id', '=', offering.id),
            ('enrollment_state', '=', 'registered'),
        ])

        action = kwargs.get('action', 'save')

        for enr in enrollments:
            enr_id = enr.id
            internal_key = 'internal_%d' % enr_id
            external_key = 'external_%d' % enr_id
            remarks_key = 'remarks_%d' % enr_id

            try:
                internal = float(
                    kwargs.get(internal_key, 0) or 0,
                )
                external = float(
                    kwargs.get(external_key, 0) or 0,
                )
            except (ValueError, TypeError):
                internal = 0.0
                external = 0.0

            remarks = kwargs.get(remarks_key, '') or ''

            existing = GradeEntry.search([
                ('enrollment_id', '=', enr_id),
            ], limit=1)

            entry_state = (
                'submitted' if action == 'submit'
                else 'draft'
            )

            if existing:
                if existing.entry_state in (
                    'draft', 'submitted',
                ):
                    existing.write({
                        'internal_marks': internal,
                        'external_marks': external,
                        'faculty_remarks': remarks,
                        'entry_state': entry_state,
                    })
            else:
                GradeEntry.create({
                    'enrollment_id': enr_id,
                    'internal_marks': internal,
                    'external_marks': external,
                    'faculty_remarks': remarks,
                    'entry_state': entry_state,
                })

        return request.redirect(
            '/my/unicore/faculty/courses/%d'
            % offering_id,
        )

    # ===================================================
    # ROUTE 9: MY EXAMS
    # ===================================================

    @http.route(
        '/my/unicore/faculty/exams',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_exams(self, **kwargs):
        """
        Exams where faculty is chief invigilator
        or assigned invigilator.
        """
        faculty = self._faculty_required()

        ExamSchedule = request.env[
            'unicore.exam.schedule'
        ].sudo()
        exams = ExamSchedule.search([
            '|',
            ('chief_invigilator_id', '=', faculty.id),
            ('invigilator_ids', 'in', [faculty.id]),
            ('exam_state', 'not in', ['cancelled']),
        ], order='exam_date desc')

        values = {
            'faculty': faculty,
            'exams': exams,
            'page_name': 'faculty_exams',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_exams',
            values,
        )

    # ===================================================
    # ROUTE 10: MY PROFILE
    # ===================================================

    @http.route(
        '/my/unicore/faculty/profile',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_profile(self, **kwargs):
        """
        Faculty profile view with qualifications,
        publications and workload summary.
        """
        faculty = self._faculty_required()

        values = {
            'faculty': faculty,
            'qualifications': (
                faculty.qualification_ids.sorted(
                    key=lambda q: q.year_of_completion
                    or 0, reverse=True,
                )
            ),
            'publications': (
                faculty.publication_ids.sorted(
                    key=lambda p: p.publication_year
                    or 0, reverse=True,
                )
                if hasattr(faculty, 'publication_ids')
                else []
            ),
            'page_name': 'faculty_profile',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_profile',
            values,
        )

    # ===================================================
    # ROUTE: MY NOTICES
    # ===================================================

    @http.route(
        '/my/unicore/faculty/notices',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_notices(self, page=1, date_begin=None, date_end=None, **kwargs):
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        Notice = request.env['unicore.notice'].sudo()
        notices = Notice.search([
            ('publisher_id', '!=', False),
        ], order='pinned desc, publish_date desc')

        today = date.today()
        notices = notices.filtered(
            lambda n: not n.expiry_date or n.expiry_date >= today,
        )

        faculty_campus_ids = faculty.campus_ids.ids if faculty else []
        notices = notices.filtered(
            lambda n: n.audience == 'all'
            or (n.audience == 'faculty')
            or (n.audience == 'specific'
                and any(c.id in faculty_campus_ids for c in n.campus_ids)),
        )

        notice_count = len(notices)
        pager = portal_pager(
            url='/my/unicore/faculty/notices',
            total=notice_count,
            page=page,
            step=20,
        )
        notices = notices[(pager['offset']):(pager['offset'] + pager['step'])]

        values = {
            'faculty': faculty,
            'notices': notices,
            'page_name': 'faculty_notices',
            'pager': pager,
            'date_begin': date_begin,
            'date_end': date_end,
        }
        return request.render(
            'unicore_notice_board.portal_faculty_notices',
            values,
        )

    # ===================================================
    # ROUTE: MY ASSIGNMENTS (list per offering)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/assignments',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_assignments(self, **kwargs):
        """
        List all assignments grouped by course offering for
        the current faculty member, with submission stats.
        """
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        offerings = self._get_faculty_offerings(faculty)
        offering_ids = offerings.ids

        Assignment = request.env['unicore.assignment'].sudo()
        assignments = Assignment.search([
            ('course_offering_id', 'in', offering_ids),
        ], order='due_date desc')

        # group by offering
        offering_data = []
        for offering in offerings:
            off_assignments = assignments.filtered(
                lambda a: a.course_offering_id.id == offering.id,
            )
            offering_data.append({
                'offering': offering,
                'assignments': off_assignments,
                'assignment_count': len(off_assignments),
            })

        values = {
            'faculty': faculty,
            'offerings': offerings,
            'offering_data': offering_data,
            'assignments': assignments,
            'total_assignments': len(assignments),
            'pending_grading': assignments.mapped(
                'submission_ids',
            ).filtered(
                lambda s: s.state in ('submitted', 'late'),
            ),
            'page_name': 'faculty_assignments',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_assignments',
            values,
        )

    # ===================================================
    # ROUTE: CREATE ASSIGNMENT (GET — form)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/assignments/new/'
        '<int:offering_id>',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_assignment_create(self, offering_id,
                                   **kwargs):
        """
        Create a new assignment for a course offering.
        """
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        Offering = request.env[
            'unicore.course.offering'
        ].sudo()
        offering = Offering.browse(offering_id)
        if not offering.exists():
            raise NotFound()
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Rubric = request.env['unicore.assignment.rubric'].sudo()
        rubrics = Rubric.search([
            ('company_id', '=', offering.company_id.id),
        ])

        values = {
            'faculty': faculty,
            'offering': offering,
            'rubrics': rubrics,
            'assignment_types': [
                ('homework', 'Homework'),
                ('project', 'Project'),
                ('lab', 'Lab'),
                ('quiz', 'Quiz'),
            ],
            'page_name': 'faculty_assignment_create',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_assignment_create',
            values,
        )

    # ===================================================
    # ROUTE: CREATE ASSIGNMENT (POST — save)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/assignments/new/'
        '<int:offering_id>/save',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def faculty_assignment_create_save(self, offering_id,
                                        **kwargs):
        """
        Save a newly created assignment and optionally
        publish it immediately.
        """
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        Offering = request.env[
            'unicore.course.offering'
        ].sudo()
        offering = Offering.browse(offering_id)
        if not offering.exists():
            raise NotFound()
        if offering.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        title = (kwargs.get('title') or '').strip()
        if not title:
            raise UserError(_('Title is required.'))

        try:
            max_marks = float(kwargs.get('max_marks') or 0)
        except (ValueError, TypeError):
            max_marks = 0.0
        try:
            pass_marks = float(kwargs.get('pass_marks') or 0)
        except (ValueError, TypeError):
            pass_marks = 0.0

        due_date_str = kwargs.get('due_date')
        due_date = False
        if due_date_str:
            try:
                due_date = datetime.strptime(
                    due_date_str, '%Y-%m-%d',
                ).date()
            except ValueError:
                due_date = False
        if not due_date:
            raise UserError(_('A valid due date is required.'))

        assignment_type = kwargs.get('assignment_type') or 'homework'
        description = kwargs.get('description') or ''
        rubric_id = kwargs.get('rubric_id')
        due_time = kwargs.get('due_time') or '23:59'

        assignment_vals = {
            'title': title,
            'description': description,
            'assignment_type': assignment_type,
            'max_marks': max_marks,
            'pass_marks': pass_marks,
            'due_date': due_date,
            'due_time': due_time,
            'course_offering_id': offering.id,
            'is_late_submission_allowed': bool(
                kwargs.get('is_late_submission_allowed'),
            ),
            'late_penalty_percent': float(
                kwargs.get('late_penalty_percent') or 0,
            ),
        }
        if rubric_id:
            assignment_vals['rubric_id'] = int(rubric_id)

        action = kwargs.get('action', 'save')
        if action == 'publish':
            assignment_vals['assignment_state'] = 'published'

        Assignment = request.env['unicore.assignment'].sudo()
        assignment = Assignment.create(assignment_vals)

        if action == 'publish':
            try:
                assignment._notify_students()
            except Exception as e:
                _logger.error(
                    'Assignment notify failed: %s', str(e),
                )

        return request.redirect(
            '/my/unicore/faculty/assignments/%d'
            % assignment.id,
        )

    # ===================================================
    # ROUTE: ASSIGNMENT DETAIL (submissions list)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/assignments/'
        '<int:assignment_id>',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_assignment_detail(self, assignment_id,
                                   **kwargs):
        """
        Detail view of an assignment with the list of
        student submissions and grading status.
        """
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        Assignment = request.env['unicore.assignment'].sudo()
        assignment = Assignment.browse(assignment_id)
        if not assignment.exists():
            raise NotFound()
        if assignment.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Enrollment = request.env['unicore.enrollment'].sudo()
        enrollments = Enrollment.search([
            ('course_offering_id', '=',
             assignment.course_offering_id.id),
            ('enrollment_state', '=', 'registered'),
        ], order='student_id')

        Submission = request.env[
            'unicore.assignment.submission'
        ].sudo()
        submissions = Submission.search([
            ('assignment_id', '=', assignment.id),
        ])
        submission_map = {
            s.student_id.id: s for s in submissions
        }

        values = {
            'faculty': faculty,
            'assignment': assignment,
            'enrollments': enrollments,
            'submission_map': submission_map,
            'submissions': submissions,
            'page_name': 'faculty_assignment_detail',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_assignment_detail',
            values,
        )

    # ===================================================
    # ROUTE: GRADE SUBMISSION (GET — form)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/assignments/'
        '<int:assignment_id>/grade/<int:submission_id>',
        type='http',
        auth='user',
        website=True,
    )
    def faculty_assignment_grade(self, assignment_id,
                                  submission_id, **kwargs):
        """
        Grade form for a single submission. Shows marks,
        feedback, rubric criteria and annotation JSON input.
        """
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        Assignment = request.env['unicore.assignment'].sudo()
        assignment = Assignment.browse(assignment_id)
        if not assignment.exists():
            raise NotFound()
        if assignment.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Submission = request.env[
            'unicore.assignment.submission'
        ].sudo()
        submission = Submission.browse(submission_id)
        if not submission.exists() or (
                submission.assignment_id.id != assignment.id):
            raise NotFound()

        # Pre-populate rubric evaluation lines if rubric present
        if (assignment.rubric_id
                and not submission.rubric_evaluation_ids):
            commands = []
            for criterion in assignment.rubric_id.criterion_ids:
                commands.append((0, 0, {
                    'criterion_id': criterion.id,
                    'points_awarded': 0.0,
                }))
            submission.rubric_evaluation_ids = commands

        try:
            annotations = submission.get_annotations()
        except Exception:
            annotations = []

        values = {
            'faculty': faculty,
            'assignment': assignment,
            'submission': submission,
            'annotations': annotations,
            'page_name': 'faculty_assignment_grade',
        }
        return request.render(
            'unicore_portal_faculty'
            '.portal_faculty_assignment_grade',
            values,
        )

    # ===================================================
    # ROUTE: GRADE SUBMISSION (POST — save)
    # ===================================================

    @http.route(
        '/my/unicore/faculty/assignments/'
        '<int:assignment_id>/grade/<int:submission_id>/save',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def faculty_assignment_grade_save(self, assignment_id,
                                       submission_id,
                                       **kwargs):
        """
        Save the grading of a submission: marks, feedback,
        rubric evaluation and annotations.
        """
        faculty = self._faculty_required()
        if not isinstance(
            faculty,
            request.env['unicore.faculty.member'].__class__,
        ):
            return faculty

        Assignment = request.env['unicore.assignment'].sudo()
        assignment = Assignment.browse(assignment_id)
        if not assignment.exists():
            raise NotFound()
        if assignment.faculty_member_id.id != faculty.id:
            raise AccessError(
                _('You do not teach this course.'),
            )

        Submission = request.env[
            'unicore.assignment.submission'
        ].sudo()
        submission = Submission.browse(submission_id)
        if not submission.exists() or (
                submission.assignment_id.id != assignment.id):
            raise NotFound()

        try:
            marks = float(kwargs.get('marks_obtained') or 0)
        except (ValueError, TypeError):
            marks = 0.0
        feedback = kwargs.get('feedback') or ''

        # Rubric evaluation
        rubric_eval_vals = []
        for key, value in kwargs.items():
            if key.startswith('criterion_'):
                criterion_id = int(key.split('_')[1])
                try:
                    points = float(value or 0)
                except (ValueError, TypeError):
                    points = 0.0
                rubric_eval_vals.append((criterion_id, points))

        existing_eval = {
            line.criterion_id.id: line
            for line in submission.rubric_evaluation_ids
        }
        for criterion_id, points in rubric_eval_vals:
            if criterion_id in existing_eval:
                existing_eval[criterion_id].write({
                    'points_awarded': points,
                })
            else:
                submission.rubric_evaluation_ids = [
                    (0, 0, {
                        'criterion_id': criterion_id,
                        'points_awarded': points,
                    }),
                ]

        # If a rubric is used and no explicit marks given,
        # default marks to rubric points awarded
        if (assignment.rubric_id
                and kwargs.get('marks_obtained') in (None, '')):
            marks = submission.rubric_points_awarded

        # Annotations (JSON text)
        annotations_raw = kwargs.get('annotations') or ''
        try:
            annotation_list = json.loads(annotations_raw) \
                if annotations_raw.strip() else []
            if not isinstance(annotation_list, list):
                annotation_list = []
        except (ValueError, TypeError):
            annotation_list = []

        submission.write({
            'marks_obtained': marks,
            'feedback': feedback,
            'annotations': json.dumps(
                annotation_list, ensure_ascii=False,
            ) if annotation_list else False,
        })

        # Set graded state and notify the student (action_grade
        # also records graded_by / graded_date).
        try:
            submission.action_grade()
        except Exception as e:
            _logger.error('Grade finalize failed: %s', str(e))

        return request.redirect(
            '/my/unicore/faculty/assignments/%d'
            % assignment.id,
        )
