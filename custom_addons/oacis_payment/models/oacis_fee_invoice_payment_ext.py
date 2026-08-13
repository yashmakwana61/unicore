"""
UniCore Fee Invoice — Online Payment Extension

Bridges a UniCore fee invoice to Odoo's native online payment flow.

The fee invoice already produces a posted GL account.move
(`account_move_id`). The `account_payment` module natively supports paying
such an invoice online (`/invoice/transaction/<id>`, payment providers,
automatic reconciliation). This module simply exposes that capability from
the fee invoice and keeps the fee-invoice status in sync.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class UniCoreFeeInvoicePaymentExt(models.Model):
    _inherit = 'unicore.fee.invoice'

    payment_tx_count = fields.Integer(
        string='Online Payments',
        compute='_compute_payment_tx_count',
        store=False,
        help='Number of payment transactions linked to the GL invoice.',
    )

    @api.depends('account_move_id.transaction_ids')
    def _compute_payment_tx_count(self):
        for rec in self:
            move = rec.account_move_id
            rec.payment_tx_count = len(move.transaction_ids) if move else 0

    # -------------------- HELPERS --------------------

    def _get_payable_gl_invoice(self):
        """
        Return the linked, posted GL invoice available for online payment.

        :return: The `account.move` record, or False
        :rtype: account.move | bool
        """
        self.ensure_one()
        move = self.account_move_id
        if not move or move.state != 'posted':
            return False
        return move

    def _is_payable_online(self):
        """
        Whether the fee invoice can be paid online right now.

        Delegates to the native `_has_to_be_paid()` of the GL invoice so the
        exact same rules apply (posted, outstanding balance, portal payments
        enabled, no pending transaction, ...).
        """
        self.ensure_one()
        move = self._get_payable_gl_invoice()
        return bool(move and move._has_to_be_paid())

    def _get_online_payment_error(self):
        """
        Return a human readable reason why the invoice cannot be paid online.

        :rtype: str
        """
        self.ensure_one()
        move = self._get_payable_gl_invoice()
        if not move:
            return _(
                'The GL invoice is not available for online payment. '
                'Make sure the fee invoice has been sent (GL invoice created '
                'and posted).',
            )
        return move._get_online_payment_error()

    def get_online_payment_portal_url(self):
        """
        Return the portal URL of the GL invoice (native checkout page).

        :return: The portal URL of the GL invoice, or False
        :rtype: str | bool
        """
        self.ensure_one()
        move = self._get_payable_gl_invoice()
        if not move:
            return False
        return move.get_portal_url()

    # -------------------- ACTIONS --------------------

    def action_generate_payment_link(self):
        """
        Open the native payment link wizard for the GL invoice.

        The wizard builds a shareable link (and QR code) that lets the
        student pay online without logging in.
        """
        self.ensure_one()
        move = self._get_payable_gl_invoice()
        if not move:
            raise UserError(_(
                'No posted GL invoice is linked to this fee invoice. '
                'Send the fee invoice first.',
            ))
        if not move._has_to_be_paid():
            raise UserError(_(
                'This invoice cannot be paid online. %s',
            ) % move._get_online_payment_error())

        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Payment Link'),
            'res_model': 'payment.link.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'account.move',
                'active_id': move.id,
            },
        }

    def action_view_online_payments(self):
        """Open the list of online payment transactions of the GL invoice."""
        self.ensure_one()
        txs = self.env['payment.transaction'].sudo().search([
            ('invoice_ids', 'in', self.account_move_id.ids),
        ]) if self.account_move_id else self.env['payment.transaction']
        return {
            'type': 'ir.actions.act_window',
            'name': _('Online Payments'),
            'res_model': 'payment.transaction',
            'view_mode': 'list,form',
            'domain': [('id', 'in', txs.ids)],
        }
