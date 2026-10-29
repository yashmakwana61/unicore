# -*- coding: utf-8 -*-
from odoo import fields, models


class NavigationPreviewWizard(models.TransientModel):
    _name = 'navigation.preview.wizard'
    _description = 'Navigation Preview Toggle (admin only)'

    state = fields.Selection(
        [('off', 'Original navigation (baseline)'),
         ('on', 'Preview: 11 workspaces active')], default='off',
        string='Current state', compute='_compute_state')
    info = fields.Text(default=(
        'Enable moves 39 menus into 11 workspaces exactly as recorded in '
        'docs/navigation_audit/menu_migration_manifest.csv and snapshots their '
        'originals. Disable restores them without data loss. Per-database '
        'scope: apply on staging/demo databases only.'))

    def _compute_state(self):
        util = self.env['navigation.preview.util'].sudo()
        for rec in self:
            rec.state = 'on' if util._state() == 'on' else 'off'

    def action_enable_preview(self):
        self.ensure_one()
        self.env['navigation.preview.util'].sudo().enable_preview()
        return self._reopen()

    def action_disable_preview(self):
        self.ensure_one()
        self.env['navigation.preview.util'].sudo().disable_preview()
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'navigation.preview.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
