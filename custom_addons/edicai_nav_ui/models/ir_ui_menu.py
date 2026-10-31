# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools


ICON_SELECTION = [
    ('ic_home', 'Home'),
    ('ic_institution', 'Institution'),
    ('ic_admissions', 'Admissions'),
    ('ic_student', 'Student'),
    ('ic_teaching', 'Teaching'),
    ('ic_exams', 'Exams'),
    ('ic_finance', 'Finance'),
    ('ic_campus', 'Campus'),
    ('ic_careers', 'Careers'),
    ('ic_insights', 'Insights'),
    ('ic_communication', 'Communication'),
    ('ic_administration', 'Administration'),
    ('ic_website', 'Website'),
    ('ic_apps', 'Apps'),
    ('ic_calendar', 'Calendar'),
]

ICON_COLORS = {
    'ic_home': '#875A7B',
    'ic_institution': '#00A09D',
    'ic_admissions': '#F05545',
    'ic_student': '#21B799',
    'ic_teaching': '#F0AD4E',
    'ic_exams': '#5BC0DE',
    'ic_finance': '#5CB85C',
    'ic_campus': '#9B59B6',
    'ic_careers': '#E67E22',
    'ic_insights': '#3498DB',
    'ic_communication': '#1ABC9C',
    'ic_administration': '#7F8C8D',
    'ic_website': '#2C3E50',
    'ic_apps': '#34495E',
    'ic_calendar': '#F39C12',
}


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    edicai_icon = fields.Selection(
        selection=ICON_SELECTION,
        string='Edicai Icon',
        help='Choose a colorful icon for this menu. Overrides web_icon when set.',
    )

    def _compute_web_icon(self):
        """If edicai_icon is set, generate web_icon path automatically."""
        for menu in self:
            if menu.edicai_icon:
                menu.web_icon = 'edicai_nav_ui,static/src/icons/%s.svg' % menu.edicai_icon

    @api.onchange('edicai_icon')
    def _onchange_edicai_icon(self):
        if self.edicai_icon:
            self.web_icon = 'edicai_nav_ui,static/src/icons/%s.svg' % self.edicai_icon

    def write(self, vals):
        if 'edicai_icon' in vals and vals['edicai_icon']:
            vals['web_icon'] = 'edicai_nav_ui,static/src/icons/%s.svg' % vals['edicai_icon']
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('edicai_icon'):
                vals['web_icon'] = 'edicai_nav_ui,static/src/icons/%s.svg' % vals['edicai_icon']
        return super().create(vals_list)