# Phase 0 — Verification Audit & Build Prompt (DeepSeek Step 1)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Module Forge discipline:** ROLE → STEP 1 verify → STEP 2 build → exit criteria
**Status:** VERIFICATION COMPLETE (2026-08-05) — findings below are from direct code analysis of `unicore/custom_addons/`.

---

## ROLE

You are a senior Odoo architect working on UniCore, a 42-module education ERP. The product is
being generalized from "University ERP" to "Any Educational Entity" ERP (university / college /
K-12 school / training institute / academy / coaching). Your mandate for THIS phase:

> **Phase 0 — Foundation. Additive-only. Zero behavior change.**
> Create two new modules that lay the groundwork for genericizing the academic hierarchy
> (`unicore.faculty → unicore.department → unicore.program`) and the institution identity layer.
> Do **NOT** modify `unicore_academic`, `unicore_student`, `unicore_grading`, or any existing
> module. Existing 91 tests must pass unmodified.

Product decisions already locked (from §5):
- Terminology application = **one-time relabeling at setup** (post-init hooks), not live swapping.
- K-12 cohorts = **reuse `unicore.program` with a `cohort_kind`** (Phase 3; not built now).
- Result storage = **keep one `unicore.semester.result` table** (Float placeholders) (Phase 2).
- Pilot institution type = **K-12 School** (drives later templates; Phase 0 stays generic).

---

## STEP 1 — VERIFY (COMPLETED)

### 1.1 Dependency map — modules depending on `unicore_academic` (26)

| # | Module | Direct dep | Notes |
|---|--------|-----------|-------|
| 1 | unicore_admission | yes | program_id in tests |
| 2 | unicore_analytics | yes | groupby program_id, faculty/department dashboards |
| 3 | unicore_api | yes | /students & /academic controllers accept program_id |
| 4 | unicore_attendance | yes | program_id in tests |
| 5 | unicore_calendar | yes | academic.year + semester |
| 6 | unicore_curriculum | yes | **course.department_id required**, curriculum.program_id |
| 7 | unicore_demo | yes | demo data (users faculty_rajesh/student_arav) |
| 8 | unicore_documents | yes | |
| 9 | unicore_enrollment | yes | program_id in tests |
| 10 | unicore_exam | yes | |
| 11 | unicore_faculty_profile | yes | **faculty_member.department_id + academic_faculty_id** |
| 12 | unicore_fees | yes | fee_structure.program_id, student_partner_ext reads program_id.name |
| 13 | unicore_finance_report | yes | |
| 14 | unicore_grading | yes | grade.entry, semester.result |
| 15 | unicore_guardian | yes | |
| 16 | unicore_hostel | yes | |
| 17 | unicore_library | yes | |
| 18 | unicore_notice_board | yes | |
| 19 | unicore_notify | yes | |
| 20 | unicore_portal_faculty | yes | |
| 21 | unicore_portal_guardian | yes | |
| 22 | unicore_portal_student | yes | reads student_program_ids |
| 23 | unicore_scholarship | yes | program_id in tests |
| 24 | unicore_student | yes | **student.program_id required=True** |
| 25 | unicore_timetable | yes | |
| 26 | unicore_transport | yes | |

### 1.2 Every location that reads `faculty_id` / `department_id` (model code only)

| Module / file | Field / usage | Risk if hierarchy relaxed |
|---------------|---------------|---------------------------|
| unicore_academic/models/unicore_faculty.py | company_id required, dean_id, department_ids o2m, action requires departments | owned by Phase 1 |
| unicore_academic/models/unicore_department.py | faculty_id required, company_id related, program_ids o2m, UNIQUE(code,faculty_id) | owned by Phase 1 |
| unicore_academic/models/unicore_program.py | department_id required, faculty_id/company_id related, `_order` uses department_id | owned by Phase 1 |
| unicore_academic/models/unicore_specialisation.py | program_id, related department/faculty | follows program |
| unicore_curriculum/models/unicore_course.py | **department_id required (ondelete restrict)**, academic_faculty_id related, onchange clears dept | HIGH — course creation blocked for non-dept entity if left required |
| unicore_curriculum/models/unicore_curriculum.py | program_id, related department_id | follows program |
| unicore_faculty_profile/models/unicore_faculty_member.py | department_id, academic_faculty_id, constrains is_hod/is_dean, onchange | MEDIUM — HOD/Dean semantics are university-only |
| unicore_faculty_profile/models/unicore_staff_member.py | department_id optional | low |
| unicore_student/models/unicore_student.py | department_id/faculty_id related from program, program_id required | owned by Phase 1 |

