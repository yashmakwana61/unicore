from odoo import _, api, fields, models


class AlumniExt(models.Model):
    _inherit = 'oacis.student'

    alumni_mailing_list_ids = fields.Many2many(
        'mailing.list',
        'oacis_alumni_mailing_list_rel',
        'student_id', 'list_id',
        string='Alumni Mailing Lists',
        help='Mass mailing lists this alumni contact belongs to.',
    )
    alumni_event_ids = fields.Many2many(
        'event.event',
        'oacis_alumni_event_rel',
        'student_id', 'event_id',
        string='Alumni Events',
        help='Alumni events this student is registered for.',
    )
    alumni_registration_count = fields.Integer(
        string='Event Registrations',
        compute='_compute_alumni_registration_count',
        store=False,
    )

    @api.depends('alumni_event_ids')
    def _compute_alumni_registration_count(self):
        for rec in self:
            rec.alumni_registration_count = len(rec.alumni_event_ids)

    def action_view_alumni_mailing_lists(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alumni Mailing Lists'),
            'res_model': 'mass_mailing.mailing.list',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.alumni_mailing_list_ids.ids)],
        }

    def action_view_alumni_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alumni Events'),
            'res_model': 'event.event',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.alumni_event_ids.ids)],
        }
