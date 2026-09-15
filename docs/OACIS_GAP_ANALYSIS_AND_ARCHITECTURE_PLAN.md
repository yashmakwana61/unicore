# OACIS Suite — Gap Analysis & Architecture Change Plan

**Scope:** `unicore/custom_addons` (~60 `oacis_*` modules + MuK theme stack + telegram integration), Odoo 19.
**Method:** Full read-only code audit across six focus areas: UX & Usability, Portals, Smart Automation, Unified Ecosystems, Data & AI Insights, Security & Compliance.
**Date:** 2026-08-24

---

## 1. Executive Summary

OACIS is a functionally broad education ERP with a clean dependency layering (no circular deps), disciplined ORM usage, and several genuinely well-engineered kernels (notification engine, API-key vault, GL-aware finance snapshots, read-only SQL analytics views). However, the audit found a consistent pattern: **scaffolding exists but is inert or disconnected** — dead config toggles, orphaned security rules, un-bundled chart libraries, an AI provider with zero consumers, triggers that never fire, and portals that are read-heavy where the market expects self-service transactions.

Six systemic themes emerged:

1. **Security debt is structural, not incidental** — the defense-in-depth layer (`oacis_security`) never installs its record rules; one API scope bug grants read access to notify-only keys; secrets are stored in plaintext despite claims otherwise.
2. **No event backbone** — every automation is hand-wired at call sites; there are no outbound webhooks, no pub/sub, no SLA/escalation engine.
3. **Portals under-serve their personas** — guardians are fully read-only, students cannot self-enroll or request documents, and the website produces CRM leads instead of admission applications.
4. **The API cannot power a mobile app** — ~40% read parity, ~0% write parity, no per-user tokens (only admin-managed server keys).
5. **AI and analytics are descriptive islands** — no data-grounded AI (no RAG/tools/streaming/cost controls) and zero predictive capability, while KPI formulas diverge between modules.
6. **UX investment went to the shell, not the tasks** — three competing navigation systems coexist while bulk actions, search panels, onboarding tours, dark mode, i18n, and role dashboards are absent.

The plan below sequences remediation into **Phase 0 (critical fixes) → Phase 5 (ecosystem expansion)**, introducing eight new modules and targeted upgrades to existing ones.

---

## 2. Current-State Snapshot

| Area | What exists today | Health |
|---|---|---|
| Core domain | Campus → academic → student/faculty → fees/exam/attendance/hostel/library/transport/LMS/placement chains | Good layering; fan-in hotspots (`oacis_student` ← 38 modules, `oacis_base` ← 37) |
| Portals | Student (15 pages + assignment submit + leave + grievance), Faculty (17 routes incl. attendance marking & grade entry), Guardian (6 read-only routes) | Partial |
| Automation | `oacis_notify` multi-channel engine (email/WhatsApp/in-app), 12 crons | Kernel good; half inert |
| Ecosystem | `oacis_api` (11 GET + 1 POST endpoints, X-Oacis-Key auth), native payment providers via GL bridge, WhatsApp Cloud API | Thin |
| Data/AI | 8 PostgreSQL analytics views, 1 OWL dashboard, finance snapshots/KPIs, OpenAI-compatible AI chatbot | Descriptive only |
| Security | 52 ACL CSVs, 226 record rules, role groups, SHA-256 transcript verification, API key hashing | Rules exist but critical gaps (see §3.6) |

---

## 3. Gap Analysis by Focus Area

### 3.1 User Experience & Usability

**Strengths:** Three-layer theming (SCSS vars → runtime CSS engine → per-user prefs in `oacis_design`), keyboard-friendly app switching, per-user personalization, rich view-mode coverage via `*_view_mode_ext.xml`, comprehensive demo dataset.

**Gaps:**