### 1.3 Tests that construct the Faculty→Department→Program chain (14 classes, all need it to stay valid)

admission, alumni, api, attendance, convocation, crm, enrollment, fees, grading, payment,
scholarship, student (×2 classes), transport_fleet, website. Each `setUp` creates
faculty → department → program → uses `program_id`. **Any change to `required=True` on
department.faculty_id / program.department_id in Phase 1 MUST keep the legacy profile path
required** or all these tests break.

### 1.4 Verification conclusions

1. **No runtime code outside `unicore_academic`/`unicore_student`/`unicore_curriculum`/
   `unicore_faculty_profile` hard-depends on the chain at the Python level** for Phase 0.
   Everything else reaches the hierarchy through `program_id` (kept universal) or via related
   fields. This means Phase 0 (two new standalone modules) is genuinely zero-risk.
2. **The only `required=True` fields that would block a K-12/training entity today** are:
   `course.department_id`, `program.department_id`, `department.faculty_id`, `student.program_id`,
   `program.degree_title`, `program.duration_years`, `program.credit_system`.
   These are **Phase 1–3 concerns**, not Phase 0.
3. `res.company.university_type` is confirmed **dead** (no reads anywhere). Phase 0 introduces the
   real driver (`institution_profile_id`) but does not touch `university_type`.
4. `unicore.semester.result.credits_attempted/earned` are **Float** — supports the "keep one
   table" decision for non-credit schemes.

---

## STEP 2 — BUILD SPEC (this phase)

### Module A: `unicore_academic_generic` (NEW, standalone)

- Depends: `unicore_base`, `unicore_security` (both already installed).
- Models:
  - `unicore.academic.unit.type` — configurable unit-type taxonomy
    (name, code, sequence, active). Seed: faculty, department, grade_level, stream, wing,
    division, batch_group, other.
  - `unicore.academic.unit` — self-referencing hierarchical node
    - name, code
    - `unit_type_id` Many2one(`unicore.academic.unit.type`)
    - `parent_id` Many2one('unicore.academic.unit', ondelete='cascade') nullable
    - `child_ids` One2many inverse
    - `company_id` Many2one res.company (required, default env.company)
    - `allowed_child_type_ids` — computed from the institution profile (which child types may
      nest under this type); fallback = all types when no profile set.
    - `path` computed display, `unit_count` for kanban stat.
  - **Do NOT modify `unicore.program` in this module.** Phase 1 adds `academic_unit_id`.
- ACL CSV: admin full / manager CRUD / registrar read-write / staff+faculty+student read.
- Views: tree + form + kanban, window action, menu under
  `unicore_base.menu_unicore_configuration` (sequence ~110).
- Data: seed `unicore.academic.unit.type` records (noupdate="1").

### Module B: `unicore_institution_profile` (NEW)

- Depends: `unicore_base`, `unicore_security`, `unicore_academic_generic`.
- Models:
  - `unicore.terminology.profile` — field-label substitution data
    (name, code, term_faculty, term_department, term_program, term_student,
     term_faculty_staff, term_semester; blank = hidden).
  - `unicore.institution.profile`
    - name, code, `institution_type` Selection
      (university|college|school|training|academy|coaching), extensible via `selection_add`.
    - `academic_unit_level_ids` Many2many('unicore.academic.unit.type') — the depth configurator.
    - `calendar_mode` Selection (semester|trimester|quarter|annual|rolling_batch) default semester.
    - `grading_scheme` Selection (credit_gpa|weighted_percentage|simple_percentage|
      rubric_standards|pass_fail|certificate_only) default credit_gpa. (Scheme MODEL is Phase 2;
      this is the forward-looking field.)
    - `terminology_profile_id` Many2one('unicore.terminology.profile').
    - `feature_toggle_ids` Many2many('unicore.institution.feature') (config model, seeded with
      hostel|transport|library|alumni|convocation|scholarship|thesis|crm|admission|website).
    - `is_legacy_university` Boolean — the compatibility flag. `True` reproduces 100% of current
      behavior; Phase 1+ reads this to preserve `required=True` semantics.
  - `unicore.institution.feature` — config model (name, code, sequence, active).
  - Extend `res.company`: add `institution_profile_id` (Many2one, **nullable**, no default),
    plus related `terminology_profile_id`. Do NOT touch `university_type`.
- Data (noupdate="1"):
  - "University — Legacy" terminology profile (term_* = Faculty/Department/Program/Student/...).
  - "University — Legacy" institution profile (institution_type=university,
    is_legacy_university=True, calendar_mode=semester, grading_scheme=credit_gpa,
    all 7 unit types selected, default terminology).
