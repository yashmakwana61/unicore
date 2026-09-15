import json
import logging
import time
from urllib.parse import urlparse

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_API_URL = 'https://opencode.ai/zen/v1/chat/completions'
DEFAULT_MODELS_URL = 'https://opencode.ai/zen/v1/models'
DEFAULT_MODEL = 'deepseek-v4-flash'
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048
DEFAULT_SYSTEM_PROMPT = (
    'You are Oacis AI, a helpful and friendly assistant '
    'integrated into the Oacis Education Management System. '
    'Answer questions about academics, administration, '
    'assignments, exams, fees, or any other education-related '
    'topics. Be concise and professional.'
)

# Static fallback used when the live Zen model list cannot be reached
# (offline server, custom endpoint, …). Refreshed from
# https://opencode.ai/zen/v1/models — the Settings "Refresh Models"
# button updates the cached live list.
ZEN_STATIC_MODELS = [
    'big-pickle',
    'claude-fable-5',
    'claude-fable-5-1',
    'claude-haiku-4-5',
    'claude-opus-4-5',
    'claude-opus-4-6',
    'claude-opus-4-7',
    'claude-opus-4-8',
    'claude-opus-5',
    'claude-sonnet-4',
    'claude-sonnet-4-5',
    'claude-sonnet-4-6',
    'claude-sonnet-5',
    'deepseek-v4-flash',
    'deepseek-v4-flash-free',
    'deepseek-v4-flash-vision-exp',
    'deepseek-v4-pro',
    'gemini-3-flash',
    'gemini-3.1-pro',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite',
    'gemini-3.6-flash',
    'gemini-3.7-flash',
    'gemini-3.8-flash',
    'glm-5',
    'glm-5.1',
    'glm-5.2',
    'glm-5.3',
    'glm-5.3-flash',
    'gpt-5',
    'gpt-5-codex',
    'gpt-5-nano',
    'gpt-5.1',
    'gpt-5.1-codex',
    'gpt-5.1-codex-max',
    'gpt-5.1-codex-mini',
    'gpt-5.2',
    'gpt-5.2-codex',
    'gpt-5.3-codex',
    'gpt-5.3-codex-spark',
    'gpt-5.4',
    'gpt-5.4-mini',
    'gpt-5.4-nano',
    'gpt-5.4-pro',
    'gpt-5.5',
    'gpt-5.5-pro',
    'gpt-5.6-luna',
    'gpt-5.6-sol',
    'gpt-5.6-terra',
    'gpt-6-astra',
    'grok-4.5',
    'grok-4.6',
    'grok-build-0.1',
    'kimi-k2.5',
    'kimi-k2.6',
    'kimi-k2.7-code',
    'kimi-k3',
    'ling-3.0-flash-fin-free',
    'mimo-v2.5-free',
    'minimax-m2.5',
    'minimax-m2.7',
    'minimax-m3',
    'muse-spark-1.2',
    'muse-spark-1.2-contributor-free',
    'muse-spark-1.3',
    'muse-spark-1.3-contributor-free',
    'nemotron-3-ultra-free',
    'nemotron-3.5-lightning-free',
    'qwen3.5-plus',
    'qwen3.6-plus',
]

# How long (seconds) a fetched model list is reused without re-calling
# the API. Keeps opening Settings fast.
ZEN_MODEL_CACHE_TTL = 86400

# Whitelisted models for record-aware grounding + safe display fields.
# Keeps AI from dumping arbitrary tables / sensitive fields.
GROUNDED_MODELS = {
    'oacis.student': ['name', 'email', 'phone', 'state', 'course_id'],
    'oacis.admission': ['name', 'applicant_name', 'state', 'course_id'],
    'oacis.enrollment': ['name', 'state', 'course_id', 'student_id'],
    'oacis.assignment': ['name', 'state', 'due_date', 'course_id'],
    'oacis.exam': ['name', 'state', 'exam_date'],
}


