# Edicai AI — Generic Tool Layer Plan (Phase G1–G5)

**Status:** **G1 SHIPPED** (2026-10-22), **G2 SHIPPED** (2026-10-23)
and **G3 SHIPPED** (2026-10-24).

* **G1** — deployed to prod as `edicai_ai 19.0.1.11.0` (upgrade logs
  `odoo_upgrade8/9.log`, 0 CRITICAL). Local suite 513/513 green
  (was 493; +20 entity-layer tests).
* **G2** — deployed to prod as `edicai_ai 19.0.1.12.0` (upgrade logs
  `odoo_upgrade10.log` + `odoo_upgrade11.log`, 0 CRITICAL, HTTP 200).
  Local suite **530/530 green** (+17 G2 tests). **Live-prod verified end
  to end**: `entity.create` staged a preview (nothing written), the chat
  turn `confirm <ref>` executed it as the confirming user (student
  created with exactly the supplied fields), a second confirm was a
  no-op ("Already done"), `entity.update` changed only the given
  columns, and the deny path (entity without a write grant) returned the
  sanitized `You are not allowed to use this AI operation.` The
  temporary verification state (grant, flag, test records, temp user)
  was reverted; prod is back to deny-by-default (flag absent, every
  policy `ops` read-only, `write_groups` empty, 0 pending rows).

G1 delivered: `edicai.ai.entity.policy` + `edicai.ai.entity.action`
(G3 surface, manager ACL), 5 seeded entities, the generic read floor
`entity.list_models / describe / search / read / aggregate`
(policy-gated, no sudo, PII masking, closed filter grammar, row caps),
and the internal `aggregate_for_policy` engine shared with the Phase 13
cohort tools — `fees.fee_summary` is now a THIN WRAPPER over the generic
engine with a byte-identical reply template (attendance keeps its
copilot for now). Live-prod verified: entity calls return masked PII
(`mobile ***********01`), the aggregate counts cohorts, and the chat
replies keep the exact Phase 13 format. Odoo-19 implementation notes:
`models.Constraint` replaces `_sql_constraints`, `res.users` groups is
`group_ids` (recordset union), `_read_group` returns m2o groups as
RECORDSETS (label fixed), ACL CSVs must not contain comment lines, and
seed data may pre-register models from optional modules (existence is
enforced at USE time, not seed time).

G2 delivered (generic, not per-app): two fixed capability tools —
`entity.create` / `entity.update` (plus `entity.list_actions`, the G3
read surface) — parameterized ONLY by the declarative
`edicai.ai.entity.policy`, for **any** entity a manager grants. They never
write: they validate and stage ONE `edicai.ai.pending.action` (preview).
The write itself happens only in the existing locked
`confirm_and_execute` → `_execute_entity_locked`, exactly once, as the
confirming user (no sudo), with a savepoint, ACL mapping, policy
re-authorization, a verification re-read, and a reason-coded audit event
for every branch. Writable fields are derived from the model (simple
types only, minus identity/company/readonly/computed), required-with-
default fields may be omitted, and types are coerced and size-capped.
Two gates: the master flag `edicai_ai.action_entity_write_enabled`
(default OFF) and the per-entity `write_groups` grant; both are
re-checked at confirm time (revocation between preview and confirm
denies, leaving the row retryable). Delete is not offered at all.
Additional Odoo-19 notes from G2: `record.exists()` is a **raw SQL**
check that does NOT apply record rules (use `check_access('read')`
before reading a foreign row — otherwise a foreign chat session leaks a
raw `AccessError`), `fields_get()` carries no `'default'` key (read
`_fields[name].default`), `noupdate="1"` belongs on the `<data>` element
(never on `<record>`), and Odoo business constraints fire at CREATE time,
not staging time — a `ValidationError` there is reported as
`VALIDATION_FAILED` and returns the row to `draft` (retryable), never
`failed`.

