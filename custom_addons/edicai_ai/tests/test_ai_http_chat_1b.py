"""Phase 1B — HTTP chat regression with LLM-assisted understanding.

Real HTTP turns over ``/edicai_ai/chat/send`` with the 1B flags ON:

* grammar-served grounded turns keep working (no LLM call needed);
* grammar-UNKNOWN turns consult the provider; without a configured key
  the REAL provider-failure path returns the safe UNKNOWN reply (no
  traceback, no provider text);
* LLM composition over a verified tool result is served end-to-end, and
  a fabricated composition falls back to the deterministic template;
* unsupported turns are refused exactly as in Phase 1A.
"""

import odoo.tests
from odoo.tests.common import HttpCase

from odoo.addons.edicai_ai.tests.phase1a_common import Phase1AFixtures
from odoo.addons.edicai_ai.tests.phase1b_common import (
    ScriptedProvider,
    ensure_flags_clean,
    patch_provider,
)

FLAGS = (
    'edicai_ai.orchestrator_enabled',
    'edicai_ai.conversation_llm_enabled',
)

_CHAT = '/edicai_ai/chat/send'


@odoo.tests.tagged('edicai', 'security', 'post_install', '-at_install')
class AIChatHttp1BHarness(HttpCase, Phase1AFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_flags_clean(cls)
        cp = cls.env['ir.config_parameter'].sudo()
        cls._cp = cp
        cls._build_academic_core(suffix='LLHTTP')
        cls.user = cls._create_staff_user(login_suffix='llhttp')
        cls.student, _portal = cls._create_student(
            login_suffix='llhttp', name='Dom', last_name='Grounded')
        cls._create_fee_invoice(cls.student, 12500.0)
        cls.passwords = {cls.user.login: 'staff_pwd_1!'}

    @classmethod
    def tearDownClass(cls):
        ensure_flags_clean(cls)
        super().tearDownClass()

    def _rpc(self, params):
        self.authenticate(self.user.login, self.passwords[self.user.login])
        response = self.url_open(
            _CHAT, json=self.build_rpc_payload(params))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn('error', body)
        return body['result']

    def _turn(self, message, stub=None):
        self._cp.set_param('edicai_ai.orchestrator_enabled', 'True')
        self._cp.set_param('edicai_ai.conversation_llm_enabled', 'True')
        self._cp.set_param('edicai_ai.llm_composition_enabled',
                           'True' if stub is not None else 'False')
        if stub is None:
            return self._rpc({
                'session_id': self._new_session(), 'message': message})
        with patch_provider(stub):
            return self._rpc({
                'session_id': self._new_session(), 'message': message})

    def _new_session(self):
        self.authenticate(self.user.login, self.passwords[self.user.login])
        response = self.url_open(
            '/edicai_ai/chat/new_session', json=self.build_rpc_payload({}))
        self.assertEqual(response.status_code, 200)
        return response.json()['result']['id']

    # ------------------------------------------------------------------
    # Grounded behaviour — with 1B flags fully ON
    # ------------------------------------------------------------------

    def test_01_grounded_reply_keeps_source_and_value(self):
        result = self._turn('fee status of Dom Grounded')
        self.assertEqual(result.get('source'), 'Fee Status')
        self.assertIn('12,500', result.get('reply') or '')
        self.assertNotIn('Traceback', result.get('reply') or '')

    def test_02_unsupported_refusal_unchanged(self):
        result = self._turn('Delete this student')
        self.assertIn("I can't perform that action yet.",
                      result.get('reply') or '')
        self.assertFalse(result.get('source'))

    # ------------------------------------------------------------------
    # Grammar-UNKNOWN turn — REAL provider failure path (no API key)
    # ------------------------------------------------------------------

    def test_03_unknown_turn_fails_safe_without_provider(self):
        result = self._turn('what does the rune stone foretell?')
        self.assertIn("I don't have enough information",
                      result.get('reply') or '')
        self.assertFalse(result.get('source'))
        self.assertNotIn('Traceback', result.get('reply') or '')

    # ------------------------------------------------------------------
    # LLM composition end-to-end (scripted, deterministic)
    # ------------------------------------------------------------------

    def test_04_composed_reply_from_verified_data(self):
        stub = ScriptedProvider(compose=[
            'Dom Grounded has 12,500 USD outstanding.'])
        result = self._turn('fee status of Dom Grounded', stub=stub)
        self.assertEqual(result.get('source'), 'Fee Status')
        self.assertIn('Dom Grounded has 12,500 USD',
                      result.get('reply') or '')
        self.assertEqual(result.get('error_code'), None)

    def test_05_fabricated_composition_falls_back_to_template(self):
        stub = ScriptedProvider(compose=[
            'Dom Grounded owes 15,000 USD.'])
        result = self._turn('fee status of Dom Grounded', stub=stub)
        self.assertEqual(result.get('source'), 'Fee Status')
        self.assertIn('12,500', result.get('reply') or '')
        self.assertNotIn('15,000', result.get('reply') or '')
