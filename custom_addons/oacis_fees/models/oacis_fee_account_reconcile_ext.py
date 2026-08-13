"""
Oacis Fee Invoice — GL Reconciliation Extension

Bridges the Odoo Accounting reconciliation flow (account.payment.register,
manual reconciliation, bank statement reconciliation) back to the Fees module.

Whenever an `account.partial.reconcile` is created (a payment is matched to a
GL invoice receivable line) or removed (the payment is un-reconciled), the fee
invoices linked to the involved GL invoices are refreshed so that
`amount_paid`, `amount_outstanding` and `invoice_state` stay in sync with the
GL. Without this hook the Fees module would keep showing a paid invoice as
outstanding.
"""

from odoo import api, models


class OacisFeeAccountReconcileExt(models.Model):
    _inherit = 'account.partial.reconcile'

    @api.model_create_multi
    def create(self, vals_list):
        partials = super().create(vals_list)
        self._sync_fee_invoices(
            partials.debit_move_id + partials.credit_move_id,
        )
        return partials

    def unlink(self):
        # Snapshot the involved journal items before the partials are removed,
        # since `self` is empty after super().unlink().
        amls = self.debit_move_id + self.credit_move_id
        res = super().unlink()
        self._sync_fee_invoices(amls)
        return res

    def _sync_fee_invoices(self, amls):
        """Refresh fee invoices linked to the GL moves of these journal items."""
        moves = amls.move_id
        if not moves:
            return

        invoices = self.env['oacis.fee.invoice'].sudo().search([
            ('account_move_id', 'in', moves.ids),
        ])
        for invoice in invoices:
            # Reads the (recomputed) amount_outstanding / amount_paid and
            # refreshes invoice_state to paid / partial / overdue.
            invoice._update_payment_state()
