from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    theme_font_family = fields.Selection([
        ('system', 'System Default'),
        ('inter', 'Inter'),
        ('roboto', 'Roboto'),
        ('outfit', 'Outfit'),
    ], string='Theme Font Family', default='system', required=True)

    theme_list_density = fields.Selection([
        ('default', 'Default'),
        ('comfortable', 'Comfortable'),
        ('compact', 'Compact'),
    ], string='Theme List Density', default='default', required=True)

    theme_border_radius = fields.Selection([
        ('none', 'None'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ], string='Theme Border Radius', default='medium', required=True)

    theme_chatter_position = fields.Selection([
        ('bottom', 'Bottom'),
        ('side', 'Side'),
    ], string='Theme Chatter Position', default='bottom', required=True)

    theme_start_menu_bg = fields.Selection([
        ('none', 'Plain (No Decoration)'),
        ('aurora', 'Aurora'),
        ('ocean', 'Deep Ocean'),
        ('sunset', 'Sunset'),
        ('midnight', 'Midnight'),
    ], string='Start Menu Background', default='aurora', required=True)
