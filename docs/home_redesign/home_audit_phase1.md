# Phase 1 — Home Redesign Audit (Odoo 19 CE / Edicai)

Verified against repo `unicore/custom_addons` and live DB `edicai_preview` on 2026-10-29.
Scope: current landing/"Home" experience, existing dashboards, notifications/announcements,
onboarding, role groups, access rules, frontend conventions.

## 1. Current landing behavior (live-verified)

| Fact | State |
|---|---|
| `res.users.action_id` (default home action) | **NULL for every active user,** including admin — nobody has a configured landing action in `edicai_preview` |
| `edicai_theme` (Apps Landing Screen, `action_edicai_apps_landing`) | **module uninstalled** — its `apps_landing_action.xml` (which set admin landing) is not active |
| `odoo_modern_backend_full` (hardcoded-data dashboard, root menu `menu_modern_dashboard`) | **module uninstalled** |
| `edicai_studio` (studio home) | **uninstalled** |
| `muk_web_theme` + `muk_web_appsbar` | **installed** (navbar/apps-bar chrome; neither defines a home action nor sets `document.title`) |
| Existing "Home" app menu | **none** — no `ir.ui.menu` named "Home" exists; `document.title` "Edicai AI Workspace" seen in browser is just the action *name* of `edicai_ai.action_edicai_ai_workspace` while that action is open |
| Effective landing today | Odoo standard default action (webclient first reachable app); per-user `Preferences → Home Action` only |

**Preserve:** the Apps-bar/navbar chrome and all existing app menus; do not replace the
webclient. The standard user-tunable landing (`action_id`) remains the integration point.

## 2. Existing dashboard implementations (candidates to reuse/reference)

| Dashboard | Module | Mechanism / data source | Menu / groups (live) |
|---|---|---|---|
| SIS Overview | `edicai_base` | OWL `EdicaiOverviewDashboard` tag `edicai_overview_dashboard`; `orm.call("edicai.overview.dashboard","get_overview_data")`; KPIs (students/applicants/faculty/invoices/attendance) + 6 Chart.js charts + drill-down doActions; company/campus filters | `menu_edicai_overview` under `menu_edicai_root` "Edicai"; groups `group_edicai_staff` (single-group attr — fragile: registrar/finance/manager rely on implied chains) |
| Admission Dashboard | `edicai_analytics` | OWL `AdmissionDashboard`; `orm.call("edicai.admission.applicant","get_admission_dashboard_data")`; cycle/campus/program/state filters | `menu_edicai_analytics_admission_dashboard`; grouped `group_edicai_manager (+admin)` |
| Finance dashboards | `edicai_finance_report` | **no OWL** — graph/pivot act_windows on `edicai.finance.kpi`, `edicai.fee.invoice`, `edicai.scholarship.award` | root ungrouped (visible to all who have model read → finance) |
| Portal dashboards | `edicai_portal_student/_faculty/_guardian` | QWeb, HTTP routes `/my/edicai/*` | portal users only (group_portal) |
| Studio dashboards / Modern dashboard / AI workspace | `edicai_studio`, `odoo_modern_backend_full`, `edicai_ai` | studio ORM/fetch double-path; hardcoded data (uninstalled); AI chat workspace | out of scope |

Charts all use `('include','web.chartjs_lib')` + hand-rolled Chart.js wrappers
(`chartInstances` destroy map, setTimeout render race — documented pattern).

## 3. Reusable data sources for KPI widgets (models, live access matrix)

Read values from `ir.model.access.csv` rows (read/write/create/unlink):

| Model | admin | manager | registrar | finance | faculty | staff | student |
|---|---|---|---|---|---|---|---|
| `edicai.student` | rwcU | rwcU | rwcU | r··· | r··· | r··· | r··· |
| `edicai.fee.invoice` | rwcU | rw· | rwc· | rwc· | — | r··· | r··· |
| `edicai.attendance(.session/.record)` | rwcU | rw· | rwcU | — | rw· / rwc· session+record | r··· | r··· |
| `edicai.assignment` | rwcU | rwc· | rwc· | — | rw· | rw· | r··· |
| `edicai.assignment_submission` | rwcU | rwc· | rwc· | — | rwc· | rw· | rwc· |
| `edicai.grade_entry` / `edicai.semester_result` | rwcU / rwcU | rw· / r·· | rwcU / r·· | — | rwc· / r·· | r·/r· | r·/r· |
| `edicai.exam.schedule` (+hall_ticket/seating) | rwcU | rw· | rwcU | — | r··· (schedule) | r··· | r··· |
| `edicai.library_*` | rwcU | — | — | — | book/member r· | rwc· | — |
| `edicai.notice` | rwcU | rwcU¹ | rwcU¹ | — | — | r··· | — |
| `edicai.notification.log` | r· | r· | r· | r· | — | — | — |

