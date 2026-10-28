"""Phase 1B — bounded per-session conversational context.

Phase 1B adds short-term conversational memory so natural follow-ups
understand without repeating themselves:

    Turn 1: "How's my attendance?"      -> attendance summary
    Turn 2: "What about semester 5?"    -> same TOPIC, new entity

The context is deliberately minimal and BOUNDED.  It stores topical
resolution state only — NEVER conversation content, tool payloads,
secrets, role claims or authorization state:

    {
      "v": 1,
      "turns": [
        {"intent": "fees.fee_status", "source": "Fee Status",
         "student": "Dom Grounded", "semester": false, "ok": true}
      ],
      "pending": {"intent": "fees.fee_status", "kind": "student",
                  "question": "Which student do you mean?"}
    }

Hard rules enforced here:

* BOUNDED  — at most ``MAX_TURNS`` recent turns; every stored string is
  trimmed to ``MAX_STR`` characters; the persisted JSON never exceeds
  ``MAX_JSON`` characters (excess turns are dropped first).
* NO CONTENT — user/assistant message text is never stored (the audit
  trail already stores only letter counts; this model never sees full
  text except resolved *display names* of records the rule-checked tools
  themselves returned inside the caller's own authorized scope).
* NOT AUTHORIZATION — context is advisory hint material for DETECTION
  only.  Every tool execution each turn still passes the policy gate +
  the registry checks; a carried student name is only ever a SEARCH HINT
  which the tool handler re-resolves under the CURRENT user's record
  rules (never an identifier or a permission).
* Fail-CLOSED — corrupted / oversized / unknown-version context is
  discarded and rebuilt as empty; nothing ever raises to the caller.
"""

import json
import logging
import time

from odoo import api, models

_logger = logging.getLogger(__name__)

CONTEXT_SCHEMA_VERSION = 1
MAX_TURNS = 6
MAX_STR = 120
MAX_JSON = 4000
MAX_QUERY_JSON = 2048
QUERY_TTL_SECONDS = 30 * 60
QUERY_FILTER_KEYS = frozenset({
    'program_query', 'program_level', 'campus', 'state', 'threshold',
    'date', 'overdue', 'no_followup', 'limit',
    'open_only',
})

CONTEXT_KEY_TOPICS = ('intent', 'source', 'student', 'semester', 'ok')
PENDING_KINDS = ('student', 'semester')

EMPTY_CONTEXT = {'v': CONTEXT_SCHEMA_VERSION, 'turns': [], 'pending': False}
FIELD_CONTEXT = 'context_json'


