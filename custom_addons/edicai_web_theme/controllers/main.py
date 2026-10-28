from odoo import http

PARAM_KEY = 'edicai.web.color_scheme'
SCHEMES = ('light', 'dark')


def normalize_scheme(value):
    """Collapse anything unknown to the 'light' default."""
    return value if value in SCHEMES else 'light'


def scheme_for_env(env):
    """Boot payload for a model Environment — also used by tests."""
    value = env['ir.config_parameter'].sudo().get_param(PARAM_KEY)
    return {'scheme': normalize_scheme(value)}


class EdicaiThemeController(http.Controller):
    """Return the active color scheme to the webclient boot service.

    Keyless, auth-user jsonrpc: nothing but the scheme string is
    exposed, and the value is a presentation preference — never a
    permission.
    """

    @http.route('/edicai_web_theme/scheme', type='jsonrpc', auth='user',
                readonly=True)
    def current_scheme(self):
        return scheme_for_env(http.request.env)
