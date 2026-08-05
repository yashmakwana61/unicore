# Gap-Fill — 5 Open Gaps Closed (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 17 new tests green, migration verified on real DB.
**Closes the 5 open gaps recorded at the end of Phase 8.** The 8-phase migration is now feature-complete
for the multi-entity story.

---

## ROLE

You are a senior Odoo architect on UniCore. The 8-phase migration ended with 5 documented open gaps.
This gap-fill closes every one of them. All work is additive and **legacy-inert**: a legacy university
(no profile, or `is_legacy_university=True`) sees byte-identical behavior and vocabulary.

The 5 gaps and their fills:
1. **`course.department_id` still required for non-legacy schools** → made optional with a
   legacy-enforcing check + view `required="is_legacy_institution"`.
2. **Terminology only a helper + preview, not wired into static view field labels** → runtime
   `ir.ui.view.get_view()` rewrite gated on the company's terminology profile.
3. **Admission-cycle `cohort_kind` binding** → `unicore.admission.applicant` carries cohort_kind +
   grade_level_id, validated and passed through on confirmation.
4. **Report/portal cohort filters** → the analytics SQL view + faculty/guardian portals surface
   `cohort_kind` / `grade_level_id` / `cohort_start_date`.
5. **Graduation/convocation cohort grouping** → convocation smart buttons group graduates by cohort.

Hard exit criteria:
1. Legacy path 100% unchanged (university vocabulary + department-required courses + semester cohorts).
2. Zero regression on the full suite — identical pre-existing failure set (`6 failed, 3 error(s)`).
3. Tag-list expansion (`/unicore_analytics` added) is deliberate and recorded (precedent: Phases 2/8).
4. Test count grows monotonically.

---

## WHAT CHANGED

### Gap 1 — optional `course.department_id` (`unicore/custom_addons/unicore_curriculum/`)

**`models/unicore_course.py`**
- Removed `required=True` from `department_id` (kept the field + default).
- NEW `_check_course_department()` — a legacy institution (no profile or
  `is_legacy_university=True`) with **no** department on a course → `ValidationError`
  ("A Department is required for legacy institutions."). Non-legacy schools may omit it.
- Wired into explicit `create(vals_list)` / `write(vals)` overrides under the
  `# ------- COHORT / ANCHOR (Gap-1 shim) -------` header (create always; write only when
  `department_id` is in `vals`) — same constrains-skip rationale as Phase 1 (`@api.constrains` won't
  fire on create when a now-optional field is absent from `vals`).

**`views/unicore_course_views.xml`**
- Form Identity group: `<field name="department_id" required="is_legacy_institution"/>` so the UI
  enforces the same rule (hidden legacy shim `is_legacy_institution` already present from Phase 2).

**Tests:** `tests/test_course_department.py` (NEW, 4, tagged `unicore/unit`):
01 legacy course w/o department → ValidationError; 02 legacy with department → ok; 03 school course
w/o department → ok (is_legacy False); 04 legacy `write` removing department → ValidationError.

### Gap 2 — terminology wired into view labels (`unicore/custom_addons/unicore_institution_profile/`)

**`models/ir_ui_view.py`** (NEW, `_inherit = 'ir.ui.view'`)
- `_TERM_VIEW_FIELDS` — m2o field name → terminology concept
  (`program_id→program`, `department_id→department`, `faculty_id→faculty`, `student_id→student`,
  `semester_id→semester`, `academic_year_id→academic_year`).
- `_TERM_VIEW_MODELS` — whitelist of UniCore models whose views are eligible
  (`unicore.student`, `unicore.enrollment`, `unicore.admission.applicant`, `unicore.program`,
  `unicore.course`, `unicore.semester`, `unicore.department`, `unicore.faculty`).
- `@api.model get_view(...)` override:
  - Calls `super()`, resolves the view's real model via `self.browse(view_id).model`
    (fallback: first key of `result['models']`). **Gotcha:** base `get_view` sets
    `result['model'] = self._name` (always `'ir.ui.view'`), so it must NOT be used.
  - Gated on `self.env.company.terminology_profile_id`; returns unchanged otherwise.
  - Cheap fast-path: if none of the generic quoted labels appear in `arch`, skip parsing.
  - `etree.fromstring(arch)` → for each `<field>` whose `name` maps to a concept, if its `string`
    equals the generic term AND `profile.resolve_label(concept)` differs → rewrite the `string`.
  - Returns `dict(result)` with re-serialized `arch` only when something changed (byte-identical
    otherwise). Legacy companies resolve to generic terms → nothing changes.

