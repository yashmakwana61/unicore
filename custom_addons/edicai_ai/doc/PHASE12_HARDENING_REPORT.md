# Phase 12 — Conversational ERP Hardening Report (§34)

**Module:** `edicai_ai` (EDICAI SIS, Odoo 19.0)
**Scope:** Remediation of the 100-case manual conversational-ERP test workbook,
P0-P3 root causes, and regression hardening while preserving every Phase 0-5
safety guarantee.
**Report date:** 2026-10-26
**Decision:** `READY FOR PHASE 6: NO`

---

## 1. Executive summary

The Phase 12 work closed the shared root causes behind the P0-P3 defects found in
the manual workbook and added a bounded, deterministic conversational query layer
plus §31 regression coverage. All **automated** Phase 0-5 suites are green on the
dedicated test database:

| Suite | Command (summary) | Result |
|---|---|---|
| `edicai_ai` (full) | `odoo-bin -d odoo_test_unit --test-tags /edicai_ai` | **606 tests - 0 failed, 0 errors** |
| Broader EDICAI (touched modules) | `--test-tags /edicai_admission,/edicai_attendance,/edicai_fees,/edicai_grading,/edicai_grievance` | **90 tests - 0 failed, 0 errors** |

The final readiness gate is **NO** because the defining requirement - a full
manual re-execution of the 100 conversational cases - has **not** been completed.
The hardened workbook therefore records **92 NOT RUN** and **8 BLOCKED**
(environment-limited) retest rows. Automated unit/HTTP coverage is not, and must
not be presented as, a manual pass.

---

## 2. Method & reproduction

Tests are Odoo `TransactionCase` / `HttpCase` suites and must run through
`odoo-bin`, not bare pytest. The repository `odoo.conf` pins
`dbfilter = ^edicai$`; when running tests against `odoo_test_unit` the HTTP
harnesses would otherwise resolve to the `edicai` database, producing spurious
registry failures. The canonical invocation overrides the filter:

```bash
DB=odoo_test_unit \
TAGS='/edicai_ai' \
DNFILTER='^odoo_test_unit$' \
LOG=/tmp/phase12_remediation14.log \
bash _run_odoo_test.sh
```

`_run_odoo_test.sh` wraps `odoo-bin -c odoo.conf -d <DB> --test-tags <TAGS>
--db-filter <DNFILTER> --stop-after-init --log-level=test`.

> Note: A naive run **without** `--db-filter ^odoo_test_unit$` reported 44
> failures / 10 errors. Every one was an environment artifact (HTTP requests
> hitting the `edicai` DB and racing the test registry). With the filter override
> the same suite is 606/0. This is documented so future runs are not misread as
> code regressions.

---

## 3. Root-cause remediation (P0-P3)

| Bug | Priority | Root cause | Remediation |
|---|---|---|---|
| BUG-011 | P0 | Approval could execute after the target changed materially | Material snapshot + `material_hash` frozen at submission; re-compared at approval; mismatch → `STATUS_INVALIDATED`, `APPROVAL_INVALIDATED` audit, nothing executed |
| BUG-010 | P0 | Stale workflow preview/plan could execute after state change | Preview/plan hash captured; state change invalidates preview; `WORKFLOW_INVALIDATED` audit; re-preview required |
| BUG-006 | P0 | User filters were silently dropped | Bounded session `query_state_json`; filter-safety gate rejects unsupported filters (`QUERY_FILTER_REJECTED`) instead of discarding; no constraint is ever silently lost |
| BUG-013 | P1 | Proactive insights never resolved/refreshed | Lifecycle resolves stale insights when evidence clears; `PROACTIVE_SIGNAL_RESOLVED`; "why" stays fresh |
| BUG-005 | P1 | No short-term conversation memory | `edicai.ai.chat.session.query_state_json` bounded state + deterministic follow-up resolution (`explain`, `clarify`, `replay`) |
| BUG-004 | P1 | Read coverage gaps (collection/aggregate/record) | New read intents + tools + catalogue phrases (§5) |
| BUG-003 | P1 | Collection/aggregate queries mishandled | Explicit scope + `record_ids` replay; deterministic list rendering (`MAX_LIST_ROWS`) |
| BUG-007 | P1 | "timetable view" conflated with "clash check" | Split `timetable.view` from `timetable.clash_check` |
| BUG-001 | P2 | Indian mobile numbers not extracted reliably | `_normalized_indian_mobile` normaliser + ambiguous-phone handling |
| BUG-002 | P2 | Single-word names failed to resolve | Single-word entity resolution with explicit ambiguity → clarification, never a guess |
| - | P2/P3 | Invalid dates accepted; workflow quantity extraction; approval-request veto bypass; stale duplicate summary; faculty fee cohort read | Targeted validations and guards (see files below) |

