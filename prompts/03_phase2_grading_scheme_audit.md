# Phase 2 — Grading Scheme Abstraction (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 15 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 2 = turn the dormant
`profile.grading_scheme` Selection into a first-class **`unicore.grading.scheme`** strategy model and
make grade-result computation **dispatch on the institution's effective scheme**, while keeping the
legacy `credit_gpa` path 100% identical:

- A dedicated scheme record (one per strategy) drives result computation.
- The legacy Selection stays as a fallback so unset profiles behave exactly as before.
- `course.credit_hours` becomes **conditionally required** (mandatory only for legacy universities)
  through the same `is_legacy_university` shim as Phase 1.

Hard exit criteria (from §5):
1. Legacy path 100% unchanged — CGPA math, grade flow, and every existing test behave identically.
2. Zero regression on the full suite (identical pre-existing failure set).
3. `cohort_kind` is Phase 3 — MUST NOT be added now.
4. A non-legacy institution can pick a non-GPA scheme and get the matching aggregate result.

---

## WHAT CHANGED

### `unicore.grading.scheme` model — lives in `unicore_institution_profile`
> **Why here?** `unicore_grading → unicore_academic → unicore_institution_profile`, so
> `unicore_institution_profile` CANNOT depend on `unicore_grading`. The scheme model is a pure
> configuration catalog, so it belongs with the other profile config models anyway.

`unicore/custom_addons/unicore_institution_profile/models/unicore_grading_scheme.py`:
- `name` (Char, translate), `code` (Char size 20), `scheme_type` (Selection of the 6 profile options),
  `sequence` (default 10), `is_default` (Boolean), `description` (Text).
- `_unique_scheme_code = models.Constraint('UNIQUE(code)', …)`.
- Wired into `models/__init__.py`, ACL (`security/ir.model.access.csv`, profile pattern:
  admin 1,1,1,1 / manager 1,1,1,0 / registrar 1,1,0,0 / staff+faculty+student 1,0,0,0),
  `views/unicore_grading_scheme_views.xml` (list + form + act_window), menu seq 107 under
  `unicore_base.menu_unicore_configuration`, manifest data list.
- 6 seed records (noupdate=1) in `data/unicore_institution_profile_data.xml`:
  `CREDIT_GPA` (is_default), `WEIGHTED_PCT`, `SIMPLE_PCT`, `RUBRIC_STD`, `PASS_FAIL`, `CERT_ONLY`.

### `unicore.institution.profile`
- **NEW** `grading_scheme_id` Many2one → `unicore.grading.scheme` (nullable, tracking). The legacy
  `grading_scheme` Selection is KEPT as the fallback (label now "Grading Scheme (legacy)").
- **NEW** computed `effective_grading_scheme` = `grading_scheme_id.scheme_type or grading_scheme`.
- Form view: `grading_scheme_id`, `effective_grading_scheme` (readonly), `grading_scheme`.

### `res.company._get_effective_grading_scheme()` helper
Resolution order:
1. `profile.grading_scheme_id.scheme_type` (dedicated record)
2. `profile.grading_scheme` (legacy selection)
3. `'credit_gpa'` (no profile / unset → legacy university default)

Guarantees: a company without a profile (or on UNI_LEGACY) resolves to `credit_gpa`.

### Grade-entry dispatch (`unicore_grading/models/unicore_grade_entry.py`)
- `_update_student_cgpa()` is **preserved** as the entry point (still called by `_update_enrollment()`
  from `action_publish`) and now dispatches on the company effective scheme:
  - `credit_gpa` (and any unknown fallback) → `_update_student_result_credit_gpa()` — **exact old
    CGPA math** (`sum(grade_points_earned)/sum(credit_hours)` over published|locked, credit_hours>0).
  - `simple_percentage` / `weighted_percentage` → `_update_student_result_percentage()` — writes
    `student.average_percentage` = mean of `e.percentage` over published|locked.
  - `pass_fail` / `rubric_standards` / `certificate_only` → `_update_student_result_pass_fail()` —
    writes `student.courses_passed` / `student.courses_failed` counts.

### Student aggregate fields (`unicore_grading/models/unicore_enrollment_ext.py`)
Added to `UniCoreStudentGradingExt`: `average_percentage` (Float 5,2 default 0.0),
`courses_passed` (Integer default 0), `courses_failed` (Integer default 0).

### Course conditional `credit_hours` (`unicore_curriculum`)
- `unicore_course.py`: `required=True` **removed** from `credit_hours` (default 3.0 kept); **NEW**
  computed `is_legacy_institution` (`not profile or profile.is_legacy_university`, mirrors Phase 1).
