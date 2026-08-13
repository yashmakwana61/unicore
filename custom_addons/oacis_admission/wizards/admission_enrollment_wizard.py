"""Enroll in Program wizard.

Turns a confirmed admission applicant into an enrolled (optionally active)
student with course registrations, all in one step:

1. Pick the target semester / term of the cycle's academic year (the picker is
   calendar-mode aware: it lists the semesters/terms of the cycle's academic
   year, defaulting to the first one).
2. The wizard pre-fills one line per mandatory Semester-1 curriculum course of
   the applicant's program, resolving the open offering for that course in the
   chosen semester (company + campus scoped).
3. Confirming enrolls the student (student_state enrolled, optionally active),
   creates a ``oacis.admission.enrollment`` record and delegates course
   registration to ``oacis.enrollment`` — full offerings auto-route to the
   waitlist, gaps and duplicates are reported in the chatter (never fatal).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AdmissionEnrollmentWizard(models.TransientModel):
    _name = 'oacis.admission.enrollment.wizard'
    _description = 'Enroll Applicant in Program'

    applicant_id = fields.Many2one(
        comodel_name='oacis.admission.applicant', string='Applicant',
        required=True, readonly=True,
    )
    student_id = fields.Many2one(
        comodel_name='oacis.student', string='Student',
        related='applicant_id.student_id', readonly=True,
    )
    cycle_id = fields.Many2one(
        comodel_name='oacis.admission.cycle', string='Admission Cycle',
        related='applicant_id.cycle_id', readonly=True,
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program', string='Program',
        related='applicant_id.program_id', readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus', string='Campus',
        related='applicant_id.campus_id', readonly=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year', string='Academic Year',
        related='cycle_id.academic_year_id', readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester', string='Semester / Term',
        required=True,
        domain="[('academic_year_id', '=', academic_year_id)]",
        help='Target semester / term for the first year of the program. For '
             'term-based (K-12) and rolling institutions, pick the relevant '
             'term of the cycle\'s academic year.',
    )
    activate_student = fields.Boolean(
        string='Activate Student', default=True,
        help='Also move the student to Active once enrolled. The wizard sets '
             'the current semester, which activation requires.',
    )
    line_ids = fields.One2many(
        comodel_name='oacis.admission.enrollment.wizard.line',
        inverse_name='wizard_id', string='Course Lines',
    )

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        """Seed the semester and the curriculum-based course lines.

        Odoo 19 dropped the ``_default_get`` hook; seeding is done by
        overriding ``default_get`` directly (still invoked on ``create``
        through ``_add_missing_default_values`` and by the web client).
        """
        res = super().default_get(fields_list)
        applicant_id = res.get('applicant_id') or self.env.context.get(
            'default_applicant_id')
        if not applicant_id:
            return res
        applicant = self.env['oacis.admission.applicant'].browse(
            applicant_id)
        year = applicant.cycle_id.academic_year_id
        if ('semester_id' in fields_list and not res.get('semester_id')
                and year):
            semester = self._first_semester(year)
            if semester:
                res['semester_id'] = semester.id
        if ('line_ids' in fields_list and not res.get('line_ids')
                and res.get('semester_id')):
            semester = self.env['oacis.semester'].browse(
                res['semester_id'])
            res['line_ids'] = self._prepare_line_commands(applicant, semester)
        return res

    @api.model
    def _first_semester(self, year):
        """Earliest semester/term of an academic year (calendar-aware)."""
        return year.semester_ids.sorted(
            key=lambda s: (s.sequence, s.date_start))[:1]

    # ------------------------------------------------------------------
    # Line preparation
    # ------------------------------------------------------------------

    def _get_curriculum_lines(self, applicant):
        """Mandatory Semester-1 curriculum lines of the applicant's program."""
        program = applicant.program_id
        curriculum = self.env['oacis.curriculum'].search([
            ('program_id', '=', program.id),
            ('is_current', '=', True),
        ], limit=1)
        if not curriculum:
            curriculum = self.env['oacis.curriculum'].search([
                ('program_id', '=', program.id),
            ], limit=1)
        if not curriculum:
            return self.env['oacis.curriculum.line']
        return curriculum.curriculum_line_ids.filtered(
            lambda line: line.is_mandatory and line.semester_number == 1,
        )

    def _resolve_offering(self, applicant, line, semester):
        """Open offering for a curriculum course in the target semester,
        scoped to the applicant's program, campus and company."""
        return self.env['oacis.course.offering'].search([
            ('course_id', '=', line.course_id.id),
            ('program_id', '=', applicant.program_id.id),
            ('semester_id', '=', semester.id),
            ('campus_id', '=', applicant.campus_id.id),
            ('company_id', '=', applicant.company_id.id),
            ('offering_state', '=', 'open'),
        ], limit=1)

    def _line_state(self, applicant, offering):
        """Per-line validation preview used before anything is created."""
        if not offering:
            return 'no_offering'
        if offering.enrolled_count >= offering.max_enrollment:
            return 'full'
        if applicant.student_id:
            duplicate = self.env['oacis.enrollment'].search_count([
                ('student_id', '=', applicant.student_id.id),
                ('course_id', '=', offering.course_id.id),
                ('semester_id', '=', offering.semester_id.id),
                ('enrollment_state', '!=', 'cancelled'),
            ])
            if duplicate:
                return 'duplicate'
        return 'resolved'

    @staticmethod
    def _line_warning(state):
        if state == 'no_offering':
            return _('No open offering for this course in the selected '
                     'semester. It will be skipped on confirm.')
        if state == 'full':
            return _('The open offering for this course is full. Confirm '
                     'will add the student to the waitlist.')
        if state == 'duplicate':
            return _('This student is already registered for this course in '
                     'the selected semester.')
        return False

    def _prepare_line_vals(self, applicant, line, semester):
        offering = self._resolve_offering(applicant, line, semester)
        state = self._line_state(applicant, offering)
        return {
            'curriculum_line_id': line.id,
            'course_id': line.course_id.id,
            'semester_number': line.semester_number,
            'offering_id': offering.id if offering else False,
            'offering_state': state,
            # Full lines stay checked so confirm routes them to the waitlist.
            'checked': state in ('resolved', 'full'),
            'warning': self._line_warning(state),
        }

    def _prepare_line_commands(self, applicant, semester):
        return [
            (0, 0, self._prepare_line_vals(applicant, line, semester))
            for line in self._get_curriculum_lines(applicant)
        ]

    @api.onchange('semester_id')
    def _onchange_semester_id(self):
        if not self.semester_id:
            self.line_ids = [(5, 0, 0)]
            return
        self.line_ids = [(5, 0, 0)]
        self.line_ids = self._prepare_line_commands(
            self.applicant_id, self.semester_id)

    def action_preview(self):
        """(Re)build the course lines for the selected semester."""
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        if self.semester_id:
            self.line_ids = self._prepare_line_commands(
                self.applicant_id, self.semester_id)
        return {'type': 'ir.actions.do_nothing'}

    # ------------------------------------------------------------------
    # Confirm
    # ------------------------------------------------------------------

    def action_confirm(self):
        self.ensure_one()
        applicant = self.applicant_id
        if applicant.state != 'confirmed':
            raise UserError(_(
                'Only confirmed applicants can be enrolled in a program.'))
        if not applicant.student_id:
            raise UserError(_(
                'No student record exists for this applicant. Confirm the '
                'admission first.'))
        if not self.semester_id:
            raise UserError(_('Please select a semester / term.'))

        student = applicant.student_id
        semester = self.semester_id

        # 1) Move the student up the ladder: admitted -> enrolled -> active.
        if student.student_state == 'admitted':
            student.action_enroll()
        student.write({'current_semester_id': semester.id})
        if (self.activate_student
                and student.student_state in ('enrolled', 'admitted')):
            student.action_activate()

        # 2) Create the program-level admission enrollment record.
        admission_enrollment = self.env[
            'oacis.admission.enrollment'].create({
                'applicant_id': applicant.id,
                'student_id': student.id,
                'cycle_id': applicant.cycle_id.id,
                'program_id': applicant.program_id.id,
                'campus_id': applicant.campus_id.id,
                'academic_year_id': semester.academic_year_id.id,
                'semester_id': semester.id,
                'company_id': applicant.company_id.id,
                'enrollment_state': 'pending',
            })

        # 3) Register courses, reusing the full enrollment validation chain.
        Enrollment = self.env['oacis.enrollment']
        messages = []
        created_count = 0
        for line in self.line_ids.filtered('checked'):
            if not line.offering_id:
                continue
            try:
                Enrollment.with_context(auto_waitlist=True).create({
                    'student_id': student.id,
                    'course_offering_id': line.offering_id.id,
                    'admission_enrollment_id': admission_enrollment.id,
                })
                created_count += 1
            except UserError as exc:
                # e.g. offering full (auto-waitlisted) or a conflict — the
                # message is recorded, the rest of the batch still proceeds.
                messages.append(_('%s: %s') % (line.course_id.code, exc))

        if created_count:
            admission_enrollment.write({'enrollment_state': 'enrolled'})

        if messages:
            admission_enrollment.message_post(
                body=_('Some courses could not be registered:<br/>- %s')
                % '<br/>- '.join(messages))

        # 4) Audit trail + chatter.
        summary = _(
            'Enrolled in program %(program)s for %(semester)s. '
            '%(count)d course registration(s) created.',
        ) % {
            'program': applicant.program_id.name,
            'semester': semester.name,
            'count': created_count,
        }
        admission_enrollment.message_post(body=summary)
        applicant.message_post(body=summary)
        student.message_post(body=summary)
        _logger.info(
            'Applicant %s enrolled in program %s (%s) — %d course '
            'registration(s).', applicant.application_number,
            applicant.program_id.code, semester.name, created_count,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Program Enrollment'),
            'res_model': 'oacis.admission.enrollment',
            'view_mode': 'form',
            'res_id': admission_enrollment.id,
        }


class AdmissionEnrollmentWizardLine(models.TransientModel):
    _name = 'oacis.admission.enrollment.wizard.line'
    _description = 'Enroll in Program Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='oacis.admission.enrollment.wizard',
        string='Wizard', required=True, ondelete='cascade',
    )
    curriculum_line_id = fields.Many2one(
        comodel_name='oacis.curriculum.line', string='Curriculum Line',
        readonly=True,
    )
    course_id = fields.Many2one(
        comodel_name='oacis.course', string='Course', required=True,
        readonly=True,
    )
    semester_number = fields.Integer(
        string='Program Semester', readonly=True,
    )
    offering_id = fields.Many2one(
        comodel_name='oacis.course.offering', string='Offering',
        readonly=True,
    )
    offering_state = fields.Selection(
        selection=[
            ('resolved', 'Offering Available'),
            ('no_offering', 'No Open Offering'),
            ('full', 'Offering Full'),
            ('duplicate', 'Already Enrolled'),
        ],
        string='Offering Status', readonly=True,
    )
    checked = fields.Boolean(string='Enroll', default=True)
    warning = fields.Char(string='Warning', readonly=True)
