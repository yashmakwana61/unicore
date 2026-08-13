"""
Oacis Fee Invoice — GL Migration & Batch Processing
Handles one-time migration of existing invoices and continuous processing.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisFeeInvoiceMigration(models.Model):
    _inherit = 'oacis.fee.invoice'

    gl_migrated = fields.Boolean(
        string='GL Migrated',
        default=False,
        readonly=True,
        help='True if this invoice has been migrated to GL',
    )

    def action_migrate_to_gl(self):
        """
        Migrate existing fee invoice to GL invoice.

        Can be called individually or in batch.
        Only creates GL invoice if:
        - Invoice status is 'sent' or later
        - No GL invoice already exists
        - GL config exists
        """
        migrated_count = 0
        failed_count = 0
        errors = []

        for invoice in self:
            try:
                # Skip if already has GL invoice
                if invoice.account_move_id:
                    _logger.info('Invoice %s already has GL invoice, skipping',
                                invoice.invoice_number)
                    continue

                # Skip if draft (not yet sent)
                if invoice.invoice_state == 'draft':
                    _logger.info('Invoice %s is draft, skipping', invoice.invoice_number)
                    continue

                # Create GL invoice using existing method
                invoice._create_account_invoice()
                invoice.write({'gl_migrated': True})
                migrated_count += 1

                _logger.info('Successfully migrated invoice %s to GL',
                            invoice.invoice_number)

            except UserError as e:
                failed_count += 1
                error_msg = 'Invoice %s: %s' % (invoice.invoice_number, str(e))
                errors.append(error_msg)
                _logger.error(error_msg)
            except Exception as e:
                failed_count += 1
                error_msg = 'Invoice %s: Unexpected error: %s' % (
                    invoice.invoice_number, str(e))
                errors.append(error_msg)
                _logger.error(error_msg)

        # Log summary
        summary = _('GL Migration Complete\n'
                   'Migrated: %d invoices\n'
                   'Failed: %d invoices') % (migrated_count, failed_count)

        if errors:
            summary += '\n\nErrors:\n' + '\n'.join(errors)

        if self.env.context.get('return_summary'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Migration Summary',
                    'message': summary,
                    'type': 'warning' if errors else 'success',
                },
            }

        return summary

    @api.model
    def action_batch_create_gl_invoices(self):
        """
        Batch create GL invoices for all sent invoices without GL.

        Called by cron job to continuously process pending invoices.
        """
        # Find all sent invoices without GL invoice
        pending_invoices = self.search([
            ('invoice_state', 'in', ['sent', 'partial', 'paid', 'overdue']),
            ('account_move_id', '=', False),
        ])

        if not pending_invoices:
            _logger.info('No pending invoices for GL migration')
            return 0

        _logger.info('Processing %d pending invoices for GL migration',
                    len(pending_invoices))

        return len(pending_invoices.action_migrate_to_gl())

    def action_batch_reconcile_payments(self):
        """
        Deprecated: Payment reconciliation is now handled by GL payment recording.

        Payments are recorded directly in Odoo Accounting module via the
        "Record Payment" button on fee invoices. No batch reconciliation needed.
        """
        _logger.info('Payment reconciliation is now handled by GL module directly')
        return 0


class OacisFeeInvoiceBatchWizard(models.TransientModel):
    _name = 'oacis.fee.invoice.batch.wizard'
    _description = 'Fee Invoice GL Batch Migration Wizard'

    migration_type = fields.Selection(
        string='Migration Type',
        required=True,
        selection=[
            ('all', 'Migrate All Invoices (Without GL)'),
            ('sent', 'Migrate Sent Invoices Only'),
            ('paid', 'Migrate Paid Invoices Only'),
            ('reconcile', 'Reconcile Pending Payments'),
        ],
        default='all',
    )

    create_partners = fields.Boolean(
        string='Create Missing Partners',
        default=True,
        help='Auto-create res.partner for students without partners',
    )

    auto_post = fields.Boolean(
        string='Auto-Post GL Invoices',
        default=False,
        help='Automatically post GL invoices to GL (recommended: False for review)',
    )

    dry_run = fields.Boolean(
        string='Dry Run (Preview Only)',
        default=False,
        help='Preview what would be migrated without making changes',
    )

    def action_migrate(self):
        """Execute batch migration."""
        self.ensure_one()

        Invoice = self.env['oacis.fee.invoice']

        # Build query based on migration type
        if self.migration_type == 'all':
            query = [
                ('invoice_state', 'in', ['sent', 'partial', 'paid', 'overdue']),
                ('account_move_id', '=', False),
            ]
        elif self.migration_type == 'sent':
            query = [
                ('invoice_state', '=', 'sent'),
                ('account_move_id', '=', False),
            ]
        elif self.migration_type == 'paid':
            query = [
                ('invoice_state', '=', 'paid'),
                ('account_move_id', '=', False),
            ]
        else:  # reconcile
            # Handle payment reconciliation instead
            return self._action_reconcile_payments()

        invoices = Invoice.search(query)

        if not invoices:
            raise UserError(_('No invoices found matching the criteria.'))

        # Create missing partners if requested
        if self.create_partners:
            self._create_missing_partners(invoices)

        # Perform dry run or actual migration
        if self.dry_run:
            message = _(
                'DRY RUN: Would migrate %d invoices to GL.\n\n'
                'Invoices to migrate:\n%s',
            ) % (len(invoices), '\n'.join(
                [inv.invoice_number for inv in invoices[:20]],
            ))
            if len(invoices) > 20:
                message += _('\n... and %d more') % (len(invoices) - 20)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Migration Preview',
                    'message': message,
                    'type': 'info',
                    'sticky': True,
                },
            }
        # Perform actual migration
        summary = invoices.action_migrate_to_gl()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Migration Complete',
                'message': summary,
                'type': 'success',
                'sticky': True,
            },
        }

    def _create_missing_partners(self, invoices):
        """Create res.partner for students without partners."""
        for invoice in invoices:
            if not invoice.student_id.partner_id:
                try:
                    partner = invoice.student_id._create_student_partner(
                        invoice.student_id,
                    )
                    invoice.student_id.write({'partner_id': partner.id})
                    _logger.info('Created partner for student %s',
                                invoice.student_id.student_id_number)
                except Exception as e:
                    _logger.warning(
                        'Failed to create partner for student %s: %s',
                        invoice.student_id.student_id_number, str(e),
                    )

    def _action_reconcile_payments(self):
        """Reconcile pending payments."""
        Payment = self.env['oacis.fee.payment']

        pending_payments = Payment.search([
            ('payment_state', '=', 'confirmed'),
            ('gl_matching_line_ids', '=', False),
            ('invoice_id.account_move_id', '!=', False),
        ])

        if not pending_payments:
            raise UserError(_(
                'No pending payments to reconcile.',
            ))

        if self.dry_run:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Reconciliation Preview',
                    'message': _(
                        'DRY RUN: Would reconcile %d payments with GL.',
                    ) % len(pending_payments),
                    'type': 'info',
                },
            }

        # Perform reconciliation
        reconciled = 0
        for payment in pending_payments:
            try:
                payment._reconcile_with_gl()
                reconciled += 1
            except Exception as e:
                _logger.error('Failed to reconcile payment %s: %s',
                            payment.receipt_number, str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reconciliation Complete',
                'message': _('Reconciled %d payments.') % reconciled,
                'type': 'success',
            },
        }
