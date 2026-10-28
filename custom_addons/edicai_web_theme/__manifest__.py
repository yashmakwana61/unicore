{
    'name': 'Edicai Web Theme',
    'version': '19.0.1.0.0',
    'category': 'Edicai/Hidden',
    'summary': 'Light/dark color scheme with a General Settings toggle (modern SaaS UI base)',
    'description': """
Edicai Web Theme
===============

Adds a swappable color scheme (Light / Dark) driven from
General Settings > Appearance.

- ``edicai.web.color_scheme`` system parameter (light default).
- Applies Bootstrap 5.3 ``data-bs-theme`` for native form, button and
  table chrome and remaps EDICAI design tokens (cards, dashboards, AI
  workspace) so every custom surface follows the same scheme.
- A boot service applies the stored scheme before the first paint
  (localStorage-first, server-confirmed).
    """,
    'author': 'Precisefect Solutions Pvt. Ltd.',
    'website': 'https://www.precisefect.com',
    'license': 'OPL-1',
    'depends': ['web'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edicai_web_theme/static/src/scss/edicai_theme.scss',
            'edicai_web_theme/static/src/js/boot.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