G3 delivered (declared record actions, still generic): ONE tool —
`entity.execute` — whose behaviour is fixed in code and parameterized
only by declarative data. TWO independent gates must both pass: the
DATA gate (an enabled `edicai.ai.entity.action` row + a NEW per-entity
`execute_groups` grant + the master flag
`edicai_ai.action_entity_execute_enabled`, default OFF and independent
of the G2 write flag) and the CODE gate (the fixed registry
`models/ai_entity_actions.py:ENTITY_ACTIONS` keyed `(model, method)`).
A data row naming any undeclared method (`write`, `unlink`, `sudo`,
`create`) is dead data and is refused with no side effect; the executed
method name is a code literal, never the payload string. Like G2, the
tool never executes at call time: it stages ONE pending action, and the
confirming user's `confirm` runs the ERP's own state-machine method —
locked, exactly once, no sudo — then verifies by re-reading the
declared state column (already-in-state is a clean no-op). Params are a
closed per-action grammar (`note` ≤ 500 → `verification_notes` is the
only shipped one). Business rejections return the row to `draft`
(retryable); ACL denials are sanitized `denied`.

Original plan text follows.
**Supersedes:** the "one static tool per question type" scaling model.
**Constraint:** every existing security guarantee of the static tools must
survive — no sudo anywhere, record rules always apply, closed allow-lists,
group gate, rate limit, durable audit, confirmation for every write.

---

## 1. Why the static tools existed (and why they must evolve)

Phase 1A shipped five *named* tools because a fixed allow-list made the
policy **provable**: every tool had a hardcoded contract (risk level,
groups, schema), intent routing was deterministic, and no LLM output was
ever trusted with an execution decision.

That scaling model is correct for **10 tools** and dead by **100**:
each new ERP capability = new tool + contract + tests + catalogue
phrasings + router updates. Phase 13's aggregates were the third such
duplication (per-student fees → cohort fees; per-student attendance →
cohort attendance). The repeating pattern is a *generic* one:

| requested | really asked |
|---|---|
| "fees of Aarav" | search/read on entity |
| "how many students owe" | aggregate on entity |
| "create an inquiry" | create on entity |
| "mark the invoice paid" | execute a record action |
| "what can I do with applicants" | describe the entity |

So the plan: **nine tools, parameterized by a declarative entity policy
registry** — the allow-list becomes a *configuration table*, not code.

---

## 2. Target architecture

```
User question
   │
   ├─ deterministic intent matcher (catalogue)          fast path
   ├─ or LLM proposal (ai_understanding)                rich path
   ▼
GENERIC PROPOSAL:  {op: search|read|aggregate|create|update|...
                    model, filters, fields, ids, data, action}
   ▼
POLICY VALIDATION  (deterministic — never trusts the LLM)
   ├─ model in ENTITY_POLICY allow-list?
   ├─ op allowed on that model? field allow-list? PII mask?
   ├─ caller's group grant? row cap? record rules (no sudo)?
   ▼
EXECUTION (registry.execute_tool — rate limit + audit + redaction remain)
   ▼
GROUNDED COMPOSER (existing _compose / llm.responder, same rules)
```

The user-visible pieces of the flow that already work (catalogue routing,
clarify, QA toolkit, Workspace UI, audit) are **unchanged** — only the
tool layer under them becomes generic.

---

## 3. The nine tools (fixed vocabulary, forever)

| # | Tool | Reads/Writes | Never |
|---|---|---|---|
| 1 | `entity.list_models(query)` | resolves "students" → `edicai.student` (label + synonym table from `ir.model` restricted to the allow-list) | exposes internal models |
| 2 | `entity.describe(model)` | fields, labels, types, required flags, relations, *AI-enabled actions* | secret/technical fields |
| 3 | `entity.search(model, filters, fields, limit, order)` | search as the calling user (record rules apply) | sudo, cross-company scans |
| 4 | `entity.read(model, ids)` | read with field allow-list + PII masking | — |
| 5 | `entity.aggregate(model, group_by, measures, filters)` | `read_group`: counts, sums, averages, min/max | any write |
| 6 | `entity.create(model, data)` | only for policy-opted-in models | auto-confirm (always preview → confirm) |
| 7 | `entity.update(model, ids, data)` | same + **row cap** (default ≤ 20) | mass updates, money/approval-locked fields |
| 8 | `entity.delete(model, ids)` | **default OFF for every model**; enabled only for an explicit, per-model, per-group opt-in | cascades; archive-only by preference |
| 9 | `entity.execute(model, ids, action, params)` | whitelisted state-machine methods (workflow buttons) per model | unlisted `def ` methods on any model |

