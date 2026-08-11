"""
UniCore Enrollment Model
The core record of a student's registration into a
specific course offering for a specific semester.
Implements the full 6-step validation chain:
offering availability, student eligibility,
prerequisite verification, duplicate prevention,
timetable conflict detection, and seat capacity
enforcement with automatic waitlist routing.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class UniCoreEnrollment(models.Model):
    _name = 'unicore.enrollment'
    _description = 'Student Course Enrollment'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'semester_id desc, student_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), "
               "('student_state', 'in', ['enrolled','active'])]",
    )

    course_offering_id = fields.Many2one(
        comodel_name='unicore.course.offering',
        string='Course Offering',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id', '=', company_id), "
               "('offering_state', '=', 'open')]",
    )

    course_id = fields.Many2one(
        comodel_name='unicore.course',
        string='Course',
        related='course_offering_id.course_id',
        store=True,
        readonly=True,
    )

    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        related='course_offering_id.semester_id',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='course_offering_id.company_id',
        store=True,
        readonly=True,
    )

    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        related='course_offering_id.campus_id',
        store=True,
        readonly=True,
    )

    # --- COHORT (from the enrolled student; Phase 7 rollup) ---
    # Stored relateds so enrollments can be searched / grouped by cohort.
    cohort_kind = fields.Selection(
        related='student_id.cohort_kind', string='Cohort Kind',
        readonly=True, store=True,
        help='Cohort kind of the enrolled student\'s program (Phase 7).',
    )
    grade_level_id = fields.Many2one(
        comodel_name='unicore.academic.unit', string='Grade Level',
        related='student_id.grade_level_id', readonly=True, store=True,
        help='Grade level of the enrolled student (K-12; Phase 7).',
    )
    cohort_start_date = fields.Date(
        string='Cohort Start Date', related='student_id.cohort_start_date',
        readonly=True, store=True,
        help='Intake / cohort start date of the enrolled student (Phase 7).',
    )
    batch_year = fields.Integer(
        string='Batch Year', related='student_id.batch_year',
        readonly=True, store=True,
        help='Batch year of the enrolled student (Phase 7).',
    )
    cohort_label = fields.Char(
        string='Cohort', compute='_compute_cohort_label',
        help='Human-readable cohort of the enrolled student (Phase 7).',
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['student_id', 'course_id'],
    )

    registration_date = fields.Datetime(
        string='Registration Date',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )

    registration_type = fields.Selection(
        string='Registration Type',
        required=True,
        default='self',
        selection=[
            ('self', 'Self Registration'),
            ('advisor', 'Advisor Assisted'),
            ('admin', 'Administrative Override'),
            ('waitlist_promotion', 'Promoted from Waitlist'),
        ],
    )

    registered_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Registered By',
        default=lambda self: self.env.uid,
        readonly=True,
    )

    # --- PROGRAM-LEVEL ENROLLMENT (Phase 3: admission pipeline) ---
    # Set when this course registration was created by the
    # 'Enroll in Program' wizard on a confirmed admission applicant.
    admission_enrollment_id = fields.Many2one(
        comodel_name='unicore.admission.enrollment',
        string='Program Enrollment',
        ondelete='set null', index=True,
        help='Program-level admission enrollment this course registration '
             'belongs to (created by the Enroll in Program wizard).',
    )

    prerequisite_check_passed = fields.Boolean(
        string='Prerequisites Satisfied',
        default=True,
        readonly=True,
        help='Result of automatic prerequisite validation '
             'performed at registration time',
    )

    prerequisite_check_notes = fields.Text(
        string='Prerequisite Check Notes',
        readonly=True,
    )

    schedule_conflict_checked = fields.Boolean(
        string='Schedule Checked',
        default=False,
        readonly=True,
    )

    grade_status = fields.Selection(
        string='Grade Status',
        default='in_progress',
        tracking=True,
        selection=[
            ('in_progress', 'In Progress'),
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('incomplete', 'Incomplete'),
            ('not_applicable', 'Not Applicable'),
        ],
        help='Placeholder for grading outcome. Full grade '
             'entry and GPA calculation is handled by the '
             'future unicore_grading module. This field '
             'allows prerequisite checks in THIS module to '
             'determine pass/fail status without circular '
             'dependency on a module that does not exist yet.',
    )

    final_grade_letter = fields.Char(
        string='Final Grade',
        readonly=True,
        help='Set by future unicore_grading module. '
             'Read-only here — this module does not compute grades.',
    )

    credit_hours = fields.Float(
        string='Credit Hours',
        related='course_id.credit_hours',
        store=True,
        readonly=True,
        digits=(4, 1),
    )

    enrollment_state = fields.Selection(
        string='Enrollment Status',
        required=True,
        default='registered',
        tracking=True,
        selection=[
            ('registered', 'Registered'),
            ('dropped', 'Dropped'),
            ('withdrawn', 'Withdrawn'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        help='Registered: actively enrolled. Dropped: removed before '
             'add/drop deadline (no record on transcript). Withdrawn: '
             'removed after deadline (recorded with W on transcript). '
             'Completed: semester finished, grade assigned. Cancelled: '
             'administrative cancellation.',
    )

    drop_date = fields.Date(
        string='Drop / Withdrawal Date',
        readonly=True,
    )

    drop_reason = fields.Text(
        string='Drop / Withdrawal Reason',
    )

    _sql_constraints = [
        (
            'unique_student_course_semester',
            'UNIQUE(student_id, course_id, semester_id)',
            'This student is already enrolled in this course '
            'for this semester.',
        ),
    ]

    @api.depends('student_id', 'course_id')
    def _compute_display_name(self):
        for rec in self:
            student_name = (
                rec.student_id.display_name if rec.student_id else ''
            )
            course_code = (
                rec.course_id.code if rec.course_id else ''
            )
            rec.display_name = '%s - %s' % (student_name, course_code)

    @api.depends('student_id.cohort_label')
    def _compute_cohort_label(self):
        for rec in self:
            rec.cohort_label = rec.student_id.cohort_label or ''

    def _check_prerequisites(self, student, course):
        """
        Returns tuple (passed: bool, notes: str)
        Checks all MANDATORY prerequisites for the given course
        have a 'pass' grade_status in a prior completed enrollment
        for this student.
        """
        Prerequisite = self.env['unicore.course.prerequisite']
        mandatory_prereqs = Prerequisite.search([
            ('course_id', '=', course.id),
            ('prerequisite_type', '=', 'mandatory'),
        ])
        if not mandatory_prereqs:
            return True, _('No mandatory prerequisites.')

        missing = []
        for prereq in mandatory_prereqs:
            passed_enrollment = self.search([
                ('student_id', '=', student.id),
                ('course_id', '=', prereq.prerequisite_course_id.id),
                ('grade_status', '=', 'pass'),
            ], limit=1)
            if not passed_enrollment:
                missing.append(prereq.prerequisite_course_id.code)

        if missing:
            return False, _('Missing prerequisite(s): %s') % ', '.join(missing)
        return True, _('All prerequisites satisfied.')

    def _check_schedule_conflict(self, student, offering):
        """
        Returns tuple (has_conflict: bool, notes: str)
        Compares the new offering's timetable entries against
        timetable entries of all offerings the student is ALREADY
        actively enrolled in for the SAME semester.
        """
        TimetableEntry = self.env['unicore.timetable.entry']
        new_entries = TimetableEntry.search([
            ('course_offering_id', '=', offering.id),
            ('entry_state', '!=', 'cancelled'),
        ])
        if not new_entries:
            return False, _('No timetable entries to check '
                            '(offering not yet scheduled).')

        existing_enrollments = self.search([
            ('student_id', '=', student.id),
            ('semester_id', '=', offering.semester_id.id),
            ('enrollment_state', '=', 'registered'),
        ])
        existing_offering_ids = existing_enrollments.mapped(
            'course_offering_id'
        ).ids
        if not existing_offering_ids:
            return False, _('No other active enrollments this semester.')

        existing_entries = TimetableEntry.search([
            ('course_offering_id', 'in', existing_offering_ids),
            ('entry_state', '!=', 'cancelled'),
        ])

        for new_entry in new_entries:
            for existing_entry in existing_entries:
                if (new_entry.day_of_week == existing_entry.day_of_week
                        and new_entry.time_slot_id == existing_entry.time_slot_id):
                    return True, _(
                        'Schedule conflict with course "%s" on %s at %s.'
                    ) % (
                        existing_entry.course_id.code,
                        dict(new_entry._fields['day_of_week'].selection).get(
                            new_entry.day_of_week
                        ),
                        new_entry.time_slot_id.name,
                    )
        return False, _('No schedule conflicts found.')

    @api.model_create_multi
    def create(self, vals_list):
        EnrollmentLog = self.env['unicore.enrollment.log'].sudo()
        Waitlist = self.env['unicore.enrollment.waitlist']

        created_records = self.browse()

        for vals in vals_list:
            student = self.env['unicore.student'].browse(vals.get('student_id'))
            offering = self.env['unicore.course.offering'].browse(
                vals.get('course_offering_id')
            )

            # STEP 1: Offering must be open
            if offering.offering_state != 'open':
                raise UserError(
                    _('Cannot enroll: course offering "%s" is not open '
                      'for enrollment (current status: %s).')
                    % (offering.display_name, offering.offering_state)
                )

            # STEP 2: Student eligibility
            if student.student_state not in ('enrolled', 'active'):
                raise UserError(
                    _('Cannot enroll: student "%s" has status "%s" which '
                      'is not eligible for course registration.')
                    % (student.display_name, student.student_state)
                )

            # STEP 3: Prerequisite check
            prereq_passed, prereq_notes = self._check_prerequisites(
                student, offering.course_id
            )
            vals['prerequisite_check_passed'] = prereq_passed
            vals['prerequisite_check_notes'] = prereq_notes
            if not prereq_passed and not self.env.context.get(
                'force_enrollment_override'
            ):
                raise UserError(
                    _('Cannot enroll: %s\n\nIf this is an authorized '
                      'exception, an administrator must use the '
                      'override option.') % prereq_notes
                )

            # STEP 4: Duplicate check (SQL constraint backup)
            duplicate = self.search([
                ('student_id', '=', student.id),
                ('course_id', '=', offering.course_id.id),
                ('semester_id', '=', offering.semester_id.id),
                ('enrollment_state', '!=', 'cancelled'),
            ], limit=1)
            if duplicate:
                raise UserError(
                    _('Student "%s" is already enrolled in "%s" '
                      'for this semester.')
                    % (student.display_name, offering.course_id.code)
                )

            # STEP 5: Schedule conflict check
            has_conflict, conflict_notes = self._check_schedule_conflict(
                student, offering
            )
            vals['schedule_conflict_checked'] = True
            if has_conflict and not self.env.context.get(
                'force_enrollment_override'
            ):
                raise UserError(_('Cannot enroll: %s') % conflict_notes)

            # STEP 6: Seat capacity check
            current_enrolled = self.search_count([
                ('course_offering_id', '=', offering.id),
                ('enrollment_state', 'in', ['registered', 'completed']),
            ])
            if current_enrolled >= offering.max_enrollment:
                if self.env.context.get('auto_waitlist', True):
                    position = Waitlist.search_count([
                        ('course_offering_id', '=', offering.id),
                        ('waitlist_state', '=', 'waiting'),
                    ]) + 1
                    Waitlist.create({
                        'student_id': student.id,
                        'course_offering_id': offering.id,
                        'position': position,
                    })
                    raise UserError(
                        _('Course offering "%s" is full. %s has been '
                          'added to the waitlist at position %d.')
                        % (offering.display_name, student.display_name, position)
                    )
                else:
                    raise UserError(
                        _('Cannot enroll: course offering "%s" has reached '
                          'maximum capacity.')
                        % offering.display_name
                    )

        created_records = super().create(vals_list)

        for rec in created_records:
            EnrollmentLog.create({
                'enrollment_id': rec.id,
                'student_id': rec.student_id.id,
                'course_offering_id': rec.course_offering_id.id,
                'action': 'registered',
                'action_date': fields.Datetime.now(),
                'performed_by_id': self.env.uid,
                'notes': _('Initial registration.'),
            })
            rec.message_post(
                body=_('Enrolled in %s.') % rec.course_id.display_name
            )

        return created_records

    def action_drop(self):
        self.ensure_one()
        semester = self.semester_id
        today = date.today()

        if semester.add_drop_end and today > semester.add_drop_end:
            raise UserError(
                _('The add/drop deadline (%s) has passed. Use Withdraw '
                  'instead, which will be recorded on the transcript.')
                % semester.add_drop_end
            )

        self.write({
            'enrollment_state': 'dropped',
            'drop_date': today,
        })
        self.env['unicore.enrollment.log'].sudo().create({
            'enrollment_id': self.id,
            'student_id': self.student_id.id,
            'course_offering_id': self.course_offering_id.id,
            'action': 'dropped',
            'action_date': fields.Datetime.now(),
            'performed_by_id': self.env.uid,
            'notes': self.drop_reason or _('No reason provided.'),
        })
        self.message_post(body=_('Course dropped on %s.') % today)
        self._promote_from_waitlist()

    def action_withdraw(self):
        self.ensure_one()
        today = date.today()

        self.write({
            'enrollment_state': 'withdrawn',
            'drop_date': today,
        })
        self.env['unicore.enrollment.log'].sudo().create({
            'enrollment_id': self.id,
            'student_id': self.student_id.id,
            'course_offering_id': self.course_offering_id.id,
            'action': 'withdrawn',
            'action_date': fields.Datetime.now(),
            'performed_by_id': self.env.uid,
            'notes': self.drop_reason or _('No reason provided.'),
        })
        self.message_post(
            body=_('Withdrawn from course on %s. This will appear '
                   'on the transcript.') % today
        )
        self._promote_from_waitlist()

    def action_complete(self):
        self.ensure_one()
        self.enrollment_state = 'completed'
        self.env['unicore.enrollment.log'].sudo().create({
            'enrollment_id': self.id,
            'student_id': self.student_id.id,
            'course_offering_id': self.course_offering_id.id,
            'action': 'completed',
            'action_date': fields.Datetime.now(),
            'performed_by_id': self.env.uid,
            'notes': _('Course marked as completed.'),
        })
        self.message_post(body=_('Course completed.'))

    def action_cancel(self):
        self.ensure_one()
        self.enrollment_state = 'cancelled'
        self.env['unicore.enrollment.log'].sudo().create({
            'enrollment_id': self.id,
            'student_id': self.student_id.id,
            'course_offering_id': self.course_offering_id.id,
            'action': 'cancelled',
            'action_date': fields.Datetime.now(),
            'performed_by_id': self.env.uid,
            'notes': _('Administrative cancellation.'),
        })
        self.message_post(body=_('Enrollment cancelled.'))
        self._promote_from_waitlist()

    def _promote_from_waitlist(self):
        """
        When a seat opens up, find the next waiting student and notify
        the registrar via chatter rather than auto-enrolling them.
        Auto-enrollment without consent is poor practice — registrar
        or student must confirm.
        """
        self.ensure_one()
        Waitlist = self.env['unicore.enrollment.waitlist']
        next_waiting = Waitlist.search([
            ('course_offering_id', '=', self.course_offering_id.id),
            ('waitlist_state', '=', 'waiting'),
        ], order='position asc', limit=1)
        if next_waiting:
            next_waiting.message_post(
                body=_('A seat has opened up in "%s". Please process '
                       'this waitlist entry for promotion to enrollment.')
                % self.course_offering_id.display_name
            )
            _logger.info(
                'Seat opened in offering %s — next waitlist candidate '
                'is student %s.',
                self.course_offering_id.offering_code,
                next_waiting.student_id.display_name,
            )