**Duplicate-reply handling:** duplicate confirmation now replies
deterministically ("Already done... No operations were repeated.") with
`WORKFLOW_DUPLICATE` / `APPROVAL_DUPLICATE` audit events, so repeated "confirm"
turns are idempotent and never re-execute.

---

## 4. Conversation state (bounded, non-authoritative)

- Stored in `edicai.ai.chat.session.query_state_json`, **separate** from the
  legacy `context_json` (leaves `test_ai_context.py` schema untouched).
- Holds only: last intent, normalised filters, resolved scope, bounded
  `record_ids`, row cap, and the last rendered shape. **No** business payloads,
  **no** secrets, **no** provider content.
- It is **never** an authorization cache: every execution re-checks ACLs, record
  rules, company/campus isolation, and tool allow-list at execution time.
- Bounded: row caps (`MAX_LIST_ROWS`) and a fixed filter whitelist prevent
  unbounded growth or state-driven privilege escalation.
- Follow-up resolution is deterministic: `explain` (why this result),
  `clarify` (ambiguous entity), `replay` (repeat/format), all bounded.

---

## 5. Intent & tool architecture (reads / aggregates / records)

Extended intent grammar exposes **domain / operation / scope / filters /
entities** and adds deterministic extraction for program, campus, state,
overdue/threshold, follow-up date window, and "open" grievance.

New read intents and registered conversational tools:

| Intent constant | Value | Purpose |
|---|---|---|
| `INTENT_APPLICANT_LIST` | `admission.applicant_list` | List/aggregate applicants with filters |
| `INTENT_FOLLOWUP_LIST` | `admission.followup_list` | Applicants with/without follow-ups |
| `INTENT_PROGRAMS` | `admission.program_search` | Program availability (campus-aware) |
| `INTENT_FEES` | `fees.fee_status` | Single-student fee status |
| `INTENT_FEES_SUMMARY` | `fees.fee_summary` | Outstanding/overdue cohort aggregate |
| `INTENT_ATTENDANCE` | `attendance.shortage_report` | Attendance shortage list (threshold) |
| `INTENT_ATTENDANCE_SUMMARY` | `attendance.shortage_summary` | Shortage aggregate |
| `INTENT_GRADES` | `grading.grade_summary` | Grade list/summary |
| `INTENT_TIMETABLE_VIEW` | `timetable.view` | "What is my timetable" |
| `INTENT_TIMETABLE` | `timetable.clash_check` | "Timetable clashes" |
| `INTENT_GRIEVANCE_SUMMARY` | `grievance.summary` | Recent/open grievance summary |
| `INTENT_ENTITY_SEARCH` | `entity.search` | Generic grounded read |
| `INTENT_ENTITY_MODELS` | `entity.list_models` | Discovery (no provider call) |
| `INTENT_ENTITY_ACTIONS` | `entity.list_actions` | Action discovery |

All are registered in the tool registry and `CONVERSATIONAL_TOOL_SPEC`, with ACL
gating, company/campus scoping, and audit on every execution.

---

## 6. Entity resolution

- Indian mobiles normalised via `_normalized_indian_mobile` (handles spacing,
  `+91`, leading `0`), with explicit handling when a number matches more than one
  record → clarification, never an arbitrary pick.
- Single-word names now resolve; ambiguous single-word names return a bounded
  clarification instead of guessing.
- Entity resolution is always scoped by the caller's record rules and
  company/campus, and re-verified at execution (TOCTOU safe).

---

## 7. Filter safety

