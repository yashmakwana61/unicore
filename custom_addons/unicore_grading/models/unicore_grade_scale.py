"""
UniCore Grade Scale Model
Defines the institutional grading system mapping
percentage ranges to letter grades and grade points.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreGradeScale(models.Model):
    _name = 'unicore.grade.scale'
    _description = 'Grade Scale'
    _inherit = ['unicore.mixin']
    _order = 'company_id, sequence'
    _check_company_auto = True

    name = fields.Char(
        string='Scale Name',
        required=True,
        help='e.g. Standard 4.0 Scale, 10-Point Scale',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    is_default = fields.Boolean(
        string='Default Scale',
        default=False,
        tracking=True,
        help='Default scale used for all grade computations',
    )
    max_gpa = fields.Float(
        string='Maximum GPA',
        required=True,
        default=4.0,
        digits=(4, 2),
        help='Maximum possible GPA on this scale (e.g. 4.0 or 10.0)',
    )
    line_ids = fields.One2many(
        comodel_name='unicore.grade.scale.line',
        inverse_name='scale_id',
        string='Grade Lines',
    )
    description = fields.Text(string='Description')

    _unique_scale_name_company = models.Constraint(
        'UNIQUE(name, company_id)',
        'A grade scale with this name already exists.',
    )

    @api.constrains('is_default', 'company_id')
    def _check_single_default(self):
        for rec in self:
            if rec.is_default:
                existing = self.search([
                    ('company_id', '=', rec.company_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', rec.id),
                ])
                if existing:
                    raise ValidationError(
                        _('Company "%s" already has a '
                          'default grade scale. Please '
                          'unset the existing default first.')
                        % rec.company_id.name
                    )

    @api.model
    def get_default_scale(self, company_id):
        """Returns the default grade scale for a company."""
        scale = self.search([
            ('company_id', '=', company_id),
            ('is_default', '=', True),
            ('active', '=', True),
        ], limit=1)
        if not scale:
            scale = self.search([
                ('company_id', '=', company_id),
                ('active', '=', True),
            ], order='sequence asc', limit=1)
        return scale

    def get_grade_for_percentage(self, percentage):
        """
        Returns (letter_grade, grade_point) tuple
        for a given percentage using this scale's lines.
        Returns ('F', 0.0) if percentage is below
        all defined ranges.
        """
        self.ensure_one()
        for line in self.line_ids.sorted(
            key=lambda l: l.min_percentage, reverse=True
        ):
            if percentage >= line.min_percentage:
                return line.letter_grade, line.grade_point
        return 'F', 0.0


class UniCoreGradeScaleLine(models.Model):
    _name = 'unicore.grade.scale.line'
    _description = 'Grade Scale Line'
    _order = 'scale_id, min_percentage desc'

    scale_id = fields.Many2one(
        comodel_name='unicore.grade.scale',
        string='Grade Scale',
        required=True,
        ondelete='cascade',
        index=True,
    )
    letter_grade = fields.Char(
        string='Letter Grade',
        required=True,
        size=5,
        help='e.g. A+, A, B+, B, C, F',
    )
    min_percentage = fields.Float(
        string='Minimum Percentage (%)',
        required=True,
        digits=(5, 2),
        help='Minimum percentage to achieve this grade',
    )
    max_percentage = fields.Float(
        string='Maximum Percentage (%)',
        required=True,
        digits=(5, 2),
    )
    grade_point = fields.Float(
        string='Grade Point',
        required=True,
        digits=(4, 2),
        help='Grade point value for GPA computation',
    )
    is_passing = fields.Boolean(
        string='Is Passing Grade',
        default=True,
        help='Students with this grade pass the course',
    )
    description = fields.Char(string='Description')

    _unique_letter_grade_scale = models.Constraint(
        'UNIQUE(scale_id, letter_grade)',
        'Duplicate letter grade in this scale.',
    )

    @api.constrains('min_percentage', 'max_percentage')
    def _check_percentage_range(self):
        for rec in self:
            if rec.min_percentage < 0:
                raise ValidationError(
                    _('Minimum percentage cannot be negative.')
                )
            if rec.max_percentage > 100:
                raise ValidationError(
                    _('Maximum percentage cannot exceed 100.')
                )
            if rec.min_percentage >= rec.max_percentage:
                raise ValidationError(
                    _('Minimum percentage must be less '
                      'than maximum percentage.')
                )

    @api.constrains('grade_point', 'scale_id')
    def _check_grade_point(self):
        for rec in self:
            if rec.grade_point < 0:
                raise ValidationError(
                    _('Grade point cannot be negative.')
                )
            if (rec.scale_id.max_gpa
                    and rec.grade_point > rec.scale_id.max_gpa):
                raise ValidationError(
                    _('Grade point %s exceeds scale maximum %s.')
                    % (rec.grade_point, rec.scale_id.max_gpa)
                )
