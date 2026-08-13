from odoo import api, models


class ResCompany(models.Model):
    """Auto-seed the default admission pipeline when a new company is created."""

    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            self.env['oacis.admission.stage']._ensure_default_stages(company)
        return companies
