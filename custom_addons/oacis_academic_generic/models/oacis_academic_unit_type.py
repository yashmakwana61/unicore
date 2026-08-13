from odoo import fields, models


class UnicoreAcademicUnitType(models.Model):
    """Configurable taxonomy of academic unit types.

    Seed values cover university vocabulary (Faculty, Department) and the
    non-university vocabulary needed by the multi-entity migration (Grade Level,
    Wing, Division, Stream, Batch Group). Admins can add more; the allowed
    child-type matrix drives which levels may nest under one another.
    """

    _name = 'unicore.academic.unit.type'
    _description = 'Academic Unit Type'
    _inherit = ['unicore.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Unit Type Name',
        required=True,
        translate=True,
        help='e.g. Faculty, Department, Grade Level, Wing, Division',
    )
    code = fields.Char(
        string='Unit Type Code',
        required=True,
        size=20,
        help='Short unique code e.g. FAC, DEP, GRADE, WING',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    allowed_child_type_ids = fields.Many2many(
        comodel_name='unicore.academic.unit.type',
        relation='unicore_academic_unit_type_allowed_rel',
        column1='parent_type_id',
        column2='child_type_id',
        string='Allowed Child Types',
        help='Which unit types may nest directly under a unit of this type. '
             'Leave empty to allow any type.',
    )
    description = fields.Text(
        string='Description',
    )

    _unique_type_code = models.Constraint(
        'UNIQUE(code)',
        'A unit type with this code already exists.',
    )
