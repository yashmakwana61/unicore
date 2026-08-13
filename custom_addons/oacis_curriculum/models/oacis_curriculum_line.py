"""
Oacis Curriculum Line Model
Each line represents one course assigned to a
specific semester number within a curriculum plan.
This defines WHAT is taught in WHICH semester
of the program — independent of real calendar dates.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisCurriculumLine(models.Model):
    _name = 'oacis.curriculum.line'
    _description = 'Curriculum Course Line'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['curriculum_id.display_name', 'course_id.display_name',
                 'semester_number'],
    )

    @api.depends('curriculum_id.display_name', 'course_id.display_name',
                 'semester_number')
    def _compute_display_name(self):
        for rec in self:
            curriculum_name = (
                rec.curriculum_id.display_name if rec.curriculum_id else ''
            )
            course_name = (
                rec.course_id.display_name if rec.course_id else ''
            )
            if rec.semester_number:
                rec.display_name = '%s - Sem %s - %s' % (
                    curriculum_name, rec.semester_number, course_name,
                )
            else:
                rec.display_name = '%s - %s' % (
                    curriculum_name, course_name,
                )
    _order = 'curriculum_id, semester_number, sequence'
    _check_company_auto = True

    curriculum_id = fields.Many2one(
        comodel_name='oacis.curriculum',
        string='Curriculum',
        required=True,
        ondelete='cascade',
        index=True,
    )
    course_id = fields.Many2one(
        comodel_name='oacis.course',
        string='Course',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('course_state', 'in', ['approved','active']), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='curriculum_id.company_id',
        store=True,
        readonly=True,
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program',
        string='Program',
        related='curriculum_id.program_id',
        store=True,
        readonly=True,
    )
    semester_number = fields.Integer(
        string='Semester Number',
        required=True,
        default=1,
        help='Which semester of the program: 1, 2, 3, 4...',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order within the semester',
    )
    credit_hours = fields.Float(
        string='Credit Hours',
        related='course_id.credit_hours',
        store=True,
        readonly=True,
        digits=(4, 1),
    )
    course_category = fields.Selection(
        string='Course Category',
        related='course_id.course_category',
        store=True,
        readonly=True,
    )
    course_type = fields.Selection(
        string='Delivery Type',
        related='course_id.course_type',
        store=True,
        readonly=True,
    )
    is_elective = fields.Boolean(
        string='Is Elective',
        default=False,
        help='Student can choose from a set of electives',
    )
    elective_group = fields.Char(
        string='Elective Group',
        help='Group code for elective pool e.g. ELEC-A, ELEC-B',
    )
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Must be completed to fulfil program requirements',
    )

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_course_in_curriculum',
            'UNIQUE(curriculum_id, course_id)',
            'This course is already in this curriculum.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('semester_number')
    def _check_semester_number(self):
        for rec in self:
            if rec.semester_number < 1:
                raise ValidationError(
                    _('Semester number must be at least 1.'),
                )
            if rec.semester_number > 20:
                raise ValidationError(
                    _('Semester number cannot exceed 20.'),
                )

    @api.constrains('curriculum_id', 'semester_number')
    def _check_semester_within_program(self):
        for rec in self:
            program = rec.curriculum_id.program_id
            if program.duration_years:
                max_semesters = int(program.duration_years * 2)
                if rec.semester_number > max_semesters:
                    raise ValidationError(
                        _('Semester number %d exceeds the program duration of %d semesters.')
                        % (rec.semester_number, max_semesters),
                    )
