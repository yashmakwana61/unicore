from odoo import api, fields, models


class EventEventExt(models.Model):
    _inherit = 'event.event'

    oacis_alumni_event = fields.Boolean(
        string='Oacis Alumni Event',
        help='Mark this event as an alumni engagement event.',
    )
    alumni_registration_count = fields.Integer(
        string='Alumni Registrations',
        compute='_compute_alumni_registration_count',
        store=True,
    )

    @api.depends('registration_ids')
    def _compute_alumni_registration_count(self):
        for rec in self:
            rec.alumni_registration_count = len(rec.registration_ids)
