"""Per-company feature menu gating + terminology menu relabeling.

Two jobs:

* Feature gating — hide the menus of optional UniCore modules when the current
  company's institution profile does not enable the corresponding feature.
* Terminology relabeling — rewrite the visible menu names (``Faculties``,
  ``Departments``, ``Programs``, ...) to the institution's vocabulary. This is
  done in ``load_menus`` (copy-on-write on top of the ormcached tree), so each
  request relabels from ``self.env.company`` fresh.

Legacy (no profile, or the UNI_LEGACY profile with all 13 features + generic
terminology) changes nothing, so the backfilled default is byte-identical.

Feature gating lives in ``_filter_visible_menus`` (NOT the cached
``_visible_menu_ids``) so it is computed per company from ``self.env.company``.
Caching note: ``load_menus`` is ormcached by (uid, debug, lang) — not by
company — so ``res.company.write`` clears the menu cache whenever the
institution profile changes; switching company in-session serves the cached
tree until the next cache clear. Menu *names* are relabeled outside the cache
(per request), so they always match the current company.
"""

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    # technical module -> feature code. Only modules behind a feature toggle are
    # gated; everything else (base, configuration, academic core) always shows.
    _FEATURE_MODULES = {
        'unicore_hostel': 'HOSTEL',
        'unicore_transport': 'TRANSPORT',
        'unicore_transport_fleet': 'TRANSPORT',
        'unicore_library': 'LIBRARY',
        'unicore_alumni': 'ALUMNI',
        'unicore_convocation': 'CONVOCATION',
        'unicore_scholarship': 'SCHOLARSHIP',
        'unicore_crm': 'CRM',
        'unicore_admission': 'ADMISSION',
        'unicore_website': 'WEBSITE',
        'unicore_attendance': 'ATTENDANCE',
        'unicore_exam': 'EXAM',
        'unicore_fees': 'FEES',
    }

    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()
        company = self.env.company
        if not company or not company.institution_profile_id:
            return menus
        all_codes = set(
            self.env['unicore.institution.feature'].search([]).mapped('code'))
        disabled = all_codes - company._enabled_feature_codes()
        if not disabled:
            return menus

        # Resolve each visible menu's defining module in a single query.
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.ui.menu'),
            ('res_id', 'in', menus.ids),
        ])
        module_by_menu = {datum.res_id: datum.module for datum in data}

        def _is_hidden(menu):
            code = self._FEATURE_MODULES.get(module_by_menu.get(menu.id))
            return bool(code) and code in disabled

        return menus.filtered(lambda menu: not _is_hidden(menu))

    def load_menus(self, debug):
        result = super().load_menus(debug)
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
        # Copy-on-write: never mutate the ormcached dict returned by super().
        menus = dict(result)
        for menu_id, menu in result.items():
            if not isinstance(menu, dict) or not menu.get('name'):
                continue
            applied = company._terminology_apply(menu['name'], exact, prefixes)
            if applied != menu['name']:
                entry = dict(menu)
                entry['name'] = applied
                menus[menu_id] = entry
        return menus
