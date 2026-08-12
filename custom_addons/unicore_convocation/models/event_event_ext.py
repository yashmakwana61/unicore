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

    def action_view_convocation_graduates(self):
        """Open the graduates of this convocation, grouped by cohort kind."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Graduates by Cohort'),
            'res_model': 'unicore.student',
            'view_mode': 'list,form',
            'domain': [('convocation_event_id', '=', self.id)],
            'context': {'search_default_group_cohort_kind': 1},
        }
