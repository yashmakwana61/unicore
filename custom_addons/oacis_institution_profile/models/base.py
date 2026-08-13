"""Global terminology-aware field labels (the "everywhere" layer).

The web client renders field labels from the ``fields_get`` payload — the
``fields`` dict served by ``get_views``/``get_view`` — NOT from the view XML.
So the only way an institution's terminology profile can relabel *every* form,
list, kanban and search view across ALL Oacis modules is to rewrite the
``fields_get`` output itself.

We extend the ``base`` abstract model, which every model implicitly inherits,
and rewrite the ``string`` of any field whose label matches the current
company's terminology relabel rules. This is the same supported pattern used by
community "custom field label" modules.

Strictly gated for zero regression:

* No profile, or the UNI_LEGACY university profile => relabel rules are empty
  => output is byte-identical (the common/default case pays no extra work).
* Only labels that exactly match a generic term (e.g. ``Program``), a known
  compound (``Faculty Member``, ``Current Semester``) or start with a generic
  term token (``Program Name`` -> ``Course Name``) are rewritten.
* The whole rewrite is defensive: any error while resolving rules falls back to
  the untouched result, and pre-install (no ``institution_profile_id`` field)
  is a no-op.
"""

from odoo import models


class TerminologyBase(models.AbstractModel):
    _inherit = 'base'

    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields=allfields, attributes=attributes)
        if not res:
            return res
        company = self.env.company
        if not company:
            return res
        # res.company.institution_profile_id does not exist yet (fresh install
        # of modules loaded before oacis_institution_profile) => no-op.
        if 'institution_profile_id' not in self.env['res.company']._fields:
            return res
        try:
            exact, prefixes = company._terminology_label_rules()
        except Exception:
            return res
        if not exact and not prefixes:
            return res
        changed = False
        for fdef in res.values():
            label = fdef.get('string')
            if not label:
                continue
            applied = company._terminology_apply(label, exact, prefixes)
            if applied != label:
                fdef['string'] = applied
                changed = True
        return res