| # | Gap | Evidence |
|---|---|---|
| UX-1 | **Three competing nav stacks** (oacis_theme mega-menu + landing screen, oacis_design sidebar/start-menu, muk_web_theme/appsmenu+appsbar) all patch NavBar independently; whichever loads last wins | No mutual exclusion in any of the three manifests |
| UX-2 | **Fragmented IA: 30 root apps** for ~60 modules; Fees/Exam/Library each get top-level tiles while Students nests under "Oacis"; churn proven by maintenance script `fix_menus.py` | Root menus across `menus/*.xml` |
| UX-3 | Duplicate menus pointing at identical unfiltered actions (leave requests, asset requests); orphan scholarship config menu; 11 root menus without `web_icon` | `oacis_student_leave/menus/oacis_student_leave_menus.xml:18-28`, `oacis_asset_request/menus/...:31-41` |
| UX-4 | Empty-state help on only **18 of 265 actions**; no searchpanel anywhere; zero saved filters (`ir.filters`) suite-wide | grep results |
| UX-5 | Attendance marking friction: default status `'absent'`, row-by-row only — no "mark all present" / bulk wizard | `oacis_attendance_record.py:114`, session form views |
| UX-6 | Admission dashboard silently renders blank: JS guards on `window.Chart` but Chart.js is never bundled | `oacis_analytics/static/src/js/admission_dashboard.js:13,131` |
| UX-7 | No end-to-end dark mode (no user-facing toggle); two modules hardcode conflicting `prefers-color-scheme: dark` overrides producing hybrid UI | `oacis_admission/static/src/scss/admission_kanban.scss:17`, `oacis_analytics/...admission_dashboard.scss:14` |
| UX-8 | Zero responsive `@media` queries in oacis_theme despite manifest claiming mobile support; backend unusable on tablets except partial MuK navbar work | 13 SCSS files measured |
| UX-9 | No role-based home dashboards (`ir.actions.board`: none); landing screen forced onto admin only | `oacis_theme/data/apps_landing_action.xml:12-14` |
| UX-10 | No guided tours (web_tour absent), no first-login checklist, minimal tooltips/help | suite-wide grep |
| UX-11 | **Zero i18n readiness**: no `.pot`/`.po` in any oacis module, no `_t()` in JS strings | vs muk modules shipping de/es/fr/it |
| UX-12 | Sparse accessibility: 23 aria attributes suite-wide, 10 `<img>` without alt, unlabeled chatbot controls | `oacis_ai/static/src/xml/oacis_ai_chatbot.xml:86-97` |

### 3.2 Portals

**Strengths:** Consistent route/auth patterns, ownership-mapping helpers (`_get_current_student/faculty/guardian`), pagination on lists, upload validation on assignment submission, guardian multi-ward model with per-relation permission fields.

**Route inventory (verified):**

| Portal | Routes | Write transactions |
|---|---|---|
| Student `/my/oacis/student/*` | dashboard, courses, attendance, exams, results, fees, scholarships, notices, assignments ×3 (+ leave ×4 in oacis_student_leave, grievances ×4 in oacis_grievance) | Assignment submit (1 POST), leave apply, grievance raise |
| Faculty `/my/oacis/faculty/*` | dashboard, schedule, courses(+detail), attendance mark, grades entry, exams, profile, notices, assignments ×4 | 4 POSTs (attendance save, grade save, assignment create, grading) |
| Guardian `/my/oacis/guardian/*` | dashboard, ward attendance/academic/fees, exams, notices | **0 POSTs — fully read-only** |

**Gaps:**

| # | Gap | Evidence |
|---|---|---|
| PT-1 | **No online admission application.** `oacis_website` only creates CRM leads from an enquiry form + livechat; there is no public application form creating an `oacis.admission.applicant` with document upload, offer acceptance, or fee payment | `oacis_website/__manifest__.py`, `models/crm_lead_ext.py` |
| PT-2 | Guardian portal has **no actions**: cannot pay ward fees, grant/deny consents, book appointments, or message faculty | `guardian_portal.py` — zero POST routes |
| PT-3 | Student missing self-service flows: course registration/enrollment changes, hall-ticket download, transcript/certificate request, library account, hostel services, timetable page, document center, notification inbox/preferences, profile self-edit | Route table above |
| PT-4 | Faculty has no approval queue in-portal — leave/scholarship/hall-ticket approvals happen only in backend | Controllers list |
| PT-5 | **Defense-in-depth missing**: `oacis_security/security/oacis_portal_record_rules.xml` (10 portal self-view rules) exists on disk but the module's manifest has `'data': []` — it never loads. Isolation relies solely on controller-level mapping over heavy `sudo()` (student 24×, faculty 43×, guardian 18×) | `oacis_security/__manifest__.py:10` |
| PT-6 | No PWA/mobile shell; 1 media query total across portal CSS; near-zero aria coverage | UX audit cross-ref |
| PT-7 | No notification preferences/opt-out UI for any persona (and engine ignores opt-outs anyway — see AU-3) | `oacis_student` has zero opt-out fields |

