"""
UniCore Fee Structure Model
Defines the fee schedule for a specific program,
semester and campus combination. Contains line
items for different fee components (tuition,
library, sports, etc.). Used to auto-generate
fee invoices for enrolled students.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreFeeStructure(models.Model):
    _name = 'unicore.fee.structure'
    _description = 'Fee Structure'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, program_id, name'
    _check_company_auto = True

    name = fields.Char(
        string='Structure Name',
        required=True,
        tracking=True,
        help='e.g. BSCS Year 1 Fees 2025-26',
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
        tracking=True,
        domain="[('company_id','=',company_id)]",
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        ondelete='restrict',
        domain="[('academic_year_id','=',academic_year_id)]",
        help='Leave empty to apply to full year',
    )
    program_id = fields.Many2one(
        comodel_name='unicore.program',
        string='Program',
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
        help='Leave empty to apply to all programs',
    )
    campus_id = fields.Many2one(
        comodel_name='unicore.campus',
        string='Campus',
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
        help='Leave empty to apply to all campuses',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        comodel_name='unicore.fee.structure.line',
        inverse_name='structure_id',
        string='Fee Components',
    )
    total_amount = fields.Monetary(
        string='Total Fee Amount',
        compute='_compute_total_amount',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(line.amount for line in rec.line_ids)

    is_installment_allowed = fields.Boolean(
        string='Allow Installments',
        default=True,
        help='Students can pay in installments',
    )
    installment_count = fields.Integer(
        string='Number of Installments',
        default=2,
    )
    fee_due_date = fields.Date(
        string='Fee Due Date',
        tracking=True,
        help='Last date to pay without late fee',
    )
    late_fee_percentage = fields.Float(
        string='Late Fee (%)',
        default=5.0,
        digits=(5, 2),
        help='Percentage charged on overdue fees',
    )
    structure_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
    )

    _unique_fee_structure = models.Constraint(
        'UNIQUE(company_id, academic_year_id, semester_id, program_id, campus_id)',
        'A fee structure already exists for this combination of year, semester, program and campus.',
    )

    @api.constrains('installment_count')
    def _check_installment_count(self):
        for rec in self:
            if rec.is_installment_allowed and rec.installment_count < 1:
                raise ValidationError(_('Installment count must be at least 1.'))

    def action_activate(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Please add at least one fee component before activating.'))
        self.structure_state = 'active'
        self.message_post(body=_('Fee structure activated.'))

    def action_archive_structure(self):
        self.ensure_one()
        self.structure_state = 'archived'
        self.message_post(body=_('Fee structure archived.'))

    def action_reset_draft(self):
        self.ensure_one()
        self.structure_state = 'draft'

    def get_applicable_structure(self, student, semester):
        company_id = student.company_id.id
        year_id = semester.academic_year_id.id
        sem_id = semester.id
        program_id = student.program_id.id
        campus_id = student.campus_id.id
        for domain_extra in [
            [('semester_id', '=', sem_id), ('program_id', '=', program_id),
             ('campus_id', '=', campus_id)],
            [('semester_id', '=', sem_id), ('program_id', '=', program_id),
             ('campus_id', '=', False)],
            [('semester_id', '=', False), ('program_id', '=', program_id),
             ('campus_id', '=', False)],
            [('semester_id', '=', False), ('program_id', '=', False),
             ('campus_id', '=', False)],
        ]:
            structure = self.search([
                ('company_id', '=', company_id),
                ('academic_year_id', '=', year_id),
                ('structure_state', '=', 'active'),
            ] + domain_extra, limit=1)
            if structure:
                return structure
        return self.browse()


class UniCoreFeeStructureLine(models.Model):
    _name = 'unicore.fee.structure.line'
    _description = 'Fee Structure Line'
    _order = 'structure_id, sequence'
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name='res.company',
        related='structure_id.company_id',
        store=True,
    )
    structure_id = fields.Many2one(
        comodel_name='unicore.fee.structure',
        string='Fee Structure',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    fee_type = fields.Selection(
        string='Fee Type',
        required=True,
        default='tuition',
        selection=[
            ('tuition', 'Tuition Fee'),
            ('library', 'Library Fee'),
            ('sports', 'Sports Fee'),
            ('lab', 'Laboratory Fee'),
            ('exam', 'Examination Fee'),
            ('registration', 'Registration Fee'),
            ('hostel', 'Hostel Fee'),
            ('transport', 'Transport Fee'),
            ('development', 'Development Fee'),
            ('caution', 'Caution Deposit'),
            ('other', 'Other'),
        ],
    )
    name = fields.Char(string='Description', required=True)
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='structure_id.currency_id',
        store=True,
        readonly=True,
    )
    is_mandatory = fields.Boolean(string='Mandatory', default=True)
    is_refundable = fields.Boolean(string='Refundable', default=False)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_('Fee amount cannot be negative.'))
