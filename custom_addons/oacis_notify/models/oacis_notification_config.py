"""
Oacis Notification Config Model
Per-company configuration for notification channels.
Stores WhatsApp API credentials, email defaults
and global notification preferences.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class OacisNotificationConfig(models.Model):
    _name = 'oacis.notification.config'
    _description = 'Notification Configuration'
    _inherit = ['oacis.mixin']
    _order = 'company_id'
    _check_company_auto = True

    name = fields.Char(
        string='Config Name',
        required=True,
        default='Default Notification Config',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )

    # --- EMAIL SETTINGS ---

    email_enabled = fields.Boolean(
        string='Email Notifications Enabled',
        default=True,
    )
    email_from_name = fields.Char(
        string='From Name',
        default='Oacis ERP',
        help='Display name for outgoing emails',
    )
    email_footer_text = fields.Text(
        string='Email Footer',
        help='Standard footer added to all emails',
    )

    # --- WHATSAPP SETTINGS ---

    whatsapp_enabled = fields.Boolean(
        string='WhatsApp Notifications Enabled',
        default=False,
    )
    whatsapp_api_url = fields.Char(
        string='WhatsApp API URL',
        default='https://graph.facebook.com/v18.0',
        help='Meta WhatsApp Business Cloud API base URL',
    )
    whatsapp_phone_number_id = fields.Char(
        string='WhatsApp Phone Number ID',
        help='Your WhatsApp Business phone number ID '
             'from Meta Business Manager',
    )
    whatsapp_access_token = fields.Char(
        string='WhatsApp Access Token',
        help='Permanent access token from Meta '
             'Business Manager. Stored encrypted.',
    )
    whatsapp_business_account_id = fields.Char(
        string='WhatsApp Business Account ID',
    )

    # --- IN-APP SETTINGS ---

    inapp_enabled = fields.Boolean(
        string='In-App Notifications Enabled',
        default=True,
        help='Post notification as chatter messages '
             'on student/guardian records',
    )

    # --- NOTIFICATION PREFERENCES ---

    notify_on_fee_due = fields.Boolean(
        string='Fee Due Reminders',
        default=True,
    )
    notify_on_attendance_shortage = fields.Boolean(
        string='Attendance Shortage Alerts',
        default=True,
    )
    notify_on_exam_reminder = fields.Boolean(
        string='Exam Reminders',
        default=True,
    )
    notify_on_result_published = fields.Boolean(
        string='Result Published Alerts',
        default=True,
    )
    notify_on_enrollment = fields.Boolean(
        string='Enrollment Confirmation',
        default=True,
    )
    fee_reminder_days_before = fields.Integer(
        string='Fee Reminder Days Before Due',
        default=7,
        help='Send fee reminder N days before due date',
    )
    exam_reminder_days_before = fields.Integer(
        string='Exam Reminder Days Before',
        default=3,
    )

    _sql_constraints = [
        (
            'unique_config_company',
            'UNIQUE(company_id)',
            'A notification config already exists '
            'for this company.',
        ),
    ]

    @api.constrains('fee_reminder_days_before',
                    'exam_reminder_days_before')
    def _check_reminder_days(self):
        for rec in self:
            if rec.fee_reminder_days_before < 0:
                raise ValidationError(
                    _('Fee reminder days cannot '
                      'be negative.'),
                )
            if rec.exam_reminder_days_before < 0:
                raise ValidationError(
                    _('Exam reminder days cannot '
                      'be negative.'),
                )

    def action_test_whatsapp(self):
        """
        Test WhatsApp API connection by sending
        a test message to the configured number.
        """
        self.ensure_one()
        if not self.whatsapp_enabled:
            raise UserError(
                _('WhatsApp is not enabled.'),
            )
        if not self.whatsapp_phone_number_id:
            raise UserError(
                _('Please configure WhatsApp '
                  'Phone Number ID.'),
            )
        if not self.whatsapp_access_token:
            raise UserError(
                _('Please configure WhatsApp '
                  'Access Token.'),
            )
        Engine = self.env['oacis.notification.engine']
        result = Engine._test_whatsapp_connection(self)
        if result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WhatsApp Connection OK'),
                    'message': _(
                        'WhatsApp API connection '
                        'successful.',
                    ),
                    'type': 'success',
                },
            }
        raise UserError(
            _('WhatsApp API connection failed. '
              'Check your credentials and URL.'),
        )

    @api.model
    def get_config_for_company(self, company_id):
        """Returns config for company, creates default
        if not found."""
        config = self.search([
            ('company_id', '=', company_id),
        ], limit=1)
        if not config:
            config = self.create({
                'name': 'Default Notification Config',
                'company_id': company_id,
            })
        return config
