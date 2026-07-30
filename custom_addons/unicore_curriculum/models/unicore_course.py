"""
UniCore Course Model
Defines reusable academic course units that can be
assigned to multiple programs and offered in multiple
semesters. A course is the master definition —
independent of any specific program or semester.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class UniCoreCourse(models.Model):
    _name = 'unicore.course'
    _description = 'Academic Course Definition'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'code, name'
    _check_company_auto = True

    # ------- IDENTITY FIELDS -------

    name = fields.Char(
        string='Course Name',
        required=True,
        translate=True,
        tracking=True,
        help='e.g. Data Structures and Algorithms'
    )
    code = fields.Char(
        string='Course Code',
        required=True,
        size=20,
        tracking=True,
        help='e.g. CRS-CS-001, MATH-101'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True
    )
    course_category = fields.Selection(
        selection=[
            ('core', 'Core / Compulsory'),
            ('elective', 'Elective'),
            ('lab', 'Laboratory'),
            ('project', 'Project / Thesis'),
            ('seminar', 'Seminar'),
            ('internship', 'Internship'),
            ('audit', 'Audit Course'),
            ('remedial', 'Remedial'),
            ('language', 'Language Course'),
            ('general', 'General Education'),
        ],
        string='Course Category',
        required=True,
        default='core',
        tracking=True
    )
    course_type = fields.Selection(
        selection=[
            ('theory', 'Theory'),
            ('practical', 'Practical / Lab'),
            ('theory_practical', 'Theory + Practical'),
            ('online', 'Online'),
            ('blended', 'Blended Learning'),
            ('project', 'Project Based'),
            ('seminar', 'Seminar'),
        ],
        string='Delivery Type',
        required=True,
        default='theory'
    )
    department_id = fields.Many2one(
        comodel_name='unicore.department',
        string='Owning Department',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='Department that owns and maintains this course'
    )
    academic_faculty_id = fields.Many2one(
        comodel_name='unicore.faculty',
        string='Faculty / School',
        related='department_id.faculty_id',
        store=True,
        readonly=True
    )

    # ------- CREDIT FIELDS -------

    credit_hours = fields.Float(
        string='Credit Hours',
        required=True,
        default=3.0,
        digits=(4, 1),
        tracking=True,
        help='Total credit hours for this course'
    )
    theory_hours = fields.Float(
        string='Theory Hours / Week',
        default=3.0,
        digits=(4, 1)
    )
    lab_hours = fields.Float(
        string='Lab Hours / Week',
        default=0.0,
        digits=(4, 1)
    )
    tutorial_hours = fields.Float(
        string='Tutorial Hours / Week',
        default=0.0,
        digits=(4, 1)
    )
    total_contact_hours = fields.Float(
        string='Total Contact Hours / Week',
        compute='_compute_total_contact_hours',
        store=True,
        digits=(4, 1)
    )

    @api.depends('theory_hours', 'lab_hours', 'tutorial_hours')
    def _compute_total_contact_hours(self):
        for rec in self:
            rec.total_contact_hours = (
                rec.theory_hours
                + rec.lab_hours
                + rec.tutorial_hours
            )

    # ------- ASSESSMENT FIELDS -------

    has_internal_assessment = fields.Boolean(
        string='Has Internal Assessment',
        default=True
    )
    internal_assessment_marks = fields.Float(
        string='Internal Assessment Marks',
        default=40.0,
        digits=(5, 1)
    )
    external_assessment_marks = fields.Float(
        string='External / Exam Marks',
        default=60.0,
        digits=(5, 1)
    )
    total_marks = fields.Float(
        string='Total Marks',
        compute='_compute_total_marks',
        store=True,
        digits=(5, 1)
    )

    @api.depends('internal_assessment_marks', 'external_assessment_marks')
    def _compute_total_marks(self):
        for rec in self:
            rec.total_marks = (
                rec.internal_assessment_marks
                + rec.external_assessment_marks
            )

    passing_marks = fields.Float(
        string='Passing Marks',
        default=40.0,
        digits=(5, 1),
        help='Minimum marks required to pass this course'
    )
    passing_percentage = fields.Float(
        string='Passing Percentage',
        compute='_compute_passing_percentage',
        store=False,
        digits=(5, 2)
    )

    @api.depends('passing_marks', 'total_marks')
    def _compute_passing_percentage(self):
        for rec in self:
            if rec.total_marks > 0:
                rec.passing_percentage = (
                    rec.passing_marks / rec.total_marks * 100
                )
            else:
                rec.passing_percentage = 0.0

    is_graded = fields.Boolean(
        string='Graded Course',
        default=True,
        help='If False this course is Pass/Fail only'
    )

    # ------- CURRICULUM LINKS -------

    prerequisite_ids = fields.One2many(
        comodel_name='unicore.course.prerequisite',
        inverse_name='course_id',
        string='Prerequisites'
    )
    prerequisite_count = fields.Integer(
        string='Prerequisites',
        compute='_compute_prerequisite_count',
        store=True
    )

    @api.depends('prerequisite_ids')
    def _compute_prerequisite_count(self):
        for rec in self:
            rec.prerequisite_count = len(rec.prerequisite_ids)

    curriculum_line_ids = fields.One2many(
        comodel_name='unicore.curriculum.line',
        inverse_name='course_id',
        string='Curriculum Assignments'
    )
    program_count = fields.Integer(
        string='Used in Programs',
        compute='_compute_program_count',
        store=False
    )

    def _compute_program_count(self):
        for rec in self:
            rec.program_count = len(
                rec.curriculum_line_ids.mapped('curriculum_id.program_id')
            )

    offering_ids = fields.One2many(
        comodel_name='unicore.course.offering',
        inverse_name='course_id',
        string='Course Offerings'
    )
    offering_count = fields.Integer(
        string='Offerings',
        compute='_compute_offering_count',
        store=True
    )

    @api.depends('offering_ids')
    def _compute_offering_count(self):
        for rec in self:
            rec.offering_count = len(rec.offering_ids)

    # ------- CONTENT FIELDS -------

    description = fields.Html(
        string='Course Description'
    )
    syllabus = fields.Html(
        string='Syllabus / Course Outline'
    )
    learning_outcomes = fields.Html(
        string='Learning Outcomes'
    )
    reference_books = fields.Text(
        string='Reference Books / Materials'
    )

    # ------- STATUS FIELDS -------

    course_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('active', 'Active'),
            ('discontinued', 'Discontinued'),
        ],
        string='Course Status',
        required=True,
        default='draft',
        tracking=True
    )
    approved_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True
    )
    approved_on = fields.Date(
        string='Approved On',
        readonly=True
    )

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_course_code_company',
            'UNIQUE(code, company_id)',
            'Course code must be unique per institution.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('credit_hours')
    def _check_credit_hours(self):
        for rec in self:
            if rec.credit_hours <= 0:
                raise ValidationError(
                    _('Credit hours must be greater than 0.')
                )
            if rec.credit_hours > 20:
                raise ValidationError(
                    _('Credit hours cannot exceed 20.')
                )

    @api.constrains('passing_marks', 'total_marks')
    def _check_passing_marks(self):
        for rec in self:
            if rec.total_marks > 0:
                if rec.passing_marks > rec.total_marks:
                    raise ValidationError(
                        _('Passing marks cannot exceed total marks.')
                    )
                if rec.passing_marks < 0:
                    raise ValidationError(
                        _('Passing marks cannot be negative.')
                    )

    @api.constrains('theory_hours', 'lab_hours', 'tutorial_hours')
    def _check_contact_hours(self):
        for rec in self:
            if (rec.theory_hours < 0
                    or rec.lab_hours < 0
                    or rec.tutorial_hours < 0):
                raise ValidationError(
                    _('Contact hours cannot be negative.')
                )

    # ------- STATE METHODS -------

    def action_approve(self):
        self.ensure_one()
        if self.course_state != 'draft':
            raise UserError(
                _('Only draft courses can be approved.')
            )
        self.write({
            'course_state': 'approved',
            'approved_by_id': self.env.uid,
            'approved_on': date.today(),
        })
        self.message_post(
            body=_('Course approved by %s.') % self.env.user.name
        )

    def action_activate(self):
        self.ensure_one()
        if self.course_state != 'approved':
            raise UserError(
                _('Only approved courses can be activated.')
            )
        self.course_state = 'active'
        self.message_post(
            body=_('Course activated and available for curriculum assignment.')
        )

    def action_discontinue(self):
        self.ensure_one()
        self.course_state = 'discontinued'
        self.message_post(
            body=_('Course discontinued by %s.') % self.env.user.name
        )

    def action_reset_draft(self):
        self.ensure_one()
        self.write({
            'course_state': 'draft',
            'approved_by_id': False,
            'approved_on': False,
        })
        self.message_post(
            body=_('Course reset to Draft by %s.') % self.env.user.name
        )

    # ------- ONCHANGE -------

    @api.onchange('department_id')
    def _onchange_department_id(self):
        if self.department_id:
            pass
