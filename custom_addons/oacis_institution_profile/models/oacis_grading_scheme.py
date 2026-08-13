from odoo import fields, models


class OacisGradingScheme(models.Model):
    """Grading scheme strategy record (Phase 2).

    One record per grading strategy (credit_gpa, weighted/simple percentage,
    rubric / standards based, pass_fail, certificate / completion only).
    An institution profile points at one scheme via
    ``oacis.institution.profile.grading_scheme_id``; the legacy
    ``grading_scheme`` Selection on the profile stays as the fallback so unset
    profiles keep 100% of current behavior (zero regression).

    The grading dispatch (``oacis.grade.entry``) keys on the resolved
    ``scheme_type`` of the effective scheme for a company.
    """

    _name = 'oacis.grading.scheme'
    _description = 'Grading Scheme'
    _inherit = ['oacis.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Scheme Name',
        required=True,
        translate=True,
        help='e.g. Credit GPA / CGPA, Simple Percentage, Pass / Fail',
    )
    code = fields.Char(
        string='Scheme Code',
        required=True,
        size=20,
        help='Short unique code e.g. CREDIT_GPA, SIMPLE_PCT, PASS_FAIL',
    )
    scheme_type = fields.Selection(
        selection=[
            ('credit_gpa', 'Credit GPA / CGPA'),
            ('weighted_percentage', 'Weighted Percentage'),
            ('simple_percentage', 'Simple Percentage'),
            ('rubric_standards', 'Rubric / Standards Based'),
            ('pass_fail', 'Pass / Fail'),
            ('certificate_only', 'Certificate / Completion Only'),
        ],
        string='Scheme Type',
        required=True,
        default='credit_gpa',
        help='The grading strategy this scheme drives. Mirrors the legacy '
             'profile.grading_scheme selection; the Phase 2 dispatch keys on '
             'this value.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    is_default = fields.Boolean(
        string='Default Scheme',
        default=False,
        help='Flag the scheme offered by default for new institution profiles.',
    )
    description = fields.Text(
        string='Description',
    )

    _unique_scheme_code = models.Constraint(
        'UNIQUE(code)',
        'A grading scheme with this code already exists.',
    )