### 3.3 Smart Automation

**Strengths:** `_safe_emit()` guarantees notification failures can't roll back business transactions; immutable, privacy-aware notification log with retention anonymization; consolidated fee-dunning ladder; human-in-the-loop result publishing; 13 seeded branded templates; WhatsApp connection tester.

**Gaps:**

| # | Gap | Evidence |
|---|---|---|
| AU-1 | **Config toggles are dead UI**: `notify_on_*`, `fee_reminder_days_before`, `exam_reminder_days_before`, `email_footer_text` are displayed in Settings but never read by code. Config says exam reminder = 3 days; cron hardcodes 7 | `oacis_notification_config_views.xml:73-88` vs `data/oacis_notify_automation_cron.xml` |
| AU-2 | Dead triggers defined but never emitted: `exam_hall_ticket`, `welcome`, `scholarship_awarded`, `attendance_warning`, `custom` | Template selection vs grep of emit sites |
| AU-3 | Opt-out ignored: guardian `can_receive_notifications` honored only in batch fee reminders; general event path sends regardless; students have no opt-out field at all | `oacis_notification_engine.py:80-85` vs `:615-618` |
| AU-4 | Spam loops: overdue invoices and attendance-shortage alerts re-send **daily forever** (dedup set is per-run only); no suppression windows or dunning caps | `cron_fee_dunning`, `send_attendance_shortage_alerts():643-648` |
| AU-5 | No delivery feedback: `delivered` status never set; no WhatsApp status webhook; failed WA sends are synchronous `requests.post(timeout=10)` inside business transactions with no retry/queue | `oacis_notification_engine.py:261,303`; log model `:138` |
| AU-6 | Fake endpoint: `POST /api/oacis/v1/notifications/send` bypasses the engine and writes a fabricated "sent" log row without sending anything | `oacis_api/controllers/notifications.py:45-59` |
| AU-7 | Stub crons: library "overdue reminders" cron counts and logs but sends nothing (docstring lies); analytics refresh cron is a placebo log line | `oacis_library_issue.py:463-478`; `oacis_analytics/data/oacis_analytics_cron.xml` |
| AU-8 | Late fees never computed though `late_fee_percentage/amount` fields exist | `oacis_fee_structure.py:105`, `oacis_fee_invoice.py:131` |
| AU-9 | **No workflow engine**: hand-coded button state machines (18 sequential `action_*` methods on admission applicant alone); exam lifecycle manual despite dates existing to drive it; progression decisions manual | `admission_applicant.py:336-449`, `oacis_exam_schedule.py:303-439` |
| AU-10 | **No SLA timers or escalation**: zero SLA hits suite-wide; grievance `escalated` state is a dead-end bare write (no routing/notify/timer); maintenance priority drives nothing | `oacis_grievance.py:96-97` |
| AU-11 | Approvals strictly single-level, no delegation; leave-approval activity hardcoded to `RegistrarGroup.users[0]`; **fee discount/concession has no approval gate** | `oacis_student_leave_request.py:401-409`, `oacis_fee_invoice.py:238-244` |
| AU-12 | **No event bus / webhooks-out / message queue** — producers and subscribers hard-coupled; trigger selection lists duplicated verbatim across module extensions | `oacis_notification_template_ext.py:25-46` |
| AU-13 | Telegram bot is a sales-order bot with zero education-domain integration (depends only `base, sale`) | `telegram_odoo_integration/__manifest__.py` |
| AU-14 | AI is an island: reusable provider has **zero callers outside `oacis_ai`** | grep |

### 3.4 Unified Ecosystems

**Strengths:** Clean layered dependency graph (DFS verified: no cycles); exemplary cross-module hygiene (everything crosses boundaries via ORM inheritance, no private imports); raw SQL confined to analytics/finance; solid API key lifecycle (SHA-256 hash-only storage, show-once wizard, scopes, expiry, daily limits).

**Gaps:**

