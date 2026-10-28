import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GrievanceCategory(models.Model):
    _name = 'edicai.grievance.category'
    _description = 'Grievance Category'
    _inherit = ['edicai.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Category Name', required=True)
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class GrievanceTeam(models.Model):
    _name = 'edicai.grievance.team'
    _description = 'Grievance Resolution Team'
    _inherit = ['edicai.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Team Name', required=True)
    member_ids = fields.Many2many(
        'res.users',
        'edicai_grievance_team_user_rel',
        'team_id', 'user_id',
        string='Team Members',
    )
    company_id = fields.Many2one('res.company', string='Institution', default=lambda self: self.env.company)


class GrievanceRequest(models.Model):
    _name = 'edicai.grievance.request'
    _description = 'Grievance Request'
    _inherit = ['edicai.mixin', 'mail.thread', 'mail.activity.mixin']
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
    name = fields.Char(
        string='Grievance Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Institution',
        default=lambda self: self.env.company,
        required=True,
    )
    category_id = fields.Many2one(
        'edicai.grievance.category',
        string='Category',
        required=True,
        domain="[('company_id', 'in', [company_id, False])]",
        tracking=True,
    )
    description = fields.Text(string='Description', required=True)
    assigned_team_id = fields.Many2one(
        'edicai.grievance.team',
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('edicai.grievance.request') or 'New'
                )
        return super().create(vals_list)

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
        self._notify_decision('grievance_resolved')

    def action_escalate(self):
        self.write({'state': 'escalated'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        self._send_notification(_('Your grievance has been cancelled.'))
        self._notify_decision('grievance_cancelled')

    def _notify_decision(self, trigger_event):
        """Event-driven decision notification via the
        notification engine (never raises).

        The complainant (``raised_by_id``) is a generic
        partner, so the linked student is resolved via
        ``partner_id``. Non-student complainants keep the
        chatter notification only. Gated by the per-company
        ``notify_on_grievance_decision`` flag (off by
        default); the state transition above always commits
        regardless.
        """
        for rec in self:
            try:
                Engine = rec.env['edicai.notification.engine']
                if not Engine._config_allows(
                    rec.company_id.id,
                    'notify_on_grievance_decision',
                    default=False,
                ):
                    continue
                student = rec.env['edicai.student'].sudo().search([
                    ('partner_id', '=', rec.raised_by_id.id),
                ], limit=1) if rec.raised_by_id else False
                if not student:
                    continue
                Engine.notify_grievance_decision(
                    student,
                    trigger_event,
                    {
                        'student_name': student.display_name,
                        'grievance_reference': (
                            'GRV-%s' % rec.id
                        ),
                        'category_name': (
                            rec.category_id.name or ''
                        ),
                        'resolution_notes': (
                            rec.resolution_notes or ''
                        ),
                        'institution_name': (
                            rec.company_id.name or ''
                        ),
                    },
                )
            except Exception as e:
                _logger.warning(
                    'Grievance decision notify skipped '
                    'for grievance %s: %s',
                    rec.id, str(e),
                )

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