class OacisAIProvider(models.AbstractModel):
    """Utility abstract model that encapsulates all communication with the
    OpenCode Zen (OpenAI-compatible) API.  Any model that needs AI features
    can call the helper methods defined here via ``self.env['oacis.ai.provider']``.
    """
    _name = 'oacis.ai.provider'
    _description = 'Oacis AI Provider'

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @api.model
    def _get_api_key(self):
        """Return the configured API key or raise.

        Precedence: ``OACIS_AI_API_KEY`` environment variable first,
        so production deployments can avoid storing the secret in
        the database at all.
        """
        import os
        key = os.environ.get('OACIS_AI_API_KEY', '')
        if not key:
            key = self.env['ir.config_parameter'].sudo().get_param(
                'oacis_ai.api_key', default='',
            )
        if not key:
            raise UserError(_(
                'OpenCode Zen API key is not configured. '
                'Please go to Settings → Oacis AI and enter your API key, '
                'or set the OACIS_AI_API_KEY environment variable.',
            ))
        return key

    @api.model
    def _get_api_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.api_url', default=DEFAULT_API_URL,
        )

    @api.model
    def _get_model(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.model', default=DEFAULT_MODEL,
        )

    @api.model
    def _get_system_prompt(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.system_prompt', default=DEFAULT_SYSTEM_PROMPT,
        ) or DEFAULT_SYSTEM_PROMPT

    @api.model
    def _get_temperature(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.temperature', default=str(DEFAULT_TEMPERATURE),
        )
        try:
            temp = float(val)
        except (ValueError, TypeError):
            return DEFAULT_TEMPERATURE
        return max(0.0, min(2.0, temp))

    @api.model
    def _get_max_tokens(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.max_tokens', default=str(DEFAULT_MAX_TOKENS),
        )
        try:
            tokens = int(val)
        except (ValueError, TypeError):
            return DEFAULT_MAX_TOKENS
        return max(128, min(32000, tokens))

    @api.model
    def _get_rate_limit(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'oacis_ai.rate_limit_per_hour', default='60',
        )
        try:
            return max(0, int(val))
        except (ValueError, TypeError):
            return 60

    # ------------------------------------------------------------------
    # Available-model list (Settings dropdown)
    # ------------------------------------------------------------------

    @api.model
    def _get_models_url(self):
        """Derive the ``/models`` list URL from the configured API URL.

        Handles chat/completions, responses, messages and per-model
        (``…/models/<id>``) style endpoints. Falls back to the
        public Zen default.
        """
        api_url = (self._get_api_url() or '').strip().rstrip('/')
        if not api_url:
            return DEFAULT_MODELS_URL
        if '/models' in api_url:
            return api_url[:api_url.index('/models') + len('/models')]
        for suffix in ('/chat/completions', '/responses', '/messages'):
            if api_url.endswith(suffix):
                return api_url[:-len(suffix)] + '/models'
        return DEFAULT_MODELS_URL

    @api.model
    def _fetch_live_models(self):
        """GET the model list from the endpoint. Never raises; [] on failure.

        The Zen ``/models`` endpoint is public (no API key needed) and
        OpenAI-compatible: ``{"data": [{"id": …}]}``.
        """
        try:
            resp = requests.get(self._get_models_url(), timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            _logger.warning('Oacis AI: could not fetch Zen model list', exc_info=True)
            return []
        items = data.get('data', []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        ids = sorted({
            str(item.get('id')).strip()
            for item in items
            if isinstance(item, dict) and item.get('id')
        })
        return ids

    @api.model
    def _get_cached_models(self, allow_stale=True):
        """Return the cached model list, or [] when missing/expired."""
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param('oacis_ai.model_list', default='')
        if not raw:
            return []
        if not allow_stale:
            try:
                age = time.time() - int(icp.get_param('oacis_ai.model_list_ts', default='0'))
            except (ValueError, TypeError):
                return []
            if age > ZEN_MODEL_CACHE_TTL:
                return []
        try:
            ids = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
        return [str(mid) for mid in ids if mid] if isinstance(ids, list) else []

    @api.model
    def get_available_models(self, force_refresh=False):
        """Sorted Zen model ids for the Settings dropdown.

        Order: live API → fresh cache → stale cache → static fallback.
        Never raises.
        """
        icp = self.env['ir.config_parameter'].sudo()
        if not force_refresh:
            cached = self._get_cached_models(allow_stale=False)
            if cached:
                return cached
        live = self._fetch_live_models()
        if live:
            icp.set_param('oacis_ai.model_list', json.dumps(live))
            icp.set_param('oacis_ai.model_list_ts', str(int(time.time())))
            return live
        cached = self._get_cached_models(allow_stale=True)
        if cached:
            return cached
        return list(ZEN_STATIC_MODELS)

    # ------------------------------------------------------------------
    # Governance: rate limit + usage log
    # ------------------------------------------------------------------

    @api.model
    def _check_rate_limit(self):
        limit = self._get_rate_limit()
        if not limit:
            return
        one_hour_ago = time.strftime(
            '%Y-%m-%d %H:%M:%S',
            time.gmtime(time.time() - 3600),
        )
        count = self.env['oacis.ai.usage.log'].sudo().search_count([
            ('user_id', '=', self.env.user.id),
            ('create_date', '>=', one_hour_ago),
        ])
        if count >= limit:
            raise UserError(_(
                'AI usage limit reached (%(limit)s requests/hour). '
                'Please try again later or contact your administrator.',
                limit=limit,
            ))

    @api.model
    def _log_usage(self, feature, model, tokens_estimate,
                   latency_ms, success=True, error_message=''):
        try:
            self.env['oacis.ai.usage.log'].sudo().create({
                'user_id': self.env.user.id,
                'model_used': model,
                'feature': feature,
                'tokens_estimate': tokens_estimate,
                'latency_ms': latency_ms,
                'success': success,
                'error_message': error_message[:500] if error_message else '',
            })
        except Exception:
            _logger.exception('Oacis AI: failed to write usage log')

    @api.model
    def test_connection(self):
        """Called from Settings 'Test Connection' button."""
        try:
            reply = self.generate_text('Reply with exactly: OK', feature='test')
        except UserError:
            raise
        except Exception as exc:
            raise UserError(_('Connection test failed: %s') % exc)
        if not reply or not reply.strip():
            raise UserError(_('Connection test failed: empty response.'))
        return True

    # ------------------------------------------------------------------
    # Record-aware grounding (permission-safe)
    # ------------------------------------------------------------------

    @api.model
    def build_record_context(self, res_model, res_id, max_chars=1500):
        """Build a small, safe text summary of an Odoo record for grounding.

        Respects access rights: returns '' when the user cannot read the
        record or when the model is not whitelisted.
        """
        if not res_model or not res_id:
            return ''
        if res_model not in GROUNDED_MODELS:
            return ''
        try:
            res_id = int(res_id)
        except (ValueError, TypeError):
            return ''
        Model = self.env.get(res_model)
        if Model is None:
            return ''
        try:
            Model.check_access_rights('read', raise_exception=True)
        except Exception:
            return ''
        record = Model.browse(res_id)
        if not record.exists():
            return ''
        try:
            record.check_access_rule('read')
        except Exception:
            return ''
        fields_to_show = GROUNDED_MODELS[res_model]
        try:
            Model.check_field_access_rights('read', fields_to_show)
        except Exception:
            fields_to_show = ['name'] if 'name' in record._fields else []
        parts = [f'{res_model} (id={res_id}):']
        for fname in fields_to_show:
            if fname not in record._fields:
                continue
            try:
                val = record[fname]
                if hasattr(val, 'display_name'):
                    if not val:
                        continue
                    val = ', '.join(val.mapped('display_name'))[:300]
                else:
                    val = str(val)[:300]
            except Exception:
                continue
            parts.append(f'- {fname}: {val}')
        ctx = '\n'.join(parts)[:max_chars]
        return ctx

    # ------------------------------------------------------------------
    # Endpoint routing (https://opencode.ai/docs/zen "Endpoints" table).
    # Each Zen model family is served on its own endpoint/protocol:
    #   chat      → POST …/chat/completions      (OpenAI chat format)
    #   responses → POST …/responses             (OpenAI Responses API)
    #   messages  → POST …/messages              (Anthropic Messages API)
    #   gemini    → POST …/models/<id>           (Gemini generateContent)
    # Custom (non-Zen) URLs always use the OpenAI chat format.
    # ------------------------------------------------------------------

    @api.model
    def _model_protocol(self, model):
        """Return the Zen protocol for *model* ('chat' default)."""
        mid = (model or '').strip().lower()
        if mid.startswith(('gpt-', 'grok-', 'muse-spark-')):
            return 'responses'
        if mid.startswith(('claude-', 'qwen')):
            return 'messages'
        if mid.startswith('gemini-'):
            return 'gemini'
        return 'chat'

    @api.model
    def _resolve_api_url(self, model, override_url=None):
        """Return ``(url, protocol)`` for *model*.

        An explicit *override_url* (or any custom non-Zen URL) is used
        as-is with the OpenAI chat protocol. Zen URLs are re-routed to
        the endpoint serving *model*.
        """
        if override_url:
            return override_url.strip().rstrip('/'), 'chat'
        configured = (self._get_api_url() or '').strip().rstrip('/')
        try:
            parts = urlparse(configured)
        except Exception:
            parts = None
        is_zen = bool(
            parts and parts.hostname == 'opencode.ai'
            and (parts.path or '').startswith('/zen')
        )
        if not configured or not is_zen:
            return configured or DEFAULT_API_URL, 'chat'
        protocol = self._model_protocol(model)
        base = '%s://%s/zen/v1' % (parts.scheme or 'https', parts.hostname)
        if protocol == 'responses':
            return base + '/responses', protocol
        if protocol == 'messages':
            return base + '/messages', protocol
        if protocol == 'gemini':
            return '%s/models/%s' % (base, (model or '').strip()), protocol
        return base + '/chat/completions', protocol

    @staticmethod
    def _split_system(messages):
        """Split OpenAI-style *messages* into (system_text, turns)."""
        system_parts = []
        turns = []
        for msg in messages or []:
            role = msg.get('role')
            content = msg.get('content') or ''
            if role == 'system':
                if content:
                    system_parts.append(content)
            elif content:
                turns.append({'role': role, 'content': content})
        return '\n\n'.join(system_parts), turns

    @api.model
    def _build_request_body(self, protocol, messages, model, temperature, max_tokens, extra):
        """Build the HTTP body for *protocol* from chat-style *messages*."""
        system_text, turns = self._split_system(messages)
        if protocol == 'responses':
            body = {
                'model': model,
                'input': turns,
                'temperature': max(0.0, min(2.0, float(temperature or 0.0))),
                'max_output_tokens': max_tokens,
            }
            if system_text:
                body['instructions'] = system_text
            body.update(extra or {})
            return body
        if protocol == 'messages':
            body = {
                'model': model,
                'max_tokens': max_tokens,
                'messages': [
                    {'role': t['role'] if t['role'] in ('user', 'assistant') else 'user',
                     'content': t['content']}
                    for t in turns
                ],
                'temperature': max(0.0, min(1.0, float(temperature or 0.0))),
            }
            if system_text:
                body['system'] = system_text
            body.update(extra or {})
            return body
        if protocol == 'gemini':
            contents = [
                {'role': 'model' if t['role'] == 'assistant' else 'user',
                 'parts': [{'text': t['content']}]}
                for t in turns
            ]
            body = {
                'contents': contents,
                'generationConfig': {
                    'temperature': max(0.0, min(2.0, float(temperature or 0.0))),
                    'maxOutputTokens': max_tokens,
                },
            }
            if system_text:
                body['system_instruction'] = {'parts': [{'text': system_text}]}
            body.update(extra or {})
            return body
        # 'chat' — OpenAI chat-completions format (also used for custom URLs).
        body = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }
        body.update(extra or {})
        return body

    @api.model
    def _parse_reply(self, protocol, data, model, url):
        """Extract the assistant text from a *protocol* response payload."""
        def _fail(reason):
            _logger.error('Oacis AI unexpected %s payload: %s', protocol, data)
            raise UserError(_(
                'The AI service returned an unexpected response structure '
                '(%(reason)s, model %(model)s).',
                reason=reason, model=model,
            ))

        try:
            if protocol == 'responses':
                if isinstance(data.get('output_text'), str) and data['output_text']:
                    return data['output_text']
                texts = [
                    part.get('text')
                    for item in data.get('output') or []
                    if isinstance(item, dict)
                    for part in (item.get('content') or [])
                    if isinstance(part, dict) and part.get('text')
                ]
                if texts:
                    return ''.join(texts)
                return _fail('no output text')
            if protocol == 'messages':
                content = data.get('content') or []
                if isinstance(content, str):
                    return content
                texts = [
                    block.get('text')
                    for block in content
                    if isinstance(block, dict) and block.get('text')
                ]
                if texts:
                    return ''.join(texts)
                return _fail('no content text')
            if protocol == 'gemini':
                feedback = (data.get('promptFeedback') or {})
                if feedback.get('blockReason'):
                    return _fail('blocked: %s' % feedback['blockReason'])
                candidates = data.get('candidates') or []
                texts = [
                    part.get('text')
                    for cand in candidates
                    if isinstance(cand, dict)
                    for part in ((cand.get('content') or {}).get('parts') or [])
                    if isinstance(part, dict) and part.get('text')
                ]
                if texts:
                    return ''.join(texts)
                return _fail('no candidates')
            # 'chat'
            return data['choices'][0]['message']['content']
        except UserError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError):
            return _fail('unparseable')

    # ------------------------------------------------------------------
    # Core API call
    # ------------------------------------------------------------------

    @api.model
    def _call_api(self, messages, feature='general', **kwargs):
        """Send a request to the OpenCode Zen API.

        The endpoint and wire format are chosen automatically per model
        (see ``_resolve_api_url``); custom non-Zen URLs always use the
        OpenAI chat-completions format.

        :param messages: list of dicts ``[{'role': '...', 'content': '...'}]``
        :param feature: short label stored in the usage log
        :param kwargs: optional overrides for *url*, *model*, *temperature*,
                       *max_tokens*, or any extra body params.
        :returns: the assistant's reply text
        :raises UserError: on network or API errors
        """
        self._check_rate_limit()
        api_key = self._get_api_key()
        model = kwargs.pop('model', None) or self._get_model()
        url, protocol = self._resolve_api_url(model, kwargs.pop('url', None))
        temperature = kwargs.pop('temperature', None)
        if temperature is None:
            temperature = self._get_temperature()
        max_tokens = kwargs.pop('max_tokens', None) or self._get_max_tokens()

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        if protocol == 'messages':
            # Zen gateway accepts Bearer; native Anthropic headers as fallback.
            headers['x-api-key'] = api_key
            headers['anthropic-version'] = '2023-06-01'
        payload = self._build_request_body(
            protocol, messages, model, temperature, max_tokens, kwargs,
        )

        _logger.info(
            'Oacis AI → calling %s  model=%s  protocol=%s  messages=%d  feature=%s',
            url, model, protocol, len(messages), feature,
        )

        start = time.time()
        tokens_est = sum(len((m.get('content') or '')) for m in messages) // 4
        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=120,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            self._log_usage(feature, model, tokens_est,
                            int((time.time() - start) * 1000),
                            success=False, error_message='Timeout')
            raise UserError(_(
                'The AI service did not respond in time '
                '(model %(model)s). Please try again.',
                model=model,
            ))
        except requests.exceptions.ConnectionError:
            self._log_usage(feature, model, tokens_est,
                            int((time.time() - start) * 1000),
                            success=False, error_message='Connection error')
            raise UserError(_(
                'Could not connect to the AI service at %(url)s. '
                'Please check your network and API URL configuration.',
                url=url,
            ))
        except requests.exceptions.HTTPError as exc:
            body = ''
            try:
                body = exc.response.text
            except Exception:
                pass
            _logger.error('Oacis AI HTTP error: %s — %s', exc, body)
            self._log_usage(feature, model, tokens_est,
                            int((time.time() - start) * 1000),
                            success=False, error_message=body[:200])
            raise UserError(_(
                'AI service returned an error (%(status)s) for model '
                '%(model)s on %(url)s. Details: %(body)s',
                status=exc.response.status_code,
                model=model,
                url=url,
                body=body[:500],
            ))

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            self._log_usage(feature, model, tokens_est,
                            int((time.time() - start) * 1000),
                            success=False, error_message='Bad JSON')
            raise UserError(_(
                'Unexpected response from the AI service '
                '(model %(model)s).', model=model,
            ))

        reply = self._parse_reply(protocol, data, model, url)
        self._log_usage(
            feature, model, tokens_est + len(reply or '') // 4,
            int((time.time() - start) * 1000), success=True,
        )
        return reply

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    @api.model
    def generate_text(self, prompt, system_prompt=None, feature='generate'):
        """Simple one-shot text generation.

        :param prompt: the user prompt
        :param system_prompt: optional system-level instruction
        :returns: generated text string
        """
        messages = []
        messages.append({
            'role': 'system',
            'content': system_prompt or self._get_system_prompt(),
        })
        messages.append({'role': 'user', 'content': prompt})
        return self._call_api(messages, feature=feature)

    @api.model
    def rewrite_text(self, text, instruction='Improve this text'):
        """Rewrite *text* according to *instruction*."""
        system_prompt = (
            'You are a professional writing assistant. '
            'Follow the user\'s instruction to rewrite the given text. '
            'Return ONLY the rewritten text, nothing else.'
        )
        user_prompt = f'Instruction: {instruction}\n\nText:\n{text}'
        return self._call_api([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ], feature='rewrite')

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
        ], feature='summarize')

    # --- Education-specific helpers ---

    @api.model
    def generate_quiz(self, topic, num_questions=5, level='medium'):
        prompt = (
            f'Create {num_questions} {level}-level quiz questions about '
            f'"{topic}". Number each question, give 4 options (A-D) where '
            f'applicable, and provide an answer key at the end.'
        )
        return self.generate_text(
            prompt,
            system_prompt=(
                'You are an expert teacher creating fair, curriculum-aligned '
                'quiz questions. Keep language clear and age-appropriate.'
            ),
            feature='quiz',
        )

    @api.model
    def draft_notice(self, topic):
        return self.generate_text(
            f'Write a short, professional institutional notice about: {topic}\n'
            'Include a title, body (3-5 lines), and a polite closing line.',
            system_prompt=(
                'You are an school administrator drafting clear, formal '
                'notices for students, parents and staff.'
            ),
            feature='notice',
        )

    @api.model
    def summarize_record(self, res_model, res_id):
        ctx = self.build_record_context(res_model, res_id)
        if not ctx:
            raise UserError(_(
                'This record cannot be summarized (no access or unsupported type).',
            ))
        return self.generate_text(
            f'Summarize the following institutional record in 4-6 bullet points '
            f'for a staff member:\n\n{ctx}',
            system_prompt=(
                'You are a helpful school administrator. Summarize only the '
                'facts given; do not invent details.'
            ),
            feature='record_summary',
        )

    @api.model
    def chat(self, messages, res_model=None, res_id=None):
        """Multi-turn conversation, optionally grounded in an Odoo record.

        :param messages: full conversation history as list of dicts.
        :returns: assistant reply text
        """
        system_content = self._get_system_prompt()
        if res_model and res_id:
            ctx = self.build_record_context(res_model, res_id)
            if ctx:
                system_content += (
                    '\n\nRelevant institutional record (already verified '
                    'readable by this user; do not invent other data):\n' + ctx
                )
        full_messages = [{'role': 'system', 'content': system_content}] + messages
        return self._call_api(full_messages, feature='chatbot')