- A filter-safety gate runs in the orchestrator before any query executes.
- Supported filters are applied; unsupported/unknown filters are **rejected**
  with `QUERY_FILTER_REJECTED` (decision `deny`) - the turn fails closed rather
  than silently dropping the user's constraint.
- `QUERY_CONTEXT_EXPLAINED` (`allow`) records "explain" turns.
- Result sets are row-capped; replay reuses the bounded, validated state.

---

## 8. Workflow & approval integrity

- **Approval material change:** frozen snapshot + hash; any material field change
  invalidates and audits (`APPROVAL_INVALIDATED`) before the canonical
  `action_approve` is ever reached. Non-material chatter changes do not
  invalidate.
- **Stale workflow plan:** preview/plan hash + invalidation
  (`WORKFLOW_INVALIDATED`) on state/permission change; execution requires a fresh
  preview.
- **Self-approval** blocked; cross-company approvers are denied and blind;
  duplicate approvals are idempotent (`APPROVAL_DUPLICATE`).
- **Audit taxonomy** now includes `WORKFLOW_INVALIDATED`, `APPROVAL_INVALIDATED`,
  `QUERY_FILTER_REJECTED`, `QUERY_CONTEXT_EXPLAINED` (all in `EVENT_TYPES` and
  `_DECISION_BY_EVENT`).

---

## 9. Proactive resolution lifecycle

- Signals are informational only and never mutate business records.
- When the underlying evidence clears, the insight resolves
  (`PROACTIVE_SIGNAL_RESOLVED`) rather than lingering as stale advice.
- "Why" explanations remain available and fresh after resolution.
- Lifecycle is bounded and audited (`DETECTED → SURFACED → EXPLAINED →
  DISMISSED/RESOLVED`).

---

## 10. Security invariants preserved (Phase 0-5)

- No `sudo` on any AI execution path.
- No arbitrary code/SQL execution; read tools are allow-listed and parameterised.
- The LLM never grants permissions; it may only *propose*, and deterministic
  validation refuses unknown models/entities/filters.
- Conversation/query context is never an authorization cache - re-checked at
  execution.
- Tool allow-list and intent contracts enforced.
- Company/campus isolation and record rules enforced on reads and writes.
- Durable audit trail (redacted metadata only; no conversation/payload content).
- Idempotency: duplicate confirmations/approvals never re-execute.

---

## 11. Files changed (high level)

New/expanded `edicai_ai` models: `ai_context.py`, `ai_intent.py`,
`ai_orchestrator.py`, `ai_tools_conversational.py`, `ai_policy.py`,
`ai_approval.py`, `ai_workflow.py`, `ai_action_resolve.py`,
`ai_question_catalogue.py`, `ai_audit.py`, `ai_tool_registry.py`, and the
Phase 0-5 models.

Cross-module read surfaces: `edicai_admission` (campus-aware program/applicant
search), `edicai_attendance` (threshold/limit), `edicai_timetable`
(`view_schedule`), `edicai_grievance` (summary), `edicai_fees`, `edicai_grading`.

Tests: `edicai/custom_addons/edicai_ai/tests/` (Phase 0-5 harnesses plus new
regression tests for query filtering, entity resolution, workflow/approval
invalidation, proactive resolution, and follow-up resolution).

Tooling/artifacts: `_build_hardened_workbook.py` (workbook generator),
`_run_odoo_test.sh` (documented test runner),
`Conversational_ERP_Manual_Testing_Sheet_HARDENED.xlsx`.

---

## 12. Automated test evidence

- `edicai_ai` full module: **606 tests, 0 failed, 0 errors**
  (`/tmp/phase12_remediation14.log`).
- Broader touched modules: **90 tests, 0 failed, 0 errors**
  (`/tmp/phase12_broad_final.log`).
- Previously flagged cases explicitly re-verified green within the run:
  - `test_ai_approval_lifecycle.test_18a_material_field_change_invalidates_pending_approval`
  - `test_ai_evalset.test_55_generic_proposals`
  - `test_ai_orchestrator_1b.test_20_repeat_result_as_table_reexecutes_grounded_query`

---

## 13. Manual regression results (100-case workbook)

