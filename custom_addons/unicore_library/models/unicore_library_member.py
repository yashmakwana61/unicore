"""
UniCore Library Member Model
Students and faculty registered as library members
with borrowing limits and privilege levels.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreLibraryMember(models.Model):
    _name = 'unicore.library.member'
    _description = 'Library Member'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'member_id'
    _check_company_auto = True
    _rec_name = 'display_name'

    member_id = fields.Char(
        string='Library ID',
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # --- MEMBER TYPE ---

    member_type = fields.Selection(
        string='Member Type',
        required=True,
        default='student',
        tracking=True,
        selection=[
            ('student', 'Student'),
            ('faculty', 'Faculty'),
            ('staff', 'Staff'),
            ('guest', 'Guest'),
        ],
    )

    # --- LINKED RECORDS ---

    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
    )
    faculty_member_id = fields.Many2one(
        comodel_name='unicore.faculty.member',
        string='Faculty Member',
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
    )
    display_name = fields.Char(
        string='Member Name',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('student_id', 'faculty_member_id',
                 'member_type')
    def _compute_display_name(self):
        for rec in self:
            if (rec.member_type == 'student'
                    and rec.student_id):
                rec.display_name = (
                    rec.student_id.display_name
                )
            elif (rec.member_type == 'faculty'
                  and rec.faculty_member_id):
                rec.display_name = (
                    rec.faculty_member_id.display_name
                )
            else:
                rec.display_name = rec.member_id or '/'

    # --- PRIVILEGES ---

    max_books_allowed = fields.Integer(
        string='Max Books Allowed',
        default=3,
        help='Maximum number of books that can be '
             'borrowed simultaneously',
    )
    loan_period_days = fields.Integer(
        string='Loan Period (Days)',
        default=14,
        help='Default loan period in days',
    )
    fine_waiver = fields.Boolean(
        string='Fine Waiver',
        default=False,
        help='Member is exempt from overdue fines',
    )

    # --- DATES ---

    registration_date = fields.Date(
        string='Registration Date',
        default=fields.Date.today,
        readonly=True,
    )
    valid_until = fields.Date(
        string='Valid Until',
        tracking=True,
    )
    is_expired = fields.Boolean(
        string='Membership Expired',
        compute='_compute_is_expired',
        store=False,
    )

    @api.depends('valid_until')
    def _compute_is_expired(self):
        from datetime import date
        today = date.today()
        for rec in self:
            rec.is_expired = (
                bool(rec.valid_until)
                and rec.valid_until < today
            )

    # --- STATS ---

    current_issue_count = fields.Integer(
        string='Books Issued',
        compute='_compute_issue_stats',
        search='_search_current_issue_count',
        store=False,
    )
    total_issued_ever = fields.Integer(
        string='Total Books Borrowed',
        compute='_compute_issue_stats',
        store=False,
    )
    outstanding_fines = fields.Monetary(
        string='Outstanding Fines',
        compute='_compute_issue_stats',
        search='_search_outstanding_fines',
        store=False,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True,
    )

    def _compute_issue_stats(self):
        Issue = self.env['unicore.library.issue']
        for rec in self:
            active = Issue.search([
                ('member_id', '=', rec.id),
                ('issue_state', '=', 'issued'),
            ])
            all_issues = Issue.search([
                ('member_id', '=', rec.id),
            ])
            overdue = all_issues.filtered(
                lambda i: i.fine_amount > 0
                and not i.fine_paid
            )
            rec.current_issue_count = len(active)
            rec.total_issued_ever = len(all_issues)
            rec.outstanding_fines = sum(
                i.fine_amount for i in overdue
            )

    def _search_current_issue_count(self, operator, value):
        if operator == '>' and value == 0:
            issues = self.env['unicore.library.issue'].search(
                [('issue_state', '=', 'issued')]
            )
            return [('id', 'in', issues.mapped('member_id').ids)]
        elif operator == '=' and value == 0:
            issues = self.env['unicore.library.issue'].search(
                [('issue_state', '=', 'issued')]
            )
            return [('id', 'not in', issues.mapped('member_id').ids)]
        return []

    def _search_outstanding_fines(self, operator, value):
        if operator == '>' and value == 0:
            issues = self.env['unicore.library.issue'].search([
                ('fine_amount', '>', 0),
                ('fine_paid', '=', False),
            ])
            return [('id', 'in', issues.mapped('member_id').ids)]
        elif operator == '=' and value == 0:
            issues = self.env['unicore.library.issue'].search([
                ('fine_amount', '>', 0),
                ('fine_paid', '=', False),
            ])
            return [('id', 'not in', issues.mapped('member_id').ids)]
        return []

    # --- STATUS ---

    member_state = fields.Selection(
        string='Status',
        required=True,
        default='active',
        tracking=True,
        selection=[
            ('active', 'Active'),
            ('suspended', 'Suspended'),
            ('expired', 'Expired'),
            ('blacklisted', 'Blacklisted'),
        ],
    )
    suspension_reason = fields.Text(
        string='Suspension Reason',
    )

    _sql_constraints = [
        ('unique_member_id',
         'UNIQUE(member_id)',
         'Library ID must be unique.'),
        ('unique_student_library',
         'UNIQUE(student_id)',
         'Student already has a library membership.'),
    ]

    @api.constrains('member_type', 'student_id',
                    'faculty_member_id')
    def _check_linked_record(self):
        for rec in self:
            if (rec.member_type == 'student'
                    and not rec.student_id):
                raise ValidationError(
                    _('Please link a student record '
                      'for student members.')
                )
            if (rec.member_type == 'faculty'
                    and not rec.faculty_member_id):
                raise ValidationError(
                    _('Please link a faculty record '
                      'for faculty members.')
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('member_id'):
                vals['member_id'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.library.member'
                    ) or '/'
                )
        return super().create(vals_list)

    def action_suspend(self):
        self.ensure_one()
        self.member_state = 'suspended'
        self.message_post(
            body=_('Member suspended.')
        )

    def action_reactivate(self):
        self.ensure_one()
        self.member_state = 'active'
        self.suspension_reason = False
        self.message_post(
            body=_('Member reactivated.')
        )

    def action_issue_book(self):
        """Quick action to issue a book."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue Book'),
            'res_model': 'unicore.library.issue',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_member_id': self.id,
            },
        }

    def action_view_issues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue History'),
            'res_model': 'unicore.library.issue',
            'view_mode': 'list,form',
            'domain': [
                ('member_id', '=', self.id)
            ],
        }
