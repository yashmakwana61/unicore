from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'
    _description = 'Extend res.users with campus assignment for data isolation.'

    unicore_campus_ids = fields.Many2many(
        comodel_name='unicore.campus',
        relation='unicore_user_campus_rel',
        column1='user_id',
        column2='campus_id',
        string='Allowed Campuses',
        help='Campuses this user is allowed to access. Leave empty to allow all campuses.',
    )
