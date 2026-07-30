"""
UniCore Fee Invoice Model
A fee invoice is generated per student per semester
from the applicable fee structure. Supports full
payment or installments. Tracks payment status
and outstanding balance.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class UniCoreFeeInvoice(models.Model):
    _name = 'unicore.fee.invoice'
    _description = 'Student Fee Invoice'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'invoice_date desc, student_id'
    _check_company_auto = True
    _rec_name = 'invoice_number'

    invoice_number = fields.Char(
        string='Invoice Number',
        readonly=True,
        copy=False,
        index=True,
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        domain="[('company_id','=',company_id),('student_state','in',['enrolled','active'])]",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    academic_year_id = fields.Many2one(
        comodel_name='unicore.academic.year',
        string='Academic Year',
        required=True,
        ondelete='restrict',
        domain="[('company_id','=',company_id)]",
        tracking=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        ondelete='restrict',
        domain="[('academic_year_id','=',academic_year_id)]",
        tracking=True,
    )
    fee_structure_id = fields.Many2one(
        comodel_name='unicore.fee.structure',
        string='Fee Structure',
        ondelete='restrict',
        domain="[('company_id','=',company_id),('structure_state','=','active')]",
    )
    invoice_date = fields.Date(
        string='Invoice Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        comodel_name='unicore.fee.invoice.line',
        inverse_name='invoice_id',
        string='Invoice Lines',
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    discount_amount = fields.Monetary(
        string='Discount',
        default=0.0,
        currency_field='currency_id',
    )
    discount_reason = fields.Char(string='Discount Reason')
    late_fee_amount = fields.Monetary(
        string='Late Fee',
        default=0.0,
        currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_paid = fields.Monetary(
        string='Amount Paid',
        compute='_compute_payment_stats',
        store=True,
        currency_field='currency_id',
        help='Calculated from GL invoice reconciliation status',
    )
    amount_outstanding = fields.Monetary(
        string='Outstanding Balance',
        compute='_compute_payment_stats',
        store=True,
        currency_field='currency_id',
        help='Calculated from GL invoice reconciliation status',
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=False,
    )

    @api.depends('line_ids', 'line_ids.amount', 'discount_amount', 'late_fee_amount')
    def _compute_amounts(self):
        for rec in self:
            rec.subtotal = sum(line.amount for line in rec.line_ids)
            rec.total_amount = rec.subtotal - rec.discount_amount + rec.late_fee_amount

    @api.depends('account_move_id', 'account_move_id.line_ids', 'total_amount')
    def _compute_payment_stats(self):
        for rec in self:
            # Get payment status from GL invoice reconciliation
            if rec.account_move_id:
                # Find AR line and check reconciliation status
                ar_lines = rec.account_move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                )
                if ar_lines:
                    # Calculate paid amount from reconciled lines
                    reconciled_amount = sum(
                        line.credit for line in ar_lines if line.reconciled
                    )
                    rec.amount_paid = reconciled_amount
                    rec.amount_outstanding = max(0.0, rec.total_amount - rec.amount_paid)
                else:
                    rec.amount_paid = 0.0
                    rec.amount_outstanding = rec.total_amount
            else:
                # No GL invoice yet
                rec.amount_paid = 0.0
                rec.amount_outstanding = rec.total_amount

    @api.depends('due_date', 'amount_outstanding')
    def _compute_is_overdue(self):
        today = date.today()
        for rec in self:
            rec.is_overdue = (
                rec.due_date
                and rec.due_date < today
                and rec.amount_outstanding > 0
                and rec.invoice_state not in ('paid', 'cancelled')
            )

    invoice_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('sent', 'Sent to Student'),
            ('partial', 'Partially Paid'),
            ('paid', 'Fully Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ],
    )

    _unique_invoice_number = models.Constraint(
        'UNIQUE(invoice_number)',
        'Invoice number must be unique.',
    )

    _unique_student_semester_invoice = models.Constraint(
        'UNIQUE(student_id, semester_id)',
        'A fee invoice already exists for this student in this semester.',
    )

    @api.constrains('discount_amount', 'subtotal')
    def _check_discount(self):
        for rec in self:
            if rec.discount_amount < 0:
                raise ValidationError(_('Discount cannot be negative.'))
            if rec.discount_amount > rec.subtotal:
                raise ValidationError(_('Discount cannot exceed subtotal.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('invoice_number'):
                vals['invoice_number'] = (
                    self.env['ir.sequence'].next_by_code('unicore.fee.invoice') or '/'
                )
        return super().create(vals_list)

    @api.onchange('fee_structure_id')
    def _onchange_fee_structure_id(self):
        if self.fee_structure_id:
            self.line_ids = [(5, 0, 0)]
            new_lines = []
            for sl in self.fee_structure_id.line_ids:
                new_lines.append((0, 0, {
                    'fee_type': sl.fee_type,
                    'name': sl.name,
                    'amount': sl.amount,
                    'is_mandatory': sl.is_mandatory,
                }))
            self.line_ids = new_lines
            if self.fee_structure_id.fee_due_date:
                self.due_date = self.fee_structure_id.fee_due_date
            self.currency_id = self.fee_structure_id.currency_id

    def action_send(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Add invoice lines before sending.'))
        self.invoice_state = 'sent'
        self.message_post(body=_('Fee invoice sent to student %s.') % self.student_id.display_name)

    def action_cancel(self):
        self.ensure_one()
        if self.invoice_state == 'paid':
            raise UserError(_('Cannot cancel a fully paid invoice.'))
        self.invoice_state = 'cancelled'
        self.message_post(body=_('Invoice cancelled.'))

    def action_reset_draft(self):
        self.ensure_one()
        self.invoice_state = 'draft'


    def _update_payment_state(self):
        self.ensure_one()
        if self.amount_outstanding <= 0:
            self.invoice_state = 'paid'
        elif self.amount_paid > 0:
            self.invoice_state = 'partial'
        elif self.due_date and self.due_date < date.today():
            self.invoice_state = 'overdue'

    @classmethod
    def generate_invoices_for_semester(cls, env, semester_id, company_id):
        Invoice = env['unicore.fee.invoice']
        Enrollment = env['unicore.enrollment']
        FeeStructure = env['unicore.fee.structure']
        semester = env['unicore.semester'].browse(semester_id)
        enrollments = Enrollment.search([
            ('semester_id', '=', semester_id),
            ('enrollment_state', '=', 'registered'),
        ])
        created_count = 0
        for enr in enrollments:
            existing = Invoice.search([
                ('student_id', '=', enr.student_id.id),
                ('semester_id', '=', semester_id),
            ], limit=1)
            if existing:
                continue
            structure = FeeStructure.search([], limit=1).get_applicable_structure(
                enr.student_id, semester
            )
            vals = {
                'student_id': enr.student_id.id,
                'company_id': company_id,
                'academic_year_id': semester.academic_year_id.id,
                'semester_id': semester_id,
                'invoice_date': date.today(),
                'due_date': semester.date_start or date.today() + timedelta(days=30),
            }
            if structure:
                vals['fee_structure_id'] = structure.id
                vals['currency_id'] = structure.currency_id.id
            invoice = Invoice.create(vals)
            if structure:
                for sl in structure.line_ids:
                    env['unicore.fee.invoice.line'].create({
                        'invoice_id': invoice.id,
                        'fee_type': sl.fee_type,
                        'name': sl.name,
                        'amount': sl.amount,
                        'is_mandatory': sl.is_mandatory,
                    })
            created_count += 1
        return created_count


class UniCoreFeeInvoiceLine(models.Model):
    _name = 'unicore.fee.invoice.line'
    _description = 'Fee Invoice Line'
    _order = 'invoice_id, sequence'
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name='res.company',
        related='invoice_id.company_id',
        store=True,
    )
    invoice_id = fields.Many2one(
        comodel_name='unicore.fee.invoice',
        string='Invoice',
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
        related='invoice_id.currency_id',
        store=True,
        readonly=True,
    )
    is_mandatory = fields.Boolean(string='Mandatory', default=True)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_('Amount cannot be negative.'))
