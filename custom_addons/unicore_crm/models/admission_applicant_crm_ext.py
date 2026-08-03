from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AdmissionApplicantCrmExt(models.Model):
    _inherit = 'unicore.admission.applicant'

    crm_lead_id = fields.Many2one(
        'crm.lead', string='CRM Opportunity', readonly=True, copy=False,
        ondelete='set null', tracking=True,
        help='CRM opportunity/pipeline record mirroring this applicant.')
    crm_lead_count = fields.Integer(
        string='CRM', compute='_compute_crm_lead_count', store=False)

    @api.depends('crm_lead_id')
    def _compute_crm_lead_count(self):
        for rec in self:
            rec.crm_lead_count = 1 if rec.crm_lead_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.with_context(_crm_sync=True)._sync_crm_lead(create=True)
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') and not self.env.context.get('_crm_sync'):
            for rec in self:
                rec._sync_crm_lead(create=False)
        return res

    def _sync_crm_lead(self, create=False):
        self.ensure_one()
        team = self.env.ref(
            'unicore_crm.crm_team_admissions', raise_if_not_found=False)
        stage = self._get_crm_stage_for_state(self.state)
        lead = self.crm_lead_id
        if not lead:
            if not create:
                return
            lead = self.env['crm.lead'].sudo().with_context(
                _crm_sync=True).create({
                    'name': self.name or self.email,
                    'contact_name': self.name,
                    'email_from': self.email,
                    'phone': self.mobile or self.phone,
                    'type': 'opportunity',
                    'team_id': team.id if team else False,
                    'company_id': self.company_id.id,
                    'applicant_id': self.id,
                    'stage_id': stage.id if stage else False,
                })
            self.with_context(_crm_sync=True).write({'crm_lead_id': lead.id})
        else:
            vals = {
                'contact_name': self.name,
                'email_from': self.email,
                'phone': self.mobile or self.phone,
            }
            if stage:
                vals['stage_id'] = stage.id
            lead.sudo().with_context(_crm_sync=True).write(vals)

    def _get_crm_stage_for_state(self, state):
        return self.env['crm.stage'].search(
            [('uni_admission_state', '=', state)], limit=1)

    def action_view_crm_lead(self):
        self.ensure_one()
        if not self.crm_lead_id:
            raise UserError(_(
                'No CRM opportunity linked to this applicant yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('CRM Opportunity'),
            'res_model': 'crm.lead',
            'res_id': self.crm_lead_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_sync_to_crm(self):
        for rec in self:
            rec._sync_crm_lead(create=True)
        return True