| # | Gap | Evidence |
|---|---|---|
| EC-1 | **API surface too thin for mobile**: 12 endpoints (11 GET, 1 POST). Missing: assignments (list/detail/upload), notices, exam schedule/results, timetable, scholarships, leave, grievances, notifications inbox, **payment initiation**. Estimated parity: ~40% read, ~0% writes | `oacis_api/controllers/*.py` vs portal controllers |
| EC-2 | **No per-user authentication** — keys are admin-managed global credentials bound to one user; a student-facing app cannot safely authenticate | `oacis_api/models/api_key.py` |
| EC-3 | Rate limiting broken semantics: quota exhaustion returns HTTP 401 identical to bad key (no 429/`Retry-After`); day boundary uses naive server-local `datetime.now()`; daily counter only, no burst control | `api_key.py::validate_key()`, `controllers/common.py:102-112` |
| EC-4 | No OpenAPI spec despite manifest claim ("Swagger/OpenAPI compatible" refers only to JSON envelope shape); pagination only on `/students`; version prefix copy-pasted into every decorator | Repo-wide search: zero openapi/swagger files |
| EC-5 | **No SSO federation**: `auth_oauth`/`auth_ldap`/SAML unused anywhere — adoption blocker for Google Workspace/Microsoft Entra institutions | grep across manifests/code |
| EC-6 | No outbound webhooks/event push; async work is ir.cron-only; no queue_job/OCA connector | ecosystem sweep |
| EC-7 | Payments: solid GL bridge over native providers (Razorpay/Stripe/PayPal present in core install) but **no partial-refund workflow** (full reversal-on-cancel only) and no refund-request/approval process | `oacis_fee_invoice_gl_ext.py:148-174` |
| EC-8 | No hardware adapters: biometric attendance devices, barcode/RFID library circulation, QR on hall tickets — all manual | suite-wide grep |
| EC-9 | No calendar/videoconference pipeline: `oacis_calendar` never touches `calendar.event`; live-class URLs are manually pasted char fields; Google/MS calendar connectors unused | `oacis_lms/models/slide_slide.py:31-44` |
| EC-10 | **No LTI 1.3/SCORM/xAPI compliance** in LMS (thin `website_slides` extensions only) | grep: zero real matches |
| EC-11 | **No India regulatory integrations**: DigiLocker/NAD issuer, ABC credit transfer, UGC/AICTE structured exports — sole evidence is a demo-data string "AICTE". Ironic given `oacis_secure_transcript` already computes verifiable hashes | `oacis_demo/demo/02_academic_structure.xml:59` |
| EC-12 | Coupling smell: `oacis_notify` is a god-module (depends on 16 business modules; mixes channel infrastructure with dunning/alert business logic); portals depend on ~19-20 modules each | Dependency graph analysis |

### 3.5 Data & AI Insights

**Strengths:** Disciplined read-only SQL-view analytics architecture with documented patterns; consistent funnel math between view and dashboard; company isolation everywhere; GL-aware, idempotent finance snapshots/KPIs; single canonical attendance-% source consumed by eligibility/notify/portals; clean AI provider abstraction with env-var secret precedence.

**Gaps:**

| # | Gap | Evidence |
|---|---|---|
| DA-1 | **Zero predictive capability** — forecasting explicitly scoped out; no at-risk/dropout/fee-default signals even though inputs exist (`shortage_alert`, CGPA, overdue invoices, `dropped` state) | `DASHBOARD_IMPLEMENTATION.md:180,230` |
| DA-2 | **AI not grounded in OACIS data**: static generic system prompt, no RAG/context injection, no function-calling/tools — bot hallucinates institutional facts it cannot know; no streaming (blocking 120 s worker holds); no token/cost ledger, quotas, retries/backoff; `usage` field ignored | `oacis_ai_provider.py` full read |
| DA-3 | Embedded BI thin: one OWL dashboard (manager-only); registrar/finance have analytics ACLs but **no menus**; faculty/student/guardian have zero analytics surface; promised faculty-workload & dropout views don't exist | ACL CSV vs menu XML |
| DA-4 | Placebo refresh cron; no schema-drift detection for the 8 SQL views (break silently until next `-u`) | `oacis_analytics_cron.xml` |
| DA-5 | KPI formula inconsistencies: scholarship recomputes attendance % ignoring session state/course scope (disagrees with canonical cumulative % used for exam eligibility); collection % defined differently in analytics view vs GL-aware finance snapshot | `oacis_scholarship_application.py:349-362` |
| DA-6 | Unstable synthetic IDs (`ROW_NUMBER() OVER ()`) on all 8 analytics views — breaks drill-through/exports | view models |
| DA-7 | Shallow RLS: company-only record rules; no campus/program scoping for multi-campus deans | `oacis_analytics_record_rules.xml` |
| DA-8 | Reporting stack PDF-only: 10 qweb-pdf reports; no xlsx generation, no `o_spreadsheet` adoption; duplicate divergent fee-statement reports bound to same model | report actions inventory |
| DA-9 | **Applicant dedup missing**: uniqueness constraints exist on students/enrollments but applicants have none on (email\|phone, cycle, program) → duplicate applications inflate funnel KPIs | `admission_applicant.py` constraints |
| DA-10 | Coverage holes: no retention/cohort-survival, enrollment time-series, placement/hostel/library/transport analytics despite dependencies listed | analytics view list |