Source: `Conversational_ERP_Manual_Testing_Sheet_TESTED.xlsx`
Output: `Conversational_ERP_Manual_Testing_Sheet_HARDENED.xlsx`
(original verdicts preserved; retest column added; nothing inferred from unit
tests).

| Bucket | Count |
|---|---|
| Manual cases | 100 |
| **Original** PASS | 51 |
| **Original** FAIL | 36 |
| **Original** PARTIAL | 5 |
| **Original** BLOCKED | 8 |
| **Retest** PASS | 0 |
| **Retest** FAIL | 0 |
| **Retest** PARTIAL | 0 |
| **Retest** BLOCKED | 8 |
| **Retest** NOT RUN | 92 |

Manual pass rate: **not available - no full manual rerun**.

### Environment blockers

- **ENV-001** - Multi-company isolation could not be exercised end-to-end; the
  available database is effectively single-company.
- **ENV-002** - No genuinely concurrent browser harness; true concurrency
  (double-click/parallel approvals) could not be manually reproduced.

### Definition-of-done gap

The automated suites prove the code paths; they do **not** substitute for the
manual conversational walkthrough. 92 cases remain unexecuted, so the manual
regression is incomplete and the readiness gate cannot pass.

---

## 14. Residual risks / follow-ups

1. Execute the full 100-case manual rerun in a multi-company + concurrent
   harness and populate the `Hardening Retest` sheet with evidence.
2. Re-confirm the 8 BLOCKED cases once ENV-001/ENV-002 are available.
3. Keep the `--db-filter ^odoo_test_unit$` override in CI so HTTP harnesses do
   not resolve to the production DB.
4. Consider promoting `_run_odoo_test.sh` into CI tooling.

---

## 15. Final decision

**READY FOR PHASE 6: NO**

Rationale: automated Phase 0-5 regression is green (606 + 90 tests, 0 failures),
and the P0-P3 root causes are remediated with preserved security invariants - but
the mandated manual 100-case rerun is incomplete (92 NOT RUN, 8 BLOCKED under
ENV-001/ENV-002). Manual verification is a hard gate; it is not satisfied.

---

## Appendix A — Operational fix: chat "unexpected error" on a greeting

**Symptom.** Sending `hello` in the chat UI showed the front-end message
"An unexpected error occurred. Please try again." The string is emitted
client-side (`static/src/js/edicai_ai_chatbot.js`) when the JSON-RPC call itself
is rejected, i.e. the server returned a 500.

**Root cause.** The `edicai` database had never been upgraded after the
Phase 12 schema change, so the column backing
`edicai.ai.chat.session.query_state_json` did not exist:

```
psycopg2.errors.UndefinedColumn:
  column edicai_ai_chat_session.query_state_json does not exist
```

Any read of a chat session (including `_auto_title` and the session list)
therefore raised and the whole request failed. The dedicated test database had
been upgraded, which is why automation stayed green while the live database
failed.

**Fix.**
1. Schema: upgraded the module on the production database
   (`odoo-bin -c odoo.conf -d edicai -u edicai_ai --stop-after-init`) and
   confirmed `query_state_json` now exists. Module at `19.0.1.14.0`.
2. UX: added a deterministic **bare-greeting** branch in
   `edicai.ai.orchestrator.answer_turn` (`_is_greeting` / `_GREETING_RE`,
   `GREETING_REPLY`). It runs after pending-action/proactive handling and
   before any LLM understanding, so it cannot hijack a workflow, a proactive
   signal, or a real request, and it never spends a provider call. A greeting
   followed by a request (`hello, show me my fee status`) is deliberately
   **not** matched and routes to the normal intent grammar.

**Verification (real HTTP round-trip through `/edicai_ai/chat/send`).**

| Message | HTTP | Status | Routed tool | Greeting? |
|---|---|---|---|---|
| `hello` | 200 | answered | — | yes |
| `hello, show me my fee status` | 200 | clarify | `fees.fee_status` | no |
| `hi please list admission programs` | 200 | error (ACL, no leak) | `admission.program_search` | no |

The full `edicai_ai` suite remained green after the change: **606 tests, 0
failed, 0 errors**. The readiness decision above is unchanged — this appendix
fixes a live schema/UX defect; it does not substitute for the missing manual
rerun.

