import json
import logging
import os
import time

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_API_URL = 'https://opencode.ai/zen/v1/chat/completions'
DEFAULT_MODEL = 'deepseek-v4-0324'
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048

# ---------------------------------------------------------------------
# Multi-provider support (manual-testing lab phase).
#
# The application NEVER contains provider-specific logic: every AI path
# goes through this ONE abstraction.  A "provider" is just a
# configuration profile (base URL + API key + model) fed into the same
# OpenAI-compatible chat-completions call.  Gemini and OpenRouter both
# officially ship OpenAI-compatible endpoints, so they are configured
# as profiles instead of new code paths.
#
# 'compatible'  — the pre-existing OpenCode Zen / OpenAI-compatible
#                 configuration (legacy parameters, unchanged).
# 'gemini'      — Google Gemini via its OpenAI-compatible endpoint.
# 'openrouter'  — OpenRouter (supports the free-model pool).
# 'mock'        — deterministic offline provider for automated tests and
#                 manual QA without keys or network access.
# ---------------------------------------------------------------------

GEMINI_DEFAULT_BASE_URL = \
    'https://generativelanguage.googleapis.com/v1beta/openai/'
OPENROUTER_DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1/'

PROVIDER_KEYS = ('compatible', 'gemini', 'openrouter', 'mock')

PROVIDER_LABELS = {
    'compatible': 'OpenCode Zen (OpenAI-compatible)',
    'gemini': 'Google Gemini',
    'openrouter': 'OpenRouter',
    'mock': 'Mock (deterministic, offline)',
}

PARAM_ACTIVE_PROVIDER = 'edicai_ai.active_provider'

#: Per-provider configuration parameters (storage: ir.config_parameter
#: — never source code, never logs, never audit payloads).
_PROVIDER_PARAMS = {
    'compatible': {
        'key': 'edicai_ai.api_key',
        'url': 'edicai_ai.api_url',
        'model': 'edicai_ai.model',
    },
    'gemini': {
        'key': 'edicai_ai.gemini_api_key',
        'url': 'edicai_ai.gemini_base_url',
        'model': 'edicai_ai.gemini_model',
        'enabled': 'edicai_ai.gemini_enabled',
    },
    'openrouter': {
        'key': 'edicai_ai.openrouter_api_key',
        'url': 'edicai_ai.openrouter_base_url',
        'model': 'edicai_ai.openrouter_model',
        'enabled': 'edicai_ai.openrouter_enabled',
    },
    'mock': {},
}

#: Environment-variable precedence, mirroring the pre-existing
#: EDICAI_AI_API_KEY pattern so deployments can keep secrets out of the
#: database entirely.
_PROVIDER_ENV_VARS = {
    'compatible': 'EDICAI_AI_API_KEY',
    'gemini': 'GEMINI_API_KEY',
    'openrouter': 'OPENROUTER_API_KEY',
}

_DEFAULT_MODELS = {
    'compatible': DEFAULT_MODEL,
    # NO hardcoded model requirement: an empty model simply makes the
    # profile "not configured" (fail-safe), the administrator MUST
    # enter a model id.
    'gemini': '',
    'openrouter': '',
    'mock': 'mock-deterministic',
}

# Static fallback catalog used only when the live provider query fails
# (see ResConfigSettings._model_selection_fallback).  Kept minimal and
# anchored to DEFAULT_MODEL: never hardcode a drifting model list here.
ZEN_STATIC_MODELS = (DEFAULT_MODEL,)

_TRUE_VALUES = ('1', 'true', 'yes', 'on')

# Safe failure category taxonomy for connection tests.  These strings
# are the ONLY things a tester sees when a connection fails: no API
# keys, no authorization headers, no raw provider payloads, no
# stack traces.
CATEGORY_OK = 'OK'
CATEGORY_NOT_CONFIGURED = 'NOT_CONFIGURED'
CATEGORY_AUTH_ERROR = 'AUTH_ERROR'
CATEGORY_TIMEOUT = 'TIMEOUT'
CATEGORY_CONNECTION_ERROR = 'CONNECTION_ERROR'
CATEGORY_MODEL_ERROR = 'MODEL_ERROR'
CATEGORY_RATE_LIMIT = 'RATE_LIMIT'
CATEGORY_PROVIDER_DOWN = 'PROVIDER_DOWN'
CATEGORY_PROVIDER_ERROR = 'PROVIDER_ERROR'
CATEGORY_UNEXPECTED = 'UNEXPECTED'

