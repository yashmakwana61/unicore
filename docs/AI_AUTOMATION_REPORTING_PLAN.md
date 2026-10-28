# UNICORE World-Class Plan: AI Agents + Automations + Reporting + Bots
Built on: 65 modules, student lifecycle A→O, loophole report, existing `edicai_ai` (provider+chat), `edicai_analytics` (SQL VIEWs), `edicai_notify` (multi-channel), `edicai_api` (REST), `edicai_studio` (no-code), `telegram_odoo_integration`.

## 1. Vision
Every role (applicant, student, guardian, faculty, warden, librarian, accountant, principal) gets a proactive assistant + every repetitive SIS transition becomes an automation + every decision gets a live report. AI never writes grades/fees/transcripts directly — it drafts, cites, routes for human approval.

## 2. Agent catalog (role-based, all via `edicai_ai` provider + tools)
| Agent | Users | Tools (Odoo RPC) | Autonomy |
|---|---|---|---|
| Admission Counsellor | applicant, CRM team | applicant.create, docs checklist, merit rank, offer draft, `crm.lead` sync | L2: drafts, human sends offer |
| Enrollment Guardian | registrar | seat check (locked), prereq check, waitlist promote, timetable clash | L2: proposes, registrar confirms |
| Attendance Nudger | faculty, guardian, student | session open/close (perm-checked), shortage list, notify.send | L3: auto-nudge <75%, human closes |
| Grade Copilot | faculty | rubric suggest, anomaly flag (outlier vs class), gradebook preview | L1: suggest only, never publish |
| Fee Whisperer | accountant, guardian | dues list, receipt explain, defaulter list, payment-link create | L2: drafts links, human approves write-off |
| Scholarship Matcher | student | eligibility check (CGPA/attendance/income), application prefill | L2: prefill, committee approves |
| Timetable Optimizer | scheduler | clash detect (time-range), room/faculty load, suggestions | L2: suggest, human applies |
| Hostel/Transport Allocator | warden | vacancy, allocation draft, route load | L2 |
| Library Buddy | student, librarian | catalogue RAG, due/renew, reservation | L3 for search, L2 for renew |
| Grievance/Leave Triager | student/guardian | category classify, urgency, route to team, SLA timer | L3 triage, human resolves |
| Principal's Chief-of-Staff | leadership | KPI digest (admissions, collection, attendance, results), Red-flag list | L1 read-only |
| Data Hygiene Agent | admin | duplicate applicant, NULL-semester invoice, orphan session finder | L2: lists, human merges |

Guardrails: scope by `company_id/campus_id` (fix C2/B1 first), scope by role (student sees own only), tool allow-list per agent, human-in-loop for grades/fees/transcript/progression, full audit log (`edicai.ai.operation` already in studio — reuse), PII redaction in prompts.

## 3. Automation catalog (fix loopholes by automating the right thing)
- Admission: auto seat-lock on offer, merit-list cron, docs-incomplete blocker (hard, not advisory), duplicate-applicant merge suggestion, fee-receipt → auto confirm.
- Enrollment: atomic seat decrement, waitlist auto-promote + notify, deadline hard-stop, re-enroll after drop allowed (fix UNIQUE to partial).
- Timetable: time-range clash validator (replaces slot-id check), room double-book block, cancel blocked if sessions exist.
- Attendance: auto-create records for late enrollees, close requires reviewed flag, reopen needs perm + reason, face-id→student match.
- Exam: deny ticket without policy+fees, cumulative % compute, overflow hard-fail with waitlist, re-gen refreshes eligibility.
- Grading: maker-checker (different verifier/publisher), idempotent credit update, CA additive.
- Progression: auto-eligibility compute (credits/CGPA/fails), UNIQUE(student,year), auto semester roll on promote.
- Fees: idempotent batch (unique job key + row lock), money fields locked post-send, fix reverse, cancelled stays cancelled.
- Scholarship: hard eligibility + deadline + quota lock + one-award/semester cap.
- Hostel/Transport/Library/Appointment: capacity-checked transactions (SELECT FOR UPDATE), partial uniques, queue promotion.
- Notify: event bus — every state change emits `notify.automation` (admission, attendance shortage, fee due 7/3/1d, exam ticket, result published, leave decision).
- Crons: daily snapshot (idempotent), defaulter list, library overdue, SLA breach escalations.

