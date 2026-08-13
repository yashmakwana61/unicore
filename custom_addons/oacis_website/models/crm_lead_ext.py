from odoo import _, fields, models
from odoo.exceptions import UserError


class CrmLeadExt(models.Model):
    _inherit = 'crm.lead'

    website_enquiry = fields.Boolean(
        string='Website Enquiry',
        help='This lead originated from the admissions website enquiry form.')
    website_page_url = fields.Char(
        string='Website Page URL',
        help='The URL of the page where the enquiry was submitted.')
    admission_applicant_id = fields.Many2one(
        'oacis.admission.applicant',
        string='Admission Applicant',
        ondelete='set null',
        copy=False,
        help='Linked Oacis admission applicant if this enquiry is from an applicant.')

    def action_view_website_page(self):
        self.ensure_one()
        if not self.website_page_url:
            raise UserError(_(
                'No website page URL linked to this enquiry.'))
        return {
            'type': 'ir.actions.act_url',
            'name': _('View Website Page'),
            'url': self.website_page_url,
            'target': 'new',
        }
