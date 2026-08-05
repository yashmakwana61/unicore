from odoo import fields, models


class ResCompany(models.Model):
    """Extend res.company with the institution profile (Phase 0, additive)."""

    _inherit = 'res.company'

    institution_profile_id = fields.Many2one(
        comodel_name='unicore.institution.profile',
        string='Institution Profile',
        tracking=True,
        help='Configures entity-type behavior: academic unit levels, calendar '
             'mode, grading scheme and terminology. Leave empty to keep the '
             'legacy university behavior (100% current behavior).',
    )
    terminology_profile_id = fields.Many2one(
        comodel_name='unicore.terminology.profile',
        related='institution_profile_id.terminology_profile_id',
        store=True,
        readonly=True,
        string='Terminology Profile',
        help='Terminology substitutions carried from the institution profile.',
    )

    def _get_effective_grading_scheme(self):
        """Return the effective grading scheme key for this company.

        Resolution order (Phase 2):
          1. profile.grading_scheme_id.scheme_type (dedicated scheme record)
          2. profile.grading_scheme (legacy selection)
          3. 'credit_gpa' (no profile / unset -> legacy university default)

        Guarantees the legacy path is 100% identical: a company without a
        profile (or with the UNI_LEGACY profile) resolves to 'credit_gpa'.
        """
        self.ensure_one()
        profile = self.institution_profile_id
        if profile:
            if profile.grading_scheme_id:
                return profile.grading_scheme_id.scheme_type
            if profile.grading_scheme:
                return profile.grading_scheme
        return 'credit_gpa'

    def get_term_label(self, concept, default=None):
        """Effective entity label for this company (Phase 8 terminology).

        Resolves through the company's terminology profile (carried from the
        institution profile). No profile / legacy profile => the generic label
        (``default`` or the generic term) — legacy output unchanged.
        """
        self.ensure_one()
        terminology = self.terminology_profile_id
        if terminology:
            return terminology.resolve_label(concept, default=default)
        return default
