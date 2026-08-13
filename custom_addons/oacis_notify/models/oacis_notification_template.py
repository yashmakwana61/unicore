"""
UniCore Notification Template Model
Reusable message templates for multi-channel
notifications. Supports variable substitution
using Python's str.format() with named keys.

Template variables use {variable_name} syntax.
Available variables depend on trigger type.
Examples:
  {student_name} → student's display name
  {course_name}  → course name
  {due_date}     → fee due date
  {amount}       → outstanding fee amount
  {exam_date}    → exam date
  {exam_name}    → exam name
  {grade}        → letter grade
  {attendance}   → attendance percentage
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class UniCoreNotificationTemplate(models.Model):
    _name = 'unicore.notification.template'
    _description = 'Notification Template'
    _inherit = ['unicore.mixin']
    _order = 'trigger_event, channel'
    _check_company_auto = True

    name = fields.Char(
        string='Template Name',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Institution',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    trigger_event = fields.Selection(
        string='Trigger Event',
        required=True,
        selection=[
            ('fee_due', 'Fee Due Reminder'),
            ('fee_overdue', 'Fee Overdue Alert'),
            ('fee_paid', 'Fee Payment Confirmation'),
            ('attendance_shortage',
             'Attendance Shortage Alert'),
            ('attendance_warning',
             'Attendance Warning'),
            ('exam_reminder', 'Exam Reminder'),
            ('exam_hall_ticket',
             'Hall Ticket Available'),
            ('result_published',
             'Result Published'),
            ('enrollment_confirmed',
             'Enrollment Confirmed'),
            ('scholarship_approved',
             'Scholarship Approved'),
            ('scholarship_awarded',
             'Scholarship Award Disbursed'),
            ('leave_request_approved',
             'Leave Request Approved'),
            ('leave_request_rejected',
             'Leave Request Rejected'),
            ('welcome', 'Welcome / Admission'),
            ('custom', 'Custom / Manual'),
        ],
    )
    channel = fields.Selection(
        string='Delivery Channel',
        required=True,
        default='email',
        selection=[
            ('email', 'Email'),
            ('whatsapp', 'WhatsApp'),
            ('inapp', 'In-App (Chatter)'),
            ('all', 'All Channels'),
        ],
    )
    recipient_type = fields.Selection(
        string='Recipient Type',
        required=True,
        default='student',
        selection=[
            ('student', 'Student'),
            ('guardian', 'Guardian / Parent'),
            ('faculty', 'Faculty Member'),
            ('both', 'Student + Guardian'),
        ],
    )

    # --- EMAIL FIELDS ---

    email_subject = fields.Char(
        string='Email Subject',
        help='Used when channel is email or all. '
             'Supports {variable} substitution.',
    )
    email_body_html = fields.Html(
        string='Email Body (HTML)',
        help='HTML email body. '
             'Supports {variable} substitution.',
    )

    # --- WHATSAPP FIELDS ---

    whatsapp_body = fields.Text(
        string='WhatsApp Message Body',
        help='Plain text message for WhatsApp. '
             'Max 4096 characters. '
             'Supports {variable} substitution.',
    )
    whatsapp_template_name = fields.Char(
        string='WhatsApp Template Name',
        help='Pre-approved WhatsApp Business '
             'message template name (if using '
             'template messages for first-contact)',
    )

    # --- IN-APP FIELDS ---

    inapp_body = fields.Text(
        string='In-App Message Body',
        help='Posted to chatter of student/guardian '
             'record. Supports {variable} substitution.',
    )

    # --- SETTINGS ---

    is_system_template = fields.Boolean(
        string='System Template',
        default=False,
        help='System templates cannot be deleted',
    )
    is_active_trigger = fields.Boolean(
        string='Active for Auto-Send',
        default=True,
        help='If False this template is not used '
             'for automated notifications',
    )
    language_code = fields.Char(
        string='Language Code',
        default='en',
        size=10,
    )

    _sql_constraints = [
        (
            'unique_template_event_channel_company',
            'UNIQUE(trigger_event, channel, company_id)',
            'A template for this event and channel '
            'already exists for this company.',
        ),
    ]

    def render_template(self, variables):
        """
        Renders this template with given variables dict.
        Returns dict with rendered subject, body_html,
        whatsapp_body, inapp_body.
        Variables example:
        {
            'student_name': 'Arjun Mehta',
            'due_date': '2025-08-15',
            'amount': '27500',
            'course_name': 'Data Structures',
        }
        """
        self.ensure_one()
        result = {}
        try:
            if self.email_subject:
                result['email_subject'] = (
                    self.email_subject.format(**variables)
                )
            if self.email_body_html:
                body = self.email_body_html
                if isinstance(body, str):
                    result['email_body_html'] = (
                        body.format(**variables)
                    )
                else:
                    result['email_body_html'] = body
            if self.whatsapp_body:
                result['whatsapp_body'] = (
                    self.whatsapp_body.format(**variables)
                )
            if self.inapp_body:
                result['inapp_body'] = (
                    self.inapp_body.format(**variables)
                )
        except KeyError as e:
            _logger.warning(
                'Template "%s" missing variable: %s',
                self.name, str(e),
            )
            result['error'] = str(e)
        return result

    def unlink(self):
        for rec in self:
            if rec.is_system_template:
                raise ValidationError(
                    _('System templates cannot '
                      'be deleted.'),
                )
        return super().unlink()
