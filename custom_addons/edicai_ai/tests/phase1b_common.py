"""Shared Phase 1B test infrastructure.

Flags + a fully scripted (deterministic) provider stand-in. Everything
runs offline: the real ``edicai.ai.provider`` is never contacted — its
``_call_api`` is patched to a deterministic dispatcher that serves
canned STRUCTURED proposals (understanding) and canned natural replies
(composition) from explicit queues keyed on the system prompt.

Design rule: a unit under test consuming a queue it was not given must
fail loudly (AssertionError) so tests cannot silently drift.
"""

from unittest import mock  # noqa: F401 — re-exported for test files

UNDERSTANDING_MARK = 'JSON intent proposal'
COMPOSE_MARK = 'VERIFIED DATA'

_FLAG_KEYS = (
    'edicai_ai.orchestrator_enabled',
    'edicai_ai.conversation_llm_enabled',
    'edicai_ai.llm_composition_enabled',
)


def ensure_flags_clean(testcase):
    """Guarantee all conversational flags are OFF unless a test set them."""
    cp = testcase.env['ir.config_parameter'].sudo()
    for key in _FLAG_KEYS:
        cp.set_param(key, 'False')


class ScriptedProvider:
    """Deterministic stand-in for ``EdicaiAIProvider._call_api``.

    ``understanding`` items are returned verbatim for intent-proposal
    calls; ``compose`` items for response-composition calls. An item
    may also be an Exception instance (raised to simulate provider
    failure). Empty queues raise AssertionError.
    """

    def __init__(self, understanding=(), compose=()):
        self._understanding = list(understanding)
        self._compose = list(compose)
        self.understanding_calls = []
        self.compose_calls = []

    def __call__(self, messages, **kwargs):
        system = messages[0]['content'] if messages else ''
        if UNDERSTANDING_MARK in system:
            self.understanding_calls.append(messages)
            return self._next(self._understanding, 'understanding')
        self.compose_calls.append(messages)
        return self._next(self._compose, 'compose')

    @staticmethod
    def _next(queue, label):
        if not queue:
            raise AssertionError(
                'scripted provider: unexpected %s call' % label)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def total_calls(self):
        return len(self.understanding_calls) + len(self.compose_calls)


_PATCH_TARGET = ('odoo.addons.edicai_ai.models.edicai_ai_provider.'
                 'EdicaiAIProvider._call_api')


def patch_provider(stub):
    """Context manager patching the provider call path."""
    return mock.patch(_PATCH_TARGET, side_effect=stub)


def make_proposal_json(intent, entities=None, clarification=False):
    """A canned (valid-shaped) model proposal string."""
    import json as _json
    return _json.dumps({
        'intent': intent,
        'entities': entities or {},
        'clarification_required': bool(clarification),
    })
