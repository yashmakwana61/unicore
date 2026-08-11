"""UniCore Admission → Program Enrollment.

A single, program-level record tying an admission applicant (and the student
created on admission confirmation) to a concrete academic year + semester
enrollment into the program.

Course-level registrations are delegated to ``unicore.enrollment`` (one row
per course offering), linked back through ``admission_enrollment_id`` so the
registrar can see everything created by one 'Enroll in Program' step.
"""
from odoo import _, api, fields, models


class AdmissionEnrollment(models.Model):
    _name = 'unicore.admission.enrollment'
    _description = 'Program Enrollment (Admission Pipeline)'
    _inherit = ['unicore.mixin', 'unicore.sequence.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'enrollment_date desc, id desc'
    _check_company_auto = True
    _rec_name = 'name'

    name = fields.Char(
        string='Reference', readonly=True, copy=False,
        default=lambda self: _('New'), tracking=True,
    )
    applicant_id = fields.Many2one(
        comodel_name='unicore.admission.applicant', string='Applicant',
        required=True, ondelete='restrict', index=True, tracking=True,
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student', string='Student',
        required=True, ondelete='restrict', index=True, tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    cycle_id = fields.Many2one(
        comodel_name='unicore.admission.cycle', string='Admission Cycle',
        required=True, ondelete='restrict', tracking=True,
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program', string='Program',
        required=True, ondelete='restrict', tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus', string='Campus',
        required=True, ondelete='restrict', tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year', string='Academic Year',
        required=True, ondelete='restrict', tracking=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester', string='Semester / Term',
        required=True, ondelete='restrict', tracking=True,
        domain="[('academic_year_id', '=', academic_year_id)]",
    )
    enrollment_state = fields.Selection(
        string='Enrollment Status', required=True, default='pending',
        tracking=True,
        selection=[
            ('pending', 'Pending'),
            ('enrolled', 'Enrolled'),
            ('completed', 'Completed'),
            ('withdrawn', 'Withdrawn'),
            ('cancelled', 'Cancelled'),
        ],
        help='Pending: wizard opened but course registration not finished. '
             'Enrolled: student enrolled + registered to courses. Completed: '
             'program enrollment period closed.',
    )
    enrollment_date = fields.Date(
        string='Enrollment Date', default=fields.Date.today, tracking=True,
    )
    course_enrollment_ids = fields.One2many(
        comodel_name='unicore.enrollment',
        inverse_name='admission_enrollment_id',
        string='Course Enrollments',
    )
    course_enrollment_count = fields.Integer(
        string='Course Enrollments',
        compute='_compute_course_enrollment_count',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict', tracking=True,
    )

    @api.depends('course_enrollment_ids')
    def _compute_course_enrollment_count(self):
        for record in self:
            record.course_enrollment_count = len(record.course_enrollment_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                company_id = vals.get('company_id') or self.env.company.id
                seq = self._next_sequence(
                    'unicore.admission.enrollment', company_id=company_id
                ) or '/'
                vals['name'] = seq
        return super().create(vals_list)

    def action_mark_enrolled(self):
        """Manually mark the program enrollment as Enrolled."""
        for record in self:
            if record.enrollment_state == 'pending':
                record.write({'enrollment_state': 'enrolled'})

    def action_mark_completed(self):
        """Close the program enrollment period."""
        for record in self:
            if record.enrollment_state in ('pending', 'enrolled'):
                record.write({'enrollment_state': 'completed'})

    def action_cancel(self):
        for record in self:
            if record.enrollment_state != 'cancelled':
                record.write({'enrollment_state': 'cancelled'})

    def action_open_course_enrollments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Course Enrollments'),
            'res_model': 'unicore.enrollment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.course_enrollment_ids.ids)],
            'context': {
                'default_student_id': self.student_id.id,
                'default_admission_enrollment_id': self.id,
            },
        }

    def action_open_applicant(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Applicant'),
            'res_model': 'unicore.admission.applicant',
            'view_mode': 'form',
            'res_id': self.applicant_id.id,
        }

    def action_open_student(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Student'),
            'res_model': 'unicore.student',
            'view_mode': 'form',
            'res_id': self.student_id.id,
        }
