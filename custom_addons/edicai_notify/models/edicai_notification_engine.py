"""
Edicai Notification Engine
The core service class providing methods for sending
notifications across all channels. All other modules
import and call these methods.

Usage from other modules:
    Engine = self.env['edicai.notification.engine']
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

from odoo import api, fields, models

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


class EdicaiNotificationEngine(models.AbstractModel):
    """
    Abstract model providing notification sending
    methods. Use self.env['edicai.notification.engine']
    to access these methods from any model.
    """
    _name = 'edicai.notification.engine'
    _description = 'Notification Engine'

    # Per-company config flag guarding each NEW event-driven
    # trigger. Legacy triggers (fee_due, fee_overdue, ...)
    # are intentionally NOT gated here so existing flows keep
    # their exact behaviour; gating for those lives at the
    # cron / call-site level only.

    TRIGGER_CONFIG_FLAG = {
        'fee_due_7d': 'notify_on_fee_due_7d',
        'fee_due_3d': 'notify_on_fee_due_3d',
        'fee_due_1d': 'notify_on_fee_due_1d',
        'exam_hall_ticket': 'notify_on_hall_ticket',
        'leave_request_approved': 'notify_on_leave_decision',
        'leave_request_rejected': 'notify_on_leave_decision',
        'grievance_resolved': 'notify_on_grievance_decision',
        'grievance_cancelled': 'notify_on_grievance_decision',
    }

    @api.model
    def _config_allows(self, company_id, flag,
                       default=True):
        """Return True when the per-company config flag is on.

        Missing flags on older configs default to ``default``
        so upgrades stay backward compatible.
        """
        try:
            config = self.env[
                'edicai.notification.config'
            ].get_config_for_company(company_id)
            return bool(getattr(config, flag, default))
        except Exception as e:
            _logger.warning(
                'Notification config lookup failed for '
                'company %s: %s', company_id, str(e),
            )
            return default

    @api.model
    def _recently_notified(
        self, trigger_event, student_id, hours=24,
        fee_invoice_id=None, course_offering_id=None,
    ):
        """Idempotency check for event-driven notifications.

        Returns True when a log already exists for the same
        trigger + student (+ invoice / offering when given)
        within the last ``hours`` hours.
        """
        try:
            from datetime import timedelta
            cutoff = fields.Datetime.now() - timedelta(
                hours=hours,
            )
            domain = [
                ('trigger_event', '=', trigger_event),
                ('student_id', '=', student_id),
                ('sent_at', '>=', cutoff),
                ('delivery_status', 'in',
                 ['sent', 'delivered', 'pending']),
            ]
            if fee_invoice_id:
                domain.append(
                    ('fee_invoice_id', '=', fee_invoice_id),
                )
            if course_offering_id:
                domain.append(
                    ('course_offering_id', '=',
                     course_offering_id),
                )
            return bool(self.env[
                'edicai.notification.log'
            ].sudo().search_count(domain, limit=1))
        except Exception as e:
            _logger.warning(
                'Idempotency check failed for %s / '
                'student %s: %s',
                trigger_event, student_id, str(e),
            )
            return False

    # ===================================================
    # SAFE EVENT EMISSION API
    # ===================================================

    @api.model
    def _safe_emit(self, student, trigger_event,
                   variables=None, include_guardians=False,
                   fee_invoice_id=None,
                   course_offering_id=None):
        """
        Fire-and-forget event emission for business flows.

        Never raises: any failure (missing template, disabled
        channel, provider error) is logged and swallowed so a
        notification problem can never break a transaction in
        the calling module. Call sites guard the lookup with
        ``'edicai.notification.engine' in self.env`` to stay
        install-order safe.

        New event-driven triggers are additionally gated by
        their per-company config flag (see
        TRIGGER_CONFIG_FLAG); a disabled flag skips emission
        and returns False.
        """
        if not student or not student.id:
            return False
        flag = self.TRIGGER_CONFIG_FLAG.get(trigger_event)
        if flag:
            try:
                company_id = (
                    student.company_id.id
                    if hasattr(student, 'company_id')
                    and student.company_id
                    else self.env.company.id
                )
            except Exception:
                company_id = self.env.company.id
            if not self._config_allows(company_id, flag):
                return False
        try:
            self.send_to_student(
                student, trigger_event, variables,
                fee_invoice_id=fee_invoice_id,
                course_offering_id=course_offering_id,
            )
        except Exception as e:
            _logger.warning(
                'Notification %s to student %s failed: %s',
                trigger_event, student.id, str(e),
            )
            return False
        if include_guardians:
            try:
                rels = self.env[
                    'edicai.guardian.student.rel'
                ].sudo().search([
                    ('student_id', '=', student.id),
                    ('is_active_relationship', '=', True),
                ])
            except Exception as e:
                _logger.warning(
                    'Guardian lookup failed for student '
                    '%s: %s', student.id, str(e),
                )
                rels = self.env[
                    'edicai.guardian.student.rel'
                ]
            for rel in rels:
                guardian = rel.guardian_id
                if not guardian or not guardian.id:
                    continue
                try:
                    self.send_to_guardian(
                        guardian, trigger_event,
                        dict(variables or {}), student=student,
                        fee_invoice_id=fee_invoice_id,
                        course_offering_id=(
                            course_offering_id
                        ),
                    )
                except Exception as e:
                    _logger.warning(
                        'Notification %s to guardian %s '
                        'failed: %s',
                        trigger_event, guardian.id, str(e),
                    )
        return True

    @api.model
    def _get_template(self, trigger_event, channel,
                       company_id):
        """
        Find the best matching template for the given
        event, channel and company. Falls back to
        'all' channel template if no exact match.
        """
        Template = self.env[
            'edicai.notification.template'
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
                           recipient_type=None,
                           fee_invoice_id=None,
                           course_offering_id=None):
        """Create an immutable notification log entry."""
        self.env['edicai.notification.log'].sudo().create({
            'company_id': company_id,
            'channel': channel,
            'trigger_event': trigger_event,
            'recipient_type': recipient_type,
            'student_id': student_id,
            'guardian_id': guardian_id,
            'faculty_member_id': faculty_member_id,
            'fee_invoice_id': fee_invoice_id,
            'course_offering_id': course_offering_id,
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
                    from_name or 'Edicai ERP',
                    company.email or 'noreply@edicai.edu',
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
            'edicai.notification.config'
        ]
        config = Config.get_config_for_company(company_id)

        if not config.whatsapp_enabled:
            return False, 'WhatsApp not enabled'
        if not config.whatsapp_phone_number_id:
            return False, 'Phone Number ID not configured'
        access_token = config._get_whatsapp_access_token()
        if not access_token:
            return False, (
                'Access Token not configured (set EDICAI_WHATSAPP_TOKEN '
                'or the stored field as system administrator)')

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
            'Authorization': 'Bearer %s' % access_token,
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
                                 % config._get_whatsapp_access_token(),
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
                         variables=None, fee_invoice_id=None,
                         course_offering_id=None):
        """
        Main method to send notification to a student.
        Determines channel from notification config and
        student's available contact details.
        Logs the notification result.

        Args:
            student: edicai.student record
            trigger_event: str (matches template trigger)
            variables: dict of template variables

        Returns:
            dict with 'email', 'whatsapp', 'inapp'
            keys, each True/False
        """
        if variables is None:
            variables = {}

        company_id = student.company_id.id
        Config = self.env['edicai.notification.config']
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
        variables.setdefault(
            'portal_url',
            student.get_base_url() + '/my/edicai/student',
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
                    fee_invoice_id=fee_invoice_id,
                    course_offering_id=course_offering_id,
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
                        fee_invoice_id=fee_invoice_id,
                        course_offering_id=(
                            course_offering_id
                        ),
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
                            fee_invoice_id=fee_invoice_id,
                            course_offering_id=(
                                course_offering_id
                            ),
                        )
                    except Exception as e:
                        _logger.error(
                            'In-app notify failed: %s',
                            str(e),
                        )

        return results

    @api.model
    def send_to_guardian(self, guardian, trigger_event,
                          variables=None, student=None,
                          fee_invoice_id=None,
                          course_offering_id=None):
        """
        Send notification to a guardian.
        Uses guardian's preferred contact method.
        """
        if variables is None:
            variables = {}

        company_id = guardian.company_id.id
        Config = self.env['edicai.notification.config']
        config = Config.get_config_for_company(company_id)

        variables.setdefault(
            'guardian_name', guardian.display_name,
        )
        if student:
            variables.setdefault(
                'student_name', student.display_name,
            )
        variables.setdefault(
            'portal_url',
            guardian.get_base_url() + '/my/edicai/guardian',
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
                    fee_invoice_id=fee_invoice_id,
                    course_offering_id=course_offering_id,
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
                        fee_invoice_id=fee_invoice_id,
                        course_offering_id=(
                            course_offering_id
                        ),
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
        Invoice = self.env['edicai.fee.invoice']
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
        AttRecord = self.env['edicai.attendance.record']
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

    # ===================================================
    # EVENT-DRIVEN HELPERS (never raise; callers use
    # _safe_emit semantics and per-company flags)
    # ===================================================

    FEE_MILESTONES = (7, 3, 1)

    @api.model
    def send_fee_milestone_reminders(self, company_id,
                                     days_before=None):
        """Scan invoices due in N days and emit milestone
        reminders (fee_due_7d / 3d / 1d).

        Idempotency: an invoice is skipped when a log already
        exists for the same invoice + milestone in the last
        24h. Company scope and per-company flags are
        respected. Never raises.
        """
        from datetime import date, timedelta
        milestones = (
            (days_before,) if days_before is not None
            else self.FEE_MILESTONES
        )
        try:
            Invoice = self.env['edicai.fee.invoice']
        except Exception as e:
            _logger.warning(
                'Fee milestone scan skipped: %s', str(e),
            )
            return 0
        sent = 0
        for milestone in milestones:
            flag = self.TRIGGER_CONFIG_FLAG.get(
                'fee_due_%dd' % milestone
            )
            if flag and not self._config_allows(
                company_id, flag,
            ):
                continue
            target = date.today() + timedelta(
                days=milestone,
            )
            try:
                invoices = Invoice.search([
                    ('company_id', '=', company_id),
                    ('due_date', '=', target),
                    ('invoice_state', 'in',
                     ['sent', 'partial', 'overdue']),
                    ('amount_outstanding', '>', 0),
                ])
            except Exception as e:
                _logger.warning(
                    'Fee milestone search failed for '
                    'company %s: %s', company_id, str(e),
                )
                continue
            trigger = 'fee_due_%dd' % milestone
            for inv in invoices:
                try:
                    if self._recently_notified(
                        trigger, inv.student_id.id,
                        hours=24,
                        fee_invoice_id=inv.id,
                    ):
                        continue
                    ok = self._safe_emit(
                        inv.student_id,
                        trigger,
                        {
                            'amount': str(round(
                                inv.amount_outstanding, 2,
                            )),
                            'invoice_number': (
                                inv.invoice_number or ''
                            ),
                            'due_date': str(inv.due_date),
                            'days_remaining': str(milestone),
                        },
                        include_guardians=True,
                        fee_invoice_id=inv.id,
                    )
                    sent += 1 if ok else 0
                except Exception as e:
                    _logger.warning(
                        'Fee milestone %s failed for '
                        'invoice %s: %s',
                        trigger, inv.id, str(e),
                    )
        return sent

    @api.model
    def maybe_notify_attendance_shortage(self, record):
        """Notify once when a closed-session recompute drops
        a student below the policy minimum.

        ``record`` is an edicai.attendance.record with
        shortage_alert True. Skips when the company flag is
        off or a shortage log already exists for the same
        student + offering in the last 30 days (recovery
        re-arms: once attendance recovers above the minimum
        no new shortage logs accrue, so the next fresh drop
        notifies again). Never raises.
        """
        try:
            if not record or not getattr(
                record, 'shortage_alert', False,
            ):
                return False
            student = record.student_id
            if not student or not student.id:
                return False
            company_id = (
                record.company_id.id
                if getattr(record, 'company_id', False)
                else student.company_id.id
            )
            if not self._config_allows(
                company_id, 'notify_on_attendance_shortage',
            ):
                return False
            offering_id = (
                record.course_offering_id.id
                if getattr(
                    record, 'course_offering_id', False,
                ) else None
            )
            if offering_id and self._recently_notified(
                'attendance_shortage', student.id,
                hours=24 * 30,
                course_offering_id=offering_id,
            ):
                return False
            policy = None
            try:
                policy = self.env[
                    'edicai.attendance.policy'
                ].get_policy_for_offering(
                    record.course_offering_id,
                )
            except Exception:
                policy = None
            minimum = (
                str(policy.min_attendance_percentage)
                if policy else '75'
            )
            return bool(self._safe_emit(
                student,
                'attendance_shortage',
                {
                    'attendance': str(round(
                        record
                        .cumulative_attendance_percentage,
                        1,
                    )),
                    'course_name': (
                        record.course_id.display_name
                        if getattr(
                            record, 'course_id', False,
                        ) else ''
                    ),
                    'minimum_required': minimum,
                },
                include_guardians=True,
                course_offering_id=offering_id,
            ))
        except Exception as e:
            _logger.warning(
                'Attendance shortage event failed: %s',
                str(e),
            )
            return False

    @api.model
    def notify_hall_ticket_approved(self, ticket):
        """Notify a student that their hall ticket was
        approved. Never raises."""
        try:
            student = ticket.student_id
            if not student or not student.id:
                return False
            schedule = ticket.exam_schedule_id
            return bool(self._safe_emit(
                student,
                'exam_hall_ticket',
                {
                    'exam_name': (
                        schedule.display_name
                        if schedule else ''
                    ),
                    'course_name': (
                        ticket.course_id.display_name
                        if getattr(
                            ticket, 'course_id', False,
                        ) else ''
                    ),
                    'exam_date': str(
                        getattr(ticket, 'exam_date', '')
                        or '',
                    ),
                    'ticket_number': (
                        ticket.ticket_number or ''
                    ),
                },
                include_guardians=False,
            ))
        except Exception as e:
            _logger.warning(
                'Hall ticket notification failed: %s',
                str(e),
            )
            return False

    @api.model
    def notify_leave_decision(self, student, guardian,
                              trigger_event, variables):
        """Leave approve/reject fan-out via _safe_emit.

        Notifies the student (flag-gated) and, when a
        guardian record is linked, that guardian. Never
        raises.
        """
        try:
            if not self._config_allows(
                student.company_id.id,
                'notify_on_leave_decision',
            ):
                return False
        except Exception:
            pass
        ok = self._safe_emit(
            student, trigger_event,
            dict(variables or {}),
        )
        if guardian and getattr(guardian, 'id', False):
            try:
                self.send_to_guardian(
                    guardian, trigger_event,
                    dict(variables or {}),
                    student=student,
                )
            except Exception as e:
                _logger.warning(
                    'Leave decision guardian notify '
                    'failed: %s', str(e),
                )
        return bool(ok)

    @api.model
    def notify_grievance_decision(self, student,
                                  trigger_event,
                                  variables):
        """Grievance resolve/cancel fan-out via _safe_emit.
        Flag-gated (off by default). Never raises."""
        try:
            return bool(self._safe_emit(
                student, trigger_event,
                dict(variables or {}),
            ))
        except Exception as e:
            _logger.warning(
                'Grievance decision notify failed: %s',
                str(e),
            )
            return False
