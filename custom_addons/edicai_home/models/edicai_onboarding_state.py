# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class EdicaiOnboardingState(models.Model):
    _name = 'edicai.onboarding.state'
    _description = 'Edicai Home — per-user onboarding progress'
    _order = 'user_id, item_id'

    user_id = fields.Many2one('res.users', string='User', required=True,
                              index=True, ondelete='cascade')
    item_id = fields.Many2one('edicai.onboarding.item', string='Item',
                              required=True, index=True, ondelete='cascade')
    state = fields.Selection(
        [('todo', 'To do'), ('done', 'Done'), ('skipped', 'Skipped')],
        string='State', required=True, default='todo')
    completed_on = fields.Date(string='Completed on')
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)

    _unique_user_item = models.Constraint(
        'UNIQUE(user_id, item_id)',
        'One progress row per user and onboarding item.')

    @api.model
    def set_state(self, item_id, state):
        """RPC: mark an item done/skipped/todo for the current user."""
        item = self.env['edicai.onboarding.item'].browse(item_id)
        if not item.exists():
            raise ValueError('Unknown onboarding item')
        row = self.search([('user_id', '=', self.env.uid),
                           ('item_id', '=', item.id)], limit=1)
        vals = {'state': state,
                'completed_on': fields.Date.context_today(self)
                if state == 'done' else False}
        if row:
            # record rule also blocks foreign rows; this is belt & braces
            if row.user_id.id != self.env.uid and not self.env.su:
                raise AccessError('You may only change your own progress.')
            row.write(vals)
            return row.id
        return self.create({'user_id': self.env.uid,
                            'item_id': item.id, **vals}).id

    def write(self, vals):
        if not self.env.su:
            forbidden = self.filtered(
                lambda st: st.user_id.id != self.env.uid)
            if forbidden:
                raise AccessError(
                    'You may only change your own onboarding progress.')
        return super().write(vals)
