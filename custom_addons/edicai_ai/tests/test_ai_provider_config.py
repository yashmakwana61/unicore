"""Prompt-11 — provider configuration & switching tests.

Coverage:

* the config matrix (mock / gemini / openrouter × key × model),
  ALWAYS through the SAME abstraction the application uses
  (``edicai.ai.provider``), with ``requests`` mocked — no real network;
* provider switching without restart and its interaction with flags;
* NO semantic change to the legacy path (default 'compatible');
* security preservation: external provider configuration cannot
  weaken policy gates / company isolation / audit;
* masking: keys never appear in display payloads or results.

All tests run through the real provider methods; the ONLY things
mocked are external HTTP calls (``requests.post``) and time.
"""

import json

import odoo.tests
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures

P_KEY = 'odoo.addons.edicai_ai.models.edicai_ai_provider'


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIProviderConfigHarness(TransactionCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cp = cls.env['ir.config_parameter'].sudo()
        cls.cp = cp
        # Clean provider configuration state for determinism.
        for param in (
                'edicai_ai.active_provider',
                'edicai_ai.gemini_api_key', 'edicai_ai.gemini_base_url',
                'edicai_ai.gemini_model', 'edicai_ai.gemini_enabled',
                'edicai_ai.openrouter_api_key', 'edicai_ai.openrouter_base_url',
                'edicai_ai.openrouter_model', 'edicai_ai.openrouter_enabled',
                'edicai_ai.qa_test_mode', 'edicai_ai.api_key',
        ):
            cp.set_param(param, '')
        cls._build_academic_core(suffix='PV')
        cls.finance = cls._create_staff_user(
            login_suffix='pvfin', groups=('finance',))
        cls.registrar = cls._create_staff_user(
            login_suffix='pvreg', groups=('registrar',))
        cls.bystander = cls._create_staff_user(
            login_suffix='pvout')  # no edicai base role

    @classmethod
    def tearDownClass(cls):
        cls.cp.set_param('edicai_ai.active_provider', 'compatible')
        cls.cp.set_param('edicai_ai.api_key', '')
        super().tearDownClass()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def configure(self, key, enabled='True', key_val='sk-valid-key-123',
                  model='test-model-1', url=None):
        if key == 'gemini':
            self.cp.set_param('edicai_ai.gemini_enabled', enabled)
            self.cp.set_param('edicai_ai.gemini_api_key', key_val)
            self.cp.set_param('edicai_ai.gemini_model', model)
            self.cp.set_param('edicai_ai.gemini_base_url', url or '')
        elif key == 'openrouter':
            self.cp.set_param('edicai_ai.openrouter_enabled', enabled)
            self.cp.set_param('edicai_ai.openrouter_api_key', key_val)
            self.cp.set_param('edicai_ai.openrouter_model', model)
            self.cp.set_param('edicai_ai.openrouter_base_url', url or '')
        elif key == 'active':
            self.cp.set_param('edicai_ai.active_provider', key_val)

    @staticmethod
    def _fake_response(status=200, body=None):
        resp = type('R', (), {})()
        resp.status_code = status
        resp._body = json.dumps(body or {}).encode()
        resp.text = resp._body.decode() if status != 200 else ''

        def raise_for_status():
            if resp.status_code != 200:
                import requests as _r
                err = _r.exceptions.HTTPError('http %d' % resp.status_code)
                err.response = type('X', (), {
                    'status_code': status, 'text': resp.text})()
                raise err

        resp.raise_for_status = raise_for_status
        resp.json = lambda: body if body is not None else {}
        return resp

    def _post_ok(self):
        return self._fake_response(200, {
            'choices': [{'message': {'content': 'ok'}}]})

    # ------------------------------------------------------------------
    # Mock provider (offline, deterministic)
    # ------------------------------------------------------------------

    def test_01_mock_provider_matrix_pass(self):
        """Mock + no key + no network → PASS, deterministic, and NO
        external call."""
        self.configure('active', key_val='mock')
        replies = []
        with patch((P_KEY + '.requests.post')) as fake_post:
            for _ in range(2):
                reply = self.env['edicai.ai.provider'].chat(
                    [{'role': 'user', 'content': 'hello world'}])
                replies.append(reply)
        fake_post.assert_not_called()  # no external network requirement
        self.assertTrue(replies[0])
        self.assertEqual(replies[0], replies[1])  # deterministic
        self.assertNotIn('hello world', replies[0])  # no content echo
        result = self.env['edicai.ai.provider'].test_connection('mock')
        self.assertTrue(result['ok'])
        self.assertEqual(result['category'], 'OK')

    # ------------------------------------------------------------------
    # Gemini matrix
    # ------------------------------------------------------------------

    def test_02_gemini_missing_key_safe_failure(self):
        self.configure('gemini', key_val='')
        result = self.env['edicai.ai.provider'].test_connection('gemini')
        self.assertFalse(result['ok'])
        self.assertEqual(result['category'], 'NOT_CONFIGURED')
        with self.assertRaises(UserError):
            self.env['edicai.ai.provider']._call_api(
                [{'role': 'user', 'content': 'x'}], provider_key='gemini')

    def test_03_gemini_disabled_not_used(self):
        self.configure('gemini', enabled='False')
        result = self.env['edicai.ai.provider'].test_connection('gemini')
        self.assertFalse(result['ok'])
        self.assertEqual(result['category'], 'NOT_CONFIGURED')

    def test_04_gemini_invalid_key_auth_error(self):
        self.configure('gemini', key_val='bad-key')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(401, {})):
            result = self.env['edicai.ai.provider'].test_connection('gemini')
        self.assertFalse(result['ok'])
        self.assertEqual(result['category'], 'AUTH_ERROR')
        self.assertNotIn('bad-key', json.dumps(result))

    def test_05_gemini_invalid_model_safe_failure(self):
        self.configure('gemini', model='does-not-exist')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(404, {})):
            validation = self.env['edicai.ai.provider'].validate_model(
                'gemini')
        self.assertFalse(validation['valid'])
        self.assertEqual(validation['category'], 'MODEL_ERROR')
        # connection test itself (config fine, model wrong) also fails
        # safely — the tester always knows WHY.
        self.assertIn('model', validation['message'].lower())

    def test_06_gemini_valid_connection_and_call(self):
        self.configure('gemini')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(200, {
                       'choices': [{'message': {'content': 'gemini ok'}}]})) \
                as fake_post:
            result = self.env['edicai.ai.provider'].test_connection('gemini')
            self.assertTrue(result['ok'])
            reply = self.env['edicai.ai.provider']._call_api(
                [{'role': 'user', 'content': 'hi'}], provider_key='gemini')
            self.assertEqual(reply, 'gemini ok')
        args, kwargs = fake_post.call_args
        # Gemini OpenAI-compatible endpoint derived from the base URL
        self.assertIn('generativelanguage.googleapis.com', args[0])
        self.assertIn('chat/completions', args[0])
        # the request BODY (model/messages) and the endpoint never
        # carry the key material (the auth HEADER is where the key
        # legitimately lives during a call).
        self.assertNotIn('sk-valid-key-123', args[0])
        self.assertNotIn('sk-valid-key-123', json.dumps(kwargs['json']))

    def test_07_gemini_timeout_and_provider_down(self):
        self.configure('gemini')
        import requests as requests_module
        with patch((P_KEY + '.requests.post'),
                   side_effect=requests_module.exceptions.Timeout('t')):
            result = self.env['edicai.ai.provider'].test_connection('gemini')
            self.assertEqual(result['category'], 'TIMEOUT')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(503, {})):
            result = self.env['edicai.ai.provider'].test_connection('gemini')
            self.assertEqual(result['category'], 'PROVIDER_DOWN')

    # ------------------------------------------------------------------
    # OpenRouter matrix
    # ------------------------------------------------------------------

    def test_08_openrouter_missing_and_invalid_key(self):
        self.configure('openrouter', key_val='')
        result = self.env['edicai.ai.provider'].test_connection('openrouter')
        self.assertEqual(result['category'], 'NOT_CONFIGURED')
        self.configure('openrouter', key_val='or-invalid')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(403, {})):
            result = self.env['edicai.ai.provider'].test_connection(
                'openrouter')
        self.assertEqual(result['category'], 'AUTH_ERROR')

    def test_09_openrouter_free_model_valid_and_invalid(self):
        # No hardcoding: an arbitrary free-model id is only a value.
        self.configure('openrouter', model='openrouter/free')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(200, {
                       'choices': [{'message': {'content': 'free ok'}}]})):
            result = self.env['edicai.ai.provider'].test_connection(
                'openrouter')
            self.assertTrue(result['ok'])
            validation = self.env['edicai.ai.provider'].validate_model(
                'openrouter')
            self.assertTrue(validation['valid'])
        self.configure('openrouter', model='gone-model')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(404, {})):
            validation = self.env['edicai.ai.provider'].validate_model(
                'openrouter')
        self.assertFalse(validation['valid'])

    def test_10_openrouter_rate_limit(self):
        self.configure('openrouter')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(429, {})):
            result = self.env['edicai.ai.provider'].test_connection(
                'openrouter')
        self.assertEqual(result['category'], 'RATE_LIMIT')

    # ------------------------------------------------------------------
    # Active-provider switching (no restart, no code change)
    # ------------------------------------------------------------------

    def test_11_switch_provider_without_restart(self):
        self.configure('active', key_val='compatible')
        self.assertEqual(
            self.env['edicai.ai.provider'].get_active_provider_key(),
            'compatible')
        # Point Gemini but keep it DISABLED — legacy path is untouched.
        self.assertEqual(
            self.env['edicai.ai.provider'].get_provider_profile()[
                'key'], 'compatible')
        # Switch: every call site resolves the profile per call.
        self.configure('active', key_val='gemini')
        self.configure('gemini')
        self.assertEqual(
            self.env['edicai.ai.provider'].get_active_provider_key(),
            'gemini')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(200, {
                       'choices': [{'message': {'content': 'ok'}}]})) \
                as fake_post:
            self.env['edicai.ai.provider'].generate_text('ping')
        self.assertIn('generativelanguage', fake_post.call_args[0][0])
        # …and back — the next request uses the switched provider too.
        self.configure('active', key_val='openrouter')
        self.configure('openrouter', model='free-model')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(200, {
                       'choices': [{'message': {'content': 'ok'}}]})) \
                as fake_post:
            self.env['edicai.ai.provider'].generate_text('ping')
        self.assertIn('openrouter.ai', fake_post.call_args[0][0])

    def test_12_legacy_default_unchanged(self):
        """With NO provider configuration at all, everything behaves
        exactly as pre-lab: active = compatible, configured key wins,
        missing key raises the SAME classified 'not configured' error."""
        self.assertEqual(
            self.env['edicai.ai.provider'].get_active_provider_key(),
            'compatible')
        env_key = 'env-legacy-key-for-switch-test'
        import os
        with patch.dict(os.environ, {'EDICAI_AI_API_KEY': env_key}):
            self.assertEqual(
                self.env['edicai.ai.provider']._get_api_key(), env_key)
        # profile without env var and without db key → NOT available
        # (fail-safe; connection test says so safely)
        stripped = {k: v for k, v in os.environ.items()
                    if k != 'EDICAI_AI_API_KEY'}
        with patch.object(os, 'environ', stripped):
            profile = self.env['edicai.ai.provider'].get_provider_profile()
            self.assertFalse(profile['available'])
            result = self.env['edicai.ai.provider'].test_connection(
                'compatible')
            self.assertFalse(result['ok'])
            self.assertEqual(result['category'], 'NOT_CONFIGURED')

    # ------------------------------------------------------------------
    # Security preservation & masking
    # ------------------------------------------------------------------

    def test_13_provider_switch_cannot_weaken_authorization(self):
        """An external provider config NEVER weakens ERP authorization:
        the policy gate verdicts are identical for every provider, and
        unauthorized users stay unauthorized."""
        gate = self.env['edicai.ai.policy.gate']
        # The student portal user never holds group_edicai_ai_user, so
        # 'fees.fee_status' must be denied for them — under EVERY
        # active-provider setting (authorization is provider-blind).
        student_user = self._create_student(
            login_suffix='pvsec', company=self.company)
        verdicts = []
        for provider in ('compatible', 'gemini', 'openrouter', 'mock'):
            self.configure('active', key_val=provider)
            denied = gate.check_access(
                'fees.fee_status', user=student_user)
            allowed = gate.check_access(
                'fees.fee_status', user=self.finance)
            self.assertFalse(
                denied['allowed'],
                'provider %s weakened the group gate!' % provider)
            self.assertTrue(
                allowed['allowed'],
                'provider %s broke the authorized path!' % provider)
            verdicts.append(provider)
        self.assertEqual(len(verdicts), 4)

    def test_14_no_key_leaks_in_outputs(self):
        secret = 'sk-very-secret-42'
        self.configure('gemini', key_val=secret)
        display = self.env['edicai.ai.provider'].get_active_provider_display()
        blob = json.dumps(display)
        self.assertNotIn(secret, blob)
        result = self.env['edicai.ai.provider'].test_connection('gemini')
        self.assertNotIn(secret, json.dumps(result))
        validation = self.env['edicai.ai.provider'].validate_model(
            'gemini', model='whatever')
        self.assertNotIn(secret, json.dumps(validation))
        settings_vals = self.env['res.config.settings'].default_get(
            ['edicai_ai_gemini_api_key'])
        # settings may READ the stored key for editing (config_parameter
        # mechanism) but provider RESULTS and display payloads never
        # carry it.
        blob = json.dumps(result) + json.dumps(display)
        self.assertNotIn(settings_vals.get('edicai_ai_gemini_api_key', '|')
                         or '|', blob)

    def test_15_audit_metadata_carries_no_key(self):
        """The AI_PROVIDER_CALL usage-log metadata contains provider and
        model only — never any API key."""
        self.configure('active', key_val='gemini')
        self.configure('gemini')
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(200, {
                       'choices': [{'message': {'content': 'ok'}}]})):
            self.env['edicai.ai.provider'].generate_text('audit probe')
        events = self.env['edicai.ai.audit.event'].search(
            [], order='id desc', limit=5)
        for event in events:
            blob = json.dumps(event.metadata_json if hasattr(
                event, 'metadata_json') else (
                event.metadata if hasattr(event, 'metadata') else {}))
            self.assertNotIn('sk-valid-key-123', blob)

    def test_16_custom_model_identifier_never_breaks_the_settings_form(self):
        """Regression: a stored model outside the curated list (e.g.
        ``glm-5.3-flash-free``) must not make the whole Settings form
        explode with a wrong-value error."""
        self.env['ir.config_parameter'].set_param(
            'edicai_ai.model', 'glm-5.3-flash-free')
        settings = self.env['res.config.settings'].create({})
        field = settings._fields['edicai_ai_model']
        options = field.selection(settings) if callable(field.selection) \
            else field.selection
        self.assertIn('glm-5.3-flash-free', dict(options))
        # an onchange over that value must not raise (this is exactly the
        # call the Settings form makes, and what used to crash)
        settings.onchange(
            {'edicai_ai_model': 'glm-5.3-flash-free'},
            ['edicai_ai_model'],
            {'edicai_ai_model': {}},
        )

    def test_17_gemini_label_is_normalised_to_the_api_identifier(self):
        """A label typed in the UI ("Gemini 2.5 Flash") must reach the
        provider as the identifier it expects ("gemini-2.5-flash")."""
        self.configure('gemini', model='Gemini 2.5 Flash')
        profile = self.env['edicai.ai.provider'].get_provider_profile('gemini')
        self.assertEqual(profile['model'], 'gemini-2.5-flash')
        # an identifier is never touched
        self.configure('gemini', model='gemini-2.0-flash')
        profile = self.env['edicai.ai.provider'].get_provider_profile('gemini')
        self.assertEqual(profile['model'], 'gemini-2.0-flash')

    def test_18_rejected_key_reported_as_auth_error_even_on_400(self):
        """Gemini answers 400 "Please pass a valid API key" — the tester
        must see the actionable auth category, not a generic rejection."""
        self.configure('gemini', model='gemini-2.5-flash')
        body = {'error': {'code': 400, 'message': 'Please pass a valid '
                                                  'API key',
                          'status': 'INVALID_ARGUMENT'}}
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(400, body)):
            result = self.env['edicai.ai.provider'].test_connection('gemini')
        self.assertFalse(result['ok'])
        self.assertEqual(result['category'], 'AUTH_ERROR')
        self.assertIn('API key', result['message'])

    def test_19_unknown_model_reported_as_model_error(self):
        """A 400 that talks about the model must map to MODEL_ERROR."""
        self.configure('gemini', model='gemini-9.9-ultra')
        body = {'error': {'code': 400, 'message': 'Unknown model '
                                                  'gemini-9.9-ultra'}}
        with patch((P_KEY + '.requests.post'),
                   return_value=self._fake_response(400, body)):
            result = self.env['edicai.ai.provider'].test_connection('gemini')
        self.assertFalse(result['ok'])
        self.assertEqual(result['category'], 'MODEL_ERROR')

    def test_20_gemini_model_selection_never_excludes_the_stored_value(self):
        """The Gemini model dropdown keeps a custom stored id selectable
        and offers the known identifiers."""
        self.cp.set_param('edicai_ai.gemini_model', 'gemini-experimental-9')
        settings = self.env['res.config.settings'].create({})
        field = settings._fields['edicai_ai_gemini_model']
        options = dict(field.selection(settings)
                       if callable(field.selection) else field.selection)
        self.assertIn('gemini-experimental-9', options)
        self.assertIn('gemini-2.5-flash', options)
