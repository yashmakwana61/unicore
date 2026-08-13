"""
Oacis Guardian Student Relationship Model
Stores metadata about the relationship between
a guardian and a student. This is a proper relation
model — NOT a simple Many2many — because it holds
permission flags and relationship type data.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OacisGuardianStudentRel(models.Model):
    _name = 'oacis.guardian.student.rel'
    _description = 'Guardian to Student Relationship'
    _order = 'guardian_id, student_id'
    _check_company_auto = True

    guardian_id = fields.Many2one(
        'oacis.guardian',
        string='Guardian',
        required=True,
        ondelete='cascade',
        index=True,
    )
    student_id = fields.Many2one(
        'oacis.student',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
        readonly=True,
    )
    relationship_type = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('legal_guardian', 'Legal Guardian'),
        ('grandparent', 'Grandparent'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('spouse', 'Spouse'),
        ('sibling', 'Sibling'),
        ('sponsor', 'Sponsor / Benefactor'),
        ('employer', 'Employer'),
        ('other', 'Other'),
    ], string='Relationship', required=True)
    is_primary_guardian = fields.Boolean(
        string='Primary Guardian',
        default=False,
        tracking=True,
        help='Primary point of contact for this student',
    )
    is_financial_guarantor = fields.Boolean(
        string='Financial Guarantor',
        default=False,
        tracking=True,
        help='Financially responsible for this student',
    )
    can_view_academic_records = fields.Boolean(
        string='Can View Academic Records',
        default=True,
        help='Allow guardian to view student grades and attendance via portal',
    )
    can_view_fee_records = fields.Boolean(
        string='Can View Fee Records',
        default=True,
        help='Allow guardian to view and pay fees via portal',
    )
    can_receive_notifications = fields.Boolean(
        string='Receive Notifications',
        default=True,
        help='Send academic and fee notifications to this guardian',
    )
    start_date = fields.Date(
        string='Relationship Start Date',
        default=fields.Date.today,
        help='Date when this guardian relationship was established',
    )
    end_date = fields.Date(
        string='Relationship End Date',
        help='Date when this relationship ended (if applicable)',
    )
    is_active_relationship = fields.Boolean(
        string='Active Relationship',
        default=True,
        tracking=True,
    )
    notes = fields.Text(string='Relationship Notes')

    # ------- SQL CONSTRAINTS -------

    _sql_constraints = [
        (
            'unique_guardian_student_relationship',
            'UNIQUE(guardian_id, student_id)',
            'This guardian is already linked to this student.',
        ),
    ]

    # ------- CONSTRAINTS -------

    @api.constrains('is_primary_guardian', 'student_id')
    def _check_single_primary_guardian(self):
        for rec in self:
            if rec.is_primary_guardian:
                existing = self.search([
                    ('student_id', '=', rec.student_id.id),
                    ('is_primary_guardian', '=', True),
                    ('id', '!=', rec.id),
                    ('is_active_relationship', '=', True),
                ])
                if existing:
                    raise ValidationError(
                        _('Student "%s" already has a primary '
                          'guardian assigned. Only one primary '
                          'guardian is allowed per student.')
                        % rec.student_id.display_name,
                    )

    @api.constrains('is_financial_guarantor', 'student_id')
    def _check_single_financial_guarantor(self):
        for rec in self:
            if rec.is_financial_guarantor:
                existing = self.search([
                    ('student_id', '=', rec.student_id.id),
                    ('is_financial_guarantor', '=', True),
                    ('id', '!=', rec.id),
                    ('is_active_relationship', '=', True),
                ])
                if existing:
                    raise ValidationError(
                        _('Student "%s" already has a financial '
                          'guarantor assigned. Only one financial '
                          'guarantor is allowed per student.')
                        % rec.student_id.display_name,
                    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                if rec.end_date < rec.start_date:
                    raise ValidationError(
                        _('End date must be after start date.'),
                    )

    # ------- ONCHANGE -------

    @api.onchange('is_financial_guarantor')
    def _onchange_is_financial_guarantor(self):
        if self.is_financial_guarantor:
            self.can_view_fee_records = True
