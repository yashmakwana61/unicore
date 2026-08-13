from odoo import api, fields, models


class OacisInstitutionProfile(models.Model):
    """Per-institution configuration record driving multi-entity behavior.

    This is the real driver behind the (previously dead) res.company.university_type
    label. One profile is attached to each res.company via
    res.company.institution_profile_id (nullable; unset = legacy university behavior).

    Phase 0 ships only the "University - Legacy" profile which reproduces 100% of
    current behavior. School / College / Training / Academy templates arrive in
    Phase 5 together with the onboarding wizard.
    """

    _name = 'oacis.institution.profile'
    _description = 'Institution Profile'
    _inherit = ['oacis.mixin', 'mail.thread']
    _order = 'name'

    name = fields.Char(
        string='Profile Name',
        required=True,
        translate=True,
        help='e.g. University (Legacy), K-12 School',
    )
    code = fields.Char(
        string='Profile Code',
        required=True,
        size=20,
        help='Short unique code e.g. UNI_LEGACY, K12',
    )
    institution_type = fields.Selection(
        selection=[
            ('university', 'University'),
            ('college', 'College'),
            ('school', 'K-12 School'),
            ('training', 'Training Institute'),
            ('academy', 'Academy / Test-Prep'),
            ('coaching', 'Coaching Center'),
        ],
        string='Institution Type',
        default='university',
        required=True,
        tracking=True,
    )
    is_legacy_university = fields.Boolean(
        string='Legacy University Mode',
        default=True,
        help='When True (or when no profile is set on the company), the system '
             'preserves 100% of the current university behavior: the rigid '
             'Faculty -> Department -> Program chain stays required. Later phases '
             'read this flag as the compatibility shim.',
    )
    academic_unit_level_ids = fields.Many2many(
        comodel_name='oacis.academic.unit.type',
        relation='oacis_institution_profile_unit_type_rel',
        column1='profile_id',
        column2='unit_type_id',
        string='Academic Unit Levels',
        help='Unit types this institution may use in its hierarchy. '
             'University: Faculty + Department. School: Grade Level. '
             'Training: none (flat).',
    )
    calendar_mode = fields.Selection(
        selection=[
            ('semester', 'Semester'),
            ('trimester', 'Trimester'),
            ('quarter', 'Quarter'),
            ('annual', 'Annual'),
            ('term', 'Term Based'),
            ('rolling_batch', 'Rolling Batch'),
        ],
        string='Calendar Mode',
        default='semester',
        required=True,
        tracking=True,
    )
    grading_scheme = fields.Selection(
        selection=[
            ('credit_gpa', 'Credit GPA / CGPA'),
            ('weighted_percentage', 'Weighted Percentage'),
            ('simple_percentage', 'Simple Percentage'),
            ('rubric_standards', 'Rubric / Standards Based'),
            ('pass_fail', 'Pass / Fail'),
            ('certificate_only', 'Certificate / Completion Only'),
        ],
        string='Grading Scheme (legacy)',
        default='credit_gpa',
        required=True,
        tracking=True,
        help='LEGACY fallback grading strategy. Kept for backward compatibility '
             'and for profiles that do not select a dedicated scheme record. '
             'Phase 2: when grading_scheme_id is set, its scheme_type takes '
             'precedence (see effective_grading_scheme).',
    )
    grading_scheme_id = fields.Many2one(
        comodel_name='oacis.grading.scheme',
        string='Grading Scheme',
        tracking=True,
        help='Dedicated grading scheme record (Phase 2). When set, its '
             'scheme_type drives result computation via the grading dispatch; '
             'otherwise the legacy grading_scheme selection is used.',
    )
    effective_grading_scheme = fields.Selection(
        selection=[
            ('credit_gpa', 'Credit GPA / CGPA'),
            ('weighted_percentage', 'Weighted Percentage'),
            ('simple_percentage', 'Simple Percentage'),
            ('rubric_standards', 'Rubric / Standards Based'),
            ('pass_fail', 'Pass / Fail'),
            ('certificate_only', 'Certificate / Completion Only'),
        ],
        string='Effective Grading Scheme',
        compute='_compute_effective_grading_scheme',
        help='Resolved grading scheme: grading_scheme_id.scheme_type when a '
             'scheme record is selected, else the legacy grading_scheme value.',
    )

    @api.depends('grading_scheme_id.scheme_type', 'grading_scheme')
    def _compute_effective_grading_scheme(self):
        for record in self:
            record.effective_grading_scheme = (
                record.grading_scheme_id.scheme_type
                if record.grading_scheme_id
                else record.grading_scheme
            )
    terminology_profile_id = fields.Many2one(
        comodel_name='oacis.terminology.profile',
        string='Terminology Profile',
        tracking=True,
        help='Field-label substitutions applied at setup (one-time relabeling, Phase 5).',
    )
    feature_toggle_ids = fields.Many2many(
        comodel_name='oacis.institution.feature',
        relation='oacis_institution_profile_feature_rel',
        column1='profile_id',
        column2='feature_id',
        string='Relevant Features',
        help='Optional Oacis modules relevant for this institution type.',
    )
    description = fields.Text(
        string='Description',
    )

    _unique_profile_code = models.Constraint(
        'UNIQUE(code)',
        'An institution profile with this code already exists.',
    )

    def action_open_institution_profiles(self):
        """Convenience action used from the company form to open profiles."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Institution Profiles',
            'res_model': 'oacis.institution.profile',
            'view_mode': 'tree,form',
            'target': 'current',
        }
