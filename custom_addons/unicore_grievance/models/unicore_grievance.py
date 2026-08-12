from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GrievanceCategory(models.Model):
    _name = 'unicore.grievance.category'
    _description = 'Grievance Category'
    _inherit = ['unicore.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Category Name', required=True)
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class GrievanceTeam(models.Model):
    _name = 'unicore.grievance.team'
    _description = 'Grievance Resolution Team'
    _inherit = ['unicore.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Team Name', required=True)
    member_ids = fields.Many2many(
        'res.users',
        'unicore_grievance_team_user_rel',
        'team_id', 'user_id',
        string='Team Members',
    )
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class GrievanceRequest(models.Model):
    _name = 'unicore.grievance.request'
    _description = 'Grievance Request'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _check_company_auto = True
    _rec_name = 'id'

    raised_by_id = fields.Many2one(
        'res.partner',
        string='Raised By',
        required=True,
        tracking=True,
        default=lambda self: self.env.user.partner_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        default=lambda self: self.env.company,
        required=True,
    )
    category_id = fields.Many2one(
        'unicore.grievance.category',
        string='Category',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    description = fields.Text(string='Description', required=True)
    assigned_team_id = fields.Many2one(
        'unicore.grievance.team',
        string='Assigned Team',
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', required=True, tracking=True)
    resolution_notes = fields.Text(string='Resolution Notes')
    resolution_date = fields.Date(string='Resolution Date', tracking=True)

    @api.constrains('state', 'resolution_notes')
    def _check_resolution_notes(self):
        for record in self:
            if record.state == 'resolved' and not record.resolution_notes:
                raise ValidationError(_('Resolution notes must be provided before marking as resolved.'))

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_resolve(self):
        if not self.resolution_notes:
            raise ValidationError(_('Resolution notes must be provided before marking as resolved.'))
        self.write({
            'state': 'resolved',
            'resolution_date': fields.Date.today(),
        })
        self._send_notification(_('Your grievance has been resolved.'))

    def action_escalate(self):
        self.write({'state': 'escalated'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _send_notification(self, message):
        self.ensure_one()
        if self.raised_by_id:
            self.env['mail.message'].create({
                'model': self._name,
                'res_id': self.id,
                'body': message,
                'message_type': 'notification',
                'subtype_id': self.env.ref('mail.mt_note').id,
                'partner_ids': [(4, self.raised_by_id.id)],
            })