**Tests:** `unicore_enrollment/tests/test_terminology_views.py` (NEW, 4, tagged `unicore/unit`;
`setUpClass` sets `cls.company = cls.env.company`, builds a K-12 terminology profile
`code='K12TERM'` — program `Class/Section`, student `Learner`, semester `Term`,
academic_year `Session` — + school institution profile and attaches it to the company):
01 no-profile → arch unchanged; 02 K-12 rewrites enrollment `student_id`→Learner,
`semester_id`→Term; 03 K-12 rewrites `unicore.student` `program_id`→Class/Section;
04 non-whitelisted model (`unicore.course.offering`) untouched.

### Gap 3 — admission-cycle cohort binding (`unicore/custom_addons/unicore_admission/`)

**`models/admission_applicant.py`**
- NEW `cohort_kind` (related `program_id.cohort_kind`, readonly) + `grade_level_id`
  (Many2one → `unicore.academic.unit`, domain
  `[('unit_type_id.code','=','GRADE'),('company_id','=',company_id)]`, tracking,
  `ondelete='restrict'`) after `specialisation_id`.
- `action_confirm_admission()`: when `record.grade_level_id`, adds
  `student_vals['grade_level_id'] = record.grade_level_id.id`.
- `_onchange_program_id()`: clears `grade_level_id` when the program is not a grade-batch.
- NEW `@api.constrains('program_id','grade_level_id') _check_admission_cohort()` — grade-batch program
  without a grade → `ValidationError`.

**`views/admission_applicant_views.xml`**
- Title group right column: `<field name="cohort_kind" readonly="1"/>` +
  `<field name="grade_level_id" options="{'no_create_edit': True}"
  invisible="cohort_kind != 'grade_batch'" required="cohort_kind == 'grade_batch'"/>`.

**Tests:** `tests/test_admission_cohort.py` (NEW, 4, `TransactionCase` tagged `unicore/unit`; school
profile, grade unit, campus, AY, admission.cycle; `_program` passes `academic_unit_id=self.grade.id` —
**Phase-1 anchor gotcha**: without it the computed `program.company_id` is False → treated legacy →
ValidationError):
01 grade_batch without grade → ValidationError; 02 grade_batch confirm binds grade onto the student;
03 rolling confirm auto-fills `cohort_start_date`; 04 academic_year confirm unchanged.

### Gap 4 — report/portal cohort filters (`unicore/custom_addons/unicore_analytics/` + portals)

**`models/unicore_student_analytics.py`**
- `UniCoreStudentEnrollmentReport` adds `cohort_kind` (Selection with labels matching the program:
  Academic Year / Batch, Grade-Level Batch, Rolling Intake), `grade_level_id`
  (Many2one → `unicore.academic.unit`), `cohort_start_date` (Date).
- SQL view `SELECT` + `GROUP BY` now include `s.cohort_kind, s.grade_level_id, s.cohort_start_date`.

**`views/unicore_student_analytics_views.xml`**
- Pivot adds `cohort_kind` / `grade_level_id` rows; list adds
  `cohort_kind` / `grade_level_id` / `cohort_start_date`; search adds the two fields + three group-by
  filters (`group_by_cohort_kind`, `group_by_grade_level`, `group_by_intake`).

**`unicore_portal_faculty/views/portal_faculty_templates.xml`** — course student table adds a
`Cohort` column after Name (`<td><t t-esc="sd['student'].cohort_label"/></td>`).
**`unicore_portal_guardian/views/portal_guardian_templates.xml`** — ward card header adds a cohort badge
when `student.cohort_kind != 'academic_year'`.

**Tests:** `tests/test_student_report_cohort.py` (NEW in a new `unicore_analytics/tests/` + `__init__`,
2, tagged `unicore/unit`):
01 report surfaces `cohort_kind` + `grade_level_id` + `student_count` for grade-batch students;
02 `read_group` breaks down by `grade_level_id` (2 vs 1).

