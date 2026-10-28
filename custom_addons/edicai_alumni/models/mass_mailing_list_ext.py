from odoo import api, fields, models


class MassMailingListExt(models.Model):
    _inherit = 'mailing.list'

    edicai_alumni_list = fields.Boolean(
        string='Edicai Alumni List',
        help='Mark this mailing list as an alumni engagement list.',
    )
    alumni_contact_count = fields.Integer(
        string='Alumni Contacts',
        compute='_compute_alumni_contact_count',
        store=True,
    )

    @api.depends('contact_ids')
    def _compute_alumni_contact_count(self):
        for rec in self:
            rec.alumni_contact_count = len(rec.contact_ids)
