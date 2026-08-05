# Phase 3 — Cohort Kinds (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 7 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 3 = make **how students are grouped into
cohorts** an explicit, per-program property (`cohort_kind`), so non-university entities
(K-12 schools, training / coaching centres) can model grade-level and rolling cohorts — while the
legacy university path (cohorts by admission academic year) stays **100% identical**.

- `cohort_kind` Selection on `unicore.program`: `academic_year` (default, legacy), `grade_batch`
  (K-12), `rolling` (training / coaching).
- A computed `cohort_grouping_label` gives a human-readable description of the grouping.
- Legacy universities are **locked** to `academic_year` (UI-readonly + model validation).

Hard exit criteria (from §5):
1. Legacy path 100% unchanged — existing programs keep `academic_year`, no student/enrollment
   behavior change in this phase.
2. Zero regression on the full suite (identical pre-existing failure set).
3. Validation enforced at both `create()` and `write()` time for API-level calls.
4. No changes to student/enrollment models (cohort-driven defaults are a DEFERRED follow-on).

---

## WHAT CHANGED

### `unicore.program` model (`unicore/custom_addons/unicore_academic/models/unicore_program.py`)
- **NEW** `cohort_kind` Selection, `default='academic_year'`, `tracking=True`:
  - `academic_year` — "Academic Year / Batch" (legacy: students grouped by admission year)
  - `grade_batch` — "Grade-Level Batch" (K-12: grade-level cohorts)
  - `rolling` — "Rolling Intake" (training / coaching: intakes by start date)
- **NEW** `cohort_grouping_label` computed (non-stored), `depends('cohort_kind')`, per-kind labels.
- **NEW** `_check_cohort_kind()`: raises `ValidationError`
  ("University (legacy) institutions can only use Academic Year / Batch cohorts.") when
  `is_legacy_institution` and `cohort_kind != 'academic_year'`.
- Wired into the **same** `create()`/`write()` overrides as Phase 1's `_check_program_anchor`:
  `create()` runs `_check_program_anchor()` + `_check_cohort_kind()` on the created records;
  `write()` runs `_check_cohort_kind()` only when `'cohort_kind' in vals`.
  > Not `@api.constrains` for the same reason as Phase 1: a constrain on `('cohort_kind')` would
  > not fire on anchor-less `create()` when the field is absent from vals.

### Views (`unicore/custom_addons/unicore_academic/views/unicore_program_views.xml`)
- **Form** (right group, after `credit_system`): `<field name="cohort_kind"
  readonly="is_legacy_institution"/>` + `<field name="cohort_grouping_label" readonly="1"/>` —
  legacy users see the field but it is locked in the UI too.
- **List**: `<field name="cohort_kind" optional="hide"/>` after `program_type`.
- **Search**: `<field name="cohort_kind"/>` (filterable) + groupby filter `groupby_cohort`
  "Cohort Kind" in the group-by group.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_academic` on **`odoo_p0_baseline`** (pre-Phase-0 schema) and on the real **`odoo`** DB.

| Check | Result |
|---|---|
| `unicore_program.cohort_kind` column | ADDED ✓ (both DBs) |
| Existing programs keep `academic_year` | ✓ — all 3 programs on baseline AND real DB are `academic_year` (legacy preserved) |
| Upgrade exit code | EXIT=0 (both DBs; 133 modules loaded) |
| Tracebacks during upgrade | ALL benign "External ID not found … Skipping deletion" cleanup (e.g. `unicore_academic.action_unicore_department_kanban`); real DB: 176 tracebacks / 352 messages, **0 non-external errors** |

### Zero regression — identical failure set
Full 18-module suite (with `/unicore_curriculum`) on the real `odoo` DB:

```
6 failed, 3 error(s) of 144 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0/1/2):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 137 → **144** (+7 Phase 3 tests). All 7 new tests green. (First full-suite run had
a 4th error from my own test's `setUpClass` — faculty code 'P3FA' contained a digit; fixed to
letters-only 'PFAC', then clean.)

### Phase 3 tests
`unicore_academic/tests/test_program_cohort_kind.py` (7, tagged `unicore`/`unit`):
- test_01_legacy_default_cohort_kind — legacy program defaults `academic_year` + label non-empty.
- test_02_legacy_cannot_use_grade_batch — `create(cohort_kind='grade_batch')` on legacy → ValidationError.
- test_03_legacy_cannot_use_rolling — `create(cohort_kind='rolling')` on legacy → ValidationError.
- test_04_school_grade_batch_ok — school profile + grade-level unit → `grade_batch` allowed,
  `is_legacy_institution` False, label correct.
- test_05_school_rolling_ok — school/training profile + unit → `rolling` allowed.
- test_06_legacy_write_locked — `write(cohort_kind='grade_batch')` on legacy → ValidationError.
- test_07_label_follows_kind — label recomputes when `cohort_kind` changes.

---

## GOTCHAS ENCOUNTERED (Phase 3)

1. **Faculty codes are LETTERS-ONLY** (re-hit). First draft used `'P3FA'` (digit) →
   `ValidationError: Faculty code must contain only letters`. Fixed to `'PFAC'`. Department codes
   allow alphanumeric (`'P3ENG'` fine).
2. **Same create()/write() override pattern as Phase 1** — `_check_cohort_kind` cannot be a plain
   `@api.constrains` on `('cohort_kind')` because it would silently skip on anchor-less `create()`
   when the field is absent from vals.
3. **UI-readonly for legacy** (`readonly="is_legacy_institution"`) complements, not replaces, the
   model check — API writes are still guarded by `_check_cohort_kind` in `write()`.
4. The ~176 "External ID not found … Skipping deletion" tracebacks during upgrade are **pre-existing**
   benign cleanup, not from Phase 3.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy path 100% unchanged — existing programs remain `academic_year`; no student/enrollment field or behavior change.
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 137→144 tests.
- [x] Validation enforced at create() AND write() (`_check_cohort_kind` in both overrides).
- [x] K-12 / training entities can select `grade_batch` / `rolling` (school-profile tests).
- [x] No changes to student/enrollment models (cohort-driven defaults deferred to follow-on).
- [x] Upgrade applied to real `odoo` DB (`-u unicore_academic`), schema + data verified.

**Files touched:** `unicore/custom_addons/unicore_academic/{models/unicore_program.py,
views/unicore_program_views.xml, tests/__init__.py, tests/test_program_cohort_kind.py (new)}`.
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

---

## NEXT PHASE (Phase 4 — planned, NOT started)
Phase 4 continues the multi-entity rollout. Candidate scope (to be confirmed against the deep
migration plan): leveraging `cohort_kind` for **cohort-driven enrollment defaults** (grade/cohort
fields on student, intake-based batch derivation, rolling-intake scheduling) — deferred from Phase 3
to keep the legacy student/enrollment path untouched. Apply the same discipline: verify → build →
exit criteria → zero regression → record.
