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

    @api.model
    def edicai_apply_workspace_icons(self):
        """Force-apply the premium 3D PNG icon set to the workspace roots,
        Home root and the Settings menu.

        The workspace/home menus are declared in noupdate="1" data files, so
        plain <record> overrides from this module are silently skipped by the
        data loader on existing databases. An imperative ORM write is not
        subject to that guard, hence this helper (called from
        data/navigation_icons.xml on every edicai_nav_ui upgrade)."""
        assignments = [
            ('edicai_navigation.menu_workspace_10', 'ic_institution.png'),
            ('edicai_navigation.menu_workspace_20', 'ic_admissions.png'),
            ('edicai_navigation.menu_workspace_30', 'ic_student.png'),
            ('edicai_navigation.menu_workspace_40', 'ic_teaching.png'),
            ('edicai_navigation.menu_workspace_50', 'ic_exams.png'),
            ('edicai_navigation.menu_workspace_60', 'ic_finance.png'),
            ('edicai_navigation.menu_workspace_70', 'ic_campus.png'),
            ('edicai_navigation.menu_workspace_80', 'ic_careers.png'),
            ('edicai_navigation.menu_workspace_90', 'ic_insights.png'),
            ('edicai_navigation.menu_workspace_100', 'ic_communication.png'),
            ('edicai_navigation.menu_workspace_110', 'ic_administration.png'),
            ('edicai_home.menu_edicai_home_app', 'ic_home.png'),
        ]
        IMD = self.env['ir.model.data'].sudo()
        applied = 0
        for xmlid, icon in assignments:
            data = IMD.search([('model', '=', 'ir.ui.menu'),
                               ('module', '=', xmlid.split('.')[0]),
                               ('name', '=', xmlid.split('.')[1])], limit=1)
            if not data:
                continue
            menu = self.browse(data.res_id).sudo()
            path = 'edicai_nav_ui,static/src/icons/%s' % icon
            if menu.web_icon != path:
                menu.web_icon = path
                applied += 1
        return applied