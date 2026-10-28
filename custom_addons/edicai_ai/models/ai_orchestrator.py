"""Conversational orchestrator (Phase 1A deterministic + Phase 1B LLM).

Loop (strictly read-only):

    message → CONTEXT → intent (grammar first; LLM proposal validated
    when enabled) → policy gate → edicai.ai.tool.registry.execute_tool →
    tool result → grounded composer (deterministic template, optionally
    LLM-composed + grounding-validated) → reply (+ source label)

Hard invariants (Phase 0 / 1A — unchanged):

* The LLM is NEVER the security boundary and NEVER the source of
  truth.  Its structured proposal must pass schema validation, the
  intent allow-list and entity validation BEFORE routing; the policy
  gate and the central registry still authorize every execution.
* ONE tool execution per user turn — at most one
  ``execute_tool`` call; the orchestrator is not a planner.
* Authorization is decided by the policy gate + registry — never by
  anything derived from message text or conversation context.
* Unknown and unsupported requests produce fixed safe replies; write
  actions and adversarial phrasings never reach a tool.
* Ambiguous entity resolution never silently selects a record.
* Reply facts always come from the tool result; a grounding-violating
  LLM composer is discarded (deterministic template used) on ANY
  numeric value absent from the tool data.

Phase 1B additions (each strictly behind its own flag, default OFF):

* ``edicai_ai.conversation_llm_enabled`` — when the deterministic
  grammar could not classify a turn, ONE bounded provider call proposes
  ``{intent, entities, clarification_required}``; the proposal is
  validated (schema → allow-list → entities) before use.  Any failure
  falls back to the Phase 1A grammar + deterministic follow-up
  carry-over, otherwise the fixed UNKNOWN reply.
* ``edicai_ai.llm_composition_enabled`` — after a successful tool
  execution, ONE bounded provider call may phrase the answer from the
  VERIFIED tool result; a deterministic grounding validator rejects any
  reply containing numbers absent from the facts (template used then).
* Bounded session context (`edicai.ai.conversation.context`) so natural
  follow-ups ("what about semester 5?", "and her grades?") and answers
  to pending clarifications work without repeating the whole request.
  Context is TOPIC ONLY, never authorization, never message content.
"""

import logging
import hashlib
import json
import re
import time

from odoo import api, models

from odoo.addons.edicai_ai.models.ai_error import (
    AUTHORIZATION_DENIED,
    INTERNAL_ERROR,
    RATE_LIMITED,
    RECORD_NOT_FOUND,
    SAFE_MESSAGES,
)
from odoo.addons.edicai_ai.models.ai_intent import (
    INTENT_ATTENDANCE,
    INTENT_ATTENDANCE_SUMMARY,
    INTENT_ENTITY_ACTIONS,
    INTENT_ENTITY_MODELS,
    INTENT_ENTITY_SEARCH,
    INTENT_FEES,
    INTENT_FEES_SUMMARY,
    INTENT_GRADES,
    INTENT_PROGRAMS,
    INTENT_APPLICANT_LIST,
    INTENT_FOLLOWUP_LIST,
    INTENT_GRIEVANCE_SUMMARY,
    INTENT_TIMETABLE,
    INTENT_TIMETABLE_VIEW,
    INTENT_SOURCE_LABEL,
    GREETING_REPLY,
    UNSUPPORTED_REPLY,
    UNKNOWN_REPLY,
)

_logger = logging.getLogger(__name__)

MAX_LIST_ROWS = 8

NO_DATA_REPLY = (
    "I don't have enough information to answer that — no matching "
    "records were found in your authorized scope.")

STATUS_ANSWERED = 'answered'
STATUS_CLARIFY = 'clarify'
STATUS_ERROR = 'error'

# Tools whose handlers resolve a dedicated student target.
_STUDENT_TARGETED = (INTENT_ATTENDANCE, INTENT_FEES, INTENT_GRADES)

# Refinement starters a bare follow-up may begin with ("what about
# semester 5?", "and her grades?"). Deliberately conservative: without
# a starter or a pending clarification, an unclassifiable turn stays
# UNKNOWN (never guessed).
_REFINEMENT_STARTER = re.compile(
    r'^(what\s+about|and\s|any\s|how\s+many\s|so\s|what.s+)\b', re.I)

# A BARE courtesy greeting only.  Deliberately anchored with ``$`` so a
# greeting followed by a real request ("hello, show me fees") is never
# hijacked — it keeps flowing to the normal intent grammar.  The optional
# trailing filler is a closed set ("hello there", "good morning again").
_GREETING_RE = re.compile(
    r'^(?:hi|hello|hey|hiya|howdy|yo|greetings|namaste|hola'
    r'|good\s+(?:morning|afternoon|evening|day))'
    r'(?:[\s,!.]+(?:there|again|team|all|everyone|sir|ma\'am|madam))?'
    r'[\s,!.?]*$',
    re.I,
)


