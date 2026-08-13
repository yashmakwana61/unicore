"""
Oacis Notification Extensions (Assignments)
Extends the notification engine and template model to support
assignment-related trigger events and faculty notifications:
  - assignment_published : students informed when assignment is out
  - assignment_submitted : faculty informed when a submission arrives
  - assignment_graded    : student informed when work is graded

Also adds a send_to_faculty() helper to the engine that mirrors
the existing send_to_student() / send_to_guardian() helpers.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class OacisNotificationTemplateExt(models.Model):
    _inherit = 'oacis.notification.template'

    trigger_event = fields.Selection(
        selection_add=[
            ('assignment_published',
             'Assignment Published'),
            ('assignment_submitted',
             'Assignment Submitted'),
            ('assignment_graded',
             'Assignment Graded'),
        ],
        ondelete={
            'assignment_published': 'cascade',
            'assignment_submitted': 'cascade',
            'assignment_graded': 'cascade',
        },
    )


class OacisNotificationEngineExt(models.AbstractModel):
    _inherit = 'oacis.notification.engine'

    def send_to_faculty(self, faculty, trigger_event,
                        variables=None, student=None):
        """
        Send a notification to a faculty member.
        Mirrors send_to_student/send_to_guardian but
        targets oacis.faculty.member records.

        Args:
            faculty: oacis.faculty.member record
            trigger_event: str (matches template trigger)
            variables: dict of template variables
            student: optional oacis.student record

        Returns:
            dict with 'email', 'whatsapp', 'inapp' keys
        """
        if variables is None:
            variables = {}

        company_id = faculty.company_id.id
        Config = self.env['oacis.notification.config']
        config = Config.get_config_for_company(company_id)

        variables.setdefault(
            'faculty_name', faculty.display_name,
        )
        if student:
            variables.setdefault(
                'student_name', student.display_name,
            )
        variables.setdefault(
            'institution_name', faculty.company_id.name,
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
                rendered = template.render_template(variables)
                to_email = (
                    faculty.institutional_email or faculty.email
                )
                success = self._send_email(
                    to_email=to_email,
                    subject=rendered.get('email_subject'),
                    body_html=rendered.get('email_body_html'),
                    company_id=company_id,
                )
                results['email'] = success
                self._log_notification(
                    channel='email',
                    trigger_event=trigger_event,
                    company_id=company_id,
                    status='sent' if success else 'failed',
                    recipient_email=to_email,
                    message_subject=rendered.get('email_subject'),
                    message_body=rendered.get(
                        'email_body_html', '',
                    )[:2000],
                    faculty_member_id=faculty.id,
                    student_id=student.id if student else None,
                    template_id=template.id,
                    recipient_type='faculty',
                )

        # WHATSAPP
        if config.whatsapp_enabled and faculty.mobile:
            template = self._get_template(
                trigger_event, 'whatsapp', company_id,
            )
            if template:
                rendered = template.render_template(variables)
                wa_body = rendered.get('whatsapp_body')
                if wa_body:
                    success, msg_id = self._send_whatsapp(
                        to_mobile=faculty.mobile,
                        message_body=wa_body,
                        company_id=company_id,
                    )
                    results['whatsapp'] = success
                    self._log_notification(
                        channel='whatsapp',
                        trigger_event=trigger_event,
                        company_id=company_id,
                        status='sent' if success else 'failed',
                        recipient_mobile=faculty.mobile,
                        message_body=wa_body,
                        faculty_member_id=faculty.id,
                        student_id=student.id if student else None,
                        template_id=template.id,
                        whatsapp_message_id=(
                            msg_id if success else None
                        ),
                        error_message=(
                            None if success else str(msg_id)
                        ),
                        recipient_type='faculty',
                    )

        # IN-APP
        if config.inapp_enabled and faculty.partner_id:
            template = self._get_template(
                trigger_event, 'inapp', company_id,
            )
            if template:
                rendered = template.render_template(variables)
                inapp_body = rendered.get('inapp_body')
                if inapp_body and hasattr(faculty, 'message_post'):
                    try:
                        faculty.message_post(
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
                            faculty_member_id=faculty.id,
                            student_id=(
                                student.id if student else None
                            ),
                            template_id=template.id,
                            recipient_type='faculty',
                        )
                    except Exception as e:
                        _logger.error(
                            'In-app notify failed: %s', str(e),
                        )

        return results