### 3.6 Reliable Security & Compliance

**Critical findings (exploit-ready):**

| # | Finding | Evidence |
|---|---|---|
| SEC-1 | **Portal record rules never install** — `oacis_security` manifest `'data': []` leaves 10 portal self-view `ir.rule`s orphaned; compose/init-db install the module giving false assurance | `oacis_security/__manifest__.py:10`; `security/oacis_portal_record_rules.xml` |
| SEC-2 | **Privilege escalation**: `notify_only` API keys pass every `read` scope check → can read all student PII endpoints | `oacis_api/controllers/common.py:149-150` |
| SEC-3 | **Plaintext secrets**: WhatsApp token stored as plain Char with help text falsely claiming "Stored encrypted"; Telegram bot token and AI key likewise in DB params; all readable by Manager/Registrar roles per ACLs | `oacis_notification_config.py:68-72`; `telegram_bot_service.py:275`; `res_config_settings.py:7-11` |
| SEC-4 | **AI chats have no isolation rule**: any AI-group user can RPC-read other users' transcripts (may contain confidential academic data); manager "view all sessions" permission documented but unimplemented | `oacis_ai/security/` — 0 ir.rules |
| SEC-5 | **Campus isolation rules logically broken two ways**: single-company OR-clause nullifies campus filtering (student rules); inverted empty-semantics contradicts field help ("empty = all campuses") in timetable/exam/curriculum/attendance rules | `oacis_student_record_rules.xml:16-24` etc. |
| SEC-6 | Transcript verification: unsalted deterministic SHA-256 (no HMAC/asymmetric signature); public verify page leaks student name; no throttle/audit of attempts | `oacis_secure_transcript.py:114-128`; `controllers/verify.py:7-17` |
| SEC-7 | Missing ACLs: `oacis.api.key.token.wizard` (TransientModel) and `oacis.notification.automation` — AccessError traps for non-superusers | `api_key.py:169`; automation model |
| SEC-8 | Deployment weaknesses: compose mounts **staging** conf; default DB password fallback `:-odoo`; ports 8069/8071/8072 exposed with no reverse proxy; **no backup/pg_dump/DR anywhere** — volume deletion = total loss | `docker-compose.yml:12,17,24` |

**Compliance gaps:**

| Area | Status |
|---|---|
| Consent records | Absent — no consent model/checkbox/timestamp anywhere; WhatsApp messaging proceeds without recorded opt-in |
| Right to erasure/export | No subject-rights tooling beyond notification-log anonymization |
| Retention policies | Only notify logs (365d); discipline/placement/AI chats/documents indefinite |
| Audit trails | Chatter covers most models + 2 immutable logs; but no login/API-request/transcript-verification auditing; grades rely on mutable chatter |
| Brute force | No lockout/rate-limit on API key failures or login; no TOTP enforcement hooks |
| Session hardening | `proxy_mode=True` only; no cookie flags/TTL in configs |

---

## 4. Target Architecture

### 4.1 Architectural principles

