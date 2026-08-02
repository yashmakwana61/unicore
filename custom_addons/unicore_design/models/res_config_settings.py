# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    theme_font_family = fields.Selection(
        related='company_id.theme_font_family',
        readonly=False,
    )
    theme_list_density = fields.Selection(
        related='company_id.theme_list_density',
        readonly=False,
    )
    theme_border_radius = fields.Selection(
        related='company_id.theme_border_radius',
        readonly=False,
    )
    theme_chatter_position = fields.Selection(
        related='company_id.theme_chatter_position',
        readonly=False,
    )
    theme_start_menu_bg = fields.Selection(
        related='company_id.theme_start_menu_bg',
        readonly=False,
    )
