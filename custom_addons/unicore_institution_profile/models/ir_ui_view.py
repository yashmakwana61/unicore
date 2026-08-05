"""Terminology-aware view labels.

Gap-2 fill: wire the institution terminology profiles into the actual view
labels served to the web client, via a runtime ``get_view`` rewrite. Purely
cosmetic and strictly gated:

* Only rewrites when the current company has a terminology profile attached.
* Only touches a whitelist of UniCore models and a whitelist of m2o field
  names, and only when the rendered ``string`` EXACTLY equals the generic
  term (e.g. ``Program`` -> ``Class/Section`` for K-12).
* Legacy companies (no profile, or UNI_LEGACY with generic terms) get a
  byte-identical architecture back — resolve_label() returns the generic
  term, so nothing changes.

Odoo 19 note: the model-level ``get_views`` no longer exists; ``get_view`` /
``get_views`` live on ``ir.ui.view``. We override ``get_view`` so both
``get_views`` and direct ``get_view`` calls are covered.
"""

from odoo import api, models
from lxml import etree


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    # field name -> terminology concept for label rewriting
    _TERM_VIEW_FIELDS = {
        'program_id': 'program',
        'department_id': 'department',
        'faculty_id': 'faculty',
        'student_id': 'student',
        'semester_id': 'semester',
        'academic_year_id': 'academic_year',
    }

    # models whose views get terminology-aware labels
    _TERM_VIEW_MODELS = {
        'unicore.student',
        'unicore.enrollment',
        'unicore.admission.applicant',
        'unicore.program',
        'unicore.course',
        'unicore.semester',
        'unicore.department',
        'unicore.faculty',
    }

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(
            view_id=view_id, view_type=view_type, **options
        )
        if view_id:
            model = self.browse(view_id).model
        elif result.get('models'):
            model = next(iter(result['models']), None)
        else:
            model = None
        profile = self.env.company.terminology_profile_id
        if (not model or not profile
                or model not in self._TERM_VIEW_MODELS):
            return result

        arch = result.get('arch')
        if not arch:
            return result

        # Cheap fast path: none of the generic labels are present at all.
        if not any(g in arch for g in (
                '"Program"', '"Student"', '"Semester"',
                '"Academic Year"', '"Department"', '"Faculty"')):
            return result

        node = etree.fromstring(arch)
        changed = False
        for fnode in node.iter('field'):
            concept = self._TERM_VIEW_FIELDS.get(fnode.get('name'))
            if not concept:
                continue
            current = fnode.get('string')
            generic = profile._TERM_CONCEPTS[concept][1]
            applied = profile.resolve_label(concept)
            if not current or current != generic:
                continue
            if applied and applied != generic:
                fnode.set('string', applied)
                changed = True

        if changed:
            result = dict(result)
            result['arch'] = etree.tostring(node, encoding='unicode')
        return result
