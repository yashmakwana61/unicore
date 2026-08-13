"""
Oacis Course Offering Model
A course offering is a specific instance of a course
being delivered in a real calendar semester at a
specific campus by a specific faculty member.
This is the bridge between curriculum planning
and actual teaching operations.
Students enroll into course offerings
(handled by oacis_enrollment module).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisCourseOffering(models.Model):
    _name = 'oacis.course.offering'
    _description = 'Course Offering'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'semester_id, course_id'
    _check_company_auto = True

    # ------- CORE IDENTITY -------

    name = fields.Char(
        string='Offering Name',
        compute='_compute_name',
        store=True,
    )

    @api.depends('course_id', 'semester_id', 'section_code')
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.course_id:
                parts.append(rec.course_id.code)
            if rec.semester_id:
                parts.append(rec.semester_id.code)
            if rec.section_code:
                parts.append(rec.section_code)
            rec.name = ' / '.join(parts) if parts else '/'

    offering_code = fields.Char(
        string='Offering Code',
        readonly=True,
        copy=False,
        help='Auto-generated offering identifier',
    )
    section_code = fields.Char(
        string='Section / Group',
        size=10,
        help='Section identifier e.g. A, B, G1, G2',
    )

    # ------- COURSE & PROGRAM -------

    course_id = fields.Many2one(
        comodel_name='oacis.course',
        string='Course',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('course_state', 'in', ['approved','active']), ('company_id', '=', company_id)]",
    )
    curriculum_line_id = fields.Many2one(
        comodel_name='oacis.curriculum.line',
        string='Curriculum Line',
        ondelete='set null',
        help='Optional link to curriculum plan line',
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    semester_number = fields.Integer(
        string='Program Semester Number',
        help='Which semester of the program this offering is for',
    )

    # ------- CALENDAR -------

    academic_year_id = fields.Many2one(
        comodel_name='oacis.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    semester_id = fields.Many2one(
        comodel_name='oacis.semester',
        string='Semester',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('academic_year_id', '=', academic_year_id)]",
    )

    # ------- INSTITUTION -------

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus',
        string='Campus',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )

    # ------- FACULTY -------

    faculty_member_id = fields.Many2one(
        comodel_name='oacis.faculty.member',
        string='Primary Instructor',
        ondelete='set null',
        tracking=True,
        domain="[('company_id', '=', company_id), ('member_state', '=', 'active')]",
    )
    co_instructor_ids = fields.Many2many(
        comodel_name='oacis.faculty.member',
        relation='oacis_course_offering_co_instructor_rel',
        column1='offering_id',
        column2='faculty_member_id',
        string='Co-Instructors',
    )

    # ------- CAPACITY -------

    max_enrollment = fields.Integer(
        string='Maximum Enrollment',
        default=40,
        help='Maximum students allowed in this offering',
    )
    min_enrollment = fields.Integer(
        string='Minimum Enrollment',
        default=5,
        help='Minimum students required to run this offering',
    )
    enrolled_count = fields.Integer(
        string='Enrolled Students',
        default=0,
        help='Updated by oacis_enrollment module',
    )
    available_seats = fields.Integer(
        string='Available Seats',
        compute='_compute_available_seats',
        store=False,
    )
    is_full = fields.Boolean(
        string='Section Full',
        compute='_compute_is_full',
        store=True,
    )

    @api.depends('max_enrollment', 'enrolled_count')
    def _compute_available_seats(self):
        for rec in self:
            rec.available_seats = max(
                0,
                rec.max_enrollment - rec.enrolled_count,
            )

    @api.depends('max_enrollment', 'enrolled_count')
    def _compute_is_full(self):
        for rec in self:
            rec.is_full = (
                rec.enrolled_count >= rec.max_enrollment
            )

    # ------- CREDIT & MARKS -------

    credit_hours = fields.Float(
        string='Credit Hours',
        related='course_id.credit_hours',
        store=True,
        readonly=True,
        digits=(4, 1),
    )

    # ------- STATUS -------

    offering_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('open', 'Open for Enrollment'),
            ('ongoing', 'Ongoing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Offering Status',
        required=True,
        default='draft',
        tracking=True,
    )
    cancellation_reason = fields.Text(
        string='Cancellation Reason',
    )

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_offering_code',
            'UNIQUE(offering_code)',
            'Offering code must be globally unique.',
        ),
        (
            'unique_course_section_semester',
            'UNIQUE(course_id, semester_id, section_code, program_id)',
            'This course section already exists for this semester and program.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('max_enrollment', 'min_enrollment')
    def _check_enrollment_limits(self):
        for rec in self:
            if rec.max_enrollment < 1:
                raise ValidationError(
                    _('Maximum enrollment must be at least 1.'),
                )
            if rec.min_enrollment < 0:
                raise ValidationError(
                    _('Minimum enrollment cannot be negative.'),
                )
            if rec.min_enrollment > rec.max_enrollment:
                raise ValidationError(
                    _('Minimum enrollment cannot exceed maximum enrollment.'),
                )

    @api.constrains('semester_id', 'academic_year_id')
    def _check_semester_in_year(self):
        for rec in self:
            if (rec.semester_id
                    and rec.academic_year_id
                    and rec.semester_id.academic_year_id
                    != rec.academic_year_id):
                raise ValidationError(
                    _('Selected semester does not belong to the selected academic year.'),
                )

    # ------- CREATE OVERRIDE -------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('offering_code'):
                vals['offering_code'] = (
                    self.env['ir.sequence'].next_by_code(
                        'oacis.course.offering',
                    ) or '/'
                )
        return super().create(vals_list)

    # ------- ONCHANGE -------

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        self.semester_id = False

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id:
            if not self.max_enrollment:
                self.max_enrollment = 40

    # ------- STATE METHODS -------

    def action_open_enrollment(self):
        self.ensure_one()
        if self.offering_state != 'draft':
            raise UserError(
                _('Only draft offerings can be opened for enrollment.'),
            )
        if not self.faculty_member_id:
            raise UserError(
                _('Please assign a primary instructor before opening enrollment.'),
            )
        self.offering_state = 'open'
        self.message_post(
            body=_('Course offering opened for enrollment.'),
        )

    def action_start(self):
        self.ensure_one()
        if self.enrolled_count < self.min_enrollment:
            _logger.warning(
                'Offering %s started with %d students '
                '(below minimum of %d).',
                self.offering_code,
                self.enrolled_count,
                self.min_enrollment,
            )
        self.offering_state = 'ongoing'
        self.message_post(
            body=_('Course offering started. %d students enrolled.')
                 % self.enrolled_count,
        )

    def action_complete(self):
        self.ensure_one()
        self.offering_state = 'completed'
        self.message_post(
            body=_('Course offering marked as completed.'),
        )

    def action_cancel(self):
        self.ensure_one()
        if not self.cancellation_reason:
            raise UserError(
                _('Please provide a cancellation reason before cancelling this offering.'),
            )
        self.offering_state = 'cancelled'
        self.message_post(
            body=_('Course offering cancelled. Reason: %s')
                 % self.cancellation_reason,
        )

    def action_reset_draft(self):
        self.ensure_one()
        if self.offering_state == 'completed':
            raise UserError(
                _('Completed offerings cannot be reset to draft.'),
            )
        self.offering_state = 'draft'
        self.message_post(
            body=_('Course offering reset to Draft.'),
        )