Tool contracts (schema, groups, risk) still live in `ai_policy.py` —
nine entries, once. The *per-entity* policy lives in the registry model
below.

---

## 4. `edicai.ai.entity.policy` — the declarative core

One `ir.rule`-friendly, manager-editable model (seeded by data XML):

```text
model_ref       e.g. edicai.student            (unique)
label           "Students"                    (+ synonyms: pupil, learner)
read_groups     edicai_ai.group_ai_user, ...   (who may use read ops)
write_groups    [...]                          (create/update)
delete_groups   default: nobody
field_allow     []  = all simple fields;    or explicit list to hide
field_block     money-lock + audit columns always blocked for writes
pii_fields      guardian_phone, ...   → masked in replies & logs
max_rows        search/aggregate row cap (default 100, hard cap 200)
ops             (search read aggregate) / (create update) / (delete)
enabled         bool (off = entity invisible even to describes)
```

Plus **action registry** entries (the `execute` whitelist), per model:

```text
action  e.g. edicai.fee.invoice → invoice_confirm  (the state-machine
        method name), allowed_groups, param schema, needs_approval
```

`needs_approval=True` reuses `ai_pending_action`'s
preview → confirm → execute → verify lifecycle **unchanged** — the
generic `create`/`update`/`execute` tools simply *call into* it
together with a `generic_payload` validator in `ai_action_resolve`.
No new confirmation mechanism is invented.

---

## 5. Security invariants (same as today, now provable per-row)

1. **No sudo.** All searches execute on `self.env` as the caller. A
   policy row cannot grant read of a model the caller cannot already read.
2. **Closed model allow-list.** Only `edicai.*` business models may be
   registered; `res.users`, `ir.*`, `res.config` are structurally
   rejected (validator refuses non-edicai models — tested).
3. **Field allow/block + PII masking** enforced in tools 2/3/4 and in
   the audit redaction (extend `_redact_params`).
