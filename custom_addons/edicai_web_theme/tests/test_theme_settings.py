"""Edicai Web Theme — scheme storage + normalization.

Covers: default scheme (light), the settings round-trip through the
system parameter, and the fail-closed normalization behind the boot
route.  The route payload is asserted to carry the scheme string ONLY.
"""

from odoo.tests import common

from odoo.addons.edicai_web_theme.controllers.main import (
    PARAM_KEY,
    normalize_scheme,
    scheme_for_env,
)


class TestEdicaiTheme(common.TransactionCase):

    def setUp(self):
        super().setUp()
        params = self.env['ir.config_parameter'].sudo()
        self._had_param = params.search([('key', '=', PARAM_KEY)])
        self._old_value = (self._had_param.value
                           if self._had_param else None)

    def tearDown(self):
        params = self.env['ir.config_parameter'].sudo()
        if self._had_param:
            params.set_param(PARAM_KEY, self._old_value)
        else:
            params.search([('key', '=', PARAM_KEY)]).unlink()
        super().tearDown()

    def _param(self):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_KEY)

    def test_01_default_scheme_is_light_when_unset(self):
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', PARAM_KEY)]).unlink()
        self.assertEqual(normalize_scheme(self._param()), 'light')

    def test_02_settings_roundtrip_sets_parameter(self):
        settings = self.env['res.config.settings'].create({})
        settings.edicai_color_scheme = 'dark'
        settings.execute()

        self.assertEqual(self._param(), 'dark')
        payload = scheme_for_env(self.env)
        self.assertEqual(payload, {'scheme': 'dark'})

    def test_03_invalid_param_fails_closed_to_light(self):
        for bogus in ('neon', None, '', 'DARK', 0):
            self.assertEqual(
                normalize_scheme(bogus), 'light',
                'unknown scheme %r must fail closed to light' % (bogus,))

    def test_04_payload_exposes_scheme_string_only(self):
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_KEY, 'neon-untrusted')
        payload = scheme_for_env(self.env)
        self.assertEqual(set(payload.keys()), {'scheme'})

    def test_05_settings_field_defaults_to_light(self):
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(settings.edicai_color_scheme, 'light')
