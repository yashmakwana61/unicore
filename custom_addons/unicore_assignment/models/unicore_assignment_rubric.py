"""
UniCore Assignment Rubric Models
A rubric is a reusable set of grading criteria that can be
attached to one or many assignments. Each criterion defines
a name, maximum points and description of what is expected.
The total points of the rubric sum the criteria maxima.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreAssignmentRubric(models.Model):
    _name = 'unicore.assignment.rubric'
    _description = 'Assignment Rubric'
    _inherit = ['unicore.mixin']
    _order = 'name, id'
    _check_company_auto = True
    _rec_name = 'name'

    # ------- IDENTITY -------

    name = fields.Char(
        string='Rubric Name',
        required=True,
        tracking=True,
    )
    code = fields.Char(
        string='Rubric Code',
        readonly=True,
        copy=False,
        help='Auto-generated rubric identifier',
    )
    description = fields.Html(
        string='Description',
        help='High level description of what this rubric evaluates',
    )

    # ------- INSTITUTION -------

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )

    # ------- CRITERIA -------

    criterion_ids = fields.One2many(
        comodel_name='unicore.assignment.rubric.criterion',
        inverse_name='rubric_id',
        string='Criteria',
    )
    total_points = fields.Float(
        string='Total Points',
        compute='_compute_total_points',
        store=True,
        readonly=True,
        help='Sum of maximum points across all criteria',
    )

    # ------- USAGE -------

    assignment_ids = fields.One2many(
        comodel_name='unicore.assignment',
        inverse_name='rubric_id',
        string='Assignments',
    )
    assignment_count = fields.Integer(
        string='Assignments',
        compute='_compute_assignment_count',
        store=True,
    )

    # ------- COMPUTES -------

    @api.depends('criterion_ids.max_points')
    def _compute_total_points(self):
        for rec in self:
            rec.total_points = sum(
                rec.criterion_ids.mapped('max_points')
            )

    @api.depends('assignment_ids')
    def _compute_assignment_count(self):
        for rec in self:
            rec.assignment_count = len(rec.assignment_ids)

    # ------- CONSTRAINTS -------

    @api.constrains('criterion_ids')
    def _check_total_points(self):
        for rec in self:
            if rec.total_points <= 0:
                raise ValidationError(_(
                    'A rubric must have at least one criterion '
                    'with a positive maximum points value.'
                ))

    # ------- SEQUENCE -------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env[
                    'ir.sequence'
                ].next_by_code('unicore.assignment.rubric')
        return super().create(vals_list)

    # ------- ACTIONS -------

    def action_view_assignments(self):
        """Open assignments that use this rubric."""
        return {
            'name': _('Assignments'),
            'type': 'ir.actions.act_window',
            'res_model': 'unicore.assignment',
            'view_mode': 'list,form',
            'domain': [('rubric_id', '=', self.id)],
        }


class UniCoreAssignmentRubricCriterion(models.Model):
    _name = 'unicore.assignment.rubric.criterion'
    _description = 'Rubric Criterion'
    _order = 'sequence, id'
    _check_company_auto = True
    _rec_name = 'name'

    # ------- RELATIONS -------

    rubric_id = fields.Many2one(
        comodel_name='unicore.assignment.rubric',
        string='Rubric',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='rubric_id.company_id',
        store=True,
        readonly=True,
    )

    # ------- CONTENT -------

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of this criterion within the rubric',
    )
    name = fields.Char(
        string='Criterion Name',
        required=True,
    )
    max_points = fields.Float(
        string='Max Points',
        required=True,
        default=1.0,
    )
    description = fields.Text(
        string='Description',
        help='What is being evaluated and what a top score looks like',
    )
    is_bonus = fields.Boolean(
        string='Bonus Criterion',
        default=False,
        help='Bonus criteria do not count toward the rubric total',
    )

    # ------- CONSTRAINTS -------

    _sql_constraints = [
        (
            'check_max_points_positive',
            'CHECK(max_points > 0)',
            'Maximum points must be greater than zero.',
        ),
    ]
