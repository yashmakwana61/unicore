"""
Oacis Notification Log Model
Immutable audit log of every notification sent
or attempted. Records channel, recipient, status,
error message and timestamp.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OacisNotificationLog(models.Model):
    _name = 'oacis.notification.log'
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
        comodel_name='oacis.notification.template',
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
        comodel_name='oacis.student',
        string='Student',
        ondelete='set null',
        index=True,
    )
    guardian_id = fields.Many2one(
        comodel_name='oacis.guardian',
        string='Guardian',
        ondelete='set null',
    )
    faculty_member_id = fields.Many2one(
        comodel_name='oacis.faculty.member',
        string='Faculty Member',
        ondelete='set null',
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
        raise UserError(
            _('Notification logs are immutable '
              'and cannot be edited.'),
        )

    def unlink(self):
        raise UserError(
            _('Notification logs cannot be deleted. '
              'This is an audit compliance requirement.'),
        )