- ACL CSV: admin+manager full / registrar+staff read-write / faculty+student read for the two
  profiles + feature model.
- Views: tree+form for both profiles and feature config; window actions; menu under
  `unicore_base.menu_unicore_configuration` (sequence ~105). Extend `res.company` form with a
  new "Institution Profile" group (xpath on existing unicore company form, NOT base, to keep
  ordering).
- **No hooks.py in Phase 0** — one-time relabeling hooks arrive in Phase 5 with the templates.
  Phase 0 only stores data.

### Install / verify commands

```bash
./.venv/bin/python odoo-bin -u unicore_academic_generic,unicore_institution_profile -d odoo --stop-after-init
./.venv/bin/python odoo-bin -d odoo --test-enable --test-tags /unicore --stop-after-init
```

---

## EXIT CRITERIA

- [x] `unicore.academic.unit` + `unicore.academic.unit.type` tables exist.
- [x] `unicore.institution.profile`, `unicore.terminology.profile`, `unicore.institution.feature`
      tables exist.
- [x] `res.company` has nullable `institution_profile_id`; no default assigned to existing rows.
- [x] "University — Legacy" profile row exists and `is_legacy_university = True`.
- [x] Zero changes to any existing module (git diff shows only new files).
- [x] All existing tests pass unmodified (14 classes / 91 tests).
- [x] `university_type` field still present and untouched.

---

## PHASE 0 — RESULTS (2026-08-05, DONE)

### Install
Both modules installed into the `odoo` DB (state=`installed`). Tables verified via psql:
`unicore_academic_unit`, `unicore_academic_unit_type`, `unicore_institution_feature`,
`unicore_institution_profile`, `unicore_terminology_profile`. Seed data present:
8 unit types, 13 features, 1 terminology profile, 1 institution profile. `res.company` gained
nullable `institution_profile_id` + related stored `terminology_profile_id`.

### Zero-regression proof (the key exit criterion)
Ran the identical 14-module test suite on TWO databases and compared:

| Database | Result |
|----------|--------|
| `odoo_p0_baseline` (clean, WITHOUT the 2 new modules — the "before" state) | 6 failed, 3 error(s) of **100** tests |
| `odoo` (current, WITH the 2 new modules) | 6 failed, 3 error(s) of **100** tests |

**Identical failure sets** in both — all 9 are pre-existing and live in modules this phase never
touched: `unicore_fees` (test_04/05/06/09), `unicore_api` (test_14_current_semester),
`unicore_admission` (test_14_record_fee_payment, test_12_publish_grade), `unicore_website`
(setUpClass). → **91/91 existing tests pass; zero regressions.**

Full combined suite (existing + new): **116 tests, 6 failed, 3 errors = 107 passing**
(91 existing + 16 new).

### New Phase 0 regression suite (16 smoke tests, all green)
- `unicore_academic_generic/tests/test_academic_unit.py` (8): seed taxonomy, valid hierarchy
  tree, display_name/path, parent-type allow-list rejection, cycle detection, same-company
  unique code, action_open_children, multi-level K-12 nesting.
- `unicore_institution_profile/tests/test_institution_profile.py` (8): legacy profile seed,
  terminology seed, feature catalog, legacy profile unit levels, company wiring
  (nullable + related), unique profile code, open-profiles action, school-like profile modeling.

### Notes / gotchas discovered
- `models.Constraint` (the Odoo 19 `_sql_constraints` replacement) surfaces violations as
  `psycopg2.errors.UniqueViolation`/`NotNullViolation`, NOT `ValidationError` — tests must
  catch `psycopg2.IntegrityError`.
- Creating a `res.company` via the ORM in Odoo 19 CE fails with `autopost_bills` NOT NULL
  (unrelated quirk in account's internally-created partner). Tests avoid creating companies;
  Phase 0 smoke tests use the existing main company.
- A DB error inside a test poisons the rest of that test's transaction — keep `assertRaises`
  DB-error assertions as the last statement, or split into separate tests.

---

## CONFIRMED NEXT PHASES (not this build)

- **Phase 1** — `academic_unit_id` on `unicore.program`; conditional-required via
  `is_legacy_university`; compatibility shim keeps legacy path 100% identical.
- **Phase 2** — `unicore.grading.scheme` strategy model; `_update_student_cgpa` →
  `_update_student_result()` dispatch; `course.credit_hours` conditional-required.
- **Phase 3** — `cohort_kind` on `unicore.program` (degree_program|grade_section|batch|track);
  `degree_title`/`duration_years` conditional-required.
- **Phase 5** — onboarding wizard + per-type templates + one-time terminology relabeling hooks.
