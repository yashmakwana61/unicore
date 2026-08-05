from odoo import fields, models


class UnicoreInstitutionFeature(models.Model):
    """Optional product features/domains an institution profile can toggle.

    Seeded with the optional UniCore modules (hostel, transport, library, alumni,
    convocation, scholarship, thesis, crm, admission, website, ...). Institution-type
    templates pre-select sensible defaults; an admin can override per profile.
    """

    _name = 'unicore.institution.feature'
    _description = 'Institution Feature'
    _inherit = ['unicore.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Feature Name',
        required=True,
        translate=True,
        help='e.g. Hostel, Transport, Library, Alumni',
    )
    code = fields.Char(
        string='Feature Code',
        required=True,
        size=20,
        help='Short unique code e.g. HOSTEL, TRANSPORT, LIBRARY',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    description = fields.Text(
        string='Description',
    )

    _unique_feature_code = models.Constraint(
        'UNIQUE(code)',
        'A feature with this code already exists.',
    )
