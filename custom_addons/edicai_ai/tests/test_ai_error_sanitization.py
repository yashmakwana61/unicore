"""Phase 0 tests — safe error taxonomy and provider exception
sanitisation.  Proves that neither the provider nor the chat endpoints
can ever surface internals (tracebacks, upstream bodies, credentials,
SQL) to a user."""

from unittest import mock

import odoo.tests
import requests
from odoo.exceptions import (
    AccessError,
    MissingError,
    UserError,
    ValidationError,
)
from odoo.tests.common import TransactionCase

from odoo.addons.edicai_ai.models.ai_error import (
    AUTHORIZATION_DENIED,
    INTERNAL_ERROR,
    LLM_UNAVAILABLE,
    RATE_LIMITED,
    RECORD_NOT_FOUND,
    TIMEOUT,
    VALIDATION_FAILED,
    classify_exception,
    safe_error_payload,
)
from odoo.addons.edicai_ai.models.edicai_ai_provider import EdicaiAIProvider


@odoo.tests.tagged('edicai', 'unit')
class AISafeErrorMappingTest(TransactionCase):
    """Deterministic categories for every failure class."""

    def test_01_timeout_maps_to_timeout(self):
        code, _msg = classify_exception(requests.exceptions.Timeout())
        self.assertEqual(code, TIMEOUT)

    def test_02_connection_maps_to_llm_unavailable(self):
        code, _msg = classify_exception(
            requests.exceptions.ConnectionError('broker down'))
        self.assertEqual(code, LLM_UNAVAILABLE)

    def test_03_http_error_maps_to_llm_unavailable(self):
        resp = requests.models.Response()
        resp.status_code = 503
        err = requests.exceptions.HTTPError('503 server', response=resp)
        code, _msg = classify_exception(err)
        self.assertEqual(code, LLM_UNAVAILABLE)

    def test_04_odoo_authorisation_maps_to_authorization_denied(self):
        code, _msg = classify_exception(
            AccessError('record rule denied record'))
        self.assertEqual(code, AUTHORIZATION_DENIED)

    def test_05_missing_and_validation_map_deterministically(self):
        self.assertEqual(
            classify_exception(MissingError('gone'))[0], RECORD_NOT_FOUND)
        self.assertEqual(
            classify_exception(ValidationError('bad'))[0],
            VALIDATION_FAILED)

    def test_06_provider_configuration_usererror_is_recognised(self):
        code, msg = classify_exception(
            UserError('OpenCode Zen API key is not configured.'))
        self.assertEqual(code, LLM_UNAVAILABLE)
        self.assertIn('administrator', str(msg))

    def test_07_unmapped_exception_maps_to_internal_error(self):
        code, _msg = classify_exception(
            ValueError('SELECT * FROM edicai_student;'))
        self.assertEqual(code, INTERNAL_ERROR)

    def test_08_no_internal_payload_in_safe_message(self):
        secret = 'SUP3R-SECRET-API-KEY-42'
        hostile = [
            requests.exceptions.ConnectionError(secret),
            requests.exceptions.HTTPError(secret, response=None),
            AccessError(secret),
            UserError(secret),
            ValueError('traceback %s /home/odoo/path/file.py' % secret),
        ]
        for exc in hostile:
            _code, msg = classify_exception(exc)
            self.assertNotIn(secret, str(msg))
            self.assertNotIn('/home/', str(msg))

    def test_09_safe_error_payload_shape(self):
        payload = safe_error_payload('UNKNOWN-CATEGORY')
        self.assertEqual(payload['error_code'], INTERNAL_ERROR)
        self.assertTrue(payload['error'])
        self.assertNotEqual(payload['error'], 'UNKNOWN-CATEGORY')

    def test_10_provider_auth_failure_is_actionable(self):
        """A rejected key must read as a configuration problem."""
        code, msg = classify_exception(UserError(
            'The AI provider rejected the request. '
            'Please check the API key and the provider access.'))
        self.assertEqual(code, LLM_UNAVAILABLE)
        self.assertIn('administrator', str(msg))

    def test_11_rate_limit_and_timeout_map_to_dedicated_categories(self):
        code, _msg = classify_exception(UserError(
            'The AI provider is rate limiting this request. '
            'Please wait a moment and try again.'))
        self.assertEqual(code, RATE_LIMITED)
        code, _msg = classify_exception(UserError(
            'The AI service did not respond in time. Please try again.'))
        self.assertEqual(code, TIMEOUT)

    def test_12_provider_unavailable_is_not_an_internal_error(self):
        code, _msg = classify_exception(UserError(
            'The AI service is temporarily unavailable. Please try again '
            'later, or contact your administrator if the problem persists.'))
        self.assertEqual(code, LLM_UNAVAILABLE)


@odoo.tests.tagged('edicai', 'unit')
class AIProviderSanitisationTest(TransactionCase):
    """Provider internals must stop at the provider boundary."""

    def _provider_broken_post(self, side_effect):
        return (
            mock.patch.object(
                EdicaiAIProvider, '_get_api_key',
                lambda self: 'test-key-not-a-secret'),
            mock.patch('requests.post', side_effect=side_effect),
        )

    def test_10_http_error_body_never_reaches_user(self):
        secret = 'SECRET-PAYLOAD-LEAK-77'
        resp = requests.models.Response()
        resp.status_code = 503
        resp._content = (
            b'tenant blocked; account ref SECRET-PAYLOAD-LEAK-77; '
            b'retry later')
        err = requests.exceptions.HTTPError('503 error', response=resp)
        key_fp, post_fp = self._provider_broken_post(err)
        with key_fp:
            with post_fp:
                with self.assertRaises(UserError) as cm:
                    self.env['edicai.ai.provider'].generate_text('ping')
        message = str(cm.exception)
        self.assertNotIn(secret, message)
        self.assertNotIn('503', message)
        self.assertNotIn('tenant', message)
        self.assertIn('unavailable', message)

    def test_11_timeout_message_is_safe(self):
        key_fp, post_fp = self._provider_broken_post(
            requests.exceptions.Timeout())
        with key_fp:
            with post_fp:
                with self.assertRaises(UserError) as cm:
                    self.env['edicai.ai.provider'].chat(
                        [{'role': 'user', 'content': 'hello'}])
        self.assertIn('try again', str(cm.exception).lower())

    def test_12_connection_error_message_is_safe(self):
        key_fp, post_fp = self._provider_broken_post(
            requests.exceptions.ConnectionError(
                'https://api.provider.test/v1 SECRET'))
        with key_fp:
            with post_fp:
                with self.assertRaises(UserError) as cm:
                    self.env['edicai.ai.provider'].rewrite_text('abc')
        message = str(cm.exception)
        self.assertNotIn('SECRET', message)
        self.assertNotIn('api.provider.test', message)
