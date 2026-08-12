from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MisbehaviourCategory(models.Model):
    _name = 'unicore.misbehaviour.category'
    _description = 'Misbehaviour Category'
    _inherit = ['unicore.mixin']
    _order = 'severity_level desc, name'
    _check_company_auto = True

    name = fields.Char(string='Category Name', required=True)
    severity_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Severity Level', required=True, default='low')
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class DisciplineRecord(models.Model):
    _name = 'unicore.discipline.record'
    _description = 'Discipline Record'
    _inherit = ['unicore.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'incident_date desc'
    _check_company_auto = True
    _rec_name = 'student_id'

    student_id = fields.Many2one(
        'unicore.student',
        string='Student',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        related='student_id.company_id',
        store=True,
    )
    category_id = fields.Many2one(
        'unicore.misbehaviour.category',
        string='Category',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    description = fields.Text(string='Description', required=True)
    reported_by = fields.Many2one(
        'unicore.faculty.member',
        string='Reported By',
        required=True,
    )
    incident_date = fields.Date(
        string='Incident Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    action_taken = fields.Text(string='Action Taken')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('action_taken', 'Action Taken'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)

    @api.constrains('incident_date')
    def _check_incident_date(self):
        for record in self:
            if record.incident_date and record.incident_date > fields.Date.today():
                raise ValidationError(_('Incident date cannot be in the future.'))

    @api.constrains('state', 'action_taken')
    def _check_action_taken(self):
        for record in self:
            if record.state == 'action_taken' and not record.action_taken:
                raise ValidationError(_('Action taken must be specified before moving to Action Taken state.'))

    def action_under_review(self):
        self.write({'state': 'under_review'})

    def action_take_action(self):
        if not self.action_taken:
            raise ValidationError(_('Action taken must be specified before moving to Action Taken state.'))
        self.write({'state': 'action_taken'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
