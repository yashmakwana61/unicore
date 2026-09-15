"""
Oacis Admission Automation Rule — Phase A
Configurable deterministic rule engine record: trigger -> condition -> action.
Rules fire through the ``oacis.admission.automation.engine`` abstract service
(either on applicant state/stage change or on a date-based cron scan) and send
an email (``mail.template``) and/or an in-app chatter message.

Multi-institution safety follows the module pattern: every rule is scoped to a
``company_id`` and all lookups/firings are filtered by it.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_APPLICANT_STATES = [
    ('inquiry', 'Inquiry'),
    ('applied', 'Applied'),
    ('documents_pending', 'Documents Pending'),
    ('under_review', 'Under Review'),
    ('shortlisted', 'Shortlisted'),
    ('entrance_scheduled', 'Entrance Scheduled'),
    ('merit_listed', 'Merit Listed'),
    ('offer_sent', 'Offer Sent'),
    ('fee_pending', 'Fee Pending'),
    ('confirmed', 'Confirmed'),
    ('rejected', 'Rejected'),
    ('withdrawn', 'Withdrawn'),
    ('waitlisted', 'Waitlisted'),
]


class OacisAdmissionAutomationRule(models.Model):
    """A deterministic automation rule for the admission applicant lifecycle.

    Exactly one trigger axis is used at a time:

    - ``on_state_change`` -> fires when an applicant's ``state`` becomes
      ``trigger_state``.
    - ``on_stage_change`` -> fires when an applicant's ``stage_id`` becomes
      ``trigger_stage_id``.
    - ``date_based``     -> the cron scans applicants whose
      ``date_field + date_offset_days`` equals today and fires.

    ``channel`` decides delivery: ``email`` (via the linked ``mail.template``),
    ``in_app`` (chatter post) or ``both``.
    """

    _name = 'oacis.admission.automation.rule'
    _description = 'Admission Automation Rule'
    _inherit = 'oacis.mixin'
    _order = 'sequence, id'
    _check_company_auto = True

    name = fields.Char(string='Rule Name', required=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict',
    )
    trigger_type = fields.Selection(
        selection=[
            ('on_state_change', 'On State Change'),
            ('on_stage_change', 'On Stage Change'),
            ('date_based', 'Date Based (Cron)'),
        ],
        string='Trigger Type', required=True, default='on_state_change',
    )
    trigger_state = fields.Selection(
        selection=_APPLICANT_STATES,
        string='Trigger Status',
        help='Fire when the applicant moves INTO this status.',
    )
    trigger_stage_id = fields.Many2one(
        comodel_name='oacis.admission.stage', string='Trigger Stage',
        domain="[('company_id', '=', company_id)]",
        help='Fire when the applicant moves into this pipeline stage.',
    )
    date_field = fields.Selection(
        selection=[
            ('create_date', 'Inquiry Created Date'),
            ('date_of_birth', 'Date of Birth'),
            ('entrance_test_date', 'Entrance Test Date'),
        ],
        string='Date Field',
        help='Applicant field the date-based trigger is computed from.',
    )
    date_offset_days = fields.Integer(
        string='Offset (Days)', default=0,
        help='Negative = days before, positive = days after the date field. '
             'Example: -3 fires three days before the entrance test date.',
    )
    channel = fields.Selection(
        selection=[
            ('email', 'Email'),
            ('in_app', 'In-App'),
            ('both', 'Email + In-App'),
        ],
        string='Delivery Channel', required=True, default='email',
    )
    mail_template_id = fields.Many2one(
        comodel_name='mail.template', string='Email Template',
        domain="[('model_id.model', '=', 'oacis.admission.applicant')]",
        help='mail.template bound to oacis.admission.applicant. Used when '
             'channel is email or both.',
    )
    active = fields.Boolean(
        string='Active', default=True,
        help='Inactive rules never fire. New rules are created inactive so a '
             'registrar must review and activate them first.',
    )
    sequence = fields.Integer(string='Sequence', default=10)

    @api.constrains(
        'trigger_type', 'trigger_state', 'trigger_stage_id', 'date_field',
        'channel', 'mail_template_id', 'active',
    )
    def _check_rule_combination(self):
        for record in self:
            if record.trigger_type == 'on_state_change' and not record.trigger_state:
                raise ValidationError(_(
                    'Trigger Status is required for "On State Change" rules.',
                ))
            if record.trigger_type == 'on_stage_change' and not record.trigger_stage_id:
                raise ValidationError(_(
                    'Trigger Stage is required for "On Stage Change" rules.',
                ))
            if record.trigger_type == 'date_based' and not record.date_field:
                raise ValidationError(_(
                    'Date Field is required for "Date Based" rules.',
                ))
            if record.trigger_type == 'on_state_change' and record.trigger_stage_id:
                raise ValidationError(_(
                    'Trigger Stage is only used by "On Stage Change" rules.',
                ))
            if record.trigger_type == 'on_stage_change' and record.trigger_state:
                raise ValidationError(_(
                    'Trigger Status is only used by "On State Change" rules.',
                ))
            # Email delivery needs a template. Placeholder rules may be saved
            # inactive (seeded without templates) and wired up before the
            # registrar activates them.
            if (record.active
                    and record.channel in ('email', 'both')
                    and not record.mail_template_id):
                raise ValidationError(_(
                    'Active rules that deliver by email must link an Email '
                    'Template.',
                ))