1. **Event-first core**: producers emit domain events once; notifications, webhooks, AI, and future ML subscribe. Kills duplicated selection lists and hand-wired coupling (AU-12, EC-6).
2. **Separate infrastructure from business logic**: split `oacis_notify` into a channel engine (any-to-any: email/SMS/WhatsApp/push/in-app/webhook) and thin per-domain trigger packages (EC-12).
3. **DB-level security as backstop**: controller-level ownership checks remain, but record rules must enforce tenant/person isolation even when controllers regress (SEC-1).
4. **Secrets never in DB**: environment-provided configuration parameters with masked display, rotation metadata, and admin-only field-level groups (SEC-3).
5. **One formula, one source**: shared computed helpers for attendance %, collection rate, funnel math; analytics views consume them (DA-5).
6. **Portal ↔ API convergence**: portal controllers become thin wrappers over service methods that the REST API also exposes, guaranteeing feature parity across web/mobile (EC-1).

### 4.2 New module map

| New module | Purpose | Replaces/relieves |
|---|---|---|
| `oacis_event_bus` | Domain-event registry (`oacis.event.bus`): typed events, subscriber methods, replay-safe emission, test harness. Foundation for everything below | Hand-wired `_safe_emit` sites; duplicated selections |
| `oacis_workflow` | Multi-level approval chains (amount/state-conditioned), delegation, SLA timers, escalation matrix, round-robin assignee pools | Single-click approvals; dead-end `escalated` states |
| `oacis_webhook` | Outbound subscriptions: event → URL, HMAC signing, retry queue table w/ backoff, delivery log + UI | Poll-only external integrations |
| `oacis_compliance` | `oacis.consent.record` (subject/purpose/channel/grant/revoke), generic retention engine (extends notify-log pattern), subject-rights (export/anonymize) workflows, append-only audit model for sensitive transitions (grades, discounts) | Ad-hoc anonymization; mutable chatter reliance |
| `oacis_secrets` | Env-backed config-parameter facade: fetch-or-fail semantics, last-rotation metadata, field `groups=` lockdown; migration path for WA/Telegram/AI keys | Plaintext Char secrets |
| `oacis_admission_online` | Public website flow: program catalog → application form (validated uploads via existing validator) → applicant record → offer acceptance → fee payment link → enrollment hand-off | CRM-leads-only website bridge |
| `oacis_biometric` | Device-adapter framework: push-API receiver + scheduled pull adapters → `oacis.attendance.record`; barcode/QR generation for hall tickets & library accession scanning | Manual session-only marking |
| `oacis_digilocker` | DigiLocker/NAD issuer integration built on `oacis_secure_transcript` HMAC artifacts; ABC credit export formats; UGC/AISHE structured report exports | Nothing (net-new regulatory capability) |

### 4.3 Major upgrades to existing modules

| Module | Upgrade |
|---|---|
| `oacis_security` | Load the orphaned portal rules; add rewritten campus-isolation domains (correct empty-semantics + drop nullifying OR-clause); per-user rules on AI chats; document role matrix |
| `oacis_api` | **v2**: OAuth2/password-token per-user auth alongside X-Oacis-Key (server-to-server); portal-parity write endpoints lifted from proven portal controller logic; `POST /fees/{id}/payment-session`; HTTP 429 + `Retry-After` + timezone-correct windows; central version constant; served `openapi.json`; uniform offset/limit pagination |
| `oacis_ai` | **v2 platform**: tool/function-calling exposing whitelisted, ACL-respecting `read_group` queries + user-scoped prompt context (RAG-lite); streaming or queued job + polling; `oacis.ai.usage` ledger with per-group quotas/spend caps; embed points (applicant/grievance summaries, grading assist, draft-guardian-comms through notify engine with human edit-before-send); manager session-audit endpoint |
| `oacis_notify` | Split channels vs triggers; wire dead config toggles; universal opt-out enforcement in `_safe_emit`; suppression windows + dunning caps; WhatsApp status webhook → `delivered`; queued outbound sender (retry/backoff) instead of in-transaction HTTP; fix fake API endpoint to call engine |
| `oacis_analytics` | Early-warning view (rule-based risk score: attendance ∧ CGPA ∧ dues ∧ trajectory) exposed to mentors/faculty portal; cohort-retention & time-series views; campus/program-scoped RLS; menus for registrar/finance; schema-drift healthcheck cron (real one); deterministic view IDs; bundle Chart.js properly |
| `oacis_finance_report` | Adopt GL-aware collection % everywhere; retire duplicate fee-statement binding; scheduled xlsx/pdf KPI digest emails |
| Portals (all 3) | Guardian: pay-fees CTA, consent center, appointment booking, messaging. Student: course registration, hall-ticket download, transcript/certificate requests, document center, notification preferences, profile edit. Faculty: approval queue, mentor early-warning view, own leave. Shared: PWA shell (manifest + service worker), responsive pass, aria/i18n |
| `oacis_theme`/`oacis_design`/muk_* | Consolidate to ONE nav stack (recommend oacis_design sidebar/start-menu; make others mutually exclusive); IA re-org: re-parent 30 root apps into coherent sections (Academic / Finance / Campus Life / Configuration); design-token layer driving real dark mode; remove ad-hoc `prefers-color-scheme` overrides |

