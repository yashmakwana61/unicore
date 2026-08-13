from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OacisStudentEmergencyContact(models.Model):
    """Emergency contact and guardian information for students."""

    _name = 'oacis.student.emergency.contact'
    _description = 'Student Emergency Contact / Guardian'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'is_primary desc, sequence, name'
    _check_company_auto = True
    _rec_name = 'name'

    name = fields.Char(string='Full Name', required=True, tracking=True)
    relationship = fields.Selection(
        selection=[
            ('father', 'Father'),
            ('mother', 'Mother'),
            ('guardian', 'Legal Guardian'),
            ('sibling', 'Sibling'),
            ('spouse', 'Spouse'),
            ('relative', 'Relative'),
            ('friend', 'Friend'),
            ('other', 'Other'),
        ],
        string='Relationship', required=True,
    )
    is_primary = fields.Boolean(string='Primary Contact', default=False)
    email = fields.Char(string='Email')
    mobile = fields.Char(string='Mobile', required=True)
    phone = fields.Char(string='Phone')
    priority = fields.Selection(
        selection=[('1', 'Highest'), ('2', 'High'), ('3', 'Normal'), ('4', 'Low')],
        string='Contact Priority', default='3',
    )
    address = fields.Text(string='Address')
    city = fields.Char(string='City')
    state_id = fields.Many2one(comodel_name='res.country.state', string='State')
    country_id = fields.Many2one(comodel_name='res.country', string='Country')
    is_emergency_only = fields.Boolean(
        string='Emergency Only', default=False,
        help='Only contact in case of emergency',
    )
    notes = fields.Text(string='Notes')

    student_id = fields.Many2one(
        comodel_name='oacis.student', string='Student',
        required=True, ondelete='cascade',
    )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Institution',
        related='student_id.company_id', store=True, readonly=True,
    )
    campus_id = fields.Many2one(
        comodel_name='oacis.campus', string='Campus',
        related='student_id.campus_id', store=True, readonly=True,
    )

    sequence = fields.Integer(string='Sequence', default=10)

    _check_primary_contact = models.Constraint(
        'UNIQUE(student_id, is_primary)',
        'Only one primary contact is allowed per student.',
    )

    @api.constrains('is_primary')
    def _check_primary_contact(self):
        for record in self:
            if record.is_primary:
                existing_primary = self.search([
                    ('student_id', '=', record.student_id.id),
                    ('is_primary', '=', True),
                    ('id', '!=', record.id),
                ])
                if existing_primary:
                    raise ValidationError(_(
                        'Student already has a primary contact: %s') % existing_primary[0].name,
                    )