4. **Writes:** always group-gated, always field-allow-listed,
   create/update ALWAYS via the pending-action confirm flow (even for
   "trusted" staff — confirmations are the product's safety contract);
   update row-capped; **delete OFF by default**.
5. **Audit:** one `AI_TOOL_CALL` event per generic execution with
   model-op-filters-hash (filters recorded hashed to keep payloads small
   — extend the existing redactor).
6. **No silent fallback:** policy denial → explicit AUTHORIZATION_DENIED
   reply, same SAFE_MESSAGES as today.

---

## 6. Phases (each keeps the whole suite green)

### G1 — Read floor (search, read, describe, list_models, aggregate)
- Entity policy model + data seed for 5 seed entities:
  `edicai.student`, `edicai.fee.invoice`, `edicai.attendance.record`,
  `edicai.admission.applicant`, `edicai.course.offering`.
- `FILTER_GRAMMAR`: a *closed* filter mini-language (field op value:
  eq/neq/in/like/gt/gte/lt/lte/in_period) — the LLM may only emit this
  grammar; the validator rejects anything else (`ValueError →
  VALIDATION_FAILED`).
- Aggregates replace the Phase 13 static summaries: the existing
  `fees.fee_summary` / `attendance.shortage_summary` are reimplemented as
  **thin wrappers over tool 5** (same reply text = zero user-visible
  change, regression-tested byte-identical replies where possible).
- Catalogue + coverage test extended: "how many X in Y" phrasings now
  route by *entity resolution* (list_models) instead of per-domain rules.
- Tests: traversal attempts (asking for disallowed models/fields),
  PII mask, row cap, per-group grants, aggregate vs record-rule interplay
  (student sees only own rows — the existing restriction test reruns
  verbatim against the generic tool).

### G2 — Create/update (the confirmation-first tier) — **SHIPPED 2026-10-23**
- **As shipped** (wider than the draft text, and simpler): there is no
  per-app opt-in. The two capability tools work on **any** entity whose
  policy row grants `create`/`update` in `ops` AND names a `write_groups`
  group, with the master flag `edicai_ai.action_entity_write_enabled` ON.
  Deny-by-default in four independent places: no policy row → unknown
  entity; no op in `ops` → unknown entity; no `write_groups` match →
  denied; flag off → denied. Delete is simply not offered.
- Generic validator (`validate_mutation_values`) → the EXISTING
  `ai_pending_action.create_pending` (preview) → `confirm_and_execute`
  → `_execute_entity_locked` (savepoint, re-authorize, create/write as
  the confirming user) → `_verify_entity_write` re-read.
- Writable fields derive from the model: simple types only
  (char/text/int/float/bool/date/datetime/selection/many2one) minus
  identity + `company_id` (always server-forced) minus readonly/computed.
  Required fields with a model default may be omitted. Values are
  coerced, size-capped and re-validated at execution.
- Result semantics: executed (verified) / denied (row stays `preview`,
  retryable after a re-grant) / `ENTITY_POLICY_REJECT` (row `failed`) /
  business `ValidationError` or `UserError` from the model → row back to
  `draft` + `VALIDATION_FAILED` (the user restages corrected values).
- Tests: `tests/test_ai_entity_mutations.py` (17) — staging writes
  nothing, every deny path, coercion/size caps, identity-field refusal,
  foreign session, revocation between preview and confirm, flag-off
  lane closure, chat-confirm end to end, idempotent second confirm,
  seed `noupdate` protection, and the model-constraint → draft path.
- Open follow-ups (not blockers): superseding/merging a staged edit,
  and surfacing *which* business rule refused (the reply is
  deliberately generic; the audit keeps `exception_type` only).

### G3 — Whitelisted record actions — **SHIPPED (2026-10-24)**
- Actually implemented (against the original sketch):
  - **Two independent gates.** The DATA gate is an enabled
    `edicai.ai.entity.action` row (`allowed_groups`, no auto-grant) plus
    an entity policy whose `ops` lists `execute` and whose NEW
    `execute_groups` csv includes the caller (deny-by-default, empty in
    the seed — separate from `write_groups` so actions roll out
    independently of create/update). The CODE gate is a fixed Python
    registry `models/ai_entity_actions.py:ENTITY_ACTIONS` keyed
    `(model, method)`. Belt AND braces: a data row naming anything not
    in the registry (e.g. `write`, `unlink`, `sudo`, `create`) is dead
    data and is refused with no side effect; the executed method name
    is a code literal, never the payload string.
  - **4 seeded actions** (seed `data/ai_entity_action_data.xml`,
    `<data noupdate="1">`, denies nothing by itself):
    `edicai.student → action_activate`,
    `edicai.student.document → action_verify / action_unverify`,
    `edicai.admission.applicant → action_move_to_waitlist`.
    Money/approval methods (fee payment confirm, asset approvals) stay
    human-only by design.
  - **Same lifecycle as G2**: `entity.execute` NEVER executes at call
    time — it validates (flag → policy op+grant → action row → code
    registry → closed params → readable record) and stages ONE pending
    action; the confirming user's `confirm <ref>` runs the ERP's own
    state-machine method, locked, exactly once, no sudo, then verifies
    by re-reading the declared state column. Business
    UserError/ValidationError → row back to `draft` (retryable);
    ACL denial → sanitized `denied`. Already-in-state is a clean no-op
    (`changed=False`, "Nothing to do — already in that state").
  - **Closed params grammar**: each spec declares
    `name → {target field, max_len}`; the only shipped param is `note`
    (≤500) targeting `verification_notes`. Unknown/overlong param
    names are refused.
  - `entity.list_actions` is now honest per-caller: `executable` +
    `reason_code`.
  - Master flag `edicai_ai.action_entity_execute_enabled` (default OFF,
    independent of the G2 write flag).
  - `needs_approval=True` rows are REFUSED (`APPROVAL_REQUIRED`) —
    entity actions are not wired into the Phase 4 approval lane yet.
  - Test Mode: observability-only, unchanged; no ACL bypass anywhere.
- Tests: `tests/test_ai_entity_actions.py` (20 tests: both gates,
  attack names, approval refusal, noop, idempotent second confirm,
  retryable business rejection, revocation/flag-off at confirm, staff
  ACL denial at execution (no-sudo proof), closed params, audit trail
  without payload leak, chat-confirm E2E, flag-off lane closure).
- Open follow-ups (not blockers): wiring `needs_approval` into the
  Phase 4 approval lane, and mining further declared actions.

### G4 — LLM proposal hardening — **SHIPPED (2026-10-25)**
- `ai_understanding` learns the new op vocabulary: the two discovery
  intents (`entity.list_models`, `entity.list_actions`) are answered
  deterministically from the catalogue, while `entity.search`
  (deliberately uncatalogued) reaches the model/filter layer ONLY as a
  validated LLM proposal.
- Proposals are deterministically re-validated (the LLM never widens the
  policy): closed key set → model in the CALLER's catalog (deny-by-
  default, `ir.*`/`res.*`/`edicai.ai.*` structurally refused, execute-only
  entities unsearchable) → the SAME closed filter grammar the execution
  path compiles → row caps.  Any violation invalidates the WHOLE
  proposal (fallback, never repaired).