---

## 5. Phased Change Plan

### Phase 0 — Critical fixes (Weeks 0–2) *stop-the-bleeding*

| # | Item | Source gap |
|---|---|---|
| 0.1 | Wire `oacis_portal_record_rules.xml` into `oacis_security` manifest (or fold rules into owning modules); add regression tests | SEC-1, PT-5 |
| 0.2 | Fix API scope bug (`remove 'notify_only'` from read-capable set) + test | SEC-2 |
| 0.3 | Move WA/Telegram/AI secrets behind env-var precedence pattern (AI already has it); delete false help text; `groups=` on credential fields | SEC-3 |
| 0.4 | Add missing ACLs (key wizard transient, notification.automation) | SEC-7 |
| 0.5 | Bundle Chart.js in assets; visible fallback message | UX-6, DA-… |
| 0.6 | Fix duplicate/orphan menus; add `web_icon` to 11 bare roots | UX-3 |
| 0.7 | Compose hardening: mount prod conf; fail fast when `OACIS_DB_PASSWORD` unset; reverse-proxy guidance doc | SEC-8 |
| 0.8 | Backup baseline: nightly `pg_dump` sidecar + restore runbook | SEC-8 |
| 0.9 | Fix rate-limit response semantics (429 ≠ 401) | EC-3 |

### Phase 1 — Foundations (Month 1)

1. `oacis_event_bus`: bus + migrate the 10 existing emit sites; de-duplicate template-selection lists.
2. Split `oacis_notify`: channel engine stays; move dunning/shortage/exam logic into thin trigger packages reading config toggles (fixes AU-1) and honoring universal opt-out (AU-3), with suppression windows/caps (AU-4).
3. `oacis_secrets` rollout; rotation metadata.
4. Rewrite campus-isolation record rules suite-wide; add AI-chat user-isolation rules (SEC-4/5).
5. Fire dead triggers (`welcome`, `hall_ticket`, `scholarship_awarded`, `attendance_warning`) via the new bus (AU-2); implement library due-date reminders; late-fee computation in dunning ladder (AU-7, AU-8).
6. Applicant dedup constraint + merge wizard (DA-9); harmonize attendance %/collection % via shared helpers (DA-5).
7. Replace placebo analytics cron with real schema-drift healthcheck (DA-4).
8. HMAC upgrade for transcript verification; strip PII from public verify response; attempt logging + throttle (SEC-6).
9. UX quick wins: "Mark all Present" bulk action; empty-states on top-30 actions; searchpanels + saved favorites on core registries; alt/aria pass (UX-4/5/12).

### Phase 2 — Portals & Mobile parity (Months 2–3)

1. Service-layer extraction from portal controllers; then:
2. `oacis_api` v2: per-user tokens, portal-parity endpoints, payment-session initiation, OpenAPI spec served (EC-1/2/4).
3. `oacis_admission_online`: end-to-end public admission flow wired to CRM fallback (PT-1).
4. Guardian transactional upgrades: fee payment, consent capture (feeds `oacis_compliance`), appointments (PT-2).
5. Student/faculty self-service additions per §4.3 (PT-3/4).
6. Notification-preferences UI per persona backed by engine enforcement (PT-7).
7. PWA shell + responsive/accessibility/i18n (.pot export) pass on portal templates (PT-6, UX-11).
8. Authorization test suite for all portal controllers (cross-student deny assertions) — currently zero coverage over 2,657 LOC of sudo-heavy surface.

### Phase 3 — Smart Automation (Months 3–4)

