"""
Oacis Admission Automation Engine — Phase A
Deterministic rule service (trigger -> condition -> action) shared by the
applicant lifecycle and a daily cron. Rules are ``oacis.admission.automation.rule``
records; this abstract model performs the lookups and the delivery.

Every lookup is company-scoped to the triggering record, and every delivery is
wrapped so a broken template can never block the underlying state transition —
failures are logged to the applicant chatter instead.
"""

import logging
from datetime import date, datetime, time, timedelta

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class OacisAdmissionAutomationEngine(models.AbstractModel):
    _name = 'oacis.admission.automation.engine'
    _description = 'Admission Automation Engine'

    # ------------------------------------------------------------------
    # State / stage triggers
    # ------------------------------------------------------------------

    @api.model
    def _fire_state_change(self, record, old_state, new_state):
        """Fire matching active ``on_state_change`` rules for ``record``.

        :param record: oacis.admission.applicant (or recordset, iterated).
        :param old_state: previous state value or ``False``.
        :param new_state: current state value.
        """
        if old_state == new_state:
            return
        Rule = self.env['oacis.admission.automation.rule']
        for rec in record:
            rules = Rule.search([
                ('company_id', '=', rec.company_id.id),
                ('active', '=', True),
                ('trigger_type', '=', 'on_state_change'),
                ('trigger_state', '=', new_state),
            ])
            for rule in rules:
                self._send(rule, rec)

    @api.model
    def _fire_stage_change(self, record, old_stage, new_stage):
        """Fire matching active ``on_stage_change`` rules for ``record``."""
        if not new_stage or old_stage.id == new_stage.id:
            return
        Rule = self.env['oacis.admission.automation.rule']
        for rec in record:
            rules = Rule.search([
                ('company_id', '=', rec.company_id.id),
                ('active', '=', True),
                ('trigger_type', '=', 'on_stage_change'),
                ('trigger_stage_id', '=', new_stage.id),
            ])
            for rule in rules:
                self._send(rule, rec)

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    @api.model
    def _send(self, rule, record):
        """Deliver ``rule`` to ``record`` (email / in-app / both).

        Failures never propagate: they are logged to the record chatter so a
        broken template cannot block the surrounding state transition.
        """
        if rule.channel in ('email', 'both'):
            if rule.mail_template_id:
                try:
                    rule.mail_template_id.send_mail(
                        record.id, force_send=True, raise_exception=True,
                    )
                except Exception as exc:
                    _logger.warning(
                        'Automation rule "%s" email failed for %s: %s',
                        rule.name, record.display_name, exc,
                    )
                    record.message_post(
                        body=_('Automation rule "%s" failed: %s') % (
                            rule.name, exc,
                        ),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
        if rule.channel in ('in_app', 'both'):
            try:
                body = _('Automation triggered: %s') % rule.name
                if rule.mail_template_id:
                    rendered = rule.mail_template_id._render_field(
                        'body_html', record.ids,
                    )
                    rendered_body = rendered.get(record.id)
                    if rendered_body:
                        body = rendered_body
                record.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
            except Exception as exc:
                _logger.warning(
                    'Automation rule "%s" in-app delivery failed for %s: %s',
                    rule.name, record.display_name, exc,
                )
                record.message_post(
                    body=_('Automation rule "%s" failed: %s') % (
                        rule.name, exc,
                    ),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

    # ------------------------------------------------------------------
    # Date-based cron trigger
    # ------------------------------------------------------------------

    @api.model
    def _run_date_based_rules(self):
        """Scan active ``date_based`` rules and fire for applicants whose
        ``date_field + date_offset_days`` is today.

        Called daily by the ``oacis_admission_automation_cron``.
        """
        fired_count = 0
        Rule = self.env['oacis.admission.automation.rule']
        Applicant = self.env['oacis.admission.applicant']
        rules = Rule.search([
            ('active', '=', True),
            ('trigger_type', '=', 'date_based'),
        ])
        today = date.today()
        for rule in rules:
            field_name = rule.date_field
            if field_name not in ('create_date', 'date_of_birth', 'entrance_test_date'):
                _logger.warning(
                    'Automation rule "%s" has unsupported date field %r.',
                    rule.name, field_name,
                )
                continue
            target_date = today + timedelta(days=rule.date_offset_days or 0)
            domain = [('company_id', '=', rule.company_id.id)]
            if field_name == 'create_date':
                start = datetime.combine(target_date, time.min)
                end = datetime.combine(target_date, time.max)
                domain += [('create_date', '>=', start), ('create_date', '<=', end)]
            else:
                domain.append((field_name, '=', target_date))
            records = Applicant.search(domain)
            for record in records:
                self._send(rule, record)
            if records:
                _logger.info(
                    'Date-based automation rule "%s" fired for %d applicant(s).',
                    rule.name, len(records),
                )
                fired_count += len(records)
        return fired_count
