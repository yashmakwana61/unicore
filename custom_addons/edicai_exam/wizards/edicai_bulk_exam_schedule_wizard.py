from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EdicaiBulkExamScheduleWizard(models.TransientModel):
    _name = 'edicai.bulk.exam.schedule.wizard'
    _description = 'Bulk Exam Schedule Wizard'

    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
    )
    semester_id = fields.Many2one(
        'edicai.semester',
        string='Semester',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    campus_id = fields.Many2one(
        'edicai.campus',
        string='Campus',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    program_id = fields.Many2one(
        'edicai.program',
        string='Program / Grade',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    exam_type_selection = fields.Selection(
        selection=[
            ('midterm', 'Midterm Exam'),
            ('final', 'Final Exam'),
            ('supplementary', 'Supplementary / Makeup'),
            ('quiz', 'Quiz'),
            ('practical', 'Practical Exam'),
            ('viva', 'Viva Voce'),
            ('assignment', 'Assignment Based'),
            ('other', 'Other'),
        ],
        string='Exam Type',
        required=True,
        default='final',
    )
    exam_date = fields.Date(
        string='Default Exam Date',
        required=True,
        default=fields.Date.context_today,
    )
    exam_start_time = fields.Float(
        string='Default Start Time',
        required=True,
        default=9.0,
    )
    exam_end_time = fields.Float(
        string='Default End Time',
        required=True,
        default=12.0,
    )
    exam_max_marks = fields.Float(
        string='Default Exam Maximum Marks',
        required=True,
        default=60.0,
    )
    line_ids = fields.One2many(
        'edicai.bulk.exam.schedule.wizard.line',
        'wizard_id',
        string='Subject Schedules',
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.semester_id.company_id != self.company_id:
            self.semester_id = False
        if self.campus_id.company_id != self.company_id:
            self.campus_id = False
        if self.program_id.company_id != self.company_id:
            self.program_id = False

    def action_load_offerings(self):
        self.ensure_one()
        if (self.semester_id.company_id != self.company_id
                or self.campus_id.company_id != self.company_id
                or self.program_id.company_id != self.company_id):
            raise UserError(_(
                'The selected semester, campus and program must belong to '
                'the selected institution.'
            ))
        domain = [
            ('company_id', '=', self.company_id.id),
            ('semester_id', '=', self.semester_id.id),
            ('campus_id', '=', self.campus_id.id),
            ('program_id', '=', self.program_id.id),
            ('offering_state', 'in', ('open', 'ongoing', 'completed')),
        ]
        offerings = self.env['edicai.course.offering'].search(domain)
        existing = self.env['edicai.exam.schedule'].search([
            ('course_offering_id', 'in', offerings.ids),
            ('exam_type', '=', self.exam_type_selection),
        ])
        offerings -= existing.mapped('course_offering_id')
        if not offerings:
            raise UserError(_(
                'There are no eligible course offerings to schedule. '
                'Check the selected program, semester, campus and exam type; '
                'an exam of this type may already exist for each offering.'
            ))

        self.line_ids.unlink()
        self.env['edicai.bulk.exam.schedule.wizard.line'].create([
            {
                'wizard_id': self.id,
                'course_offering_id': offering.id,
                'exam_type': self.exam_type_selection,
                'exam_date': self.exam_date,
                'exam_start_time': self.exam_start_time,
                'exam_end_time': self.exam_end_time,
                'exam_max_marks': self.exam_max_marks,
            }
            for offering in offerings
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Exam Scheduling'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _check_schedule_conflicts(self):
        self.ensure_one()
        lines = self.line_ids
        for line in lines:
            offering = line.course_offering_id
            if (
                offering.company_id != self.company_id
                or offering.semester_id != self.semester_id
                or offering.campus_id != self.campus_id
                or offering.program_id != self.program_id
                or offering.offering_state not in ('open', 'ongoing', 'completed')
            ):
                raise ValidationError(_(
                    'The selected offering no longer matches this wizard. '
                    'Reload the offerings and try again.'
                ))
            if line.exam_type != self.exam_type_selection:
                raise ValidationError(_(
                    'The exam type changed after the offerings were loaded. '
                    'Reload the offerings and try again.'
                ))
            if line.exam_max_marks <= 0 or (
                offering.course_id.total_marks
                and line.exam_max_marks > offering.course_id.total_marks
            ):
                raise ValidationError(_(
                    'Enter positive maximum marks no greater than the total '
                    'marks for %(course)s.'
                ) % {'course': offering.course_id.display_name})

        for line in lines:
            if not line.venue_ids:
                raise ValidationError(_(
                    'Select at least one venue for %(course)s before creating '
                    'the exam schedule.'
                ) % {'course': line.course_offering_id.course_id.display_name})
            if not (0 <= line.exam_start_time < 24
                    and 0 <= line.exam_end_time <= 24
                    and line.exam_end_time > line.exam_start_time):
                raise ValidationError(_(
                    'Enter a valid time range for %(course)s. End time must '
                    'be after start time and within the same day.'
                ) % {'course': line.course_offering_id.course_id.display_name})
            invalid_venues = line.venue_ids.filtered(
                lambda room: room.campus_id != line.course_offering_id.campus_id
            )
            if invalid_venues:
                raise ValidationError(_(
                    'The selected venue for %(course)s must belong to '
                    'the offering campus.'
                ) % {'course': line.course_offering_id.course_id.display_name})
            invalid_invigilators = line.invigilator_ids.filtered(
                lambda faculty: faculty.company_id != self.company_id
            )
            if invalid_invigilators:
                raise ValidationError(_(
                    'Invigilators assigned to %(course)s must belong to '
                    'the selected institution.'
                ) % {'course': line.course_offering_id.course_id.display_name})

        existing_schedules = self.env['edicai.exam.schedule'].search([
            ('company_id', '=', self.company_id.id),
            ('exam_date', 'in', lines.mapped('exam_date')),
            ('exam_state', 'not in', ('cancelled', 'completed')),
        ])
        offering_ids = (
            lines.course_offering_id | existing_schedules.course_offering_id
        ).ids
        enrollments = self.env['edicai.enrollment'].search([
            ('course_offering_id', 'in', offering_ids),
            ('enrollment_state', '=', 'registered'),
        ])
        students_by_offering = {}
        for enrollment in enrollments:
            students_by_offering.setdefault(
                enrollment.course_offering_id.id, set(),
            ).add(enrollment.student_id.id)

        for index, line in enumerate(lines):
            for other in lines[index + 1:]:
                overlaps = (
                    line.exam_date == other.exam_date
                    and line.exam_start_time < other.exam_end_time
                    and other.exam_start_time < line.exam_end_time
                )
                if not overlaps:
                    continue
                shared_students = (
                    students_by_offering.get(line.course_offering_id.id, set())
                    & students_by_offering.get(other.course_offering_id.id, set())
                )
                if shared_students:
                    raise ValidationError(_(
                        '%(course_a)s and %(course_b)s overlap on %(date)s '
                        'for %(count)s learner(s). Adjust their date or time.'
                    ) % {
                        'course_a': line.course_offering_id.course_id.display_name,
                        'course_b': other.course_offering_id.course_id.display_name,
                        'date': line.exam_date,
                        'count': len(shared_students),
                    })
                shared_venues = line.venue_ids & other.venue_ids
                if shared_venues:
                    raise ValidationError(_(
                        'The same venue cannot host %(course_a)s and '
                        '%(course_b)s at overlapping times.'
                    ) % {
                        'course_a': line.course_offering_id.course_id.display_name,
                        'course_b': other.course_offering_id.course_id.display_name,
                    })
                shared_invigilators = line.invigilator_ids & other.invigilator_ids
                if shared_invigilators:
                    raise ValidationError(_(
                        'An invigilator cannot be assigned to %(course_a)s '
                        'and %(course_b)s at overlapping times.'
                    ) % {
                        'course_a': line.course_offering_id.course_id.display_name,
                        'course_b': other.course_offering_id.course_id.display_name,
                    })

            for other in existing_schedules.filtered(
                lambda schedule: schedule.exam_date == line.exam_date
                    and line.exam_start_time < schedule.exam_end_time
                    and schedule.exam_start_time < line.exam_end_time
            ):
                shared_students = (
                    students_by_offering.get(line.course_offering_id.id, set())
                    & students_by_offering.get(other.course_offering_id.id, set())
                )
                if shared_students:
                    raise ValidationError(_(
                        '%(course_a)s overlaps existing exam %(course_b)s '
                        'on %(date)s for %(count)s learner(s). Adjust the '
                        'date or time.'
                    ) % {
                        'course_a': line.course_offering_id.course_id.display_name,
                        'course_b': other.name,
                        'date': line.exam_date,
                        'count': len(shared_students),
                    })
                if line.venue_ids & other.venue_ids:
                    raise ValidationError(_(
                        'The venue assigned to %(course)s is already used '
                        'by %(exam)s at an overlapping time.'
                    ) % {
                        'course': line.course_offering_id.course_id.display_name,
                        'exam': other.name,
                    })
                if line.invigilator_ids & other.invigilator_ids:
                    raise ValidationError(_(
                        'An invigilator assigned to %(course)s is already '
                        'scheduled for %(exam)s at an overlapping time.'
                    ) % {
                        'course': line.course_offering_id.course_id.display_name,
                        'exam': other.name,
                    })

    def action_create_schedules(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Load course offerings before creating schedules.'))

        Schedule = self.env['edicai.exam.schedule']
        offering_ids = self.line_ids.course_offering_id.ids
        existing_offerings = Schedule.search([
            ('course_offering_id', 'in', offering_ids),
            ('exam_type', '=', self.exam_type_selection),
        ]).mapped('course_offering_id')
        duplicate_lines = self.line_ids.filtered(
            lambda line: line.course_offering_id in existing_offerings
        )
        if duplicate_lines:
            raise UserError(_(
                'An exam of this type already exists for: %s. Reload the '
                'offerings and remove those schedules before retrying.'
            ) % ', '.join(duplicate_lines.mapped(
                'course_offering_id.course_id.display_name'
            )))

        self._check_schedule_conflicts()
        selection = dict(Schedule._fields['exam_type'].selection)
        schedules = Schedule.create([
            {
                'name': _('%(type)s - %(offering)s') % {
                    'type': selection[line.exam_type],
                    'offering': line.course_offering_id.display_name,
                },
                'course_offering_id': line.course_offering_id.id,
                'company_id': self.company_id.id,
                'exam_type': line.exam_type,
                'exam_date': line.exam_date,
                'exam_start_time': line.exam_start_time,
                'exam_end_time': line.exam_end_time,
                'exam_max_marks': line.exam_max_marks,
                'venue_ids': [(6, 0, line.venue_ids.ids)],
                'invigilator_ids': [(6, 0, line.invigilator_ids.ids)],
            }
            for line in self.line_ids
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Created Exam Schedules'),
            'res_model': Schedule._name,
            'view_mode': 'list,form',
            'domain': [('id', 'in', schedules.ids)],
        }


class EdicaiBulkExamScheduleWizardLine(models.TransientModel):
    _name = 'edicai.bulk.exam.schedule.wizard.line'
    _description = 'Bulk Exam Schedule Wizard Line'
    _order = 'exam_date, exam_start_time, course_offering_id'

    wizard_id = fields.Many2one(
        'edicai.bulk.exam.schedule.wizard',
        required=True,
        ondelete='cascade',
    )
    course_offering_id = fields.Many2one(
        'edicai.course.offering',
        string='Subject / Offering',
        required=True,
        readonly=True,
    )
    campus_id = fields.Many2one(
        related='course_offering_id.campus_id',
        readonly=True,
    )
    exam_type = fields.Selection(
        related='wizard_id.exam_type_selection',
        readonly=True,
    )
    exam_date = fields.Date(
        string='Exam Date',
        required=True,
    )
    exam_start_time = fields.Float(
        string='Start Time',
        required=True,
    )
    exam_end_time = fields.Float(
        string='End Time',
        required=True,
    )
    exam_max_marks = fields.Float(
        string='Maximum Marks',
        required=True,
    )
    venue_ids = fields.Many2many(
        'edicai.room',
        string='Venues',
        domain="[('campus_id', '=', campus_id), "
               "('room_type', 'in', ['exam_hall', 'classroom', 'lecture_hall'])]",
    )
    invigilator_ids = fields.Many2many(
        'edicai.faculty.member',
        string='Invigilators',
        domain="[('company_id', '=', wizard_id.company_id), "
               "('member_state', '=', 'active')]",
    )
