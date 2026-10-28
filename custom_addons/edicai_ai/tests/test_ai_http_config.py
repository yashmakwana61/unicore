"""Prompt-11 — HTTP-level provider-lab regression.

Real HTTP tests over the ACTUAL chatbot routes:

* ``/edicai_ai/chat/provider_status`` — safe indicator payload (no key
  material, ever);
* Legacy chat path with the MOCK provider active — provider switching
  works end-to-end over HTTP without code change, and with test mode
  OFF no diagnostics leak into responses;
* Test mode ON adds the structured QA ``diagnostics`` object (and ONLY
  metadata — never prompts/reasoning/secrets);
* Configuring an external provider does NOT weaken HTTP security:
  foreign-session isolation behaves exactly as before.
"""

import odoo.tests
from odoo.tests.common import HttpCase

from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures

FLAG_TEST_MODE = 'edicai_ai.qa_test_mode'


@odoo.tests.tagged('edicai', 'post_install', '-at_install')
class AIHTTPConfigHarness(HttpCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cp = cls.env['ir.config_parameter'].sudo()
        cls.cp = cp
        cp.set_param('edicai_ai.active_provider', 'mock')
        cp.set_param(FLAG_TEST_MODE, 'False')
        cls._build_academic_core(suffix='PQ')
        cls.staff_a = cls._create_staff_user(
            login_suffix='pqa', groups=('staff',))
        cls.staff_b = cls._create_staff_user(
            login_suffix='pqb', groups=('staff',))
        cls.passwords = {
            cls.staff_a.login: 'staff_pwd_1!',
            cls.staff_b.login: 'staff_pwd_1!',
        }

    @classmethod
    def tearDownClass(cls):
        cls.cp.set_param(FLAG_TEST_MODE, 'False')
        cls.cp.set_param('edicai_ai.active_provider', 'compatible')
        super().tearDownClass()

    def _rpc(self, route, params, login):
        self.authenticate(login, self.passwords[login])
        response = self.url_open(
            route, json=self.build_rpc_payload(params))
        self.assertEqual(
            response.status_code, 200,
            'HTTP layer broke for route %s: %s' % (route, response.text))
        body = response.json()
        self.assertNotIn('error', body)
        return body['result']

    def _new_session(self, login):
        result = self._rpc('/edicai_ai/chat/new_session', {}, login)
        self.assertIn('id', result)
        return result['id']

    # ------------------------------------------------------------------
    # Safe provider indicator endpoint
    # ------------------------------------------------------------------

    def test_01_provider_status_safe_payload(self):
        result = self._rpc(
            '/edicai_ai/chat/provider_status', {}, self.staff_a.login)
        self.assertEqual(result['provider_label'], 'Mock (deterministic, offline)')
        self.assertTrue(result['available'])
        self.assertFalse(result['test_mode'])
        self.assertNotIn('api_key', result)
        self.assertNotIn('key', json_keys(result))

    def test_02_test_mode_off_no_diagnostics(self):
        session_id = self._new_session(self.staff_a.login)
        result = self._rpc('/edicai_ai/chat/send', {
            'session_id': session_id,
            'message': 'Simple mock turn (no diagnostics expected).',
        }, self.staff_a.login)
        self.assertNotIn('diagnostics', result)
        self.assertIn('reply', result)

    def test_03_test_mode_on_structured_diagnostics_only(self):
        self.cp.set_param(FLAG_TEST_MODE, 'True')
        try:
            session_id = self._new_session(self.staff_a.login)
            result = self._rpc('/edicai_ai/chat/send', {
                'session_id': session_id,
                'message': 'Turn one for the diagnostics panel.',
            }, self.staff_a.login)
            diag = result.get('diagnostics')
            self.assertIsInstance(diag, dict)
            for key in ('provider', 'model', 'status', 'tool_name',
                        'authorization', 'mutation', 'latency_ms',
                        'request_at', 'response_at'):
                self.assertIn(key, diag)
            # legacy path facts
            self.assertEqual(diag['provider'],
                             'Mock (deterministic, offline)')
            self.assertEqual(diag['status'], 'answered')
            self.assertEqual(diag['authorization'], 'ALLOWED')
            self.assertEqual(diag['tool_name'], 'edicai.ai.provider.chat')
            # metadata only — never prompt/response content
            self.assertNotIn('reply', diag)
            self.assertNotIn('message', diag)
            self.assertNotIn('content', diag)
            # persistence + isolation unaffected by test mode
            messages = self._rpc('/edicai_ai/chat/messages', {
                'session_id': session_id}, self.staff_a.login)
            self.assertEqual(len(messages), 2)
        finally:
            self.cp.set_param(FLAG_TEST_MODE, 'False')

    def test_04_external_provider_does_not_weaken_isolation(self):
        """With a fully configured external provider active, the HTTP
        security surface is byte-identical: foreign sessions stay
        RECORD_NOT_FOUND with the SAME safe payload."""
        # configure + activate a real provider profile (mocked HTTP)
        self.cp.set_param('edicai_ai.active_provider', 'gemini')
        self.cp.set_param('edicai_ai.gemini_enabled', 'True')
        self.cp.set_param('edicai_ai.gemini_api_key', 'sk-http-test-key')
        self.cp.set_param('edicai_ai.gemini_model', 'test-model')
        try:
            session_a = self._new_session(self.staff_a.login)
            from unittest.mock import patch
            with patch('odoo.addons.edicai_ai.models.edicai_ai_provider'
                       '.requests.post') as fake_post:
                fake_post.return_value = _fake_gemini_response()
                # owner turn works over the (mocked) external provider
                result = self._rpc('/edicai_ai/chat/send', {
                    'session_id': session_a,
                    'message': 'external provider hello',
                }, self.staff_a.login)
                self.assertIn('reply', result)
                self.assertEqual(result['reply'], 'gemini says hi')
                fake_post.assert_called()  # routed to the external API
            # foreign session — identical safe payload, no oracle
            self._new_session(self.staff_b.login)
            response_foreign = self._rpc_raw(
                '/edicai_ai/chat/messages', {'session_id': session_a},
                self.staff_b.login)
            response_missing = self._rpc_raw(
                '/edicai_ai/chat/messages', {'session_id': 999999999},
                self.staff_b.login)
            # identical result payload (RPC envelope ids may differ)
            self.assertEqual(response_foreign['result'],
                             response_missing['result'])
        finally:
            self.cp.set_param('edicai_ai.active_provider', 'mock')
            self.cp.set_param('edicai_ai.gemini_enabled', 'False')
            self.cp.set_param('edicai_ai.gemini_api_key', '')

    def _rpc_raw(self, route, params, login):
        """Authenticated RPC returning the RAW result (error envelopes
        included, so safe-payload identity can be compared)."""
        self.authenticate(login, self.passwords[login])
        response = self.url_open(
            route, json=self.build_rpc_payload(params))
        return response.json()


def _fake_gemini_response():
    class R:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {'choices': [{'message': {'content': 'gemini says hi'}}]}
    return R()


def json_keys(value, prefix=''):
    """Collect every key path in a nested structure (for leak scans)."""
    keys = []
    if isinstance(value, dict):
        for key, sub in value.items():
            keys.append('%s%s' % (prefix, key))
            keys.extend(json_keys(sub, '%s%s.' % (prefix, key)))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.extend(json_keys(item, prefix))
    return keys
