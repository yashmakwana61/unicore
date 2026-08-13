

def post_init_hook(env):
    """Add admin users to the Oacis admin group after installation."""
    group_oacis_admin = env.ref(
        'oacis_base.group_oacis_admin', raise_if_not_found=False,
    )
    if not group_oacis_admin:
        return
    group_system = env.ref('base.group_system')
    admin_users = env['res.users'].search([('group_ids', 'in', group_system.id)])
    for user in admin_users:
        if group_oacis_admin.id not in user.group_ids.ids:
            user.write({'group_ids': [(4, group_oacis_admin.id)]})
