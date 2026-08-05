# Phase 1 — Make the Academic Hierarchy Optional (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 6 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 1 = make the rigid
`unicore.faculty → unicore.department → unicore.program` chain **optional**, driven by the
`is_legacy_university` compatibility shim built in Phase 0:

- Legacy university (or unset institution profile) → `department_id` stays **mandatory**
  (behavior identical to before, enforced at the model level, not just the view).
- Any other institution (K-12 school, training, academy, …) → a program may anchor on a generic
  `unicore.academic.unit` (Grade Level, Wing, Batch Group…) **without** a Department.

Hard exit criteria (from §5):
1. Legacy path 100% unchanged — every existing program, test, and UI flow behaves identically.
2. Zero regression on the full 16-module suite.
3. `cohort_kind` is Phase 3 — MUST NOT be added now.
4. Non-legacy institutions can attach programs to academic units with no Department.

---

## WHAT CHANGED

### `unicore_academic/__manifest__.py`
```python
'depends': [
    'unicore_base',
    'unicore_campus',
    'unicore_security',
    'unicore_academic_generic',
    # Phase 1: is_legacy_institution reads company.institution_profile_id,
    # which is defined by unicore_institution_profile (standalone, no cycle).
    'unicore_institution_profile',
]
```
`unicore_institution_profile` is REQUIRED so `company_id.institution_profile_id.is_legacy_university`
resolves during module load. No circular dependency (that module is standalone).

### `unicore_academic/models/unicore_program.py`
| Field | Change |
|---|---|
| `department_id` | `required=True` **removed** (kept `ondelete='restrict'`, `tracking`) |
| `academic_unit_id` | **NEW** `Many2one('unicore.academic.unit')`, `ondelete='restrict'`, `tracking`, `domain="[('company_id','=',company_id)]"` |
| `company_id` | `related='department_id.company_id'` → **computed** `_compute_company_id` (store, readonly): `department_id.company_id or academic_unit_id.company_id or False` |
| `is_legacy_institution` | **NEW** computed Boolean (not stored): `not profile or profile.is_legacy_university` |

### Anchor validation (`_check_program_anchor`)
- **Legacy** (no profile or `is_legacy_university`): no Department → `ValidationError`
  "A Department is required for programs of a university (legacy) institution."
- **Non-legacy**: neither Department nor Academic Unit → `ValidationError`
  "A program must be attached to either a Department or an Academic Unit."

> **Critical implementation note.** This is NOT `@api.constrains('department_id','academic_unit_id')`.
> A constrains hook does not fire on `create()` when neither field is present in the vals — and both
> fields are now optional at the ORM level, so an anchor-less create would slip through. It is a
> plain method invoked from explicit overrides:
> - `@api.model_create_multi def create(self, vals_list)` → `records._check_program_anchor()` after `super().create()`
> - `def write(self, vals)` → call only when `'department_id' in vals or 'academic_unit_id' in vals`

### `unicore_academic/views/unicore_program_views.xml`
- **Form** (left group): `is_legacy_institution` `invisible="1"`; `department_id`
  `required="is_legacy_institution"`; `academic_unit_id` `invisible="is_legacy_institution"`.
  Both keep `options="{'no_create': True}"`.
- **List**: `academic_unit_id` added after `department_id` with `optional="hide"`.
- **Search**: `academic_unit_id` field + `<filter name="groupby_academic_unit" string="Academic Unit"
  context="{'group_by': 'academic_unit_id'}"/>` in the groupby group.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`createdb -T odoo odoo_p1_test` is BLOCKED while the dev server holds the `odoo` DB
("source database is being accessed by other users"). Used **`odoo_p0_baseline`** instead — it
carried the pre-Phase-0 schema (131 modules, `unicore_program.department_id NOT NULL`), the ideal
migration bed. After `-u unicore_academic`:

| Check | Result |
|---|---|
| `academic_unit_id` column | ADDED (nullable) ✓ |
| `department_id` NOT NULL | NULLABLE ✓ |
| `company_id` | preserved, NULLABLE ✓ |
| Existing 3 programs | intact, all still anchored to a department ✓ |
| `is_legacy_institution` | NOT stored (computed) ✓ |

### Zero regression — identical failure set
Full 17-module suite (`--test-tags "/unicore_admission,...,/unicore_academic"`) on the migrated
baseline AND on the real `odoo` DB:

```
6 failed, 3 error(s) of 122 tests
```

The **9 failures are exactly the pre-existing set** (unchanged from Phase 0):
- `unicore_fees` — test_04_partial_payment, test_05_full_payment, test_06_overpayment, test_08_cancelled (ERROR), test_09_fee_summary
- `unicore_api` — test_14_current_semester (start_date attribute missing in that module)
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 116 → **122** (+6 Phase 1 tests). All 6 new tests green.

### Phase 1 tests (`unicore_academic/tests/test_program_academic_unit.py`)
1. `test_01_legacy_program_requires_department` — no dept → ValidationError
2. `test_02_legacy_program_with_department_ok` — dept anchor; faculty/company derived; is_legacy True
3. `test_03_non_legacy_program_via_academic_unit` — school profile + grade-level unit; no dept/faculty; is_legacy False
4. `test_04_non_legacy_program_requires_an_anchor` — no anchor → ValidationError
5. `test_05_legacy_flag_follows_company_profile` — flag recomputes when profile changes
6. `test_06_legacy_anchor_cannot_be_dropped` — writing `department_id=False` → ValidationError

---

## GOTCHAS ENCOUNTERED (Phase 1)

1. **`@api.constrains` does not fire on anchor-less `create()`** → use explicit `create()`/`write()` overrides (see above). This is the single most important Phase 1 lesson.
2. **Dependency on `unicore_institution_profile` is mandatory** — otherwise
   `company_id.institution_profile_id` fails to resolve with "Wrong @depends … field 'institution_profile_id' not found in model res.company" during load.
3. **Faculty codes are letters-only** (ValidationError "must contain only letters"); test fixtures must avoid digits (`'ARTS'` not `'P1FA'`). Department codes allow alphanumeric.
4. **`createdb -T` blocked** while the DB is in use → use the pre-Phase-0 baseline DB as the migration test bed (it has the old NOT NULL schema).
5. The ~352 "External ID not found … Skipping deletion" warnings during upgrade are **pre-existing** benign cleanup (`unicore_academic_cleanup.xml` `<delete>` of already-deleted records) — same count on baseline and real DB.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy university path 100% identical (required= + constrains-equivalent shim; view `required` only for UX; model still enforces).
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 116→122 tests.
- [x] `cohort_kind` NOT added (Phase 3 deferred).
- [x] Non-legacy institutions can attach programs to academic units without a Department (test_03).
- [x] Upgrade applied to real `odoo` DB (`-u unicore_academic`), schema verified, data intact.
- [x] Real DB full suite green except the 9 pre-existing failures.

**Files touched:** `unicore_academic/__manifest__.py`, `models/unicore_program.py`,
`views/unicore_program_views.xml`, `tests/__init__.py` (new), `tests/test_program_academic_unit.py` (new).
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed). `odoo_p1_test` not created
(createdb -T blocked; baseline used instead).

---

## NEXT PHASE (Phase 2 — Grading Scheme Abstraction, planned, NOT started)
- `unicore.grading.scheme` strategy model (replaces the `grading_scheme` Selection on the profile).
- `_update_student_cgpa()` → generic `_update_student_result()` dispatch.
- `course.credit_hours` conditional-required via the same shim.