1. `oacis_workflow`: approval chains (start with ungated fee discounts — AU-11), delegation, SLA timers + daily scan, escalation matrix replacing dead-end states.
2. Exam lifecycle auto-progression driven by dates; progression recommendations (rule-based) with manual confirm.
3. Round-robin approver pools replacing `users[0]` hardcode.
4. `oacis_webhook` GA: initial events = `payment.confirmed`, `invoice.overdue`, `admission.decision`, `exam.published`, `grade.published`, `notice.created`.
5. Queued outbound sender (WA/email) with retry/backoff; WhatsApp status callback → delivered statuses (AU-5).
6. Fix fake notifications/send endpoint to call engine (AU-6).
7. AI-in-flows wave 1 using existing provider: summaries on applicant/grievance forms, AI-drafted comms via notify engine (AU-14).

### Phase 4 — Data & AI Insights (Months 4–6)

1. Early-warning system: rule-based risk score view + mentor/faculty portal surfacing (DA-1).
2. BI democratization: registrar/finance menus, campus-scoped RLS, finance OWL dashboard, cohort-retention/time-series views (DA-3/7/10).
3. `oacis_ai` v2 platform: tools/RAG grounding, usage ledger + quotas, streaming/async, manager audit (DA-2).
4. Scheduled xlsx/pdf KPI digests; evaluate `o_spreadsheet` for self-service (DA-8).
5. Consolidate duplicate reports; deterministic analytics IDs (DA-6, DA-8).
6. Nav consolidation + IA re-org + design tokens/dark mode + role home dashboards (UX-1/2/7/9) — placed here as it touches every user; schedule after functional waves stabilize.
7. Onboarding: web_tour snippets per app + setup checklist (UX-10).

### Phase 5 — Ecosystem expansion (Month 6+)

1. SSO federation: `auth_oauth` (Google Workspace/Microsoft Entra) for students/faculty/staff with provisioning policy (EC-5).
2. `oacis_digilocker`: DigiLocker/NAD issuance from secure-transcript HMACs; ABC credit export; UGC/AISHE structured exports from analytics aggregates (EC-11).
3. LMS standards decision point: adopt/adapt OCA LTI/SCORM player if accreditation requires e-learning evidence; else document limitation explicitly (EC-10).
4. `oacis_biometric`: device push/pull adapters; QR/barcodes on hall tickets + library circulation (EC-8).
5. Calendar/video pipeline: timetable → `calendar.event` → Meet/Teams provisioning; appointment sync (EC-9).
6. Partial-refund workflow with approval + refund-to-source (EC-7).
7. Repurpose telegram integration into education domain (notices/fee queries via bot) or retire it (AU-13).

---

## 6. Cross-Cutting Workstreams (continuous)

| Workstream | Detail |
|---|---|
| Testing | Portal authorization suite (Phase 2 gate); API contract tests against openapi.json; event-bus subscriber tests; record-rule matrix tests per group; upgrade tests for SQL views |
| Security cadence | Quarterly review of sudo() surfaces, secret rotation drill, dependency audit; brute-force lockout + login auditing land with `oacis_compliance` |
| Compliance | DPDP/GDPR readiness grows incrementally: consent (P2) → retention engine (P2/P3) → subject-rights workflows + append-only grade audit (P3) |
| Documentation | Role-permission matrix (currently undocumented; note `group_oacis_admin` does NOT imply Faculty — confirm intent); API reference generated from spec; ADRs for nav consolidation and LMS decisions |
| Performance | Async/queued outbound HTTP; streaming AI; worker sizing review after AI adoption; index review on hot fan-in tables (`oacis_student` relations) |

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Fan-in hotspots make refactors risky (`oacis_student` ← 38) | Event bus decouples before schema changes; additive-only policy already documented in analytics |
| Nav consolidation disrupts trained users | Feature-flag old/new shells during transition; keep menu paths stable where possible |
| Record-rule activation may break controllers relying on implicit visibility | Phase 0 includes full regression pass + staged rollout on staging DB first |
| AI cost overrun | Usage ledger + hard quotas ship **before** any RAG/tool features |
| Scope creep across 60 modules | Each phase gated by the specific gap IDs above; new capabilities land in new modules, not god-module growth |

---

*Evidence base: full-code audit including manifest dependency graph (cycle-checked), route inventories, cron registry (exhaustive, 12 crons), ACL/record-rule coverage scans, secret-handling greps, and view/template sampling. All file references are relative to `unicore/custom_addons/` unless prefixed.*
