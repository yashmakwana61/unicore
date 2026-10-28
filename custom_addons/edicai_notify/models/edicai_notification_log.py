"""
Edicai Notification Log Model
Immutable audit log of every notification sent
or attempted. Records channel, recipient, status,
error message and timestamp.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EdicaiNotificationLog(models.Model):
    _name = 'edicai.notification.log'
    _description = 'Notification Log'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        depends=['message_subject', 'recipient_email', 'recipient_mobile',
                 'student_id.display_name', 'guardian_id.display_name',
                 'faculty_member_id.display_name'],
    )

    @api.depends('message_subject', 'recipient_email', 'recipient_mobile',
                 'student_id.display_name', 'guardian_id.display_name',
                 'faculty_member_id.display_name')
    def _compute_display_name(self):
        for rec in self:
            recipient = (
                rec.recipient_email or rec.recipient_mobile or ''
            )
            if not recipient:
                recipient = (
                    rec.student_id.display_name
                    or rec.guardian_id.display_name
                    or rec.faculty_member_id.display_name
                    or ''
                )
            if recipient:
                rec.display_name = '%s - %s' % (
                    rec.message_subject or '', recipient,
                )
            else:
                rec.display_name = rec.message_subject or ''
    _order = 'sent_at desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        index=True,
    )
    template_id = fields.Many2one(
        comodel_name='edicai.notification.template',
        string='Template Used',
        ondelete='set null',
    )
    trigger_event = fields.Char(
        string='Trigger Event',
        readonly=True,
    )
    channel = fields.Selection(
        string='Channel',
        required=True,
        readonly=True,
        selection=[
            ('email', 'Email'),
            ('whatsapp', 'WhatsApp'),
            ('inapp', 'In-App'),
        ],
    )
    recipient_type = fields.Selection(
        string='Recipient Type',
        readonly=True,
        selection=[
            ('student', 'Student'),
            ('guardian', 'Guardian'),
            ('faculty', 'Faculty'),
        ],
    )
    student_id = fields.Many2one(
        comodel_name='edicai.student',
        string='Student',
        ondelete='set null',
        index=True,
    )
    guardian_id = fields.Many2one(
        comodel_name='edicai.guardian',
        string='Guardian',
        ondelete='set null',
    )
    faculty_member_id = fields.Many2one(
        comodel_name='edicai.faculty.member',
        string='Faculty Member',
        ondelete='set null',
    )
    # --- EVENT IDEMPOTENCY REFERENCES ---
    # Optional links populated by the event-driven engine
    # so milestone / shortage notifications can be
    # de-duplicated (same invoice+template, same
    # student+offering) without parsing message bodies.

    fee_invoice_id = fields.Many2one(
        comodel_name='edicai.fee.invoice',
        string='Fee Invoice',
        ondelete='set null',
        index=True,
    )
    course_offering_id = fields.Many2one(
        comodel_name='edicai.course.offering',
        string='Course Offering',
        ondelete='set null',
        index=True,
    )
    recipient_email = fields.Char(
        string='Recipient Email',
        readonly=True,
    )
    recipient_mobile = fields.Char(
        string='Recipient Mobile',
        readonly=True,
    )
    message_subject = fields.Char(
        string='Subject',
        readonly=True,
    )
    message_body = fields.Text(
        string='Message Body',
        readonly=True,
    )
    sent_at = fields.Datetime(
        string='Sent At',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    delivery_status = fields.Selection(
        string='Delivery Status',
        required=True,
        default='pending',
        readonly=True,
        selection=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
    )
    error_message = fields.Text(
        string='Error Message',
        readonly=True,
    )
    whatsapp_message_id = fields.Char(
        string='WhatsApp Message ID',
        readonly=True,
        help='Message ID returned by WhatsApp API',
    )

    def write(self, vals):
        # Retention anonymization is the only sanctioned write path.
        if self.env.context.get('edicai_retention_anonymize'):
            return super().write(vals)
        raise UserError(
            _('Notification logs are immutable '
              'and cannot be edited.'),
        )

    def unlink(self):
        raise UserError(
            _('Notification logs cannot be deleted. '
              'Use the retention policy to anonymize old logs.'),
        )

    # ------------------------------------------------------------------
    # GDPR / DPDP retention: personal data is scrubbed from logs older
    # than the configured window instead of deleting audit rows.
    # ------------------------------------------------------------------

    RETENTION_DAYS_PARAM = 'edicai_notify.log_retention_days'
    DEFAULT_RETENTION_DAYS = 365

    @api.model
    def _get_retention_days(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                self.RETENTION_DAYS_PARAM,
                default=str(self.DEFAULT_RETENTION_DAYS),
            ))
        except (TypeError, ValueError):
            return self.DEFAULT_RETENTION_DAYS

    @api.model
    def cron_anonymize_old_logs(self):
        """Scrub PII from notification logs past the retention window.

        Keeps the audit trail (channel, status, timestamps) intact while
        honouring the right-to-erasure for contact details and message
        content.
        """
        days = self._get_retention_days()
        if days <= 0:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        stale = self.sudo().search([
            ('sent_at', '<', cutoff),
            '|', '|',
            ('recipient_email', '!=', False),
            ('recipient_mobile', '!=', False),
            ('message_body', '!=', False),
        ])
        if not stale:
            return 0
        stale.with_context(
            edicai_retention_anonymize=True,
        ).write({
            'recipient_email': False,
            'recipient_mobile': False,
            'message_body': False,
            'whatsapp_message_id': False,
        })
        _logger.info(
            'Edicai notification log retention: anonymized %d logs '
            'older than %d days.', len(stale), days,
        )
        return len(stale)
