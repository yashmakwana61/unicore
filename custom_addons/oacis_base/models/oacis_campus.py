from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OacisCampus(models.Model):
    _name = 'oacis.campus'
    _description = 'Oacis Campus'
    _inherit = ['oacis.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    _rec_name = 'campus_display_name'

    name = fields.Char(string='Campus Name', required=True, translate=True)
    code = fields.Char(
        string='Campus Code', required=True, size=10,
        help='Unique code for the campus (e.g. MAIN, NORTH, SOUTH, ONLINE).',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        required=True, default=lambda self: self.env.company,
        ondelete='restrict',
    )
    sequence = fields.Integer(
        string='Sequence', default=10,
        help='Ordering sequence for the campus.',
    )
    campus_type = fields.Selection([
        ('main', 'Main Campus'),
        ('branch', 'Branch Campus'),
        ('online', 'Online Campus'),
        ('satellite', 'Satellite Campus'),
    ], string='Campus Type', default='main', required=True)
    street = fields.Char(string='Street', help='Street address of the campus.')
    city = fields.Char(string='City', help='City where the campus is located.')
    state_id = fields.Many2one(
        comodel_name='res.country.state', string='State',
        help='State or province of the campus.',
    )
    country_id = fields.Many2one(
        comodel_name='res.country', string='Country',
        help='Country where the campus is located.',
    )
    zip = fields.Char(string='ZIP / Postal Code')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')
    student_capacity = fields.Integer(
        string='Student Capacity',
        help='Maximum number of students the campus can accommodate.',
    )
    is_main_campus = fields.Boolean(
        string='Is Main Campus',
        help='Mark this as the primary campus of the institution.',
    )
    campus_display_name = fields.Char(
        string='Campus Display Name',
        compute='_compute_campus_display_name', store=True,
        help='Display name in [CODE] Name format.',
    )

    _sql_constraints = [
        ('unique_code_per_company', 'UNIQUE(code, company_id)',
         'Campus code must be unique per institution.'),
    ]

    @api.depends('code', 'name')
    def _compute_campus_display_name(self):
        for campus in self:
            campus.campus_display_name = f'[{campus.code}] {campus.name}'

    @api.constrains('code')
    def _check_code(self):
        for campus in self:
            if not campus.code.isalnum():
                raise ValidationError(_('Campus code must be alphanumeric only.'))
            if campus.code != campus.code.upper():
                raise ValidationError(_('Campus code must be uppercase only.'))

    @api.constrains('student_capacity')
    def _check_student_capacity(self):
        for campus in self:
            if campus.student_capacity and campus.student_capacity < 0:
                raise ValidationError(
                    _('Student capacity must be a non-negative number.'),
                )