class EdicaiAIOrchestrator(models.AbstractModel):
    """Grounded read-only conversational orchestrator."""

    _name = 'edicai.ai.orchestrator'
    _description = 'AI Conversational Orchestrator (grounded, read-only)'

    # ------------------------------------------------------------------
    # Audit helpers (reuse the Phase 0 durable audit model)
    # ------------------------------------------------------------------

    def _audit(self, event_type, conversation=None, **kwargs):
        """Best-effort durable audit write; never raises."""
        try:
            return self.env['edicai.ai.audit.event'].log_event(
                event_type, conversation=conversation, **kwargs)
        except Exception:
            _logger.exception('AI orchestrator: audit write failed '
                              '(ignored).')
            return False

    # ------------------------------------------------------------------
    # Turn handling
    # ------------------------------------------------------------------

    @api.model
    @api.model
    def _is_greeting(self, text):
        """True only for a BARE courtesy greeting (see ``_GREETING_RE``).

        A greeting followed by a real request is intentionally NOT
        matched, so it keeps flowing to the normal intent grammar.
        """
        return bool(_GREETING_RE.match(str(text or '').strip()))

    def answer_turn(self, message, session=None):
        """Process one user turn and return the safe response dict.

        :param message: the raw user text.
        :param session: ``edicai.ai.chat.session`` record of the turn.
        :returns: dict with keys ``status``, ``reply``, ``source_label``
            and ``tool_name`` (plus ``error_code`` on errors). The
            caller persists the reply and the source label; no
            conversation content is stored here.
        """
        text = str(message or '').strip()
        intent_model = self.env['edicai.ai.intent']
        user = self.env.user
        context_model = self.env['edicai.ai.conversation.context']
        ctx = context_model.get(session) if session is not None else {}
        query_state = context_model.get_query(session) \
            if session is not None else False
        flags = self.env['edicai.ai.config']
        llm_understanding_on = flags.is_conversation_llm_enabled()

        # ---- Phase 2A (additive FIRST branch): the ONE allow-listed
        # conversational write action. With the write flag OFF this
        # returns None immediately and behaviour stays byte-identical
        # to Phase 1B; the grammar below remains the first safety
        # layer for every other turn.
        action_outcome = self.env[
            'edicai.ai.action.orchestrator'].handle_turn(text, session)
        if action_outcome is not None:
            return action_outcome

        # Grammar FIRST (Phase 1A safety layer — always runs).
        parsed = intent_model.parse(text)

        # ---- unsupported (write actions, injection) — never LLM-assisted
        if parsed['status'] == 'unsupported':
            self._audit(
                'INTENT_UNSUPPORTED',
                conversation=session,
                decision='deny',
                reason_code='WRITE_OR_ADVERSARIAL_REQUEST',
                metadata={'content_chars': len(text)},
            )
            return {
                'status': STATUS_ERROR,
                'reply': UNSUPPORTED_REPLY,
                'source_label': False,
                'tool_name': False,
                'error_code': None,
            }

        if parsed['status'] == 'unknown' and re.search(
                r'\b(best|top|brightest|highest[- ]performing)\b.*'
                r'\bstudents?\b', text, re.I) and not re.search(
                r'\b(cgpa|gpa|grade|marks|attendance|fees?)\b', text, re.I):
            return {
                'status': STATUS_CLARIFY,
                'reply': ('What criteria should I use to define “best” '
                          '(for example, CGPA, grades, or attendance)?'),
                'source_label': False, 'tool_name': False,
                'error_code': None,
            }
        if parsed['status'] == 'unknown' and re.search(
                r'\b(book|reserve)\s+(?:me\s+)?(?:a\s+)?flight\b',
                text, re.I):
            self._audit('INTENT_UNKNOWN', conversation=session,
                        decision='allow', reason_code='UNSUPPORTED_CAPABILITY',
                        metadata={'content_chars': len(text)})
            return {
                'status': STATUS_ERROR,
                'reply': ("I can't book flights. I can help with supported "
                          'ERP records such as attendance, fees, grades, '
                          'timetables, and admission data.'),
                'source_label': False, 'tool_name': False,
                'error_code': None,
            }

        # Deterministic short-term query references are considered before
        # any LLM proposal. Replays only carry validated query hints; they
        # still pass the normal gate and execute the tool again below.
        query_followup = self._resolve_query_followup(text, query_state)
        if query_followup and query_followup.get('kind') == 'clarify':
            return {
                'status': STATUS_CLARIFY,
                'reply': query_followup['reply'],
                'source_label': False,
                'tool_name': False,
                'error_code': None,
            }
        if query_followup and query_followup.get('kind') == 'explain':
            self._audit('QUERY_CONTEXT_EXPLAINED', conversation=session,
                        decision='allow', tool_name=query_state.get('tool'))
            return {
                'status': STATUS_ANSWERED,
                'reply': query_followup['reply'],
                'source_label': query_state.get('tool'),
                'tool_name': query_state.get('tool'),
                'error_code': None,
            }
        if query_followup and query_followup.get('parsed'):
            parsed = query_followup['parsed']

        # ---- bare greeting / courtesy turn -----------------------------
        # Deterministic, zero-data, zero-permission.  Runs AFTER pending
        # actions, proactive surfacing and query follow-ups (so it can
        # never hijack an in-flight workflow or a real signal) and BEFORE
        # any LLM understanding (so a courtesy turn never spends a
        # provider call or leaks into intent detection).
        if parsed['status'] == 'unknown' and self._is_greeting(text):
            return {
                'status': STATUS_ANSWERED,
                'reply': GREETING_REPLY,
                'source_label': False,
                'tool_name': False,
                'error_code': None,
            }

        # ---- unknown: LLM proposal first (if enabled), then the
        # deterministic follow-up carry-over, else the fixed reply ----
        if parsed['status'] == 'unknown':
            if llm_understanding_on and not query_followup:
                outcome = self._llm_understand(text, session, ctx)
                if outcome.get('status') == 'supported':
                    parsed = outcome['parsed']
                elif outcome.get('status') == 'clarify':
                    return self._ask_clarification(
                        outcome['intent'], session)
                elif outcome.get('status') == 'action':
                    # Phase 2A: validated write-action proposal — the
                    # action layer still resolves, previews, gates and
                    # re-authorizes; nothing can execute here.
                    handled = self.env[
                        'edicai.ai.action.orchestrator'] \
                        .handle_llm_proposal(
                            text, outcome.get('entities'), session,
                            action=outcome.get('action'))
                    if handled is not None:
                        return handled
                # fallback: keep parsed['unknown'] and try deterministic
            if parsed['status'] == 'unknown' and not query_followup:
                carried = self._resolve_followup(text, ctx)
                if carried:
                    parsed = carried

        # ---- unknown (still) -------------------------------------------
        if parsed['status'] != 'supported' or not parsed.get('tool'):
            self._audit(
                'INTENT_UNKNOWN',
                conversation=session,
                decision='allow',
                reason_code='NO_MATCHING_INTENT',
                metadata={'content_chars': len(text)},
            )
            return {
                'status': STATUS_ERROR,
                'reply': UNKNOWN_REPLY,
                'source_label': False,
                'tool_name': False,
                'error_code': None,
            }

        # P0 (BUG-006): every extracted constraint must be either
        # supported by this fixed tool contract or explicitly rejected.
        # Never pass an intent to a handler while silently omitting a
        # program/campus/date/threshold filter.
        requested_filters = (parsed.get('query') or {}).get('filters') or {}
        supported_filters = {
            INTENT_PROGRAMS: {'program_query', 'program_level', 'campus', 'limit'},
            INTENT_APPLICANT_LIST: {'program_query', 'campus', 'state',
                                    'no_followup', 'limit'},
            INTENT_FOLLOWUP_LIST: {'date', 'limit'},
            INTENT_GRIEVANCE_SUMMARY: {'open_only'},
            INTENT_FEES_SUMMARY: {'overdue', 'limit'},
            INTENT_ATTENDANCE_SUMMARY: {'threshold', 'limit'},
            INTENT_TIMETABLE_VIEW: {'date'},
        }.get(parsed['tool'], set())
        rejected_filters = sorted(set(requested_filters) - supported_filters)
        if rejected_filters:
            self._audit(
                'QUERY_FILTER_REJECTED', conversation=session,
                decision='deny', reason_code='FILTER_UNSUPPORTED',
                tool_name=parsed['tool'],
                metadata={'filters': rejected_filters})
            return {
                'status': STATUS_CLARIFY,
                'reply': ('I can’t safely apply every requested filter to '
                          'that read operation. Please restate the request '
                          'using filters supported for this data.'),
                'source_label': False, 'tool_name': parsed['tool'],
                'error_code': None,
            }

        # ---- supported: audit + policy gate --------------------------------
        self._audit(
            'INTENT_DETECTED',
            conversation=session,
            decision='allow',
            reason_code='LLM_PROPOSAL' if parsed.get('origin') == 'llm'
            else 'INTENT_MATCHED',
            tool_name=parsed['tool'],
            metadata={
                'intent': parsed['intent'],
                'scope': (parsed.get('query') or {}).get('scope'),
                'filters': (parsed.get('query') or {}).get('filters') or {},
            },
        )

        gate = self.env['edicai.ai.policy.gate']
        decision = gate.check_access(parsed['tool'], user=user)
        if not decision['allowed']:
            self._audit(
                'AUTHORIZATION_DENIED',
                conversation=session,
                decision='deny',
                reason_code=decision['reason_code'],
                tool_name=parsed['tool'],
            )
            return {
                'status': STATUS_ERROR,
                'reply': '⚠️ %s' % SAFE_MESSAGES[AUTHORIZATION_DENIED],
                'source_label': False,
                'tool_name': parsed['tool'],
                'error_code': AUTHORIZATION_DENIED,
            }

        params = self._build_params(parsed['intent'], parsed['entities'])
        if parsed['intent'] == INTENT_APPLICANT_LIST:
            params['operation'] = (parsed.get('query') or {}).get(
                'operation') or 'list'
        elif parsed['intent'] == INTENT_FOLLOWUP_LIST:
            params['operation'] = (parsed.get('query') or {}).get(
                'operation') or 'list'

        # ---- execute through the existing registry path -------------------
        # EXACTLY ONE tool execution per user turn (no planner).
        registry = self.env['edicai.ai.tool.registry']
        try:
            result = registry.execute_tool(parsed['tool'], params)
        except Exception as exc:  # noqa: BLE001 — sanitised below
            _logger.info(
                'AI orchestrator: tool %s raised for user %s (%s).',
                parsed['tool'], user.id, type(exc).__name__)
            code = self._classify_tool_exception(exc)
            self._audit(
                'TOOL_ERROR',
                conversation=session,
                decision='error',
                reason_code=code,
                tool_name=parsed['tool'],
                detail=type(exc).__name__,
            )
            return {
                'status': STATUS_ERROR,
                'reply': '⚠️ %s' % SAFE_MESSAGES.get(
                    code, SAFE_MESSAGES[INTERNAL_ERROR]),
                'source_label': False,
                'tool_name': parsed['tool'],
                'error_code': code,
            }

        # ---- structured handler errors (no exception needed) ---------------
        if isinstance(result, dict) and result.get('error_code'):
            code = result['error_code']
            self._audit(
                'TOOL_ERROR',
                conversation=session,
                decision='error',
                reason_code=code,
                tool_name=parsed['tool'],
                detail=result.get('detail'),
            )
            return {
                'status': STATUS_ERROR,
                'reply': '⚠️ %s' % ({
                    'QUERY_TOO_BROAD': (
                        'That result set is too broad to show safely. '
                        'Add a stage, date, or campus filter.'),
                    'FILTER_UNSUPPORTED': (
                        'I cannot safely apply that filter to this read. '
                        'Please restate the request with supported filters.'),
                    'FILTER_INVALID': (
                        'That filter value is not valid for this read. '
                        'Please check it and try again.'),
                }.get(code) or SAFE_MESSAGES.get(
                    code, SAFE_MESSAGES[RECORD_NOT_FOUND])),
                'source_label': False,
                'tool_name': parsed['tool'],
                'error_code': code,
            }

        # ---- ambiguity: ask, never guess ----------------------------------
        # The handlers always include the ``clarify`` key on ambiguity
        # (even with an empty candidate list) — presence, not
        # truthiness, decides the branch.
        if isinstance(result, dict) and 'clarify' in result:
            rows = result.get('clarify')
            self._audit(
                'INTENT_AMBIGUOUS',
                conversation=session,
                decision='allow',
                reason_code='CANDIDATE_COUNT:%d' % (
                    len(rows) if isinstance(rows, list) else 1),
                tool_name=parsed['tool'],
            )
            reply = result.get('clarify_message') or \
                self._compose_clarify(parsed['tool'], rows)
            if session is not None and parsed['tool'] not in (
                    INTENT_APPLICANT_LIST, INTENT_PROGRAMS):
                context_model.set_pending(
                    session, parsed['intent'],
                    'semester' if parsed['tool'] == INTENT_TIMETABLE
                    else 'student',
                    question=reply)
            return {
                'status': STATUS_CLARIFY,
                'reply': reply,
                'source_label': False,
                'tool_name': parsed['tool'],
                'error_code': None,
            }

        # Conversational tools wrap their payload in ``data``; the
        # generic entity tools (G4) return the payload dict directly, so
        # fall back to the result itself rather than composing from {}.
        result_dict = result if isinstance(result, dict) else {}
        data = result_dict.get('data')
        if data is None:
            data = result_dict
        source_label = (result_dict.get('label')
                        or parsed.get('source_label') or '')
        reply = self._compose_reply(text, parsed, data, source_label)
        if (parsed.get('query') or {}).get('format') == 'table':
            reply = self._compose_data_table(data)

        # Session-linked completion audit (the registry's own
        # TOOL_EXECUTED event has no conversation context by design).
        self._audit(
            'TOOL_EXECUTED',
            conversation=session,
            decision='allow',
            reason_code='TOOL_OK',
            tool_name=parsed['tool'],
        )

        # Bounded topic context for later follow-ups (no content, no
        # authorization semantics).
        if session is not None:
            context_model.record_turn(
                session, parsed['intent'], source_label,
                student=data.get('student') or False,
                semester=data.get('semester') or False,
                ok=True)
            self._store_query_state(
                context_model, session, parsed, params, data, result_dict)

        return {
            'status': STATUS_ANSWERED,
            'reply': reply,
            'source_label': source_label,
            'tool_name': parsed['tool'],
            'error_code': None,
        }

    # ------------------------------------------------------------------
    # Phase 1B — LLM understanding (validated proposal only)
    # ------------------------------------------------------------------

    @api.model
    def _llm_understand(self, text, session, ctx):
        """One bounded provider call proposing a structured intent.

        Validation order: schema → allow-list → entities.  Everything
        else falls back (the Phase 1A grammar continues).  Never raises;
        every outcome is audited.
        """
        proposal = self.env['edicai.ai.llm.understanding'].propose(
            text, ctx)
        if proposal.get('status') == 'ok':
            self._audit(
                'LLM_UNDERSTANDING',
                conversation=session,
                decision='allow',
                reason_code='PROPOSAL_ACCEPTED',
                tool_name=proposal['intent'],
                metadata={'origin': 'llm'},
            )
            parsed = {
                'status': 'supported',
                'parsed': {
                    'status': 'supported',
                    'intent': proposal['intent'],
                    'tool': proposal['intent'],
                    'source_label': INTENT_SOURCE_LABEL.get(
                        proposal['intent'], 'ERP Data'),
                    'entities': {
                        'semester_term': False,
                        'student_name': False,
                        'program_level': False,
                        'program_query': False,
                        **(proposal.get('entities') or {}),
                    },
                    'origin': 'llm',
                },
            }
            return parsed
        if proposal.get('status') == 'action':
            # Validated Phase 2A write-action proposal (advisory only —
            # the action layer resolves, previews and re-authorizes).
            self._audit(
                'LLM_UNDERSTANDING',
                conversation=session,
                decision='allow',
                reason_code='ACTION_PROPOSAL',
                metadata={'origin': 'llm'},
            )
            return {
                'status': 'action',
                'action': proposal.get('action'),
                'entities': proposal.get('entities') or {},
            }
        if proposal.get('status') == 'clarify':
            if not proposal.get('intent') or proposal.get('intent') not in (
                    INTENT_ATTENDANCE, INTENT_FEES, INTENT_GRADES,
                    INTENT_TIMETABLE):
                # Clarification about the program list has no bounded
                # entity to ask for — treat like any invalid proposal.
                self._audit(
                    'LLM_UNDERSTANDING',
                    conversation=session,
                    decision='deny',
                    reason_code='CLARIFICATION_NOT_APPLICABLE',
                    metadata={'origin': 'llm'},
                )
                return {'status': 'fallback'}
            self._audit(
                'LLM_UNDERSTANDING',
                conversation=session,
                decision='allow',
                reason_code='PROPOSAL_CLARIFICATION',
                tool_name=proposal.get('intent'),
                metadata={'origin': 'llm'},
            )
            return {'status': 'clarify', 'intent': proposal['intent']}
        # Any invalid / unavailable output falls back safely.
        self._audit(
            'LLM_UNDERSTANDING',
            conversation=session,
            decision='deny',
            reason_code=proposal.get('reason_code') or 'INVALID',
            metadata={'origin': 'llm'},
        )
        return {'status': 'fallback'}

    def _ask_clarification(self, intent, session):
        """LLM asked for entity clarification — bounded question, no
        execution; pending clarification state recorded."""
        what = 'semester' if intent == INTENT_TIMETABLE else 'student'
        reply = 'Which %s do you mean?' % what
        if session is not None:
            self.env['edicai.ai.conversation.context'].set_pending(
                session, intent,
                'semester' if intent == INTENT_TIMETABLE else 'student',
                question=reply)
        self._audit(
            'INTENT_AMBIGUOUS',
            conversation=session,
            decision='allow',
            reason_code='LLM_CLARIFICATION_REQUESTED',
            tool_name=intent,
        )
        return {
            'status': STATUS_CLARIFY,
            'reply': reply,
            'source_label': False,
            'tool_name': intent,
            'error_code': None,
        }

    # ------------------------------------------------------------------
    # Phase 1B — deterministic follow-up carry-over (fallback when the
    # LLM is off or its proposal fell back). Conservative by design.
    # ------------------------------------------------------------------

    @api.model
    def _resolve_followup(self, text, ctx):
        """Try to classify the turn as a follow-up of the session topic.

        Allowed ONLY when:
        * the assistant currently waits for a bounded clarification
          answer (the whole turn is the missing entity), OR
        * the turn starts with an explicit refinement starter
          ("what about / and / any / how many / so / what's") while a
          successful topic exists.

        The carried intent still passes the policy gate + registry, and
        every carried NAME is only a search hint re-resolved by the
        handler under the CURRENT user's record rules.  Context NEVER
        grants authorization.
        """
        if not ctx:
            return False
        context_model = self.env['edicai.ai.conversation.context']
        pending = context_model.pending_topic(ctx)
        topic = context_model.last_topic(ctx)
        target_intent = False
        carry_student = False
        carry_semester = False

        if pending:
            target_intent = pending.get('intent')
        elif topic:
            target_intent = topic.get('intent')

        if not target_intent:
            return False

        entities = {
            'semester_term': self.env['edicai.ai.intent']
            .extract_semester_term(text),
            'student_name': self.env['edicai.ai.intent']
            .extract_student_name(text),
            'program_level': False,
            'program_query': False,
        }

        if pending:
            kind = pending.get('kind')
            if kind == 'student' and not entities['student_name']:
                # The user is directly answering "Which student …" —
                # the whole turn is the candidate name (bounded).
                entities['student_name'] = str(text)[:120]
            # kind == 'semester': extraction above already ran.
        elif not _REFINEMENT_STARTER.match(text):
            # No pending question, not phrased as a refinement → the
            # turn stays UNKNOWN (never guessed from context).
            return False
        else:
            # Carry the resolved student topic (search hint only):
            # only when the topic is student-targeted, the turn does
            # NOT name a different student explicitly, and the topic
            # turn actually resolved one.
            if target_intent in _STUDENT_TARGETED \
                    and not entities['student_name']:
                carry = topic.get('student')
                if carry and len(str(carry)) <= 120:
                    carry_student = str(carry)
            if target_intent == INTENT_TIMETABLE \
                    and not entities['semester_term'] \
                    and topic.get('semester'):
                carry_semester = topic['semester']

        if target_intent in _STUDENT_TARGETED and carry_student \
                and not entities['student_name']:
            entities['student_name'] = carry_student
        # A carried semester term from a prior clash topic.
        if target_intent == INTENT_TIMETABLE and carry_semester \
                and not entities['semester_term']:
            entities['semester_term'] = carry_semester

        carried = {
            'status': 'supported',
            'intent': target_intent,
            'tool': target_intent,
            'source_label': INTENT_SOURCE_LABEL.get(
                target_intent, 'ERP Data'),
            'entities': entities,
            'origin': 'followup',
        }
        # The grammar's own word checks stay authoritative for
        # unsupported intents — carried topics never bypass them
        # (parse() already refused unsupported turns earlier).
        return carried if target_intent in (
            INTENT_ATTENDANCE, INTENT_FEES, INTENT_GRADES,
            INTENT_TIMETABLE, INTENT_PROGRAMS) else False

    @api.model
    def _resolve_query_followup(self, text, query_state):
        """Resolve a small deterministic set of query references.

        Stored values are hints only. A returned ``parsed`` object is
        deliberately sent through the ordinary policy-gate/registry path,
        which re-authorizes and re-runs the query for the current user.
        """
        if not query_state:
            return False
        text = str(text or '').strip()
        lowered = text.lower().strip(' .!?')
        if re.fullmatch(r'(?:why|why\s+\??|explain\s+(?:that|the\s+result))\??',
                        lowered):
            filters = query_state.get('filters') or {}
            if filters:
                criteria = ', '.join('%s=%s' % (key, value)
                                     for key, value in sorted(filters.items()))
                reason = 'the recorded filters were %s' % criteria
            else:
                reason = 'the query matched the requested ERP scope'
            return {
                'kind': 'explain',
                'reply': ('The previous result came from a fresh query using '
                          '%s. I can re-run it now; the saved context does not '
                          'preserve access or authorize records.' % reason),
            }
        if re.search(r'\b(?:another|different)\s+campus\b', lowered) \
                and not re.search(r'\b(?:at|from)\s+[\w-]+', text, re.I):
            return {'kind': 'clarify',
                    'reply': 'Which campus would you like?'}
        if re.search(r'\bsame\b.*\banother\s+subject\b', lowered):
            return {'kind': 'clarify',
                    'reply': 'Which subject would you like me to use?'}

        if re.fullmatch(
                r'(?:explain\s+)?(?:the\s+)?(?:first|second)\s+one\??',
                lowered):
            return {'kind': 'clarify',
                    'reply': 'Which result do you mean? Please name the '
                    'applicant or restate the filter so I can resolve it safely.'}
        if lowered in ('that', 'those', 'them'):
            return {'kind': 'clarify',
                    'reply': 'Would you like me to repeat or explain the previous result?'}

        date_refine = re.fullmatch(
            r'(?:what\s+about\s+)?(today|tomorrow|yesterday)\s*[.!?]*',
            lowered)
        table_replay = bool(re.fullmatch(
            r'(?:repeat|show)\s+.+\s+(?:in|as)\s+(?:a\s+)?table\??',
            lowered))
        replay = table_replay or bool(re.fullmatch(
            r'(?:show\s+(?:me\s+)?(?:that|those|them|the\s+previous\s+'
            r'(?:result|list))(?:\s+again)?|repeat\s+'
            r'(?:that|it|the\s+result)|'
            r'(?:same(?:\s+again)?|previous\s+result(?:\s+again)?))\s*[.!?]*',
            lowered))
        refine = bool(re.match(r'^(?:now\s+)?only\b', lowered))
        unsupported_refinement = bool(re.match(
            r'^(?:also|exclude|instead)\b', lowered))
        smaller = bool(re.search(r'\b(?:make|show)\b.*\b(?:smaller|fewer|first\s+\d+)\b',
                                 lowered))
        if unsupported_refinement:
            return {'kind': 'clarify',
                    'reply': ('I can’t safely apply that refinement to the '
                              'previous query. Please restate the complete '
                              'filters you want.')}
        if not replay and not refine and not smaller and not date_refine:
            return False

        intent = query_state.get('intent')
        tool = query_state.get('tool')
        entities = dict(query_state.get('entities') or {})
        filters = dict(query_state.get('filters') or {})
        filter_to_entity = {
            'program_query': 'program_query',
            'program_level': 'program_level', 'campus': 'campus',
            'limit': 'limit', 'threshold': 'threshold',
            'overdue': 'overdue_only', 'date': 'schedule_date',
            'state': 'state', 'no_followup': 'no_followup',
            'open_only': 'open_only',
        }
        if tool == INTENT_FOLLOWUP_LIST:
            filter_to_entity['date'] = 'date_filter'
        for filter_key, entity_key in filter_to_entity.items():
            if filter_key in filters:
                entities[entity_key] = filters[filter_key]
        if date_refine:
            if tool != INTENT_TIMETABLE_VIEW:
                return {'kind': 'clarify',
                        'reply': 'Which ERP query should I apply that date to?'}
            filters['date'] = date_refine.group(1)
            entities['schedule_date'] = date_refine.group(1)
        if refine:
            campus = re.search(r'\b(?:at|from)\s+([\w-]+(?:\s+[\w-]+){0,2})',
                               text, re.I)
            if campus:
                filters['campus'] = re.sub(
                    r'\s+campus$', '', campus.group(1).strip(), flags=re.I)
                entities['campus'] = filters['campus']
            elif intent == INTENT_FEES_SUMMARY and re.search(
                    r'\boverdue\b', text, re.I):
                filters['overdue'] = True
                entities['overdue_only'] = True
            elif intent in (INTENT_PROGRAMS, INTENT_APPLICANT_LIST):
                program = re.search(
                    r'\bonly\s+([A-Za-z][A-Za-z0-9.&/-]{1,24})\s+'
                    r'(?:applicants?|students?|programs?)\b', text, re.I)
                if program:
                    filters['program_query'] = program.group(1).rstrip('.,?!')
                    entities['program_query'] = filters['program_query']
                else:
                    return {'kind': 'clarify',
                            'reply': 'Which filter should I apply to the previous result?'}
            else:
                return {'kind': 'clarify',
                        'reply': 'I can’t safely apply that filter to the previous query. Please restate the full request.'}
        if smaller:
            limit_match = re.search(r'\bfirst\s+(\d{1,2})\b', text, re.I)
            filters['limit'] = min(int(limit_match.group(1)), 10) \
                if limit_match else 5
            entities['limit'] = filters['limit']

        # Restrict replay/refinement to the deterministic Phase 1A read
        # allow-list. This is not a route for arbitrary tool names.
        if tool not in (INTENT_PROGRAMS, INTENT_APPLICANT_LIST,
                        INTENT_FOLLOWUP_LIST,
                        INTENT_GRIEVANCE_SUMMARY,
                        INTENT_FEES_SUMMARY,
                        INTENT_ATTENDANCE_SUMMARY, INTENT_ATTENDANCE,
                        INTENT_FEES, INTENT_GRADES, INTENT_TIMETABLE,
                        INTENT_TIMETABLE_VIEW):
            return {'kind': 'clarify',
                    'reply': 'Please restate the read request so I can verify its scope.'}
        query = {
            'domain': (query_state.get('domain') or 'erp'),
            'operation': query_state.get('operation') or 'read',
            'scope': query_state.get('scope') or 'record',
            'filters': filters,
        }
        if table_replay:
            query['format'] = 'table'
        return {'kind': 'replay', 'parsed': {
            'status': 'supported', 'intent': intent, 'tool': tool,
            'source_label': INTENT_SOURCE_LABEL.get(intent, 'ERP Data'),
            'entities': entities, 'query': query, 'origin': 'context',
        }}

    @api.model
    def _store_query_state(self, context_model, session, parsed, params,
                           data, result_dict):
        query = parsed.get('query') or {}
        filters = dict(query.get('filters') or {})
        for key in ('program_level', 'program_query', 'campus', 'limit',
                    'state', 'no_followup'):
            if params.get(key) is not None and params.get(key) is not False:
                filters[key] = params[key]
        if params.get('date_filter'):
            filters['date'] = params['date_filter']
        entities = {}
        for key in ('student_name', 'semester_term'):
            if params.get(key):
                entities[key] = str(params[key])[:120]
        for key in ('program_query', 'program_level', 'campus', 'limit',
                    'threshold', 'overdue_only', 'state', 'no_followup',
                    'date_filter', 'open_only'):
            if params.get(key) is not None and params.get(key) is not False:
                entities[key] = params[key]
        intent = parsed.get('intent') or ''
        tool = parsed.get('tool') or ''
        scope = query.get('scope') or (
            'aggregate' if intent in (INTENT_FEES_SUMMARY,
                                      INTENT_ATTENDANCE_SUMMARY)
            else 'collection' if intent in (INTENT_PROGRAMS,
                                             INTENT_APPLICANT_LIST,
                                             INTENT_FOLLOWUP_LIST)
            else 'record')
        operation = query.get('operation') or (
            'search' if intent in (INTENT_PROGRAMS,
                                   INTENT_APPLICANT_LIST,
                                   INTENT_FOLLOWUP_LIST) else
            'summary' if scope == 'aggregate' else 'read')
        signature_blob = json.dumps(
            [intent, operation, scope, filters, entities], sort_keys=True)
        data = data if isinstance(data, dict) else {}
        record_ids = []
        for key in ('student_id', 'record_id', 'id'):
            value = data.get(key)
            if isinstance(value, int) and value > 0:
                record_ids.append(value)
        rows = data.get('programs') or data.get('rows') or []
        for row in rows[:20] if isinstance(rows, list) else []:
            if isinstance(row, dict) and isinstance(row.get('id'), int):
                record_ids.append(row['id'])
        context_model.set_query(session, {
            'v': 1, 'intent': intent, 'tool': tool,
            'domain': query.get('domain') or 'erp',
            'operation': operation, 'scope': scope,
            'filters': filters, 'entities': entities,
            'record_ids': list(dict.fromkeys(record_ids))[:20],
            'signature': hashlib.sha256(
                signature_blob.encode('utf-8')).hexdigest(),
            'expires_at': int(time.time()) + 1800,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @api.model
    def _build_params(self, intent, entities):
        params = {}
        if intent in (INTENT_ATTENDANCE, INTENT_FEES, INTENT_GRADES):
            params['student_name'] = entities.get('student_name') or ''
        elif intent == INTENT_TIMETABLE:
            params['semester_term'] = entities.get('semester_term') or ''
        elif intent == INTENT_TIMETABLE_VIEW:
            params['schedule_date'] = entities.get('schedule_date') or 'today'
        elif intent == INTENT_PROGRAMS:
            params['program_level'] = entities.get('program_level') or ''
            params['program_query'] = entities.get('program_query') or ''
            params['campus'] = entities.get('campus') or ''
            params['limit'] = entities.get('limit') or 10
        elif intent == INTENT_APPLICANT_LIST:
            for key in ('state', 'program_query', 'campus', 'limit',
                        'no_followup'):
                if key in entities:
                    params[key] = entities.get(key)
        elif intent == INTENT_FOLLOWUP_LIST:
            params['date_filter'] = entities.get('date_filter') or 'all'
            params['limit'] = entities.get('limit') or 10
        elif intent == INTENT_GRIEVANCE_SUMMARY:
            params['open_only'] = bool(entities.get('open_only'))
        elif intent == INTENT_FEES_SUMMARY:
            params['overdue_only'] = bool(entities.get('overdue_only'))
            params['limit'] = entities.get('limit') or 10
        elif intent == INTENT_ATTENDANCE_SUMMARY:
            params['threshold'] = entities.get('threshold') or False
            params['limit'] = entities.get('limit') or 10
        elif intent == INTENT_ENTITY_SEARCH:
            # The LLM proposal has ALREADY been deterministically
            # re-validated (model in caller's catalog + closed filter
            # grammar) by ai_understanding; pass through the validated
            # entity map unchanged for the registry call.
            for key in ('model', 'filters', 'fields', 'order', 'limit'):
                if key in (entities or {}):
                    params[key] = (entities or {}).get(key)
        elif intent in (INTENT_ENTITY_MODELS, INTENT_ENTITY_ACTIONS):
            pass
        return params

    @api.model
    def _classify_tool_exception(self, exc):
        """Map registry exceptions to the safe error taxonomy.

        Only fixed strings raised by the registry itself are matched
        (never exception payload contents).
        """
        text = str(exc or '').lower()
        if 'rate limit' in text:
            return RATE_LIMITED
        if 'not allowed' in text:
            return AUTHORIZATION_DENIED
        return INTERNAL_ERROR

    def _compose_clarify(self, tool, rows):
        """Bounded clarification question; never selects a candidate."""
        what = ('semester' if tool == INTENT_TIMETABLE else
                'program or campus' if tool in (
                    INTENT_PROGRAMS, INTENT_APPLICANT_LIST) else 'student')
        if isinstance(rows, list) and rows:
            names = ', '.join(str(r) for r in rows)
            return 'Which %s do you mean? I found: %s.' % (what, names)
        return 'Which %s do you mean? I found: %s.' % (what, rows or (
            'several matching records'))

    # ------------------------------------------------------------------
    # Phase 1A deterministic grounded composer (fixed templates)
    # ------------------------------------------------------------------

    @api.model
    def _compose_reply(self, request_text, parsed, data, source_label):
        """Deterministic template first; optionally an LLM-composed,
        grounding-validated reply (flag).  Any LLM failure/violation
        keeps the deterministic template."""
        template = self._compose(parsed['intent'], parsed['tool'], data)
        config = self.env['edicai.ai.config']
        if template == NO_DATA_REPLY or not config.is_llm_composition_enabled():
            return template
        outcome = self.env['edicai.ai.llm.responder'].compose(
            request_text, parsed['tool'], data, source_label)
        if outcome.get('status') == 'ok':
            self._audit('LLM_COMPOSE', decision='allow',
                        reason_code='COMPOSE_OK',
                        metadata={'intent': parsed['intent']})
            return outcome['text']
        self._audit('LLM_COMPOSE', decision='error',
                    reason_code=outcome.get('reason_code') or 'FALLBACK',
                    metadata={'intent': parsed['intent']})
        return template

    def _compose(self, intent, tool, data):
        """Format a tool result. Every number/name comes from ``data``
        (the tool result); nothing is invented here."""
        if tool == INTENT_ATTENDANCE:
            return self._compose_attendance(data)
        if tool == INTENT_FEES:
            return self._compose_fees(data)
        if tool == INTENT_GRADES:
            return self._compose_grades(data)
        if tool == INTENT_TIMETABLE:
            return self._compose_clashes(data)
        if tool == INTENT_TIMETABLE_VIEW:
            return self._compose_timetable_view(data)
        if tool == INTENT_PROGRAMS:
            return self._compose_programs(data)
        if tool == INTENT_APPLICANT_LIST:
            return self._compose_applicant_list(data)
        if tool == INTENT_FOLLOWUP_LIST:
            return self._compose_followup_list(data)
        if tool == INTENT_GRIEVANCE_SUMMARY:
            return self._compose_grievance_summary(data)
        if tool == INTENT_FEES_SUMMARY:
            return self._compose_fee_summary(data)
        if tool == INTENT_ATTENDANCE_SUMMARY:
            return self._compose_attendance_summary(data)
        if tool == INTENT_ENTITY_MODELS:
            return self._compose_entity_models(data)
        if tool == INTENT_ENTITY_ACTIONS:
            return self._compose_entity_actions(data)
        if tool == INTENT_ENTITY_SEARCH:
            return self._compose_entity_search(data)
        return UNKNOWN_REPLY

    def _compose_fee_summary(self, data):
        """Cohort answer: the NUMBER of students with outstanding fees."""
        if data.get('empty'):
            return ('No student in your authorized scope has outstanding '
                    'fees.')
        count = data.get('students_with_outstanding') or 0
        currency = data.get('currency') or ''
        total = self._fmt_amount(
            data.get('total_outstanding') or 0.0, currency)
        lines = [
            ('Students with overdue fees: %s.' if data.get('overdue_only')
             else 'Students with outstanding fees: %s.') % count,
            'Total outstanding: %s.' % total,
        ]
        overdue = data.get('overdue_students') or 0
        if overdue:
            lines.append('⚠ %s student(s) have overdue invoices.' % overdue)
        rows = (data.get('top_students') or [])[:MAX_LIST_ROWS]
        for row in rows:
            lines.append('• %s: %s outstanding (%s invoice(s))' % (
                row.get('student'),
                self._fmt_amount(row.get('outstanding') or 0.0, currency),
                row.get('invoice_count')))
        if count > len(rows):
            lines.append('(showing the %s largest of %s.)' % (
                len(rows), count))
        return '\n'.join(lines)

    def _compose_attendance_summary(self, data):
        """Cohort answer: the NUMBER of students below the policy."""
        if data.get('empty'):
            return ('No student in your authorized scope is below the '
                    'attendance policy.')
        count = data.get('students_short') or 0
        threshold = data.get('threshold')
        title = ('Students below %s%% attendance: %s.' % (threshold, count)
                 if threshold else
                 'Students below the attendance policy: %s.' % count)
        lines = [title]
        rows = (data.get('worst_students') or [])[:MAX_LIST_ROWS]
        for row in rows:
            minimum = row.get('min_required')
            minimum_text = (' (policy %s%%)' % minimum) if minimum else ''
            lines.append('• %s: %s%%%s' % (
                row.get('student'), row.get('percentage'), minimum_text))
        if count > len(rows):
            lines.append('(showing the %s lowest of %s.)' % (
                len(rows), count))
        if data.get('truncated'):
            lines.append('(The source scan reached its row bound; the count is based on all authorized matching rows.)')
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Phase G4 — generic entity layer composers
    # ------------------------------------------------------------------

    def _compose_entity_models(self, data):
        rows = (data.get('entities') or [])[:MAX_LIST_ROWS]
        if not rows:
            return NO_DATA_REPLY
        lines = ['You can ask me about (by role):']
        for row in rows:
            label = row.get('label') or row.get('model') or ''
            ops = ', '.join(row.get('ops') or [])
            line = '• %s' % label
            if ops:
                line += ' [%s]' % ops
            lines.append(line)
        total = data.get('count') or len(rows)
        if total > len(rows):
            lines.append('and %d more.' % (total - len(rows)))
        lines.append("Ask \"list <topic>\" or filter with specifics.")
        return '\n'.join(lines)

    def _compose_entity_actions(self, data):
        rows = (data.get('actions') or [])[:MAX_LIST_ROWS]
        if not rows:
            return 'No declared record actions are available for your role.'
        lines = ['Declared record actions you can confirm:']
        for row in rows:
            label = row.get('label') or row.get('action') or ''
            model = row.get('model') or ''
            line = '• %s (%s)' % (label, model) if model else '• %s' % label
            if row.get('executable') is False and row.get('reason_code'):
                line += ' [not runnable: %s]' % row.get('reason_code')
            lines.append(line)
        total = data.get('count') or len(rows)
        if total > len(rows):
            lines.append('and %d more.' % (total - len(rows)))
        return '\n'.join(lines)

    def _compose_entity_search(self, data):
        if data.get('empty'):
            return NO_DATA_REPLY
        label = data.get('label') or data.get('model') or 'Records'
        count = data.get('count') or 0
        total = data.get('total_in_scope') or count
        rows = data.get('rows') or []
        lines = ['%s: %d found' % (label, total)]
        if total > count and count:
            lines[0] += ' (showing up to %d)' % count
        for row in rows[:MAX_LIST_ROWS]:
            row = row or {}
            name = row.get('name') or row.get('display_name')
            rid = row.get('id')
            if name:
                lines.append('• %s [%s]' % (name, rid))
            elif rid is not None:
                lines.append('• id %s' % rid)
            else:
                # Avoid dumping all columns; show a compact id-first view.
                keys = [k for k in row.keys() if k != 'id'][:3]
                if keys:
                    preview = ', '.join(
                        '%s=%s' % (k, row.get(k)) for k in keys)
                    lines.append('• %s: %s' % (rid if rid is not None
                                                else '-', preview))
        if len(rows) > MAX_LIST_ROWS:
            lines.append('(showing first %d rows.)' % MAX_LIST_ROWS)
        return '\n'.join(lines)

    @api.model
    def _fmt_amount(self, value, currency):
        """Format a monetary amount without ever inventing a value."""
        try:
            text = '%s' % ('{:,.0f}'.format(float(value)))
        except (TypeError, ValueError):
            return 'an unknown amount'
        return '%s %s' % (text, currency) if currency else text

    def _compose_attendance(self, data):
        if data.get('empty'):
            return NO_DATA_REPLY
        lines = []
        student = data.get('student')
        lines.append('Attendance summary for %s:' % student)
        overall = data.get('overall_percentage')
        if overall is not None and overall is not False:
            lines.append('Overall: %s%%' % overall)
        rows = (data.get('courses') or [])[:MAX_LIST_ROWS]
        for row in rows:
            lines.append(
                '• %s: %s%% '
                '(held %s, present %s, absent %s)' % (
                    row.get('course_name'), row.get('percentage'),
                    row.get('sessions_held'), row.get('sessions_present'),
                    row.get('sessions_absent')))
        if data.get('shortage'):
            count = sum(
                1 for row in (data.get('courses') or [])
                if row.get('shortage_alert'))
            lines.append('⚠ Short attendance was flagged in %s '
                         'course(s).' % count)
        return '\n'.join(lines)

    def _compose_fees(self, data):
        if data.get('empty'):
            return NO_DATA_REPLY
        outstanding = data.get('grand_outstanding') or 0.0
        currency = data.get('currency') or ''
        if outstanding == 0:
            lines = ['No outstanding fees were found.']
        else:
            display = self._fmt_amount(outstanding, currency)
            lines = ['Outstanding fees: %s.' % display]
        overdue_semesters = 0
        for bucket in (data.get('semesters') or [])[:MAX_LIST_ROWS]:
            if (bucket.get('amount_outstanding') or 0) == 0:
                continue
            semester = bucket.get('semester_name') or 'Semester'
            amount = self._fmt_amount(
                bucket.get('amount_outstanding'), currency)
            over = bucket.get('overdue_count') or 0
            if over:
                overdue_semesters += over
            lines.append('• %s: %s outstanding (open %s%s)' % (
                semester, amount, bucket.get('open_count'),
                ', %s overdue' % over if over else ''))
        if outstanding and overdue_semesters:
            lines.append('⚠ %s overdue invoice(s) found.' % overdue_semesters)
        return '\n'.join(lines)

    def _compose_grades(self, data):
        if data.get('empty'):
            return NO_DATA_REPLY
        lines = ['Grade summary for %s:' % data.get('student')]
        cgpa = data.get('cgpa')
        if cgpa is not None and cgpa is not False:
            lines.append('CGPA: %s' % cgpa)
        average = data.get('average_percentage')
        if average is not None and average is not False:
            lines.append('Average percentage: %s%%' % average)
        for row in (data.get('semesters') or [])[:MAX_LIST_ROWS]:
            lines.append(
                '• %s: GPA %s (credits attempted %s, earned %s) — %s' % (
                    row.get('semester'), row.get('gpa'),
                    row.get('credits_attempted'),
                    row.get('credits_earned'),
                    row.get('result_status') or '—'))
        return '\n'.join(lines)

    def _compose_clashes(self, data):
        scanned = data.get('scanned_entries') or 0
        count = data.get('clash_count') or 0
        if scanned == 0:
            return NO_DATA_REPLY
        lines = []
        if count:
            lines.append('Clashes found: %s '
                         '(scanned %s timetable entries).' % (
                             count, scanned))
            reasons = (data.get('clashes') or [])[:MAX_LIST_ROWS]
            lines.extend('• %s' % reason for reason in reasons)
            if data.get('truncated'):
                lines.append('(List truncated — showing the first '
                             'entries only.)')
        else:
            lines.append(
                'No clashes were found by the scan of %s timetable '
                'entries.' % scanned)
        return '\n'.join(lines)

    def _compose_timetable_view(self, data):
        rows = data.get('entries') or []
        date = data.get('date') or 'the requested date'
        if not rows:
            return "I couldn't find timetable entries for %s in your authorized scope." % date
        lines = ['Timetable entries for %s (%s found):' %
                 (date, data.get('count') or len(rows))]
        for row in rows[:MAX_LIST_ROWS]:
            lines.append('• %s %s–%s — %s; %s; %s' % (
                row.get('day_label') or '', row.get('start_time') or '?',
                row.get('end_time') or '?', row.get('course_name') or
                row.get('offering_name') or 'Class',
                row.get('room_name') or 'room not listed',
                row.get('instructor_name') or 'instructor not listed'))
        if data.get('count', 0) > len(rows):
            lines.append('(Showing %d of %d matching entries.)' %
                         (len(rows), data['count']))
        return '\n'.join(lines)

    def _compose_programs(self, data):
        programs = (data.get('programs') or [])
        if data.get('empty') or not programs:
            filters = data.get('filters') or {}
            requested = [
                '%s %s' % (label, filters[key])
                for key, label in (('program', 'program'),
                                   ('level', 'level'),
                                   ('campus', 'campus'))
                if filters.get(key)]
            if requested:
                criteria = [filters.get(key) for key in (
                    'program', 'level', 'campus') if filters.get(key)]
                return ("I couldn't find an admission program matching "
                        '%s.' % ', '.join(criteria))
            return (
                "I don't have enough information to answer that — "
                "no active admission programs were found.")
        total = data.get('total_count')
        total = len(programs) if total is None else total
        lines = ['Active admission programs found: %s.' % total]
        for row in programs[:MAX_LIST_ROWS]:
            campuses = row.get('campuses') or []
            campuses_text = ', '.join(campuses) if campuses else '—'
            line = '• %s (%s' % (
                row.get('name'), row.get('code') or 'no code')
            if row.get('level'):
                line += ', %s' % row['level']
            line += ') — campuses: %s' % campuses_text
            fee = row.get('tuition_per_semester')
            if fee:
                line += ' — tuition %s per semester' % fee
            lines.append(line)
        if data.get('possibly_truncated'):
            lines.append('(Showing %d of %d matching programs.)' %
                         (len(programs), total))
        return '\n'.join(lines)

    def _compose_applicant_list(self, data):
        rows = data.get('rows') or []
        total = data.get('total_count') or 0
        filters = data.get('filters') or {}
        if not rows:
            if filters.get('state') == 'pending':
                return ('“Pending” is not a single application stage. '
                        'Which stage do you mean?')
            requested = [
                '%s %s' % (label, filters[key])
                for key, label in (('program', 'program'),
                                   ('campus', 'campus'),
                                   ('state', 'stage'))
                if filters.get(key)]
            if requested:
                return "I couldn't find an applicant matching %s." % \
                    ' and '.join(requested)
            return "I couldn't find a matching applicant record."
        if filters.get('state'):
            heading = 'Applicants in %s stage: %d.' % (
                filters['state'].replace('_', ' '), total)
        elif filters.get('no_followup'):
            heading = 'Applicants without an open follow-up: %d.' % total
        else:
            heading = 'Applicants found: %d.' % total
        lines = [heading]
        for row in rows[:MAX_LIST_ROWS]:
            lines.append('• %s (%s) — %s; %s; %s' % (
                row.get('name') or 'Applicant',
                row.get('application_number') or 'application number not listed',
                (row.get('state') or '').replace('_', ' '),
                row.get('program') or 'program not listed',
                row.get('campus') or 'campus not listed'))
        shown = min(len(rows), MAX_LIST_ROWS)
        if total > shown:
            lines.append('(Showing %d of %d matching applicants.)' %
                         (shown, total))
        return '\n'.join(lines)

    def _compose_followup_list(self, data):
        rows = data.get('rows') or []
        total = data.get('total_count') or 0
        date_filter = data.get('date_filter') or 'all'
        if not rows:
            return "I couldn't find a matching follow-up in your authorized scope."
        label = {'today': "today's", 'yesterday': "yesterday's",
                 'overdue': 'overdue', 'all': 'pending'}[date_filter]
        lines = ['%s follow-ups: %d.' % (label.capitalize(), total)]
        for row in rows[:MAX_LIST_ROWS]:
            lines.append('• %s (%s) — %s; due %s; assigned to %s' % (
                row.get('applicant') or 'Applicant',
                row.get('application_number') or 'application number not listed',
                row.get('summary') or 'Follow-up',
                row.get('date_deadline') or 'date not listed',
                row.get('assigned_to') or 'unassigned'))
        if total > min(len(rows), MAX_LIST_ROWS):
            lines.append('(Showing %d of %d matching follow-ups.)' %
                         (min(len(rows), MAX_LIST_ROWS), total))
        return '\n'.join(lines)

    @api.model
    def _compose_data_table(self, data):
        """Render a bounded table from retrieved tool rows only."""
        rows = []
        for key in ('rows', 'programs', 'worst_students', 'top_students',
                    'entries'):
            candidate = data.get(key)
            if isinstance(candidate, list) and candidate:
                rows = candidate
                break
        if not rows and isinstance(data.get('by_category'), dict):
            rows = [{'category': key, 'count': value}
                    for key, value in sorted(data['by_category'].items())]
        if not rows:
            return NO_DATA_REPLY
        allowed = ('name', 'student', 'applicant', 'program', 'campus',
                   'state', 'application_number', 'percentage', 'offering',
                   'outstanding', 'invoice_count', 'date_deadline',
                   'summary', 'start_time', 'end_time', 'room_name',
                   'category', 'count')
        columns = [key for key in allowed
                   if any(isinstance(row, dict) and key in row
                          for row in rows[:MAX_LIST_ROWS])]
        if not columns:
            return NO_DATA_REPLY
        lines = ['| ' + ' | '.join(columns) + ' |',
                 '| ' + ' | '.join(['---'] * len(columns)) + ' |']
        for row in rows[:MAX_LIST_ROWS]:
            values = []
            for column in columns:
                value = row.get(column, '') if isinstance(row, dict) else ''
                text = str(value if value is not None else '')
                values.append(text.replace('|', '\\|').replace('\n', ' ')[:120])
            lines.append('| ' + ' | '.join(values) + ' |')
        total = (data.get('total_count') or data.get('count') or
                 data.get('students_short') or
                 data.get('students_with_outstanding'))
        if isinstance(total, int) and total > min(len(rows), MAX_LIST_ROWS):
            lines.append('Showing %d of %d matching rows.' %
                         (min(len(rows), MAX_LIST_ROWS), total))
        return '\n'.join(lines)

    def _compose_grievance_summary(self, data):
        if data.get('empty'):
            return 'No grievance records were found in your authorized scope.'
        lines = ['Grievances found: %d.' % (data.get('total_count') or 0)]
        for category, count in sorted((data.get('by_category') or {}).items()):
            lines.append('• %s: %s' % (category, count))
        states = data.get('by_state') or {}
        if states:
            lines.append('By status: ' + ', '.join(
                '%s: %s' % (state.replace('_', ' '), count)
                for state, count in sorted(states.items())))
        return '\n'.join(lines)