_CATEGORY_MESSAGES = {
    CATEGORY_NOT_CONFIGURED: (
        'The provider is not fully configured '
        '(missing API key, endpoint URL or model, '
        'or the provider is disabled).'),
    CATEGORY_AUTH_ERROR: (
        'The provider returned an authentication error — '
        'check the configured API key.'),
    CATEGORY_TIMEOUT: ('The provider did not respond in time.'),
    CATEGORY_CONNECTION_ERROR: (
        'Could not connect to the provider — check your network '
        'and the endpoint URL.'),
    CATEGORY_MODEL_ERROR: (
        'The provider could not use the configured model — '
        'check the model identifier.'),
    CATEGORY_RATE_LIMIT: (
        'The provider reported a rate limit or exceeded quota.'),
    CATEGORY_PROVIDER_DOWN: (
        'The provider service reported an error — try again later.'),
    CATEGORY_PROVIDER_ERROR: (
        'The provider rejected the test request.'),
    CATEGORY_UNEXPECTED: (
        'The provider returned an unexpected response.'),
}


def _masked_hint(value):
    """UI-safe hint of a stored key: count + last 4 characters only."""
    if not value:
        return ''
    tail = value[-4:] if len(value) > 4 else '****'
    return '*' * 15 + tail


class EdicaiAIProvider(models.AbstractModel):
    """Utility abstract model that encapsulates all communication with
    the configured AI provider (OpenAI-compatible).

    Any model that needs AI features can call the helper methods
    defined here via ``self.env['edicai.ai.provider']`` — the active
    provider (Gemini / OpenRouter / mock / the legacy compatible one)
    is resolved INSIDE this abstraction, never by callers.
    """
    _name = 'edicai.ai.provider'
    _description = 'Edicai AI Provider'

    # ------------------------------------------------------------------
    # Provider profile resolution (the ONLY provider-specific spot)
    # ------------------------------------------------------------------

    @api.model
    def get_active_provider_key(self):
        """Validated active provider key (defaults to the legacy
        'compatible' configuration — zero behaviour change unless the
        administrator opts into another provider)."""
        cp = self.env['ir.config_parameter'].sudo()
        key = str(cp.get_param(PARAM_ACTIVE_PROVIDER, 'compatible') or '')
        return key if key in PROVIDER_KEYS else 'compatible'

    @api.model
    def _default_base_url(self, provider_key):
        return {
            'compatible': DEFAULT_API_URL,
            'gemini': GEMINI_DEFAULT_BASE_URL,
            'openrouter': OPENROUTER_DEFAULT_BASE_URL,
            'mock': '',
        }.get(provider_key, DEFAULT_API_URL)

    @api.model
    def _provider_enabled(self, provider_key):
        """Whether the provider profile is switched on.

        'compatible' and 'mock' are always usable (no behaviour change
        for legacy deployments / automated tests).  Gemini and
        OpenRouter carry an explicit enable switch (default OFF):
        selecting a disabled profile fails SAFE — it never falls back
        silently to another provider.
        """
        if provider_key in ('compatible', 'mock'):
            return True
        param = (_PROVIDER_PARAMS.get(provider_key, {})
                 .get('enabled'))
        if not param:
            return False
        val = str(self.env['ir.config_parameter'].sudo()
                  .get_param(param, 'False') or '')
        return val.strip().lower() in _TRUE_VALUES

    @api.model
    def _normalize_model_id(self, model, provider_key):
        """Turn a human label into the provider's model identifier.

        Administrators often type the label shown in the UI ("Gemini 2.5
        Flash"); Gemini expects the identifier ("gemini-2.5-flash").  The
        normalisation is conservative: it only applies to Gemini-style
        ids (no ``/``) and never touches a value that already looks like
        an identifier.
        """
        model = (model or '').strip()
        if not model or provider_key != 'gemini':
            return model
        if '/' in model or model == model.lower():
            return model            # already an identifier
        normalized = model.lower().replace(' ', '-')
        if normalized.startswith('gemini-'):
            _logger.info(
                'Edicai AI: normalised the Gemini model label %r to %r.',
                model, normalized)
            return normalized
        return model

    @api.model
    def get_available_models(self, force_refresh=False):
        """Sorted model ids offered in the Settings dropdown.

        This integration has no live model-list endpoint: the catalog is
        each enabled provider's configured model plus its known default
        (``_DEFAULT_MODELS``).  ``force_refresh`` is accepted for
        backward compatibility and simply re-computes.
        Never raises — Settings must always open, even offline.
        """
        ids = set()
        for key in PROVIDER_KEYS:
            try:
                if not self._provider_enabled(key):
                    continue
                profile = self.get_provider_profile(key)
            except Exception:
                _logger.exception(
                    'Edicai AI: could not resolve models for provider %r.',
                    key)
                continue
            if profile.get('model'):
                ids.add(profile['model'])
            default = _DEFAULT_MODELS.get(key)
            if default:
                ids.add(default)
        return sorted(ids)

    @api.model
    def _model_protocol(self, model_id):
        """Display-only protocol tag for a model id (best effort).

        Used by the Settings selection label; carries no behavioural
        weight.
        """
        try:
            return self.get_active_provider_key()
        except Exception:
            return 'compatible'

    @api.model
    def get_provider_profile(self, provider_key=None):
        """Full configuration profile for a provider (or the active
        one).  Includes the API key IN MEMORY ONLY for the current
        call — never logged, never audited, never returned by UI or
        controller endpoints."""
        key = provider_key or self.get_active_provider_key()
        if key not in PROVIDER_KEYS:
            key = 'compatible'
        params = _PROVIDER_PARAMS[key]
        cp = self.env['ir.config_parameter'].sudo()
        base_url = str(cp.get_param(
            params.get('url', ''),
            self._default_base_url(key)) or '').strip()
        model = str(cp.get_param(
            params.get('model', ''), _DEFAULT_MODELS[key]) or '').strip()
        model = self._normalize_model_id(model, key)
        # Environment variable first (same precedence as pre-existing).
        api_key = os.environ.get(_PROVIDER_ENV_VARS.get(key, ''), '')
        if not api_key and params.get('key'):
            api_key = str(cp.get_param(params['key'], '') or '')
        enabled = self._provider_enabled(key)
        available = (
            enabled
            # mock has no endpoint at all; every other profile needs one
            and (key == 'mock' or bool(base_url))
            and bool(model)
            and (key == 'mock' or bool(api_key)))
        return {
            'key': key,
            'label': PROVIDER_LABELS.get(key, key),
            'base_url': base_url,
            'model': model,
            'api_key': api_key,
            'enabled': enabled,
            'available': available,
            'key_hint': _masked_hint(api_key),
        }

    @api.model
    def get_active_provider_display(self):
        """Safe, non-sensitive display information for the chat UI.

        Contains ONLY the provider label, the configured model
        identifier and the availability state — never an API key.
        """
        profile = self.get_provider_profile()
        return {
            'provider': profile['key'],
            'provider_label': profile['label'],
            'model': profile['model'],
            'available': profile['available'],
        }

    @api.model
    def _endpoint_url(self, base_url):
        """Chat-completions endpoint for a provider base URL.

        Accepts either a base URL (``.../v1/``) or a full endpoint;
        Gemini's and OpenRouter's OpenAI-compatible surface is
        ``<base>/chat/completions``.
        """
        base = str(base_url or '').strip()
        if not base:
            return DEFAULT_API_URL
        if base.rstrip('/').endswith('chat/completions'):
            return base
        return base.rstrip('/') + '/chat/completions'

    # ------------------------------------------------------------------
    # Configuration helpers (legacy-compatible surface)
    # ------------------------------------------------------------------

    @api.model
    def _get_api_key(self, provider_key=None):
        """Return the configured API key or raise.

        Delegates to the provider profile.  When the legacy
        'compatible' provider is active the behaviour is EXACTLY as
        before (environment variable first, then ``edicai_ai.api_key``).
        An explicit *provider_key* overrides the active profile (used
        by diagnostics/tests targeting one specific provider).
        """
        profile = self.get_provider_profile(provider_key)
        key = profile['api_key']
        if key:
            return key
        raise UserError(_(
            '%(provider)s API key is not configured. '
            'Please go to Settings → Edicai AI and enter your API key, '
            'or set the %(env)s environment variable.',
            provider=profile['label'],
            env=_PROVIDER_ENV_VARS.get(profile['key'], 'EDICAI_AI_API_KEY'),
        ))

    @api.model
    def _get_api_url(self):
        profile = self.get_provider_profile()
        return profile['base_url'] or self._default_base_url(
            profile['key'])

    @api.model
    def _get_model(self):
        profile = self.get_provider_profile()
        if not profile['model']:
            raise UserError(_(
                'The AI model is not configured for %(provider)s. '
                'Please go to Settings → Edicai AI and enter a model '
                'identifier.', provider=profile['label']))
        return profile['model']

    @api.model
    def _get_temperature(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'edicai_ai.temperature', default=str(DEFAULT_TEMPERATURE),
        )
        try:
            return float(val)
        except (ValueError, TypeError):
            return DEFAULT_TEMPERATURE

    @api.model
    def _get_max_tokens(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'edicai_ai.max_tokens', default=str(DEFAULT_MAX_TOKENS),
        )
        try:
            return int(val)
        except (ValueError, TypeError):
            return DEFAULT_MAX_TOKENS

    # ------------------------------------------------------------------
    # Deterministic mock provider (offline, no network, no keys)
    # ------------------------------------------------------------------

    @api.model
    def _mock_reply(self, messages, profile=None):
        """Deterministic reply for automated tests and manual QA.

        Contains NO dynamic data beyond message COUNTS/SIZES (never
        message content) and is stale-proof: identical input yields an
        identical string.
        """
        profile = profile or self.get_provider_profile('mock')
        user_turns = [
            m for m in (messages or []) if m.get('role') == 'user']
        last_len = len(str(user_turns[-1].get('content', ''))) \
            if user_turns else 0
        return (
            '[Mock AI provider — deterministic, offline.]\n'
            'Provider: Mock · Model: %s\n'
            'Received %d message(s); last user turn is %d characters.\n'
            'No external AI service was contacted; Odoo remains the '
            'source of truth for all ERP answers.'
        ) % (profile.get('model') or 'mock-deterministic',
             len(messages or []), last_len)

    # ------------------------------------------------------------------
    # Core API call
    # ------------------------------------------------------------------

    @api.model
    def _call_api(self, messages, **kwargs):
        """Send a chat-completion request to the ACTIVE provider.

        :param messages: list of dicts ``[{'role': '...', 'content': '...'}]``
        :param kwargs: optional overrides for *model*, *temperature*,
                       *max_tokens*, *provider_key* (explicit profile
                       override, used by tests/diagnostics), or any
                       extra body params.
        :returns: the assistant's reply text
        :raises UserError: on network or API errors (safe taxonomy)
        """
        provider_key = kwargs.pop('provider_key', None)
        profile = self.get_provider_profile(provider_key)
        if profile['key'] == 'mock':
            return self._mock_reply(messages, profile)
        # Fail SAFE on incomplete profile configuration.
        if (not profile['enabled'] or not profile['base_url']
                or not profile['model']):
            raise UserError(_(
                'The AI provider (%(provider)s) is not configured: '
                'enter its API key, endpoint URL and model in '
                'Settings → Edicai AI (and enable the provider), '
                'or switch back to the default provider.',
                provider=profile['label']))
        # The API key is resolved via the legacy helper so overriding
        # packages and deployments keep their hooks (env precedence
        # preserved).  Only pass the explicit override positionally
        # when one was given, so legacy monkeypatches (single-argument)
        # keep working when the ACTIVE provider is used.
        api_key = (self._get_api_key(provider_key) if provider_key
                   else self._get_api_key())
        url = kwargs.pop('url', None) or self._endpoint_url(
            profile['base_url'])
        model = kwargs.pop('model', None) or profile['model']
        temperature = kwargs.pop('temperature', None)
        if temperature is None:
            temperature = self._get_temperature()
        max_tokens = kwargs.pop('max_tokens', None) or self._get_max_tokens()

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        payload.update(kwargs)

        _logger.info(
            'Edicai AI → calling %s  model=%s  messages=%d',
            url, model, len(messages),
        )

        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=120,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise UserError(_(
                'The AI service did not respond in time. Please try again.',
            ))
        except requests.exceptions.ConnectionError:
            raise UserError(_(
                'Could not connect to the AI service. '
                'Please check your network and API URL configuration.',
            ))
        except requests.exceptions.HTTPError as exc:
            # Phase 0 sanitisation: the upstream response body can leak
            # account/credential context (quota notices, request ids,
            # signed payloads).  It stays in the server logs only; the
            # user always gets a fixed safe message.
            body = ''
            status = '?'
            try:
                body = exc.response.text
                status = exc.response.status_code
            except Exception:  # noqa: BLE001 - diagnostic only
                pass
            _logger.error(
                'Edicai AI HTTP error (status=%s): %s — body=%s',
                status, exc, body)
            # The user-facing text is a FIXED safe string; the taxonomy
            # maps it onto an actionable category (auth / rate limit /
            # unavailable) without ever interpolating provider content.
            if status in (401, 403):
                raise UserError(_(
                    'The AI provider rejected the request. '
                    'Please check the API key and the provider access.',
                )) from exc
            if status == 400:
                # Gemini answers 400 for a rejected key ("Please pass a
                # valid API key") and for an unknown model.
                lowered = body.lower()
                if any(phrase in lowered for phrase in (
                        'api key', 'api_key', 'apikey', 'unauthorized',
                        'unauthenticated', 'not authorized', 'permission',
                        'credential')):
                    raise UserError(_(
                        'The AI provider rejected the API key. '
                        'Please check the configured key and its access.',
                    )) from exc
                if 'model' in lowered:
                    raise UserError(_(
                        'The AI provider does not know the configured '
                        'model. Please check the model identifier.',
                    )) from exc
            if status == 429:
                raise UserError(_(
                    'The AI provider is rate limiting this request. '
                    'Please wait a moment and try again.',
                )) from exc
            if status >= 500:
                raise UserError(_(
                    'The AI service is temporarily unavailable. Please try '
                    'again later, or contact your administrator if the '
                    'problem persists.',
                )) from exc
            raise UserError(_(
                'The AI service is temporarily unavailable. Please try '
                'again later, or contact your administrator if the '
                'problem persists.',
            )) from exc

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            raise UserError(_('Unexpected response from the AI service.'))

        # Standard OpenAI-compatible response structure
        try:
            return data['choices'][0]['message']['content']
        except (KeyError, IndexError):
            _logger.error('Edicai AI unexpected payload: %s', data)
            raise UserError(_(
                'The AI service returned an unexpected response structure.',
            ))

    @api.model
    def generate_text(self, prompt):
        """single-prompt completion."""
        system_prompt = (
            'You are Edicai AI, a helpful assistant in an education '
            'management system. Answer queries about academics, fees, '
            'admissions, or administration.')
        return self._call_api([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt},
        ])

    @api.model
    def summarize_text(self, text):
        """Return a concise summary of *text*."""
        system_prompt = (
            'You are a summarisation assistant. '
            'Provide a concise summary of the following text. '
            'Return ONLY the summary, nothing else.'
        )
        return self._call_api([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text},
        ])

    @api.model
    def rewrite_text(self, text, instruction=None):
        """Rewrite *text* according to an optional *instruction*
        (wizard helper; without instruction, polish the text)."""
        system_prompt = (
            'You are a professional writing assistant for an '
            'education management system. Follow the user instruction '
            'and return ONLY the resulting text.'
        )
        if not instruction:
            instruction = (
                'Rewrite this text in a clear, professional way, '
                'keeping its meaning intact.')
        return self._call_api([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',
             'content': 'Instruction: %s\n\nSource text:\n%s'
                        % (instruction, text)},
        ])

    @api.model
    def chat(self, messages):
        """Multi-turn conversation.

        :param messages: full conversation history as list of dicts.
        :returns: assistant reply text
        """
        system_msg = {
            'role': 'system',
            'content': (
                'You are Edicai AI, a helpful and friendly assistant '
                'integrated into the Edicai Education Management System. '
                'Answer questions about academics, administration, '
                'assignments, exams, fees, or any other education-related '
                'topics. Be concise and professional.'
            ),
        }
        full_messages = [system_msg] + messages
        return self._call_api(full_messages)

    # ------------------------------------------------------------------
    # Connection test + model validation (administrator utilities)
    # ------------------------------------------------------------------

    @api.model
    def test_connection(self, provider_key=None, model=None, timeout=20):
        """Minimal SAFE provider request and its result.

        Performs ONE bounded chat-completion request (1 token, 'ping')
        against the provider profile — never more, never against ERP
        data.  The result NEVER contains the API key, authorization
        headers, raw payloads or stack traces; on failure the log keeps
        only the HTTP status.
        """
        started = time.time()
        profile = self.get_provider_profile(provider_key)
        result = {
            'provider': profile['label'],
            'model': model or profile['model'],
            'timestamp': fields.Datetime.now().isoformat(' ', timespec='seconds'),
        }

        def _fail(category, latency=None):
            result.update({
                'ok': False,
                'category': category,
                'message': 'Connection failed: %s'
                           % _CATEGORY_MESSAGES.get(category, 'request failed.'),
                'latency_ms': latency if latency is not None else round(
                    (time.time() - started) * 1000),
            })
            return result

        if profile['key'] == 'mock':
            latency = round((time.time() - started) * 1000)
            result.update({
                'ok': True,
                'category': CATEGORY_OK,
                'message': 'Mock provider is available '
                           '(deterministic, no external network).',
                'latency_ms': latency,
            })
            return result

        if not profile['available']:
            return _fail(CATEGORY_NOT_CONFIGURED)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {profile["api_key"]}',
        }
        payload = {
            'model': result['model'],
            'messages': [{'role': 'user', 'content': 'ping'}],
            'temperature': 0.0,
            'max_tokens': 1,
        }
        try:
            resp = requests.post(
                self._endpoint_url(profile['base_url']),
                headers=headers, json=payload, timeout=timeout,
            )
        except requests.exceptions.Timeout:
            return _fail(CATEGORY_TIMEOUT)
        except requests.exceptions.ConnectionError:
            return _fail(CATEGORY_CONNECTION_ERROR)
        latency = round((time.time() - started) * 1000)

        if resp.status_code in (401, 403):
            _logger.info('AI connection test: authentication error '
                         '(status=%s).', resp.status_code)
            return _fail(CATEGORY_AUTH_ERROR, latency)
        if resp.status_code == 404:
            _logger.info('AI connection test: model/endpoint not found '
                         '(status=404).')
            return _fail(CATEGORY_MODEL_ERROR, latency)
        if resp.status_code == 429:
            _logger.info('AI connection test: rate limit/quota '
                         '(status=429).')
            return _fail(CATEGORY_RATE_LIMIT, latency)
        if resp.status_code >= 500:
            _logger.info('AI connection test: provider down '
                         '(status=%s).', resp.status_code)
            return _fail(CATEGORY_PROVIDER_DOWN, latency)
        if resp.status_code != 200:
            # Some providers answer 400 for a rejected key (Gemini:
            # "Please pass a valid API key").  The body stays in the
            # server log; the tester only gets the matching safe
            # category, so the message stays actionable.
            body = ''
            try:
                body = resp.text[:400]
            except Exception:  # noqa: BLE001 - diagnostic only
                pass
            _logger.info('AI connection test: provider error '
                         '(status=%s) — body=%s', resp.status_code, body)
            lowered = body.lower()
            if any(phrase in lowered for phrase in (
                    'api key', 'api_key', 'apikey', 'unauthorized',
                    'unauthenticated', 'not authorized', 'permission',
                    'credential')):
                return _fail(CATEGORY_AUTH_ERROR, latency)
            if 'model' in lowered:
                return _fail(CATEGORY_MODEL_ERROR, latency)
            return _fail(CATEGORY_PROVIDER_ERROR, latency)

        try:
            data = resp.json()
            data['choices'][0]['message']
        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
            return _fail(CATEGORY_UNEXPECTED, latency)
        result.update({
            'ok': True,
            'category': CATEGORY_OK,
            'message': 'Connection successful.',
            'latency_ms': latency,
        })
        return result

    @api.model
    def validate_model(self, provider_key=None, model=None, timeout=20):
        """Verify the configured (or explicitly given) model id can
        actually be reached — VALID / INVALID with a safe reason.

        Uses the same minimal 1-token completion as ``test_connection``
        (uniform — no dependency on provider-specific listing APIs).
        """
        started = time.time()
        key = provider_key or self.get_active_provider_key()
        profile = self.get_provider_profile(key)
        target = str(model or profile['model'] or '').strip()
        if not target:
            return {
                'valid': False,
                'provider': profile['label'],
                'model': '',
                'message': 'Connection failed: no model identifier is '
                           'configured — enter a model first.',
                'latency_ms': round((time.time() - started) * 1000),
            }
        result = self.test_connection(key, model=target, timeout=timeout)
        latency_base = result.pop('latency_ms', 0)
        valid = bool(result.get('ok'))
        return {
            'valid': valid,
            'provider': result.get('provider', profile['label']),
            'model': target,
            'category': result.get('category'),
            'message': 'VALID — %s is reachable on %s.'
                       % (target, result.get('provider', ''))
                       if valid else 'INVALID — %s' % (
                           _CATEGORY_MESSAGES.get(
                               result.get('category'),
                               'the model could not be used.')),
            'latency_ms': latency_base,
        }
