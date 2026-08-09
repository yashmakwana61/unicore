"""Institution-profile enforcement on ``unicore.academic.unit``.

Wired here (not in unicore_academic_generic) because the profile model lives in
this module, which depends on unicore_academic_generic — the generic module can
never reference ``res.company.institution_profile_id`` without creating a
circular dependency. Enforcement is active only when this module is installed.
"""

from odoo import _, api, models
from odoo.exceptions import ValidationError


class UnicoreAcademicUnit(models.Model):
    _inherit = 'unicore.academic.unit'

    @api.constrains('company_id', 'unit_type_id')
    def _check_unit_type_allowed(self):
        """Enforce the institution profile's allowed academic unit levels.

        Strict only when the company has a profile AND the profile's allow-list
        is non-empty. No profile, or an empty allow-list, means unrestricted
        (legacy behavior). UNI_LEGACY lists all eight unit types, so the
        backfilled default never fires.
        """
        for record in self:
            profile = record.company_id.institution_profile_id
            allowed = profile.academic_unit_level_ids if profile else False
            if allowed and record.unit_type_id not in allowed:
                raise ValidationError(
                    _('Unit type "%(unit_type)s" is not allowed by the '
                      'institution profile "%(profile)s". Allowed unit '
                      'levels: %(allowed)s.',
                      unit_type=record.unit_type_id.name,
                      profile=profile.name,
                      allowed=', '.join(allowed.mapped('name')) or _('none'),
                    )
                )