- The catalog rendered into the system prompt is exactly what the caller
  may query — no other model names are ever offered.
- New eval set section: 60 generic-proposal prompts × ground truth in
  `test_ai_evalset.py` (44 answered, 6 fail-closed rejections, 6
  deterministic discovery phrasings, plus 4 execute-only rejections),
  and a dedicated 29-test validator suite in
  `test_ai_entity_proposal.py` (schema, allow-list, grammar, smuggling,
  catalog visibility, execution re-validation).
- Preview and execution share ONE compiler: the preview returns the
  normalized SYMBOLIC filters and `entity.search` compiles them at
  execution time (no double-compilation, no pre-compiled-domain bypass).

### G5 — Migration & retirement
- The 7 static conversational tools are reimplemented over the generic
  layer and kept as *aliases* for one release (their names appear in the
  catalogue and the Workspace UI's tool chips) — then removed.
- `mine_open_questions` gains entity-name mining: unresolved questions
  report the entity + op they *almost* resolved to → which policy row to
  review next (the growth loop: **data seeds policy, not code**).

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| LLM proposes a malicious filter (`user_ids` joins etc.) | closed filter grammar over whitelisted fields only; validator is authoritative |
| Mass data exfiltration via search | row cap + field allow-list + PII mask + same record rules the user already has |
| Accidental `delete`/mass update | delete default OFF; update row cap ≤ 20; every mutation preview → confirm |
| Performance (broad aggregates) | `read_group` only, hard group_by + limits, existing rate limiting |
| Registry bloat *in data* | entities enter only with a mined/evaluated demand (the G5 miner gate) |

---

## 8. Non-goals

- No arbitrary Python method execution via `entity.execute`.
- No cross-model chaining inside one tool call (one op per turn —
  matches today's "EXACTLY ONE tool execution per user turn").
- No direct field writes on money-locked, GL-posted, or approval-state
  columns — the existing locks stay authoritative.

---

## 9. Effort & order

G1 ≈ the work of Phase 13 (policy model + 5 tools + tests ≈ 3–4 dense
sessions); G2/G3 smaller because `ai_pending_action` already implements
the hard parts; G4/G5 mostly test data. **No phase starts before G1's
suite is green and deployed**, and Phase 6 remains out of scope.
