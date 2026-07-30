from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'Extend res.company with UniCore-specific institution fields.'

    university_type = fields.Selection([
        ('university', 'University'),
        ('college', 'College'),
        ('school', 'School'),
        ('training', 'Training Institute'),
        ('academy', 'Online Academy'),
    ], string='Institution Type', default='college', required=True,
        help='Type of educational institution.')

    established_year = fields.Integer(
        string='Established Year',
        help='Year the institution was established.',
    )

    accreditation_body = fields.Char(
        string='Accreditation Body',
        help='Accrediting body for this institution.',
    )

    website = fields.Char(
        string='Institution Website',
        help='Official website URL of the institution.',
    )

    campus_ids = fields.One2many(
        comodel_name='unicore.campus',
        inverse_name='company_id',
        string='Campuses',
        help='Campuses belonging to this institution.',
    )
