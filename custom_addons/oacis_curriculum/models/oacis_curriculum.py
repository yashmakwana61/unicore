"""
Oacis Curriculum Model
A curriculum is the structured plan of courses
assigned to a specific academic program, organised
by semester number. Each program has one curriculum.
The curriculum defines WHAT is taught and WHEN
(which semester number) — not WHO teaches it
or in which real calendar semester.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisCurriculum(models.Model):
    _name = 'oacis.curriculum'
    _description = 'Program Curriculum'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'program_id, version'
    _check_company_auto = True

    name = fields.Char(
        string='Curriculum Name',
        required=True,
        tracking=True,
        help='e.g. BSCS Curriculum 2024, MBA Plan v2',
    )
    program_id = fields.Many2one(
        comodel_name='oacis.program',
        string='Program',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    specialisation_id = fields.Many2one(
        comodel_name='oacis.specialisation',
        string='Specialisation',
        ondelete='restrict',
        tracking=True,
        domain="[('program_id', '=', program_id)]",
        help='Optional: curriculum specific to a specialisation',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='program_id.company_id',
        store=True,
        readonly=True,
    )
    department_id = fields.Many2one(
        comodel_name='oacis.department',
        string='Department',
        related='program_id.department_id',
        store=True,
        readonly=True,
    )
    version = fields.Char(
        string='Curriculum Version',
        required=True,
        default='1.0',
        help='e.g. 1.0, 2024, v2',
    )
    effective_from_year = fields.Integer(
        string='Effective From Year',
        help='Batch year from which this curriculum applies',
    )
    effective_to_year = fields.Integer(
        string='Effective To Year',
        help='Last batch year for which this curriculum applies',
    )
    is_current = fields.Boolean(
        string='Current Curriculum',
        default=True,
        tracking=True,
        help='Mark as the currently active curriculum version',
    )
    curriculum_line_ids = fields.One2many(
        comodel_name='oacis.curriculum.line',
        inverse_name='curriculum_id',
        string='Curriculum Lines',
    )
    total_courses = fields.Integer(
        string='Total Courses',
        compute='_compute_curriculum_stats',
        store=True,
    )
    total_credits = fields.Float(
        string='Total Credits',
        compute='_compute_curriculum_stats',
        store=True,
        digits=(6, 1),
    )
    total_semesters = fields.Integer(
        string='Total Semesters',
        compute='_compute_curriculum_stats',
        store=True,
    )

    @api.depends('curriculum_line_ids', 'curriculum_line_ids.credit_hours', 'curriculum_line_ids.semester_number')
    def _compute_curriculum_stats(self):
        for rec in self:
            lines = rec.curriculum_line_ids
            rec.total_courses = len(lines)
            rec.total_credits = sum(
                l.credit_hours for l in lines
            )
            sem_numbers = lines.mapped('semester_number')
            rec.total_semesters = max(sem_numbers) if sem_numbers else 0

    curriculum_state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('review', 'Under Review'),
            ('approved', 'Approved'),
            ('active', 'Active'),
            ('retired', 'Retired'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
    )
    approved_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Approved By',
        readonly=True,
    )
    approved_on = fields.Date(
        string='Approved On',
        readonly=True,
    )
    description = fields.Html(
        string='Curriculum Notes',
    )

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_curriculum_program_version',
            'UNIQUE(program_id, version)',
            'A curriculum with this version already exists for this program.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('effective_from_year', 'effective_to_year')
    def _check_effective_years(self):
        for rec in self:
            if (rec.effective_from_year
                    and rec.effective_to_year):
                if (rec.effective_to_year
                        < rec.effective_from_year):
                    raise ValidationError(
                        _('Effective To Year must be after Effective From Year.'),
                    )

    @api.constrains('program_id', 'is_current')
    def _check_single_current_curriculum(self):
        for rec in self:
            if rec.is_current:
                existing = self.search([
                    ('program_id', '=', rec.program_id.id),
                    ('specialisation_id', '=', rec.specialisation_id.id),
                    ('is_current', '=', True),
                    ('id', '!=', rec.id),
                ])
                if existing:
                    raise ValidationError(
                        _('Program "%s" already has a current '
                          'curriculum. Please retire the '
                          'existing one before creating a new.')
                        % rec.program_id.name,
                    )

    # ------- STATE METHODS -------

    def action_submit_review(self):
        self.ensure_one()
        if not self.curriculum_line_ids:
            raise UserError(
                _('Cannot submit an empty curriculum '
                  'for review. Please add courses first.'),
            )
        self.curriculum_state = 'review'
        self.message_post(
            body=_('Curriculum submitted for review by %s.') % self.env.user.name,
        )

    def action_approve(self):
        self.ensure_one()
        self.write({
            'curriculum_state': 'approved',
            'approved_by_id': self.env.uid,
            'approved_on': date.today(),
        })
        self.message_post(
            body=_('Curriculum approved by %s.') % self.env.user.name,
        )

    def action_activate(self):
        self.ensure_one()
        if self.curriculum_state != 'approved':
            raise UserError(
                _('Only approved curricula can be activated.'),
            )
        self.curriculum_state = 'active'
        self.message_post(
            body=_('Curriculum activated.'),
        )

    def action_retire(self):
        self.ensure_one()
        self.write({
            'curriculum_state': 'retired',
            'is_current': False,
        })
        self.message_post(
            body=_('Curriculum retired by %s.') % self.env.user.name,
        )

    def action_reset_draft(self):
        self.ensure_one()
        self.write({
            'curriculum_state': 'draft',
            'approved_by_id': False,
            'approved_on': False,
        })
        self.message_post(
            body=_('Curriculum reset to Draft.'),
        )
