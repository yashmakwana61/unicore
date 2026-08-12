from odoo import _, fields, models
from odoo.exceptions import UserError


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    uni_admission_state = fields.Selection([
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
    ], string='Admission Stage')


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    applicant_id = fields.Many2one(
        'unicore.admission.applicant', string='Admission Applicant',
        ondelete='cascade', index=True, copy=False,
        help='UniCore admission applicant this opportunity mirrors.')

    def write(self, vals):
        res = super().write(vals)
        if vals.get('stage_id'):
            for lead in self:
                if lead.applicant_id and lead.applicant_id.state != lead.stage_id.uni_admission_state:
                    lead.applicant_id.with_context(
                        _crm_sync=True).write({'state': lead.stage_id.uni_admission_state})
        return res

    def action_view_admission_applicant(self):
        self.ensure_one()
        if not self.applicant_id:
            raise UserError(_(
                'No admission applicant linked to this opportunity.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Applicant'),
            'res_model': 'unicore.admission.applicant',
            'res_id': self.applicant_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }
