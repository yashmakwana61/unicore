"""
UniCore Online Payments — Transaction Post-Processing

Keeps the UniCore fee invoice status in sync with Odoo's native online
payment flow.

When a `payment.transaction` linked to the fee invoice's GL invoice is
confirmed (`done`), `account_payment` already creates and posts the
`account.payment` and reconciles the GL invoice. This extension simply
propagates that result back to the `unicore.fee.invoice` record so its
`invoice_state` stays correct for the rest of the UniCore modules.
"""

from odoo import _, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _post_process(self):
        """Override of `payment` to update fee invoice status after processing.

        Runs the native post-processing first (payment creation, posting and
        reconciliation of the linked invoices), then propagates the resulting
        GL status to the linked UniCore fee invoices.
        """
        super()._post_process()
        done_txs = self.filtered(lambda tx: tx.state == 'done' and tx.invoice_ids)
        if not done_txs:
            return

        invoices = done_txs.mapped('invoice_ids')
        fee_invoices = self.env['unicore.fee.invoice'].sudo().search([
            ('account_move_id', 'in', invoices.ids),
        ])
        for fee_invoice in fee_invoices:
            move = fee_invoice.account_move_id
            # The GL invoice is authoritative for the payment status: drop any
            # cached pre-reconciliation value before reading it.
            move.invalidate_recordset()
            move.line_ids.invalidate_recordset()
            fee_invoice.invalidate_recordset()
            if move.payment_state == 'paid':
                fee_invoice.invoice_state = 'paid'
            elif move.payment_state == 'partial':
                fee_invoice.invoice_state = 'partial'
            last_reference = fee_invoice.account_move_id.transaction_ids._get_last().reference or 'Unknown'
            fee_invoice.message_post(body=_(
                'Online payment confirmed (transaction %s).'
            ) % last_reference)