**Debugging note (resolved):** the view row initially read `cohort_kind=False` while the ORM read
`'grade_batch'`. Root cause: `student.cohort_kind` is a **stored related** field — raw SQL views only
see **flushed** writes, and the test's single `create()` hadn't flushed. Fix: `self.env.flush_all()`
before querying the report (correct Odoo semantics; production flushes naturally on form save).

### Gap 5 — convocation cohort grouping (`unicore/custom_addons/unicore_convocation/`)

**`models/event_event_ext.py`** — NEW `action_view_convocation_graduates()` → act_window on
`unicore.student`, domain `[('convocation_event_id','=',self.id)]`, context
`{'search_default_group_cohort_kind': 1}`.

**`models/student_convocation_ext.py`** — NEW `action_view_convocation_cohort_mates()` — uses
`self._cohort_members_domain()` (from Phase 6) or `[('id','=',self.id)]`, appends
`('convocation_event_id','=',self.convocation_event_id.id)`, `UserError` when no convocation event,
context `group_cohort_kind`.

**`views/event_event_views.xml`** — smart button "Graduates by Cohort" in the
`//div[hasclass('oe_button_box')]`, type="object", `fa-graduation-cap`,
`invisible="not unicore_convocation_event"`.

**Tests:** `tests/test_convocation_cohort.py` (NEW, 3, tagged `unicore/convocation`; mirrors
`test_convocation.py` setUpClass — faculty, dept, program, campus, AY, convocation event, graduated
student): 01 event action domain + context; 02 cohort mates share convocation + batch year;
03 no event raises `UserError`.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_institution_profile,unicore_analytics,unicore_admission,unicore_curriculum,
unicore_convocation,unicore_enrollment` on **`odoo_p0_baseline`** and on the real **`odoo`** DB.

| Check | Result |
|---|---|
| Upgrade exit code | EXIT=0 (both DBs) |
| ERROR/CRITICAL lines | 0 CRITICAL / 0 non-benign ERROR (both DBs; only the pre-existing docutils "Unexpected indentation" noise) |
| SQL view | `unicore_student_enrollment_report` rebuilt with all 14 columns incl. `cohort_kind`, `grade_level_id`, `cohort_start_date` (verified via psql earlier) |

### Isolated runs
| Tag list | Result |
|---|---|
| `/unicore_curriculum` | 0 failed, 0 errors (12 tests) |
| `/unicore_convocation` | 0 failed, 0 errors (12 tests) |
| `/unicore_enrollment,/unicore_analytics` | 0 failed, 0 errors (14 tests) |
| `/unicore_admission` | 1 failed, 1 error — **only the 2 PRE-EXISTING failures** (`test_14_record_fee_payment`, `test_12_publish_grade`); all 4 new cohort tests pass |

### Zero regression — identical failure set
Full 20-module suite (with `/unicore_analytics` added to the tag list) on the real `odoo` DB:

```
6 failed, 3 error(s) of 186 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 169 → **186** (+4 Gap1 + 4 Gap2 + 4 Gap3 + 2 Gap4 + 3 Gap5 = 17 new, all green).

> **Scope decision (flagged):** `/unicore_analytics` was added to the full-suite tag list
> (19 → 20 modules) — the same precedent as Phase 2 adding `/unicore_curriculum` and Phase 8 adding
> `/unicore_calendar`. `unicore_analytics` previously had **no tests**; Gap 4 gives it 2.

---

## EXIT CRITERIA — ALL MET

| # | Criterion | Status |
|---|---|---|
| 1 | Legacy path 100% unchanged | ✅ Only legacy-gated checks + additive fields; all legacy tests pass |
| 2 | Terminology wired into labels, legacy-inert | ✅ Runtime rewrite; legacy resolves generic → byte-identical arch |
| 3 | Zero regression (identical `6 failed, 3 error(s)`) | ✅ 186 tests, exact pre-existing set |
| 4 | Tag-list expansion deliberate + recorded | ✅ `/unicore_analytics` added, precedent cited |
| 5 | Test count grows | ✅ 169 → 186 (+17) |

**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

**Test trajectory:** `100 → 116 → 122 → 137 → 144 → 149 → 152 → 156 → 160 → 169 → 186`.

**Next candidates (post-gap-fill, out of scope):** `unicore_alumni`/`unicore_crm` are installed but
uninstalled on this DB; deeper K-12 features (division/timetable), or tightening the remaining
pre-existing failure set (fees payment rounding, API current-semester, admission publish-grade,
website setUpClass).
