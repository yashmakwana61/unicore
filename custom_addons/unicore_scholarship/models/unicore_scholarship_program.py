"""
UniCore Scholarship Program Model
Defines a scholarship or financial aid scheme.
Stores eligibility criteria, funding details,
award amounts and application quota.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UniCoreScholarshipProgram(models.Model):
    _name = 'unicore.scholarship.program'
    _description = 'Scholarship Program'
    _inherit = ['unicore.mixin', 'mail.thread',
                'mail.activity.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(
        string='Scholarship Name',
        required=True,
        tracking=True,
        help='e.g. Merit Scholarship 2025-26',
    )
    code = fields.Char(
        string='Code',
        required=True,
        size=20,
        help='e.g. MERIT-2526, SPORTS-2526',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        tracking=True,
    )
    academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
        tracking=True,
    )

    # --- TYPE & FUNDING ---

    scholarship_type = fields.Selection(
        string='Scholarship Type',
        required=True,
        default='merit',
        tracking=True,
        selection=[
            ('merit', 'Merit Based'),
            ('need_based', 'Need Based'),
            ('sports', 'Sports Excellence'),
            ('cultural', 'Cultural Achievement'),
            ('government', 'Government Grant'),
            ('institutional', 'Institutional Aid'),
            ('research', 'Research Fellowship'),
            ('disability', 'Disability Support'),
            ('minority', 'Minority Support'),
            ('other', 'Other'),
        ],
    )
    funding_source = fields.Selection(
        string='Funding Source',
        required=True,
        default='institutional',
        selection=[
            ('institutional', 'Institutional Funds'),
            ('government', 'Government / State'),
            ('donor', 'Donor / Endowment'),
            ('corporate', 'Corporate Sponsorship'),
            ('trust', 'Charitable Trust'),
            ('other', 'Other'),
        ],
    )
    sponsor_name = fields.Char(
        string='Sponsor / Donor Name',
        help='Name of sponsoring organization or donor',
    )

    # --- ELIGIBILITY CRITERIA ---

    min_cgpa = fields.Float(
        string='Minimum CGPA',
        default=0.0,
        digits=(4, 2),
        help='Minimum CGPA required. Set 0 to skip.',
    )
    min_attendance_percentage = fields.Float(
        string='Minimum Attendance %',
        default=0.0,
        digits=(5, 2),
        help='Minimum attendance %. Set 0 to skip.',
    )
    max_annual_income = fields.Monetary(
        string='Maximum Family Income',
        currency_field='currency_id',
        default=0.0,
        help='Maximum family annual income. 0 = no limit.',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    eligible_program_ids = fields.Many2many(
        comodel_name='unicore.program',
        relation='unicore_scholarship_program_rel',
        column1='scholarship_id',
        column2='program_id',
        string='Eligible Programs',
        help='Leave empty to allow all programs',
        domain="[('company_id','=',company_id)]",
    )
    min_year_of_study = fields.Integer(
        string='Minimum Year of Study',
        default=1,
        help='Minimum year level student must be in',
    )
    max_year_of_study = fields.Integer(
        string='Maximum Year of Study',
        default=0,
        help='0 means no maximum restriction',
    )
    is_renewable = fields.Boolean(
        string='Renewable',
        default=True,
        help='Can be renewed each academic year',
    )

    # --- AWARD DETAILS ---

    award_type = fields.Selection(
        string='Award Type',
        required=True,
        default='fee_waiver',
        selection=[
            ('fee_waiver', 'Fee Waiver / Discount'),
            ('cash_grant', 'Cash Grant'),
            ('full_tuition', 'Full Tuition Waiver'),
            ('partial_tuition', 'Partial Tuition'),
            ('stipend', 'Monthly Stipend'),
            ('mixed', 'Mixed Benefits'),
        ],
    )
    award_amount = fields.Monetary(
        string='Award Amount Per Semester',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )
    award_percentage = fields.Float(
        string='Award Percentage (%)',
        default=0.0,
        digits=(5, 2),
        help='If percentage-based, % of total fee waived',
    )
    total_quota = fields.Integer(
        string='Total Seats / Quota',
        default=10,
        help='Maximum number of students per year',
    )
    application_deadline = fields.Date(
        string='Application Deadline',
        tracking=True,
    )

    # --- STATS ---

    application_ids = fields.One2many(
        comodel_name='unicore.scholarship.application',
        inverse_name='scholarship_program_id',
        string='Applications',
    )
    application_count = fields.Integer(
        string='Applications',
        compute='_compute_stats',
        store=True,
    )
    approved_count = fields.Integer(
        string='Approved',
        compute='_compute_stats',
        store=True,
    )
    total_awarded = fields.Monetary(
        string='Total Amount Awarded',
        compute='_compute_stats',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('application_ids',
                 'application_ids.application_state')
    def _compute_stats(self):
        Award = self.env['unicore.scholarship.award']
        for rec in self:
            apps = rec.application_ids
            rec.application_count = len(apps)
            approved = apps.filtered(
                lambda a: a.application_state
                == 'approved',
            )
            rec.approved_count = len(approved)
            awards = Award.search([
                ('scholarship_program_id', '=', rec.id),
                ('award_state', '=', 'disbursed'),
            ])
            rec.total_awarded = sum(
                a.award_amount for a in awards
            )

    # --- STATUS ---

    program_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('open', 'Open for Applications'),
            ('closed', 'Applications Closed'),
            ('completed', 'Completed'),
        ],
    )

    _unique_scholarship_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Scholarship code must be unique per institution.',
    )

    @api.constrains('min_cgpa')
    def _check_min_cgpa(self):
        for rec in self:
            if not (0.0 <= rec.min_cgpa <= 10.0):
                raise ValidationError(
                    _('Minimum CGPA must be between '
                      '0 and 10.'),
                )

    @api.constrains('total_quota')
    def _check_quota(self):
        for rec in self:
            if rec.total_quota < 1:
                raise ValidationError(
                    _('Quota must be at least 1.'),
                )

    @api.constrains('award_amount')
    def _check_award_amount(self):
        for rec in self:
            if rec.award_amount < 0:
                raise ValidationError(
                    _('Award amount cannot be negative.'),
                )

    def action_open(self):
        self.ensure_one()
        if not self.award_amount and not self.award_percentage:
            raise UserError(
                _('Please set an award amount or '
                  'percentage before opening '
                  'for applications.'),
            )
        self.program_state = 'open'
        self.message_post(
            body=_('Scholarship program opened '
                   'for applications.'),
        )

    def action_close(self):
        self.ensure_one()
        self.program_state = 'closed'
        self.message_post(
            body=_('Application window closed.'),
        )

    def action_complete(self):
        self.ensure_one()
        self.program_state = 'completed'
        self.message_post(
            body=_('Scholarship program completed.'),
        )

    def action_reset_draft(self):
        self.ensure_one()
        self.program_state = 'draft'
