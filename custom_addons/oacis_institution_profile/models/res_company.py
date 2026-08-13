import re

from odoo import api, fields, models

# Cache of compiled relabel regexes, keyed by the tuple of (token, applied)
# pairs. Distinct profiles produce a handful of distinct keys.
_TERMINOLOGY_APPLY_CACHE = {}


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

    def _terminology_label_rules(self):
        """Build (exact, prefixes) relabel rules for this company's profile.

        ``exact``   : {generic_label: applied_label} for exact string matches,
                      including known compounds like ``Faculty Member`` and the
                      ``Current Semester`` / ``Current Academic Year`` phrases.
        ``prefixes``: [(generic_token, applied_token)] sorted by token length
                      descending, used for whole-word rewrites anywhere in a
                      label (leading, mid-string or trailing), e.g.
                      ``Program Name`` -> ``Course Name`` and ``Active
                      Programs`` -> ``Active Courses``.

        No profile, or the UNI_LEGACY university profile => empty rules, so the
        label pipeline output is byte-identical (legacy zero-regression).
        """
        self.ensure_one()
        exact = {}
        prefixes = []
        profile = self.institution_profile_id
        terminology = self.terminology_profile_id
        if not profile or not terminology or getattr(profile, 'is_legacy_university', False):
            return exact, prefixes
        concepts = terminology._TERM_CONCEPTS
        generic = {concept: info[1] for concept, info in concepts.items()}
        applied = {}
        for concept, info in concepts.items():
            value = getattr(terminology, info[0], None)
            if not value:
                value = info[1]  # blank term -> generic fallback
            applied[concept] = value
        for concept, generic_label in generic.items():
            if applied[concept] != generic_label:
                exact[generic_label] = applied[concept]
                prefixes.append((generic_label, applied[concept]))
        # Known compound labels (statinfo cards / portal wording).
        fstaff = applied.get('faculty_staff')
        fstaff_generic = generic['faculty_staff']
        if fstaff and fstaff != fstaff_generic:
            exact['Faculty Member'] = fstaff
        semester = applied.get('semester')
        if semester and semester != generic['semester']:
            exact['Current Semester'] = 'Current %s' % semester
        academic_year = applied.get('academic_year')
        if academic_year and academic_year != generic['academic_year']:
            exact['Current Academic Year'] = 'Current %s' % academic_year
        # Longest tokens first so e.g. 'Academic Year' wins over 'Academic'.
        prefixes.sort(key=lambda item: len(item[0]), reverse=True)
        return exact, prefixes

    @staticmethod
    def _terminology_apply(text, exact, prefixes):
        """Rewrite ``text`` against the relabel rules.

        Priority: exact match > whole-word token substitution. A generic token
        is matched at any word boundary (leading, trailing or mid-string, e.g.
        ``Active Programs`` -> ``Active Courses``) and carries a simple
        ``s``/``es`` plural suffix across (``Programs`` -> ``Courses``). No
        match => the text is returned untouched.
        """
        if text in exact:
            return exact[text]
        if not prefixes:
            return text
        key = tuple(prefixes)
        compiled = _TERMINOLOGY_APPLY_CACHE.get(key)
        if compiled is None:
            mapping = {token: applied for token, applied in prefixes}
            pattern = '|'.join(
                re.escape(token) + r'(?:s|es)?'
                for token, _applied in prefixes)
            regex = re.compile(r'\b(' + pattern + r')\b')

            def _sub(match):
                word = match.group(1)
                for token, applied in mapping.items():
                    if word == token:
                        return applied
                    if word.startswith(token) and \
                            word[len(token):] in ('s', 'es'):
                        return applied + word[len(token):]
                return word

            compiled = (regex, _sub)
            _TERMINOLOGY_APPLY_CACHE[key] = compiled
        regex, _sub = compiled
        return regex.sub(_sub, text)

    enabled_feature_codes = fields.Char(
        string='Enabled Features',
        compute='_compute_enabled_feature_codes',
        help='Comma-separated codes of the features enabled by the institution '
             'profile. No profile (legacy university) = all features enabled.',
    )

    @api.depends('institution_profile_id.feature_toggle_ids.code')
    def _compute_enabled_feature_codes(self):
        for record in self:
            record.enabled_feature_codes = ', '.join(
                sorted(record._enabled_feature_codes()))

    def _enabled_feature_codes(self):
        """Set of feature codes enabled for this company.

        No profile => legacy university => every seeded feature is available
        (the UNI_LEGACY profile carries all 13 toggles anyway).
        """
        self.ensure_one()
        profile = self.institution_profile_id
        if not profile:
            return set(
                self.env['unicore.institution.feature'].search([]).mapped('code'))
        return set(profile.feature_toggle_ids.mapped('code'))

    def has_feature(self, code):
        """Whether the company's profile enables the given feature code."""
        self.ensure_one()
        return code in self._enabled_feature_codes()

    def write(self, vals):
        # Menu visibility depends on the company profile. Drop the menu cache
        # when the profile changes so feature-gated menus refresh immediately
        # (load_menus is ormcached by uid/lang, not company).
        if 'institution_profile_id' in vals:
            self.env.registry.clear_cache()
        return super().write(vals)
