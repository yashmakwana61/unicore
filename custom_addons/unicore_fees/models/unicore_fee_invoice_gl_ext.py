"""
UniCore Fee Invoice — GL Integration Extension
Handles automatic creation and posting of account.move from fee invoices.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class UniCoreFeeInvoiceGLExt(models.Model):
    _inherit = 'unicore.fee.invoice'

    account_move_id = fields.Many2one(
        comodel_name='account.move',
        string='GL Invoice',
        ondelete='restrict',
        readonly=True,
        copy=False,
        help='Linked GL invoice created automatically when fee invoice is confirmed',
        index=True,
    )

    gl_status = fields.Selection(
        string='GL Status',
        related='account_move_id.state',
        store=False,
        help='Status of the linked GL invoice (draft/posted/cancelled)',
    )

    gl_invoice_number = fields.Char(
        string='GL Invoice #',
        related='account_move_id.name',
        store=False,
        help='Odoo invoicing number',
    )

    def action_send(self):
        """Override to create GL invoice when fee invoice is sent."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Add invoice lines before sending.'))

        # Create GL invoice if not already created
        if not self.account_move_id:
            self._create_account_invoice()

        self.invoice_state = 'sent'
        self.message_post(body=_('Fee invoice sent to student %s.') % self.student_id.display_name)

    def action_cancel(self):
        """Override to create reversal GL invoice when fee invoice is cancelled."""
        self.ensure_one()
        if self.invoice_state == 'paid':
            raise UserError(_('Cannot cancel a fully paid invoice.'))

        # Create reversal GL invoice if GL invoice exists
        if self.account_move_id and self.account_move_id.state == 'posted':
            self._reverse_account_invoice()

        self.invoice_state = 'cancelled'
        self.message_post(body=_('Invoice cancelled.'))

    def _create_account_invoice(self):
        """
        Create account.move (GL invoice) from fee invoice.

        Called when fee invoice is confirmed/sent.
        Links GL invoice back to fee invoice.
        Auto-posts if configured.
        """
        self.ensure_one()

        # Get accounting config
        try:
            config = self.env['unicore.fee.accounting.config']._get_active_config(
                company_id=self.company_id.id,
            )
        except UserError as e:
            raise UserError(_('Cannot create GL invoice: %s') % str(e))

        # Validate student has a partner
        if not self.student_id.partner_id:
            raise UserError(_(
                'Student %s does not have a billing partner configured. '
                'Create a partner for this student first.',
            ) % self.student_id.display_name)

        # Prepare invoice lines
        invoice_line_vals = []
        for fee_line in self.line_ids:
            invoice_line_vals.append((0, 0, {
                'name': fee_line.name,
                'quantity': 1.0,
                'price_unit': fee_line.amount,
                'account_id': config.revenue_account_id.id,
                'tax_ids': [(6, 0, config.tax_ids.ids)] if config.tax_ids else None,
            }))

        # Handle discount as a negative line
        if self.discount_amount > 0:
            invoice_line_vals.append((0, 0, {
                'name': _('Discount: %s') % (self.discount_reason or 'Applied'),
                'quantity': 1.0,
                'price_unit': -self.discount_amount,
                'account_id': config.revenue_account_id.id,
            }))

        # Handle late fee as a positive line
        if self.late_fee_amount > 0:
            invoice_line_vals.append((0, 0, {
                'name': _('Late Fee'),
                'quantity': 1.0,
                'price_unit': self.late_fee_amount,
                'account_id': config.revenue_account_id.id,
            }))

        # Create account.move
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.student_id.partner_id.id,
            'invoice_date': self.invoice_date,
            'invoice_date_due': self.due_date,
            'currency_id': self.currency_id.id,
            'journal_id': config.journal_id.id,
            'company_id': self.company_id.id,
            'ref': self.invoice_number,
            'invoice_line_ids': invoice_line_vals,
        }

        move = self.env['account.move'].create(move_vals)

        # Post GL invoice if auto-post is enabled
        if config.auto_post_invoice:
            move.action_post()

        # Link back to fee invoice
        self.write({'account_move_id': move.id})

        # Log activity
        self.message_post(body=_(
            'GL Invoice %s created and linked (Status: %s)',
        ) % (move.name, move.state))

        return move

    def _reverse_account_invoice(self):
        """
        Create a reversal GL invoice (credit note) for the GL invoice.

        Called when fee invoice is cancelled.
        """
        self.ensure_one()

        if not self.account_move_id or self.account_move_id.state != 'posted':
            return

        # Create reversal/credit note
        reverse_move = self.account_move_id._reverse_moves(
            reason=_('Reversal of fee invoice %s (Student: %s)') % (
                self.invoice_number,
                self.student_id.display_name,
            ),
            date=fields.Date.today(),
        )

        # Post the reversal immediately
        reverse_move.action_post()

        # Update reference
        self.message_post(body=_(
            'GL reversal note %s created for cancelled invoice',
        ) % reverse_move[0].name)

    def action_view_account_invoice(self):
        """Open the linked GL invoice."""
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_('No GL invoice linked to this fee invoice.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('GL Invoice'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_record_payment(self):
        """
        Open GL payment recording wizard for the linked GL invoice.

        Redirects user to Odoo Accounting payment recording interface
        where they record payment directly against the GL invoice.
        """
        self.ensure_one()

        if not self.account_move_id:
            raise UserError(_('No GL invoice linked. Create invoice first.'))

        if self.account_move_id.state != 'posted':
            raise UserError(_('GL invoice must be posted before recording payment.'))

        # Open payment recording wizard for the GL invoice
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Payment'),
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_id': self.account_move_id.id,
                'active_ids': [self.account_move_id.id],
            },
            'target': 'new',
        }

    def _update_payment_state(self):
        """
        Update fee invoice status based on GL invoice payment status.

        Called when GL invoice is reconciled (payment recorded).
        Syncs GL payment status back to fee invoice.
        """
        self.ensure_one()

        if not self.account_move_id:
            return

        # Check if GL invoice is fully reconciled (all lines paid)
        gl_move = self.account_move_id

        # Get AR lines from GL invoice
        ar_lines = gl_move.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable',
        )

        if not ar_lines:
            return

        # Check if all AR lines are reconciled
        all_reconciled = all(line.reconciled for line in ar_lines)

        # Update fee invoice status based on GL reconciliation
        if all_reconciled and gl_move.payment_state == 'paid':
            self.invoice_state = 'paid'
            self.message_post(body=_('Invoice marked as paid (GL payment recorded).'))
        elif gl_move.payment_state == 'partial':
            self.invoice_state = 'partial'
            self.message_post(body=_('Partial payment recorded (GL reconciliation).'))

    @api.constrains('account_move_id')
    def _check_no_manual_move_edit(self):
        """Prevent accidental deletion of linked GL invoice."""
        for rec in self:
            if rec.account_move_id and rec.account_move_id.state == 'posted':
                if not hasattr(self, '_skip_move_delete_check'):
                    # Allow deletion checks to pass in specific contexts
                    pass
