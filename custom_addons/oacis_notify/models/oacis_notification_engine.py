"""
UniCore Notification Engine
The core service class providing methods for sending
notifications across all channels. All other modules
import and call these methods.

Usage from other modules:
    Engine = self.env['unicore.notification.engine']
    Engine.send_to_student(
        student=student_record,
        trigger_event='fee_due',
        variables={
            'student_name': student.display_name,
            'due_date': str(invoice.due_date),
            'amount': str(invoice.amount_outstanding),
        }
    )
"""

import json
import logging

from odoo import api, models

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    _logger = logging.getLogger(__name__)
    _logger.warning(
        'requests library not available. '
        'WhatsApp notifications will not work. '
        'Install requests: pip install requests',
    )

_logger = logging.getLogger(__name__)


class UniCoreNotificationEngine(models.AbstractModel):
    """
    Abstract model providing notification sending
    methods. Use self.env['unicore.notification.engine']
    to access these methods from any model.
    """
    _name = 'unicore.notification.engine'
    _description = 'Notification Engine'

    @api.model
    def _get_template(self, trigger_event, channel,
                       company_id):
        """
        Find the best matching template for the given
        event, channel and company. Falls back to
        'all' channel template if no exact match.
        """
        Template = self.env[
            'unicore.notification.template'
        ]
        template = Template.search([
            ('trigger_event', '=', trigger_event),
            ('channel', '=', channel),
            ('company_id', '=', company_id),
            ('is_active_trigger', '=', True),
            ('active', '=', True),
        ], limit=1)
        if not template:
            template = Template.search([
                ('trigger_event', '=', trigger_event),
                ('channel', '=', 'all'),
                ('company_id', '=', company_id),
                ('is_active_trigger', '=', True),
                ('active', '=', True),
            ], limit=1)
        return template

    @api.model
    def _log_notification(self, channel, trigger_event,
                           company_id, status,
                           recipient_email=None,
                           recipient_mobile=None,
                           message_subject=None,
                           message_body=None,
                           student_id=None,
                           guardian_id=None,
                           faculty_member_id=None,
                           template_id=None,
                           error_message=None,
                           whatsapp_message_id=None,
                           recipient_type=None):
        """Create an immutable notification log entry."""
        self.env['unicore.notification.log'].sudo().create({
            'company_id': company_id,
            'channel': channel,
            'trigger_event': trigger_event,
            'recipient_type': recipient_type,
            'student_id': student_id,
            'guardian_id': guardian_id,
            'faculty_member_id': faculty_member_id,
            'recipient_email': recipient_email,
            'recipient_mobile': recipient_mobile,
            'message_subject': message_subject,
            'message_body': message_body,
            'template_id': template_id,
            'delivery_status': status,
            'error_message': error_message,
            'whatsapp_message_id': whatsapp_message_id,
        })

    @api.model
    def _send_email(self, to_email, subject, body_html,
                     company_id, from_name=None):
        """
        Send email using Odoo's mail.mail model.
        Returns True on success, False on failure.
        """
        if not to_email:
            _logger.warning(
                'Cannot send email: no recipient address.',
            )
            return False
        try:
            company = self.env['res.company'].browse(
                company_id,
            )
            email_from = (
                '%s <%s>' % (
                    from_name or 'UniCore ERP',
                    company.email or 'noreply@unicore.edu',
                )
            )
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject or '(No Subject)',
                'body_html': body_html or '',
                'email_to': to_email,
                'email_from': email_from,
                'auto_delete': False,
            })
            mail.send()
            return True
        except Exception as e:
            _logger.error(
                'Email send failed to %s: %s',
                to_email, str(e),
            )
            return False

    @api.model
    def _send_whatsapp(self, to_mobile, message_body,
                        company_id):
        """
        Send WhatsApp message via Meta Business
        Cloud API. Returns (success, message_id_or_error).
        """
        if not HAS_REQUESTS:
            return False, 'requests library not installed'
        if not to_mobile:
            return False, 'No mobile number provided'

        Config = self.env[
            'unicore.notification.config'
        ]
        config = Config.get_config_for_company(company_id)

        if not config.whatsapp_enabled:
            return False, 'WhatsApp not enabled'
        if not config.whatsapp_phone_number_id:
            return False, 'Phone Number ID not configured'
        if not config.whatsapp_access_token:
            return False, 'Access Token not configured'

        # Clean mobile number (remove spaces, dashes)
        clean_mobile = ''.join(
            c for c in to_mobile
            if c.isdigit() or c == '+'
        )
        if clean_mobile.startswith('+'):
            clean_mobile = clean_mobile[1:]

        url = '%s/%s/messages' % (
            config.whatsapp_api_url,
            config.whatsapp_phone_number_id,
        )
        headers = {
            'Authorization': 'Bearer %s'
                             % config.whatsapp_access_token,
            'Content-Type': 'application/json',
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': clean_mobile,
            'type': 'text',
            'text': {
                'body': message_body,
            },
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                message_id = (
                    data.get('messages', [{}])[0]
                    .get('id', 'unknown')
                )
                return True, message_id
            error = response.text
            _logger.error(
                'WhatsApp API error %s: %s',
                response.status_code, error,
            )
            return False, error
        except Exception as e:
            _logger.error(
                'WhatsApp send failed: %s', str(e),
            )
            return False, str(e)

    @api.model
    def _test_whatsapp_connection(self, config):
        """
        Test WhatsApp API by checking account info.
        Returns True if API responds correctly.
        """
        if not HAS_REQUESTS:
            return False
        try:
            url = '%s/%s' % (
                config.whatsapp_api_url,
                config.whatsapp_phone_number_id,
            )
            headers = {
                'Authorization': 'Bearer %s'
                                 % config.whatsapp_access_token,
            }
            response = requests.get(
                url, headers=headers, timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            _logger.error(
                'WhatsApp test failed: %s', str(e),
            )
            return False

    @api.model
    def send_to_student(self, student, trigger_event,
                         variables=None):
        """
        Main method to send notification to a student.
        Determines channel from notification config and
        student's available contact details.
        Logs the notification result.

        Args:
            student: unicore.student record
            trigger_event: str (matches template trigger)
            variables: dict of template variables

        Returns:
            dict with 'email', 'whatsapp', 'inapp'
            keys, each True/False
        """
        if variables is None:
            variables = {}

        company_id = student.company_id.id
        Config = self.env['unicore.notification.config']
        config = Config.get_config_for_company(company_id)

        # Default variables always available
        variables.setdefault(
            'student_name', student.display_name,
        )
        variables.setdefault(
            'student_id', student.student_id_number,
        )
        variables.setdefault(
            'institution_name',
            student.company_id.name,
        )

        results = {
            'email': False,
            'whatsapp': False,
            'inapp': False,
        }

        # EMAIL
        if config.email_enabled:
            template = self._get_template(
                trigger_event, 'email', company_id,
            )
            if template:
                rendered = template.render_template(
                    variables,
                )
                to_email = (
                    student.institutional_email
                    or student.email
                )
                success = self._send_email(
                    to_email=to_email,
                    subject=rendered.get('email_subject'),
                    body_html=rendered.get(
                        'email_body_html',
                    ),
                    company_id=company_id,
                )
                results['email'] = success
                self._log_notification(
                    channel='email',
                    trigger_event=trigger_event,
                    company_id=company_id,
                    status='sent' if success else 'failed',
                    recipient_email=to_email,
                    message_subject=rendered.get(
                        'email_subject',
                    ),
                    message_body=rendered.get(
                        'email_body_html', '',
                    )[:2000],
                    student_id=student.id,
                    template_id=template.id,
                    recipient_type='student',
                )

        # WHATSAPP
        if config.whatsapp_enabled and student.mobile:
            template = self._get_template(
                trigger_event, 'whatsapp', company_id,
            )
            if template:
                rendered = template.render_template(
                    variables,
                )
                wa_body = rendered.get('whatsapp_body')
                if wa_body:
                    success, msg_id = self._send_whatsapp(
                        to_mobile=student.mobile,
                        message_body=wa_body,
                        company_id=company_id,
                    )
                    results['whatsapp'] = success
                    self._log_notification(
                        channel='whatsapp',
                        trigger_event=trigger_event,
                        company_id=company_id,
                        status='sent' if success
                               else 'failed',
                        recipient_mobile=student.mobile,
                        message_body=wa_body,
                        student_id=student.id,
                        template_id=template.id,
                        whatsapp_message_id=(
                            msg_id if success else None
                        ),
                        error_message=(
                            None if success
                            else str(msg_id)
                        ),
                        recipient_type='student',
                    )

        # IN-APP
        if config.inapp_enabled and student.partner_id:
            template = self._get_template(
                trigger_event, 'inapp', company_id,
            )
            if template:
                rendered = template.render_template(
                    variables,
                )
                inapp_body = rendered.get('inapp_body')
                if inapp_body and hasattr(
                    student, 'message_post',
                ):
                    try:
                        student.message_post(
                            body=inapp_body,
                            message_type='comment',
                            subtype_xmlid='mail.mt_note',
                        )
                        results['inapp'] = True
                        self._log_notification(
                            channel='inapp',
                            trigger_event=trigger_event,
                            company_id=company_id,
                            status='sent',
                            message_body=inapp_body,
                            student_id=student.id,
                            template_id=template.id,
                            recipient_type='student',
                        )
                    except Exception as e:
                        _logger.error(
                            'In-app notify failed: %s',
                            str(e),
                        )

        return results

    @api.model
    def send_to_guardian(self, guardian, trigger_event,
                          variables=None, student=None):
        """
        Send notification to a guardian.
        Uses guardian's preferred contact method.
        """
        if variables is None:
            variables = {}

        company_id = guardian.company_id.id
        Config = self.env['unicore.notification.config']
        config = Config.get_config_for_company(company_id)

        variables.setdefault(
            'guardian_name', guardian.display_name,
        )
        if student:
            variables.setdefault(
                'student_name', student.display_name,
            )

        results = {'email': False, 'whatsapp': False}

        # EMAIL
        if config.email_enabled and guardian.email:
            template = self._get_template(
                trigger_event, 'email', company_id,
            )
            if template:
                rendered = template.render_template(
                    variables,
                )
                success = self._send_email(
                    to_email=guardian.email,
                    subject=rendered.get('email_subject'),
                    body_html=rendered.get(
                        'email_body_html',
                    ),
                    company_id=company_id,
                )
                results['email'] = success
                self._log_notification(
                    channel='email',
                    trigger_event=trigger_event,
                    company_id=company_id,
                    status='sent' if success else 'failed',
                    recipient_email=guardian.email,
                    message_subject=rendered.get(
                        'email_subject',
                    ),
                    guardian_id=guardian.id,
                    student_id=student.id if student
                               else None,
                    template_id=template.id,
                    recipient_type='guardian',
                )

        # WHATSAPP (prefer whatsapp_number over mobile)
        wa_number = (
            guardian.whatsapp_number or guardian.mobile
        )
        if config.whatsapp_enabled and wa_number:
            template = self._get_template(
                trigger_event, 'whatsapp', company_id,
            )
            if template:
                rendered = template.render_template(
                    variables,
                )
                wa_body = rendered.get('whatsapp_body')
                if wa_body:
                    success, msg_id = self._send_whatsapp(
                        to_mobile=wa_number,
                        message_body=wa_body,
                        company_id=company_id,
                    )
                    results['whatsapp'] = success
                    self._log_notification(
                        channel='whatsapp',
                        trigger_event=trigger_event,
                        company_id=company_id,
                        status='sent' if success
                               else 'failed',
                        recipient_mobile=wa_number,
                        message_body=wa_body,
                        guardian_id=guardian.id,
                        student_id=student.id if student
                                   else None,
                        template_id=template.id,
                        whatsapp_message_id=(
                            msg_id if success else None
                        ),
                        error_message=(
                            None if success
                            else str(msg_id)
                        ),
                        recipient_type='guardian',
                    )

        return results

    @api.model
    def send_batch_fee_reminders(self, company_id,
                                  days_before=7):
        """
        Send fee due reminders to all students whose
        fee is due in `days_before` days.
        Called by cron or manually by finance staff.
        """
        from datetime import date, timedelta
        Invoice = self.env['unicore.fee.invoice']
        target_date = date.today() + timedelta(
            days=days_before,
        )
        due_invoices = Invoice.search([
            ('company_id', '=', company_id),
            ('due_date', '=', target_date),
            ('invoice_state', 'in', ['sent', 'partial']),
            ('amount_outstanding', '>', 0),
        ])
        sent_count = 0
        for invoice in due_invoices:
            student = invoice.student_id
            variables = {
                'student_name': student.display_name,
                'due_date': str(invoice.due_date),
                'amount': str(
                    round(invoice.amount_outstanding, 2),
                ),
                'invoice_number': invoice.invoice_number,
            }
            self.send_to_student(
                student=student,
                trigger_event='fee_due',
                variables=variables,
            )
            for rel in student.guardian_rel_ids.filtered(
                lambda r: r.can_receive_notifications
                          and r.is_active_relationship,
            ):
                self.send_to_guardian(
                    guardian=rel.guardian_id,
                    trigger_event='fee_due',
                    variables=variables,
                    student=student,
                )
            sent_count += 1
        _logger.info(
            'Sent %d fee reminders for company %d.',
            sent_count, company_id,
        )
        return sent_count

    @api.model
    def send_attendance_shortage_alerts(self, company_id):
        """
        Send attendance shortage alerts to all students
        with shortage_alert = True. Called by cron.
        """
        AttRecord = self.env['unicore.attendance.record']
        shortage_records = AttRecord.search([
            ('company_id', '=', company_id),
            ('shortage_alert', '=', True),
        ])
        student_ids_alerted = set()
        for record in shortage_records:
            student = record.student_id
            if student.id in student_ids_alerted:
                continue
            student_ids_alerted.add(student.id)
            variables = {
                'student_name': student.display_name,
                'attendance': str(
                    round(
                        record
                        .cumulative_attendance_percentage,
                        1,
                    ),
                ),
                'course_name': (
                    record.course_id.name
                    if record.course_id else ''
                ),
                'minimum_required': '75',
            }
            self.send_to_student(
                student=student,
                trigger_event='attendance_shortage',
                variables=variables,
            )
        _logger.info(
            'Sent attendance shortage alerts to %d '
            'students for company %d.',
            len(student_ids_alerted), company_id,
        )
        return len(student_ids_alerted)
