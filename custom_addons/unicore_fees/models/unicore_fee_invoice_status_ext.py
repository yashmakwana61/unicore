"""
UniCore Fee Invoice — Status Update Extension
Updates invoice status based on GL reconciliation and payments.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class UniCoreFeeInvoiceStatusExt(models.Model):
    _inherit = 'unicore.fee.invoice'

    gl_fully_reconciled = fields.Boolean(
        string='GL Fully Reconciled',
        compute='_compute_gl_reconciliation_status',
        store=True,
        help='True if all GL receivable lines are matched and reconciled',
    )

    @api.depends('account_move_id', 'account_move_id.line_ids', 'account_move_id.payment_state')
    def _compute_gl_reconciliation_status(self):
        """Check if all GL receivable lines are reconciled in the GL."""
        for rec in self:
            if not rec.account_move_id or rec.account_move_id.state != 'posted':
                rec.gl_fully_reconciled = False
                continue

            # Get all receivable lines from GL invoice
            ar_lines = rec.account_move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
            )

            if not ar_lines:
                rec.gl_fully_reconciled = False
                continue

            # Check if all AR lines are reconciled
            unreconciled = ar_lines.filtered(lambda l: not l.reconciled)
            rec.gl_fully_reconciled = len(unreconciled) == 0

    def _update_payment_state(self):
        """
        Override to update invoice state based on GL reconciliation.

        Updates invoice state considering both fee payments
        and GL reconciliation status.
        """
        self.ensure_one()

        # Original logic from parent
        if self.amount_outstanding <= 0:
            self.invoice_state = 'paid'
        elif self.amount_paid > 0:
            self.invoice_state = 'partial'
        elif self.due_date and self.due_date < date.today():
            self.invoice_state = 'overdue'

        # Log GL reconciliation status
        if self.account_move_id and self.gl_fully_reconciled:
            self.message_post(body=_(
                'Invoice status updated: %s (GL: Fully Reconciled)'
            ) % self.get_selection_value('invoice_state'))
        elif self.account_move_id:
            self.message_post(body=_(
                'Invoice status updated: %s (GL: Partial Reconciliation)'
            ) % self.get_selection_value('invoice_state'))

    def get_selection_value(self, field_name):
        """Helper to get display value for selection field."""
        field = self._fields[field_name]
        value = getattr(self, field_name)
        if field.type == 'selection':
            selection_dict = dict(field.selection)
            return selection_dict.get(value, value)
        return value

    def action_view_gl_reconciliation_status(self):
        """Open a report view showing GL reconciliation status."""
        self.ensure_one()

        if not self.account_move_id:
            raise UserError(_('No GL invoice linked to this fee invoice.'))

        if not self.account_move_id.line_ids:
            raise UserError(_('GL invoice has no line items.'))

        # Show GL lines with reconciliation status
        return {
            'type': 'ir.actions.act_window',
            'name': _('GL Reconciliation Status'),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.account_move_id.id)],
            'context': {
                'group_by': 'reconciled',
                'create': False,
            },
        }