¹ notice-board CSV grants registrar full create *and unlink* (likely unintended; flag).
No dedicated "Placement Officer"/"Librarian"/"Guardian" backend groups exist —
 remodeling is staff/faculty/manager/registrar/finance/admin/student/portal only.

## 4. Announcements / product updates (Recent Updates inputs)

- **`edicai.notice`** (`edicai_notice_board`): `mail.thread` model — title, html body,
  `notice_type` {general, academic, exam, fee, event}, **`audience`** {all, students,
  faculty, guardians, specific}, publish/expiry dates, pinned, company + campus/program m2m.
  Audience field exists but is **not enforced by any record rule** in the backend — it is
  only honored by portal templates. No read group for students/faculty.
- **Product updates:** **no release-note/changelog store exists anywhere** (only studio
  version changelogs, unrelated). A lightweight published product-update source must be
  net-new.
- `edicai_notify`: trigger/whatsapp/log delivery pipeline — **not** a feed source
  (transational notifications, not announcements); logs not student-visible.

## 5. Onboarding / Getting Started

- Nothing shipped (studio-core localStorage flag only). Net-new persistence required.
- Institution profile module mentions a planned "onboarding wizard" (comment only, not shipped).

## 6. Role groups (from `edicai_base/security/edicai_groups.xml`, noupdate=1)

`group_edicai_admin` (→ base.group_erp_manager), `_manager`, `_registrar`, `_finance`,
`_staff` (→ base.group_user), `_faculty` (→ base.group_user), `_student` (→ base.group_portal).
Windows demo users: admin (+website editor/designer, API admin), registrar01, faculty01,
finance01, student01 (backend-only student). No guardian backend user — guardian features
are portal-only (`/my/edicai/guardian`).

## 7. Conventions to follow (quote-verified)

```js
// data fetch pattern (edicai_overview_dashboard.js)
this.orm = useService("orm");
const data = await this.orm.call("edicai.overview.dashboard", "get_overview_data", [],
    { company_id, campus_id });
```
Assets pattern: `web.assets_backend` with `('include','web.chartjs_lib')` + explicit
scss/xml/js listing (edicai_base manifest). Registry pattern: `registry.category("actions").add(tag, Component)`.

## 8. Fragilities found (do not copy)

1. `safe_count` swallows AccessError → silently renders zero (hide nothing; surface errors).
2. Full-recordset `.mapped()` sums in overview (perf) — use `read_group`/`search_read` aggregates.
3. Chart render `setTimeout(100)` race — bind to DOM refs and render on state change.
4. `menu_edicai_root` gated on single `group_edicai_staff` — role visibility story is inconsistent.
5. Registrar has unlink on notices (CSV bug, separate fix, needs approval).
6. `edicai_navigation` preview reparents 51 menus when ON — keep the Home as a client
   action record (not a reparented menu item); verify coexistence with `EdicaiNavPreviewBadge`
   (a `main_components` registrant; no WebClient patch — safe).
7. `apps_landing_action.xml` was `noupdate=1` and theme is uninstalled; landing via
   `action_id` needs an explicit, reversible write (snapshot first).

## 9. Proposed architecture (Phase 2 sketch, for review)

- **Net-new module `edicai_home`** (web, mail, edicai_base + edicai_notice_board only).
- One `ir.actions.client` → OWL `edicai_home.Home` with tabs **Dashboard / Getting Started
  / Recent Updates**; server model `edicai.home.data` returns a role-profiled payload in a
  **single ORM call** (widgets selected server-side from actual groups; deterministic dedupe).
- Widgets reuse patterns (not code) from the three OWL dashboards; charts via chartjs_lib.
- **Getting Started:** `edicai.onboarding.item` (role-keyed seed data, noupdate) +
  `edicai.onboarding.state` (per-user progress; runtime completion where derivable from
  real records — e.g., "review permissions" auto-true for admin after config counts).
- **Recent Updates:** new `edicai.product.update` (publish state/date/title/summary/body,
  company, audience group restriction) **+** filtered reuse of `edicai.notice` for
  institutional announcements (publish/expiry/audience applied server-side, respect access).
- **Landing wire-in:** reversible write of `action_id` (snapshotted in `ir.config_parameter`)
  to the new action for internal users; standard Preferences→Home Action still wins.
- Tests: role→widget determinism, access boundaries (student sees no finance KPI),
  onboarding state roundtrip, update visibility, empty/error states.

## 10. Untouched-guard confirmation

No production impact: module installs only into `edicai_preview`; baseline DB and
:18069 stay as-is; module not added to any auto-install chain.
