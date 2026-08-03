from odoo import _, api, fields, models


class EventEventConvocationExt(models.Model):
    _inherit = 'event.event'

    unicore_convocation_event = fields.Boolean(
        string='UniCore Convocation Event',
        help='Mark this event as a convocation ceremony.')
    convocation_registration_count = fields.Integer(
        string='Convocation Registrations',
        compute='_compute_convocation_registration_count',
        store=True)

    @api.depends('registration_ids')
    def _compute_convocation_registration_count(self):
        for rec in self:
            rec.convocation_registration_count = len(
                rec.registration_ids)