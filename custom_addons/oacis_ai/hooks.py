import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Ensure AI Managers can also use the chatbot.

    Since group_oacis_ai_manager intentionally does NOT imply
    group_oacis_ai_user (so 'own only' record rules don't restrict
    managers), grant both groups to existing managers on install/upgrade.
    """
    try:
        manager = env.ref('oacis_ai.group_oacis_ai_manager', raise_if_not_found=False)
        user = env.ref('oacis_ai.group_oacis_ai_user', raise_if_not_found=False)
        if manager and user:
            managers = manager.users
            for u in managers:
                if user not in u.groups_id:
                    u.write({'groups_id': [(4, user.id)]})
            if managers:
                _logger.info('Oacis AI: granted AI User to %d AI Manager(s)', len(managers))
    except Exception:
        _logger.exception('Oacis AI post_init_hook failed (non-blocking)')