- `_check_credit_hours`: `>0` enforced **only when `is_legacy_institution`**; `<=20` cap for ALL
  institution types.
- Form view: `credit_hours required="is_legacy_institution"` + hidden `is_legacy_institution`.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_institution_profile,unicore_grading,unicore_curriculum` on **`odoo_p0_baseline`**
(pre-Phase-0 schema) and on the real **`odoo`** DB. Both EXIT=0.

| Check | Result |
|---|---|
| `unicore_grading_scheme` table + 6 seed rows | ✓ (CREDIT_GPA … CERT_ONLY) |
| `unicore_institution_profile.grading_scheme_id` column | ADDED ✓ |
| `unicore_student.average_percentage / courses_passed / courses_failed` | ADDED ✓ |
| `unicore_course.credit_hours` | now NULLABLE ✓ |
| Existing UNI_LEGACY profile | intact ✓ |

### Zero regression — identical failure set
Full 18-module suite (previous 17 + `/unicore_curriculum`) on the real `odoo` DB:

```
6 failed, 3 error(s) of 137 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0/1):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 122 → **137** (+15 Phase 2 tests). All 15 new tests green; the one initial error
(test_02 scheme unique code) was a wrong-exception-type in the test itself, fixed, then green.

### Phase 2 tests
- `unicore_institution_profile/tests/test_grading_scheme.py` (8) — create, unique code, seeded
  schemes, profile effective fallback + scheme override, company helper no-profile/legacy/scheme.
- `unicore_grading/tests/test_grading_scheme_dispatch.py` (3) — legacy credit_gpa → CGPA
  (percentage fields untouched); simple_percentage → average_percentage; pass_fail → passed/failed
  counts (one pass + one fail via two enrollments).
- `unicore_curriculum/tests/test_course_credit_hours.py` (NEW dir, 4) — legacy zero credits →
  ValidationError; legacy default 3.0 + is_legacy True; school allows 0 + is_legacy False; 21.0 cap
  for all.

---

## GOTCHAS ENCOUNTERED (Phase 2)

1. **`models.Constraint` UNIQUE violation raises `psycopg2.IntegrityError`, not `ValidationError`**
   (same as Phase 0). `test_02_scheme_code_unique` initially used `assertRaises(ValidationError)` and
   ERRORED — fixed to `from psycopg2 import IntegrityError`.
2. **The scheme model must live in `unicore_institution_profile`** — putting it in `unicore_grading`
   would create a circular dependency.
3. **`_update_student_cgpa()` name must be preserved** as the entry point (called by
   `_update_enrollment()`); the dispatch happens inside it so the legacy callers are untouched.
4. The ~176 "External ID not found … Skipping deletion" tracebacks during upgrade are **pre-existing**
   benign cleanup (`*_cleanup.xml`), not from Phase 2.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy credit_gpa path 100% identical (`_update_student_result_credit_gpa` = old math; helper falls back to `credit_gpa`).
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 122→137 tests.
- [x] `cohort_kind` NOT added (Phase 3 deferred).
- [x] Non-legacy institutions can pick a non-GPA scheme and get matching aggregates (dispatch tests).
- [x] Course credit_hours conditional: legacy still requires `>0`, non-legacy may be `0`, `<=20` cap for all.
- [x] Upgrade applied to real `odoo` DB (`-u unicore_institution_profile,unicore_grading,unicore_curriculum`), schema + data verified.

**Files touched:** `unicore_institution_profile/{models/unicore_grading_scheme.py, models/unicore_institution_profile.py,
models/res_company.py, models/__init__.py, security/ir.model.access.csv, views/unicore_grading_scheme_views.xml,
views/unicore_institution_profile_views.xml, menus/unicore_institution_profile_menus.xml,
data/unicore_institution_profile_data.xml, __manifest__.py, tests/__init__.py, tests/test_grading_scheme.py}`;
`unicore_grading/{models/unicore_grade_entry.py, models/unicore_enrollment_ext.py, tests/__init__.py,
tests/test_grading_scheme_dispatch.py}`; `unicore_curriculum/{models/unicore_course.py,
views/unicore_course_views.xml, tests/__init__.py (new), tests/test_course_credit_hours.py (new)}`.
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

---

## NEXT PHASE (Phase 3 — Cohort Kinds, planned, NOT started)
- `cohort_kind` Selection on `unicore.program` (e.g. `academic_year`, `grade_batch`, `rolling`) for
  K-12 / training / coaching batch semantics.
- Batch grouping / grade-level cohorts per institution type; cohort-driven enrollment defaults.
