"""
UniCore Scholarship Award Model
The actual disbursement record for an approved
scholarship application. Links to fee invoice
for direct adjustment. Tracks per-semester
disbursements.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class UniCoreScholarshipAward(models.Model):
    _name = 'unicore.scholarship.award'
    _description = 'Scholarship Award Disbursement'
    _inherit = ['unicore.mixin', 'mail.thread']
    _order = 'disbursement_date desc'
    _check_company_auto = True

    award_number = fields.Char(
        string='Award Number',
        readonly=True,
        copy=False,
        index=True,
    )
    application_id = fields.Many2one(
        comodel_name='unicore.scholarship.application',
        string='Application',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    scholarship_program_id = fields.Many2one(
        comodel_name='unicore.scholarship.program',
        string='Scholarship Program',
        related='application_id.scholarship_program_id',
        store=True,
        readonly=True,
    )
    student_id = fields.Many2one(
        comodel_name='unicore.student',
        string='Student',
        related='application_id.student_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        related='application_id.company_id',
        store=True,
        readonly=True,
    )
    semester_id = fields.Many2one(
        comodel_name='unicore.semester',
        string='Semester',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    award_amount = fields.Monetary(
        string='Award Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='scholarship_program_id.currency_id',
        store=True,
        readonly=True,
    )
    disbursement_method = fields.Selection(
        string='Disbursement Method',
        required=True,
        default='fee_adjustment',
        tracking=True,
        selection=[
            ('fee_adjustment', 'Fee Invoice Adjustment'),
            ('bank_transfer', 'Bank Transfer'),
            ('cheque', 'Cheque'),
            ('cash', 'Cash'),
        ],
    )
    disbursement_date = fields.Date(
        string='Disbursement Date',
        tracking=True,
    )

    # --- FEE INVOICE LINK ---

    fee_invoice_id = fields.Many2one(
        comodel_name='unicore.fee.invoice',
        string='Applied to Fee Invoice',
        ondelete='set null',
        domain="[('student_id','=',"
               "student_id),"
               "('invoice_state','not in',"
               "['paid','cancelled'])]",
        help='Link to the fee invoice this award '
             'is applied against as a discount',
        tracking=True,
    )
    fee_adjustment_applied = fields.Boolean(
        string='Fee Adjustment Applied',
        default=False,
        readonly=True,
    )
    reference = fields.Char(
        string='Reference / Transaction ID',
    )
    remarks = fields.Text(
        string='Remarks',
    )

    # --- STATUS ---

    award_state = fields.Selection(
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('disbursed', 'Disbursed'),
            ('cancelled', 'Cancelled'),
        ],
    )

    _unique_award_number = models.Constraint(
        'UNIQUE(award_number)',
        'Award number must be unique.',
    )

    @api.constrains('award_amount')
    def _check_award_amount(self):
        for rec in self:
            if rec.award_amount <= 0:
                raise ValidationError(
                    _('Award amount must be positive.')
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('award_number'):
                vals['award_number'] = (
                    self.env['ir.sequence'].next_by_code(
                        'unicore.scholarship.award'
                    ) or '/'
                )
        return super().create(vals_list)

    def action_approve_award(self):
        self.ensure_one()
        if (self.application_id.application_state
                != 'approved'):
            raise UserError(
                _('The linked application must be '
                  'approved before approving the award.')
            )
        self.award_state = 'approved'
        self.message_post(
            body=_('Award approved.')
        )

    def action_disburse(self):
        """
        Mark award as disbursed. If method is
        fee_adjustment and fee_invoice_id is set,
        apply the award amount as a discount on
        the linked fee invoice.
        """
        self.ensure_one()
        if self.award_state != 'approved':
            raise UserError(
                _('Only approved awards can be disbursed.')
            )

        if (self.disbursement_method == 'fee_adjustment'
                and self.fee_invoice_id
                and not self.fee_adjustment_applied):
            invoice = self.fee_invoice_id
            current_discount = invoice.discount_amount
            new_discount = min(
                current_discount + self.award_amount,
                invoice.subtotal,
            )
            reason = (
                (invoice.discount_reason or '')
                + _(' | Scholarship: %s')
                % self.scholarship_program_id.name
            ).strip(' |')
            invoice.sudo().write({
                'discount_amount': new_discount,
                'discount_reason': reason,
            })
            self.fee_adjustment_applied = True
            invoice.message_post(
                body=_(
                    'Scholarship award %s applied '
                    'as discount of %s.'
                ) % (self.award_number,
                     self.award_amount)
            )

        self.write({
            'award_state': 'disbursed',
            'disbursement_date': fields.Date.today(),
        })
        self.message_post(
            body=_('Award disbursed: %s via %s.')
                 % (self.award_amount,
                    self.disbursement_method)
        )

    def action_cancel(self):
        self.ensure_one()
        if (self.award_state == 'disbursed'
                and self.fee_adjustment_applied):
            raise UserError(
                _('Cannot cancel a disbursed award '
                  'that has been applied to a fee '
                  'invoice. Reverse the fee adjustment '
                  'first.')
            )
        self.award_state = 'cancelled'
        self.message_post(
            body=_('Award cancelled.')
        )
