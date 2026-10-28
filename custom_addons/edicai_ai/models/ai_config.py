"""AI configuration layer: feature flag + conversation throttling.

Phase 0 (Security Foundation) — infrastructure only.

* ``edicai_ai.orchestrator_enabled``: server-side feature flag for the
  FUTURE conversational orchestrator.  Default ``False``; nothing reads
  it yet except this helper (the orchestrator itself is Phase 1 and is
  NOT implemented here).  The existing provider-based chatbot keeps
  working unchanged while the flag is off.
* Conversation-level throttling: a conservative rolling window per user
  (default 30 user turns / 5 minutes) implemented on top of — never
  replacing — the existing per-tool hourly rate limits of
  ``edicai.ai.tool.registry``.  Limits come from configuration
  parameters, so deployments can tune them without code changes.

Throttle check failure is fail-CLOSED (a user turn is refused), per the
architecture invariant that an unavailable layer must never open the
way to execution.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

FLAG_ORCHESTRATOR = 'edicai_ai.orchestrator_enabled'
# Phase 1B — LLM-assisted understanding and grounded response
# composition. Both default OFF; OFF = exact Phase 1A behaviour.
FLAG_CONVERSATION_LLM = 'edicai_ai.conversation_llm_enabled'
FLAG_LLM_COMPOSITION = 'edicai_ai.llm_composition_enabled'
PARAM_THROTTLE_TURNS = 'edicai_ai.throttle_turns'
PARAM_THROTTLE_WINDOW = 'edicai_ai.throttle_window_minutes'
# Manual QA test mode (observability only — never weakens security).
PARAM_QA_TEST_MODE = 'edicai_ai.qa_test_mode'

DEFAULT_THROTTLE_TURNS = 30
DEFAULT_THROTTLE_WINDOW_MINUTES = 5

_TRUE_VALUES = ('1', 'true', 'yes', 'on')


class EdicaiAIConfig(models.AbstractModel):
    """Read-only configuration helpers (flag + throttle)."""

    _name = 'edicai.ai.config'
    _description = 'AI Configuration (Feature Flag and Throttling)'

    @api.model
    def _get_param(self, key, default):
        try:
            return self.env['ir.config_parameter'].sudo().get_param(
                key, default=default)
        except Exception:
            _logger.exception(
                'AI config: could not read parameter %s (using default '
                '%r).', key, default)
            return default

    # ------------------------------------------------------------------
    # Feature flag (reserved for Phase 1; safe to expose now)
    # ------------------------------------------------------------------

    @api.model
    def is_orchestrator_enabled(self):
        """Return the server-side orchestrator feature flag.

        Default is ``False``; the flag is *infrastructure preparation
        only* — no orchestrator is connected in Phase 0.
        """
        return str(self._get_param(FLAG_ORCHESTRATOR, 'False')).strip().lower() \
            in _TRUE_VALUES

    @api.model
    def is_conversation_llm_enabled(self):
        """Phase 1B: LLM-assisted structured INTENT UNDERSTANDING.

        Independent of ``edicai_ai.orchestrator_enabled`` (the
        orchestrator path itself must be on too). Default OFF — with
        the flag off the orchestrator behaves exactly as in Phase 1A
        (deterministic grammar only, zero provider calls).
        """
        return str(self._get_param(FLAG_CONVERSATION_LLM, 'False'))\
            .strip().lower() in _TRUE_VALUES

    @api.model
    def is_llm_composition_enabled(self):
        """Phase 1B: LLM-assisted RESPONSE COMPOSITION from verified
        tool results (grounding-validated; falls back to the fixed
        Phase 1A templates on any failure). Default OFF.
        """
        return str(self._get_param(FLAG_LLM_COMPOSITION, 'False'))\
            .strip().lower() in _TRUE_VALUES

    @api.model
    def is_qa_test_mode_enabled(self):
        """Manual-testing lab: compact diagnostic metadata on chat
        turns. Observability ONLY — never weakens authorization,
        confirmations, approvals, idempotency or audit logging.
        Default OFF."""
        return str(self._get_param(PARAM_QA_TEST_MODE, 'False'))\
            .strip().lower() in _TRUE_VALUES

    # ------------------------------------------------------------------
    # Conversation throttle
    # ------------------------------------------------------------------

    @api.model
    def get_conversation_throttle(self):
        """Resolve ``(max_turns, window_minutes)``.

        Both values are configuration-driven and floored at 1.
        """
        def _int(value, default, minimum):
            try:
                return max(minimum, int(float(value)))
            except (TypeError, ValueError):
                return default

        turns = _int(
            self._get_param(PARAM_THROTTLE_TURNS, DEFAULT_THROTTLE_TURNS),
            DEFAULT_THROTTLE_TURNS, 1)
        window = _int(
            self._get_param(
                PARAM_THROTTLE_WINDOW, DEFAULT_THROTTLE_WINDOW_MINUTES),
            DEFAULT_THROTTLE_WINDOW_MINUTES, 1)
        return turns, window

    @api.model
    def check_conversation_throttle(self, user=None):
        """Rolling-window conversation throttle, per user.

        Counts user-role chat messages persisted inside the window for
        this user — the message table is the counter, so no extra
        in-memory state or new model is needed in Phase 0.

        :returns: ``(allowed, info)`` where ``info`` carries
            ``{'turns': limit, 'window_minutes': window, 'used': count}``
            (``used`` is ``None`` if the check itself failed).
        """
        user = user or self.env.user
        turns, window = self.get_conversation_throttle()
        info = {
            'turns': turns,
            'window_minutes': window,
            'used': None,
        }
        try:
            since = fields.Datetime.now() - timedelta(minutes=window)
            used = self.env['edicai.ai.chat.message'].search_count([
                ('role', '=', 'user'),
                ('create_date', '>=', since),
                ('session_id.user_id', '=', user.id),
            ])
        except Exception:
            # Fail closed: refuse the turn rather than bypass the guard.
            _logger.exception(
                'AI conversation throttle check failed for user %s '
                '(failing closed).', getattr(user, 'id', '?'))
            return False, info
        info['used'] = used
        return used < turns, info