## 4. Reporting (everything concerned: school/college/university)
Keep `edicai_analytics` VIEWs (fix: stable ids, campus scope, exclude drafts, include GL payments) + add:
- Leadership: admissions funnel, seat fill %, collection vs target, attendance at-risk %, pass %, placement %.
- Academic: CO-PO attainment, grade distribution, faculty workload vs results, quiz/assignment completion.
- Finance: fee aging, scholarship utilization, net revenue/semester (fix all-time subtraction), payment-method mix (GL-sourced).
- Campus: hostel occupancy, bus load, library circulation, grievance SLA, leave trends.
- Delivery: nightly `finance.snapshot` (fix NULL key), dashboard widgets via `edicai_studio` dashboards, export `/studio/export`, PDF via `/studio/report`.
- Ask-data bot: NL → safe read-only SQL/VIEW query with company/campus filter injected, chart rendered in portal.

## 5. Interactive bots (one brain, many faces)
- In-portal copilot (student/faculty/guardian): RAG over docs + own records only. e.g. "Why am I ineligible for exam?" → cites attendance % + fee due + links.
- WhatsApp (via notify engine): fee reminders with pay link, attendance alerts, result publish, leave approve buttons.
- Telegram (harden existing): secret-token check, tie chat→student/guardian via OTP, scope commands.
- Website/livechat: admissions FAQ + eligibility + document checklist → creates `crm.lead`/applicant draft.
- Voice-ready: same intents, STT/TTS later; keep intents channel-agnostic.

## 6. Architecture
- `edicai_ai`: single provider abstraction (OpenAI-compatible) + per-agent system prompts + tool registry (`@ai_tool` decorator wrapping existing action methods, perm-checked). Reuse `edicai_studio` AI Copilot + `ai.request/operation` logs.
- RAG: catalogue, regulations, curriculum docs in pgvector (new `edicai_knowledge` or studio datasets); always cite chunk + record.
- API: route all through `authenticate_request()` (fix 429 + scope + company filter + body-size). API keys per integration with minimal scope.
- Notify: single dispatch with rate limits, template versioning, delivery log.
- Reporting: VIEWs + snapshots + studio dashboards; no AI direct SQL — NL layer generates parameterized queries against allow-listed VIEWs.

## 7. Phased roadmap (12 weeks)
- W1-2 Hardening: fix C2/B1 company scope, telegram secret, admission/enrollment/exam/fee guards, UNIQUE fixes. No AI without this.
- W3-4 Notify+Reports fix: event automations, VIEW fixes, snapshot idempotency, leadership dashboard.
- W5-6 Copilots v1: Admission FAQ, Library Buddy, Fee explainer, Ask-data (read-only).
- W7-8 Agents v2: Attendance nudger, Grievance triager, Timetable optimizer (suggest), Grade copilot (suggest).
- W9-10 Bots: portal copilot, WhatsApp flows, Telegram OTP binding.
- W11-12 Eval + rollout: golden test set per agent, red-team (IDOR, quota, prompt-injection), pilot one campus, KPIs.

## 8. KPIs
Admission conversion +10%, manual follow-ups −50%, attendance marking time −40%, fee collection +15%, grievance SLA met 95%, report load <2s, agent helpfulness ≥4/5, zero cross-company leaks in pentest.

## 9. Risks
Cross-company leak (mitigate: scope first), grade/fee auto-write (mitigate: human-in-loop), chatbot hallucination on policy (mitigate: RAG cite-or-say-unknown), quota/cost blowout (mitigate: per-key limits + caching).
