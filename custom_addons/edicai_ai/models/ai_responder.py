"""Phase 1B — LLM response composition over VERIFIED tool results.

The Phase 1A deterministic composer stays the safety layer; this module
may only add natural-language fluency ON TOP of authoritative data:

    TOOL RESULT (authoritative Odoo data)
      ↓
    GROUNDING OBJECT (bounded, sanitized facts + source label)
      ↓
    provider call (existing Phase 0 abstraction)
      ↓
    LLM NATURAL REPLY
      ↓
    DETERMINISTIC GROUNDING VALIDATION (fail-closed)
      ↓
    presented reply  OR  the fixed Phase 1A template

Composer contract: it receives the bounded grounding object and never
an ORM environment, model references, credentials, registry internals
or secrets.

Fabrication defense: every numeric token of an LLM-composed reply must
be traceable to the grounding facts; otherwise the reply is DISCARDED
and the fixed Phase 1A template is used.  Unsupported claims (exam
eligibility, bar risk…) either carry numbers (checked) or are dropped
by the facts-only system policy; the deterministic validator is the
last gate.
"""

import json
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

MAX_FACTS_CHARS = 4000
MAX_REPLY_CHARS = 2000

SYSTEM_COMPOSER_PROMPT = """You write a chat reply for the EDICAI ERP read-only assistant.

You receive VERIFIED DATA (facts returned by an authorized ERP tool) and the user's request. Rules:
- Compose the answer ONLY from the VERIFIED DATA. Never invent any number, name, date, currency, status or conclusion.
- Copy every number and name EXACTLY as the data gives it.
- If the data is empty or does not contain what the user wants, say plainly that the information is not available — do not guess.
- Do not add advice, policy interpretation, warnings or predictions that are not literally present in the data.
- Keep it short, professional and natural (at most about 120 words). Plain text only, no markdown headings.
- Return ONLY the reply text."""

_NUMBER_TOKEN = re.compile(r'(?<![\w.])(\d[\d,.]*)(?![\w])')


class EdicaiAILLMResponder(models.AbstractModel):
    """Grounded LLM response composer + deterministic validator."""

    _name = 'edicai.ai.llm.responder'
    _description = 'AI LLM Grounded Response Composer (validated)'

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    @api.model
    def compose(self, request_text, intent, data, source_label):
        """Compose a natural reply from verified tool-result data.

        :returns: ``{'status': 'ok', 'text': <reply>}`` or
            ``{'status': 'fallback'}`` (the caller then uses the fixed
            Phase 1A template — safe on every failure mode).
        Never raises.
        """
        facts = self._grounding_object(intent, data, source_label)
        messages = self._build_messages(request_text, facts)
        try:
            raw = self.env['edicai.ai.provider']._call_api(
                messages, temperature=0.3, max_tokens=400)
        except Exception as exc:  # noqa: BLE001 — classified, not leaked
            _logger.info('AI responder: provider call failed (%s).',
                         type(exc).__name__)
            return {'status': 'fallback', 'reason_code': 'LLM_UNAVAILABLE'}

        text = self._extract_reply(raw)
        if not text:
            return {'status': 'fallback', 'reason_code': 'EMPTY'}
        violation = self._grounding_violation(text, facts)
        if violation:
            _logger.info(
                'AI responder: grounding validation failed (%s); '
                'falling back to the deterministic template.', violation)
            return {'status': 'fallback', 'reason_code': violation}
        return {'status': 'ok', 'text': text}

    # ------------------------------------------------------------------
    # Grounding object (facts + safe meta, bounded)
    # ------------------------------------------------------------------

    @api.model
    def _grounding_object(self, intent, data, source_label):
        """Serialize the authoritative tool result to bounded facts —
        no ORM env, no registry internals, no secrets: only the
        already-safe ``data`` payload the deterministic composer uses.
        Never raises (unsanitized data degrades to minimal facts)."""
        try:
            payload = {
                'intent': intent,
                'source_label': source_label or '',
                'data': data if isinstance(data, dict) else {},
            }
            facts = json.dumps(payload, ensure_ascii=True, default=str)
            if len(facts) > MAX_FACTS_CHARS:
                for key, value in list(payload['data'].items()):
                    if isinstance(value, list) and len(value) > 2:
                        payload['data'][key] = value[:2]
                    elif isinstance(value, str) and len(value) > 200:
                        payload['data'][key] = value[:200]
                facts = (json.dumps(payload, ensure_ascii=True, default=str)
                         [:MAX_FACTS_CHARS])
            return facts
        except Exception:  # noqa: BLE001 — fail-safe: minimal facts
            _logger.info('AI responder: facts serialization degraded.')
            return json.dumps({
                'intent': str(intent or ''),
                'source_label': str(source_label or ''),
                'data': {},
            }, ensure_ascii=True)

    @api.model
    def _build_messages(self, request_text, facts):
        user_content = (
            'VERIFIED DATA (authoritative, from the ERP tool):\n'
            '%s\n\nUSER REQUEST:\n"""\n%s\n"""' % (
                facts, str(request_text or '')[:2000]))
        return [
            {'role': 'system', 'content': SYSTEM_COMPOSER_PROMPT},
            {'role': 'user', 'content': user_content},
        ]

    # ------------------------------------------------------------------
    # Reply extraction
    # ------------------------------------------------------------------

    @api.model
    def _extract_reply(self, raw):
        if not raw or not isinstance(raw, str):
            return ''
        text = raw.strip()
        # Strip markdown code fences the model may add.
        fence = re.match(r'^```[a-z]*\n(.*?)\n?```$', text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        text = text[:MAX_REPLY_CHARS].strip()
        return text or ''

    # ------------------------------------------------------------------
    # Deterministic grounding validation (fail-closed)
    # ------------------------------------------------------------------

    @api.model
    def _grounding_violation(self, text, facts):
        """Return a reason string when ``text`` contains a number that
        the verified facts cannot sanction, else ``False``.

        Models often enumerate reply lines ('1. ', '2) ') — leading
        enumeration numbers are tolerated; every other numeric token is
        treated as a factual claim and must be traceable to the facts.
        """
        sanctioned = self._sanctioned_numbers(facts)
        for line in text.splitlines():
            # De-enumerate list items the model may write ('1. ...').
            line = re.sub(r'^\s*\d{1,2}[.)]\s+', '', line)
            for raw_match in _NUMBER_TOKEN.finditer(line):
                token = raw_match.group(1)
                normalized = token.replace(' ', '')
                if normalized in sanctioned:
                    continue
                try:
                    if float(normalized.replace(',', '')) in sanctioned:
                        continue
                except (TypeError, ValueError):
                    pass
                return 'FABRICATION:CANDIDATE:%s' % normalized
        return False

    @api.model
    def _sanctioned_numbers(self, facts):
        """Every number that appears anywhere in the verified facts,
        in its common renderings."""
        sanctioned = set()
        try:
            for match in re.finditer(r'\d[\d.]*', facts):
                try:
                    value = float(match.group(0))
                except (TypeError, ValueError):
                    continue
                sanctioned.add(value)
            for value in list(sanctioned):
                renderings = (
                    str(value), '%g' % value,
                    '{:,.0f}'.format(value),
                    '{:,.1f}'.format(value),
                    '{:,.2f}'.format(value),
                    str(int(value)) if value == int(value) else None)
                for rendering in renderings:
                    if rendering is not None:
                        sanctioned.add(rendering)
        except Exception:  # noqa: BLE001 — safety net only
            pass
        return sanctioned
