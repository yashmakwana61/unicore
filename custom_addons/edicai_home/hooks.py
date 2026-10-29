# -*- coding: utf-8 -*-
"""Reversible landing wire-in for the Edicai Home client action.

Policy (approved design decision):
- Only users whose `res.users.action_id` was NULL get the Home action.
- The list of touched users is snapshotted in ir.config_parameter BEFORE any
  write, and `restore_home_action()` clears them from the snapshot.
- Uninstalling this module is NOT a rollback path; use the restore util.
"""
import json
import logging

PARAM_SNAPSHOT = 'edicai_home.landing_snapshot'

_logger = logging.getLogger(__name__)


def post_init_wire_home(env):
    """Snapshot the touched-user list, then assign the Edicai Home action to
    active internal users whose home action was NULL."""
    icp = env['ir.config_parameter'].sudo()
    if icp.get_param(PARAM_SNAPSHOT, ''):
        _logger.info('Edicai Home: landing snapshot exists, wiring skipped '
                     '(idempotent install).')
        return
    action = env.ref('edicai_home.action_edicai_home', raise_if_not_found=False)
    if not action:
        _logger.warning('Edicai Home: action not found, wiring skipped.')
        return
    from .models.edicai_home_data import ROLE_GROUPS
    # portal-implied roles (student) are excluded: base.group_portal is
    # exclusive with base.group_user, so those users keep the portal landing.
    INTERNAL_ROLES = [r for r in ROLE_GROUPS if r != 'student']
    role_gids = {
        env.ref(xmlid).id
        for xmlid in (ROLE_GROUPS[r] for r in INTERNAL_ROLES)
        if env.ref(xmlid, raise_if_not_found=False)
    }
    users = env['res.users'].sudo().search([
        ('active', '=', True), ('action_id', '=', False),
        ('share', '=', False),
    ])
    users = users.filtered(lambda u: set(u.group_ids.ids) & role_gids)
    snapshot = [str(user.login) for user in users]
    try:
        users.write({'action_id': action.id})
        icp.set_param(PARAM_SNAPSHOT, json.dumps(snapshot, sort_keys=True))
        _logger.info('Edicai Home: wired as landing action for %s user(s).',
                     len(users))
    except Exception:
        env.cr.rollback()
        _logger.warning('Edicai Home: landing wiring failed; leaving users '
                        'unchanged.', exc_info=True)
