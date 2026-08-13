"""Terminology-aware action labels (page titles / breadcrumbs).

The action name served to the web client (page title and breadcrumb) comes
from ``/web/action/load`` -> ``ir.actions.act_window._get_action_dict()``.
Relabel it per company, gated like every other terminology layer (no profile /
legacy profile => byte-identical, and copy-on-write so the read result is
never mutated).
"""

from odoo import models


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        result = super()._get_action_dict()
        name = result.get('name')
        if not name:
            return result
        company = self.env.company
        if not company:
            return result
        # Pre-install (fresh DB loading modules before this one) => no-op.
        if 'institution_profile_id' not in self.env['res.company']._fields:
            return result
        try:
            exact, prefixes = company._terminology_label_rules()
        except Exception:
            return result
        if not exact and not prefixes:
            return result
        applied = company._terminology_apply(name, exact, prefixes)
        if applied != name:
            result = dict(result)
            result['name'] = applied
        return result
