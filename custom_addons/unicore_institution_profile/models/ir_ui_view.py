"""Terminology-aware view architectures.

Field labels reach the web client through two channels:

* ``fields_get`` (handled globally in ``models/base.py``) for every field,
  including bare ``<field name="..."/>`` nodes which inherit their label from
  the field definition.
* The view architecture itself, where explicit ``string`` attributes live on
  ``<filter>``, ``<label>``, ``<button>``, ``<field string=...>`` (statinfo
  cards) and ``<group>/<page>`` nodes.

This module rewrites those explicit architecture strings at runtime in
``get_view`` (which also feeds ``get_views``). It is mapping-driven from the
company's terminology rules and strictly gated:

* No profile, or the UNI_LEGACY university profile => empty rules => the
  architecture is returned byte-identical.
* A substring fast-path skips parsing entirely when no generic term token is
  present in the architecture at all.
* Only ``string`` attributes whose value matches an exact generic label or a
  leading generic token are rewritten; everything else is untouched.
"""

from odoo import api, models
from lxml import etree


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(
            view_id=view_id, view_type=view_type, **options
        )
        arch = result.get('arch')
        if not arch:
            return result
        company = self.env.company
        if not company:
            return result
        if 'institution_profile_id' not in self.env['res.company']._fields:
            return result
        try:
            exact, prefixes = company._terminology_label_rules()
        except Exception:
            return result
        if not exact and not prefixes:
            return result

        # Substring fast-path: if no generic token is present in the raw arch,
        # no ``string`` attribute can match => skip the parse entirely.
        tokens = set(exact) | {token for token, _applied in prefixes}
        if not any(token in arch for token in tokens):
            return result

        node = etree.fromstring(arch)
        changed = False
        for element in node.iter():
            value = element.get('string')
            if not value:
                continue
            applied = company._terminology_apply(value, exact, prefixes)
            if applied != value:
                element.set('string', applied)
                changed = True

        if changed:
            result = dict(result)
            result['arch'] = etree.tostring(node, encoding='unicode')
        return result

    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        """Make the view cache company-aware.

        The base cache key is (view_id, view_type, mobile, lang, *_view_ref) —
        it does NOT include the company. Since terminology relabeling (both the
        cached ``fields`` dict and our per-request arch rewrite) depends on the
        company's institution profile, two companies must not share cached
        field labels. Adding the company id gives each company its own view
        cache entry. ``res.company.write`` already clears the whole registry
        cache on profile change, so switching profiles still refreshes.
        """
        key = super()._get_view_cache_key(
            view_id=view_id, view_type=view_type, **options)
        company = self.env.company
        if company:
            key = key + (('company', company.id),)
        return key