class EdicaiAIConversationContext(models.AbstractModel):
    """Bounded, safe, per-session conversational context (Phase 1B)."""

    _name = 'edicai.ai.conversation.context'
    _description = 'AI Conversational Session Context (bounded, read-only \
intent hints)'

    # ------------------------------------------------------------------
    # Load / save (fail-closed)
    # ------------------------------------------------------------------

    @api.model
    def _clean_str(self, value):
        if not isinstance(value, str):
            return False
        value = value.strip()[:MAX_STR]
        return value or False

    @api.model
    def _sanitize(self, raw):
        """Validate loaded JSON against the strict schema; anything else
        becomes an EMPTY context (fail-closed, never raises)."""
        try:
            if not isinstance(raw, dict):
                return dict(EMPTY_CONTEXT)
            if raw.get('v') != CONTEXT_SCHEMA_VERSION:
                return dict(EMPTY_CONTEXT)
            turns = []
            for turn in (raw.get('turns') or [])[:MAX_TURNS]:
                if not isinstance(turn, dict):
                    break
                clean = {
                    'intent': self._clean_str(turn.get('intent')),
                    'source': self._clean_str(turn.get('source')),
                    'student': self._clean_str(turn.get('student')),
                    'semester': self._clean_str(turn.get('semester')),
                    'ok': turn.get('ok') is True,
                }
                if clean['intent'] and clean['ok']:
                    turns.append(clean)
            pending = raw.get('pending')
            pend_intent = isinstance(pending, dict) \
                and self._clean_str(pending.get('intent'))
            pend_kind = isinstance(pending, dict) \
                and self._clean_str(pending.get('kind'))
            if pend_intent and pend_kind in PENDING_KINDS:
                pending = {
                    'intent': pend_intent,
                    'kind': pend_kind,
                    'question': self._clean_str(pending.get('question')),
                }
            else:
                pending = False
            return {'v': CONTEXT_SCHEMA_VERSION,
                    'turns': turns,
                    'pending': pending}
        except Exception:
            _logger.exception('AI context: sanitization failed '
                              '(dropping context).')
            return dict(EMPTY_CONTEXT)

    @api.model
    def get(self, session):
        """Load the sanitized bounded context of one session. No
        session / no context -> EMPTY; failures fail closed."""
        if session is None:
            return dict(EMPTY_CONTEXT)
        try:
            raw = session.read([FIELD_CONTEXT])[0][FIELD_CONTEXT]
        except Exception:
            # Field not present (pre-1B DB) or access issue — degrade to
            # empty context, never raise.
            return dict(EMPTY_CONTEXT)
        if not raw:
            return dict(EMPTY_CONTEXT)
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return dict(EMPTY_CONTEXT)
        return self._sanitize(parsed)

    @api.model
    def save(self, session, context):
        """Persist a bounded context dict.  Drops oldest turns when the
        serialized size exceeds the cap.  Best-effort: never raises —
        a context write failure must not break the chat turn."""
        try:
            context = self._sanitize(context)
            blob = json.dumps(context, ensure_ascii=True)
            while len(blob) > MAX_JSON and context['turns']:
                context['turns'] = context['turns'][1:]
                blob = json.dumps(context, ensure_ascii=True)
            if len(blob) > MAX_JSON:
                # Even a single oversized turn cannot be persisted —
                # store nothing rather than truncating structured data.
                blob = json.dumps(empty_context(), ensure_ascii=True)
            session.write({FIELD_CONTEXT: blob})
        except Exception:
            _logger.exception('AI context: save failed (ignored).')
        return True

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    @api.model
    def record_turn(self, session, intent, source_label,
                    student=False, semester=False, ok=True):
        """Append a successful turn to the topic memory and clears any
        pending clarification (a completed answer resolves it)."""
        if session is None:
            return
        context = self.get(session)
        turn = {
            'intent': self._clean_str(intent),
            'source': self._clean_str(source_label),
            'student': self._clean_str(student),
            'semester': self._clean_str(semester),
            'ok': bool(ok),
        }
        context['turns'] = (context.get('turns') or [])[-(MAX_TURNS - 1):]
        if isinstance(turn['intent'], str):
            context['turns'].append(turn)
        context['pending'] = False
        self.save(session, context)

    @api.model
    def set_pending(self, session, intent, kind, question=''):
        """Mark that the assistant just asked a bounded clarification."""
        if session is None or kind not in PENDING_KINDS:
            return
        context = self.get(session)
        context['pending'] = {
            'intent': self._clean_str(intent),
            'kind': kind,
            'question': self._clean_str(question),
        }
        self.save(session, context)

    @api.model
    def clear_pending(self, session):
        if session is None:
            return
        context = self.get(session)
        context['pending'] = False
        self.save(session, context)

    # ------------------------------------------------------------------
    # Phase 12 — bounded structured query state (not authorization)
    # ------------------------------------------------------------------

    @api.model
    def _clean_query_value(self, value):
        if isinstance(value, str):
            return value.strip()[:MAX_STR] or None
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        return False

    @api.model
    def _sanitize_query(self, raw):
        if not isinstance(raw, dict) or raw.get('v') != 1:
            return False
        try:
            expires_at = int(raw.get('expires_at') or 0)
            if expires_at <= int(time.time()):
                return False
            intent = self._clean_str(raw.get('intent'))
            tool = self._clean_str(raw.get('tool'))
            scope = raw.get('scope')
            operation = raw.get('operation')
            if not intent or not tool or scope not in (
                    'record', 'collection', 'aggregate') or operation not in (
                    'read', 'search', 'list', 'count', 'summary'):
                return False
            filters = {}
            for key, value in (raw.get('filters') or {}).items():
                if key not in QUERY_FILTER_KEYS:
                    continue
                clean_value = self._clean_query_value(value)
                if clean_value is not None:
                    filters[key] = clean_value
            entities = {}
            for key in ('student_name', 'semester_term', 'program_query',
                        'program_level', 'campus', 'limit', 'threshold',
                        'overdue_only', 'state', 'no_followup',
                        'date_filter', 'open_only'):
                value = self._clean_query_value(
                    (raw.get('entities') or {}).get(key))
                if value is not None and value is not False:
                    entities[key] = value
            ids = []
            for record_id in (raw.get('record_ids') or [])[:20]:
                if isinstance(record_id, int) and record_id > 0:
                    ids.append(record_id)
            clean = {
                'v': 1, 'intent': intent, 'tool': tool,
                'domain': self._clean_str(raw.get('domain')) or 'erp',
                'operation': operation, 'scope': scope,
                'filters': filters, 'entities': entities,
                # Hints only. Callers MUST re-run the query and never use
                # these IDs directly for a read or mutation.
                'record_ids': ids,
                'signature': self._clean_str(raw.get('signature')) or '',
                'expires_at': expires_at,
            }
            return clean
        except (AttributeError, TypeError, ValueError):
            return False

    @api.model
    def get_query(self, session):
        if session is None:
            return False
        try:
            raw = session.query_state_json
            parsed = json.loads(raw) if raw else False
            return self._sanitize_query(parsed)
        except Exception:
            return False

    @api.model
    def set_query(self, session, query):
        """Persist a bounded, expiring query hint; never stores messages."""
        if session is None:
            return False
        try:
            clean = dict(query or {})
            clean['v'] = 1
            clean['expires_at'] = int(time.time()) + QUERY_TTL_SECONDS
            clean = self._sanitize_query(clean)
            if not clean:
                return False
            blob = json.dumps(clean, sort_keys=True, ensure_ascii=True)
            if len(blob) > MAX_QUERY_JSON:
                return False
            session.write({'query_state_json': blob})
            return True
        except Exception:
            _logger.exception('AI context: query-state save failed (ignored).')
            return False

    # ------------------------------------------------------------------
    # Read-only introspection helpers (orchestrator)
    # ------------------------------------------------------------------

    @api.model
    def last_topic(self, context):
        """The most recent successfully answered intent, or False."""
        turns = (context or {}).get('turns') or []
        for turn in reversed(turns):
            if turn.get('ok') and turn.get('intent'):
                return turn
        return False

    @api.model
    def pending_topic(self, context):
        return (context or {}).get('pending') or False


def empty_context():
    return dict(EMPTY_CONTEXT)
