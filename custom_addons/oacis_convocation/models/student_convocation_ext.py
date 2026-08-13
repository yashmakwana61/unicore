from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StudentConvocationExt(models.Model):
    _inherit = 'oacis.student'

    convocation_event_id = fields.Many2one(
        'event.event', string='Convocation Event',
        readonly=True, copy=False,
        ondelete='set null', tracking=True,
        help='Convocation event this graduate is registered for.')
    convocation_registration_count = fields.Integer(
        string='Convocation Registrations',
        compute='_compute_convocation_registration_count',
        store=False)

    @api.depends('convocation_event_id')
    def _compute_convocation_registration_count(self):
        for rec in self:
            rec.convocation_registration_count = (
                1 if rec.convocation_event_id else 0)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.student_state == 'graduated':
                rec._sync_convocation_event()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('student_state') and not self.env.context.get(
                '_convocation_sync'):
            for rec in self:
                if rec.student_state == 'graduated':
                    rec._sync_convocation_event()
        return res

    def _sync_convocation_event(self):
        self.ensure_one()
        if self.convocation_event_id:
            return
        event = self.env['event.event'].search(
            [('oacis_convocation_event', '=', True)], limit=1)
        if not event:
            return
        registration = self.env['event.registration'].search(
            [('event_id', '=', event.id),
             ('partner_id', '=', self.partner_id.id)],
            limit=1)
        if not registration:
            registration.sudo().create({
                'event_id': event.id,
                'partner_id': self.partner_id.id,
                'name': self.display_name,
                'email': self.email,
                'phone': self.mobile or False,
            })
            self.with_context(
                _convocation_sync=True).write(
                {'convocation_event_id': event.id})

    def action_view_convocation_event(self):
        self.ensure_one()
        if not self.convocation_event_id:
            raise UserError(_(
                'No convocation event linked to this student yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Convocation Event'),
            'res_model': 'event.event',
            'res_id': self.convocation_event_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }

    def action_view_convocation_cohort_mates(self):
        """Open the student's same-cohort graduates of the same convocation."""
        self.ensure_one()
        if not self.convocation_event_id:
            raise UserError(_(
                'No convocation event linked to this student yet.'))
        domain = self._cohort_members_domain() or [('id', '=', self.id)]
        domain = list(domain) + [
            ('convocation_event_id', '=', self.convocation_event_id.id),
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cohort Mates'),
            'res_model': 'oacis.student',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'search_default_group_cohort_kind': 1},
        }

    def action_register_convocation(self):
        for rec in self:
            rec._sync_convocation_event()
        return True
