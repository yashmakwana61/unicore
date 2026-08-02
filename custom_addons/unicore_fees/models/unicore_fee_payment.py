from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class UniCoreFeePayment(models.Model):
    _name = 'unicore.fee.payment'
    _description = 'Fee Payment (Archived - Use GL Invoicing)'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    _check_company_auto = True
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['receipt_number', 'invoice_id.display_name'],
    )

    @api.depends('receipt_number', 'invoice_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            invoice_name = (
                rec.invoice_id.display_name if rec.invoice_id else ''
            )
            if invoice_name:
                rec.display_name = '%s - %s' % (
                    rec.receipt_number, invoice_name
                )
            else:
                rec.display_name = rec.receipt_number or ''

    receipt_number = fields.Char(
        string='Receipt Number',
        readonly=True,
        copy=False,
        index=True,
    )
    invoice_id = fields.Many2one(
        comodel_name='unicore.fee.invoice',
        string='Invoice',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    payment_date = fields.Date(
        string='Payment Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    payment_method = fields.Selection(
        string='Payment Method',
        required=True,
        default='cash',
        tracking=True,
        selection=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('online', 'Online'),
            ('dd', 'Demand Draft'),
            ('upi', 'UPI'),
            ('card', 'Card'),
            ('scholarship', 'Scholarship'),
            ('waiver', 'Waiver'),
        ],
    )
    transaction_reference = fields.Char(
        string='Transaction Reference',
        help='External transaction ID or reference number',
    )
    payment_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
            ('reversed', 'Reversed'),
        ],
    )
    remarks = fields.Text(string='Remarks')
    active = fields.Boolean(
        string='Active',
        default=False,
        help='Historical records are inactive by default',
    )

    _sql_constraints = [
        (
            'unique_receipt_number',
            'UNIQUE(receipt_number)',
            'Receipt number must be unique across all payments.',
        ),
    ]

    @api.constrains('amount', 'invoice_id')
    def _check_payment_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Payment amount must be positive.'))
            if rec.invoice_id and rec.amount > rec.invoice_id.amount_outstanding + rec.amount:
                raise ValidationError(_(
                    'Payment amount (%.2f) exceeds outstanding balance (%.2f).'
                ) % (rec.amount, rec.invoice_id.amount_outstanding))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('receipt_number'):
                vals['receipt_number'] = (
                    self.env['ir.sequence'].next_by_code('unicore.fee.payment') or '/'
                )
        return super().create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if self.payment_state != 'draft':
            raise UserError(_('Only draft payments can be confirmed.'))
        if self.invoice_id.invoice_state == 'cancelled':
            raise UserError(_('Cannot confirm payment for a cancelled invoice.'))
        self.write({'payment_state': 'confirmed'})
        self._update_invoice_state()
        self.message_post(body=_('Payment %s confirmed. Amount: %s') % (
            self.receipt_number, self.amount
        ))

    def action_cancel(self):
        self.ensure_one()
        if self.payment_state != 'draft':
            raise UserError(_('Only draft payments can be cancelled.'))
        self.write({'payment_state': 'cancelled'})
        self.message_post(body=_('Payment %s cancelled.') % self.receipt_number)

    def action_reverse(self):
        self.ensure_one()
        if self.payment_state != 'confirmed':
            raise UserError(_('Only confirmed payments can be reversed.'))
        reverse = self.copy(default={
            'amount': -self.amount,
            'payment_state': 'draft',
            'payment_date': date.today(),
            'remarks': _('Reversal of %s') % self.receipt_number,
        })
        reverse.action_confirm()
        self.write({'payment_state': 'reversed'})
        self.message_post(body=_('Payment %s reversed.') % self.receipt_number)

    def _update_invoice_state(self):
        self.ensure_one()
        invoice = self.invoice_id
        invoice._update_payment_state()
