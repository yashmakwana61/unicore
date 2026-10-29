# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ONBOARDING_ROLES = ['admin', 'registrar', 'finance', 'manager',
                    'faculty', 'staff', 'student']

DERIVED_CHECKS = [
    ('', 'Manual / not derived'),
    ('academic_year_exists', 'Academic year configured'),
    ('semester_scheduled', 'Semesters scheduled'),
    ('roles_assigned', 'Users holding role groups'),
]


class EdicaiOnboardingItem(models.Model):
    _name = 'edicai.onboarding.item'
    _description = 'Edicai Home — Getting Started item (config)'
    _order = 'role, sequence, id'

    name = fields.Char(string='Title', required=True, translate=True)
    description = fields.Text(string='Explainer', translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    role = fields.Selection([(r, r.title()) for r in ONBOARDING_ROLES],
                            string='Target role', required=True, index=True)
    completion_mode = fields.Selection(
        [('manual', 'User confirms'), ('derived', 'Derived from system state')],
        string='Completion', required=True, default='manual')
    derive_check = fields.Selection(DERIVED_CHECKS, string='Derived check')
    link_label = fields.Char(string='Link label', translate=True)
    link_action = fields.Char(
        string='Open action (XML ID)',
        help='Optional ir.actions XML ID opened by the item link.')

    @api.model
    def get_role_onboarding(self, user, roles):
        """Items visible for the user's roles + per-user state."""
        if not roles:
            return {'items': [], 'progress': None}
        State = self.env['edicai.onboarding.state']
        items = self.search([('role', 'in', roles)])
        states = State.search([('user_id', '=', user.id)])
        state_map = {st.item_id.id: st for st in states}
        payload = []
        for item in items:
            st = state_map.get(item.id)
            derived = None
            if item.completion_mode == 'derived':
                derived = self._check_derived(item, user)
            payload.append({
                'id': item.id,
                'name': item.name,
                'description': item.description or '',
                'completion_mode': item.completion_mode,
                'derived_done': derived,
                'state': st.state if st else ('done' if derived else 'todo'),
                'completed_on': st.completed_on
                if st and st.completed_on else None,
                'link_label': item.link_label or '',
                'link_action': item.link_action or '',
            })
        total = len([i for i in payload if i['state'] != 'skipped'])
        done = len([i for i in payload if i['state'] == 'done'])
        progress = {'total': total, 'done': done}
        progress['percent'] = round(100.0 * done / total, 1) if total else 100.0
        return {'items': payload, 'progress': progress}

    def _check_derived(self, item, user):
        """Honest derived completion: computed from real records only."""
        try:
            if item.derive_check == 'academic_year_exists':
                return bool(self.env['edicai.academic.year'].search_count(
                    [], limit=1))
            if item.derive_check == 'semester_scheduled':
                today = fields.Date.context_today(self)
                return bool(self.env['edicai.semester'].search_count(
                    [('date_start', '<=', today), ('date_end', '>=', today)],
                    limit=1))
            if item.derive_check == 'roles_assigned':
                gid = self.env.ref('edicai_base.group_edicai_registrar').id
                return bool(self.env['res.users'].search_count(
                    [('group_ids', 'in', [gid])], limit=1))
            return False
        except Exception:
            _logger.warning('derived onboarding check failed', exc_info=True)
            return False
