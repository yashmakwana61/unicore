# -*- coding: utf-8 -*-
{
    'name': 'Edicai SaaS Home',
    'version': '19.0.1.0.0',
    'category': 'Education/Home',
    'summary': 'Role-aware premium SaaS home: Dashboard, Getting Started, Recent Updates',
    'description': """
Home experience for Edicai (Odoo 19 Community):
- Single client action (`edicai_home.home`) with three tabs:
  Dashboard | Getting Started | Recent Updates.
- Dashboard widgets are chosen server-side from the user's actual Odoo groups
  (deterministic union, no duplicated widgets) and computed under the calling
  user's access rights — never sudo; restricted widgets degrade to empty states.
- Getting Started persists per-user progress in `edicai.onboarding.state`
  (record-rule scoped to the owner).
- Recent Updates merges admin-published product updates (`edicai.product.update`,
  audience-restricted) with filtered `edicai.notice` announcements.
- Reversible landing wire-in: post-install writes `res.users.action_id` only for
  users whose home action was NULL, snapshotting originals in
  `ir.config_parameteredicai_home.official_home_snapshot` (JSON login -> xmlid).
  Wire/restore util methods live on `edicai.home.data`.
- No core modification; no new app root menu; uninstall is NOT a rollback path
  (use restore_home_action).
""",
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'license': 'OPL-1',
    'depends': [
        'base', 'web', 'mail',
        'edicai_base',
        'edicai_notice_board',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/edicai_home_rules.xml',
        'data/edicai_onboarding_items.xml',
        'views/edicai_home_action.xml',
        'views/edicai_product_update_views.xml',
        'views/edicai_home_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_home/static/src/scss/edicai_home.scss',
            'edicai_home/static/src/xml/edicai_home.xml',
            'edicai_home/static/src/js/edicai_home.js',
            'edicai_home/static/src/js/user_menu_item.js',
        ],
    },
    'post_init_hook': 'post_init_wire_home',
    'application': False,
    'installable': True,
    'auto_install': False,
}
