# Phase 6 — Cohort Roster & Filtering (Verification Audit)

**Project:** UniCore → Multi-Entity Education Platform (Odoo 19 CE)
**Status:** COMPLETE (2026-08-05) — ZERO REGRESSION, 4 new tests green, migration verified on real DB.

---

## ROLE

You are a senior Odoo architect on UniCore. Phase 6 = make the cohort a **first-class grouping
primitive** so staff can see and filter everyone in the same cohort:

- K-12 `grade_batch` — a roster of all students in the same **grade level** (e.g. all Grade 5).
- Training / coaching `rolling` — a roster of all students in the same **intake** (cohort start date).
- Legacy `academic_year` — a roster of all students in the same **batch year** (the existing view).

Everything is purely **additive** and **legacy-inert**: no existing behavior changes, no new required
fields, no new stored columns (the count is computed). For legacy universities the roster is simply
the existing batch-year grouping.

Hard exit criteria:
1. Legacy path 100% unchanged — the legacy roster is exactly the existing batch-year view.
2. Membership is defined per cohort kind on **stored, searchable** fields only.
3. Zero regression on the full suite (identical pre-existing failure set: `6 failed, 3 error(s)`).
4. No behavior change to create/write/enroll flows — roster is read-only derived data + an action.

---

## WHAT CHANGED

### `unicore.student` model (`unicore/custom_addons/unicore_student/models/unicore_student.py`)
- **`cohort_members_count`** — new computed (non-stored) Integer, `depends('program_id.cohort_kind',
  'grade_level_id', 'cohort_start_date', 'batch_year')`. Counts students matching
  `_cohort_members_domain()` (0 when the cohort key is absent).
- **`_cohort_members_domain()`** — per-kind membership domain; every target field is **stored and
  searchable** (this is why the roster can use `search_count`/`search`):
  - `grade_batch` → `[('program_id', '=', p), ('grade_level_id', '=', g)]`
  - `rolling` → `[('program_id', '=', p), ('cohort_start_date', '=', d)]`
  - `academic_year` (legacy) → `[('program_id', '=', p), ('batch_year', '=', y)]`
  - Returns `False` when there is no program or no cohort key (→ count 0).
- **`action_open_cohort_members()`** — `ir.actions.act_window` on `unicore.student`, `list,form`,
  domain = `_cohort_members_domain()` (fallback `[('id', '=', self.id)]`). The roster includes self.

No new models, no ACL changes, no stored schema changes.

### Views (`unicore_student/views/unicore_student_views.xml`)
- **Form button box**: new stat button "Cohort" (`action_open_cohort_members`, icon `fa-users`,
  statinfo `cohort_members_count`) after the History button.
- **Search groupby group**: added `group_grade_level` ("Grade Level", `group_by: grade_level_id`)
  and `group_cohort_start` ("Intake Date", `group_by: cohort_start_date`). Both fields are stored →
  groupable (the Phase 4 non-stored related gotcha does not apply). Additive for all kinds.

---

## VERIFICATION (migration + zero regression)

### Migration path tested on an OLD-schema DB first
`-u unicore_student` on **`odoo_p0_baseline`** (pre-Phase-0 schema) and on the real **`odoo`** DB.

| Check | Result |
|---|---|
| Upgrade exit code | EXIT=0 (both DBs) |
| ERROR/CRITICAL lines | 5 (both DBs) — all pre-existing docutils "Unexpected indentation" docstring warnings, 0 real errors |
| Schema | No new columns (`cohort_members_count` is computed non-stored) |

### Zero regression — identical failure set
Full 18-module suite (with `/unicore_curriculum`) on the real `odoo` DB:

```
6 failed, 3 error(s) of 156 tests
```

The **9 failures are exactly the pre-existing set** (unchanged since Phase 0/1/2/3/4/5):
- `unicore_fees` — test_04, test_05, test_06, test_08 (ERROR), test_09
- `unicore_api` — test_14_current_semester
- `unicore_admission` — test_14_record_fee_payment (FAIL), test_12_publish_grade (ERROR)
- `unicore_website` — setUpClass error

Test count grew 152 → **156** (+4 Phase 6 tests). Isolated `/unicore_student` run: **0 failed,
0 errors of 23 tests** (19 existing + 4 new).

### Phase 6 tests
`unicore_student/tests/test_student_cohort_roster.py` (NEW, 4, tagged `unicore`/`unit`), mirrors the
per-test profile setup from the Phase 4/5 cohort suites:
- test_01_legacy_roster_by_batch — same program + batch_year → `cohort_members_count == 2`; a
  different batch_year → 1; `action_open_cohort_members()` domain returns the pair.
- test_02_grade_roster_by_grade_level — same program + grade level → 2; another grade level → 1.
- test_03_rolling_roster_by_intake_date — same program + cohort start (auto-filled from admission
  date by Phase 5) → 2; a different intake date → 1.
- test_04_action_opens_roster — the action returns `res_model unicore.student`, `list,form`, and the
  correct member domain.

---

## GOTCHAS ENCOUNTERED (Phase 6)

1. **Roster domains must use stored, searchable fields** — `cohort_label` is computed non-stored, so
   it cannot be used in `search`/`search_count`/group_by. Membership is therefore keyed on the raw
   stored cohort fields (`grade_level_id`, `cohort_start_date`, `batch_year`) — the same Phase 4 lesson
   re-applied.
2. **Empty-key handling**: when there is no program or the cohort key is absent, `_cohort_members_domain()`
   returns `False` and the count is 0 (never a spurious "all students" count).
3. **Additive + legacy-inert by construction**: the new count/action/groupbys change nothing about
   create/write/enroll; the legacy roster is just the existing batch-year view.
4. The 5 docutils "Unexpected indentation" ERROR lines during upgrade are **pre-existing** docstring
   warnings, not from Phase 6.

---

## EXIT CRITERIA — ALL MET

- [x] Legacy path unchanged — legacy roster is exactly the batch-year view; existing tests still green.
- [x] Membership defined per cohort kind on stored, searchable fields only.
- [x] Zero regression: identical `6 failed, 3 error(s)` pre-existing set; 152→156 tests.
- [x] No behavior change to create/write/enroll flows — read-only derived data + action.
- [x] Upgrade applied to real `odoo` DB (`-u unicore_student`), schema verified.

**Files touched:** `unicore/custom_addons/unicore_student/{models/unicore_student.py,
views/unicore_student_views.xml, tests/__init__.py, tests/test_student_cohort_roster.py (new)}`.
**DBs:** upgraded `odoo` (real) and `odoo_p0_baseline` (migration bed).

---

## NEXT PHASE (candidates, not yet scoped)
- Enrollment / course-offering cohort rollup (schedule & grading filtered by cohort; K-12 sections).
- Admission cycle → `cohort_kind` binding / intake windows per cohort kind.
- Graduation / convocation cohort grouping (certificates by cohort).
- Report & portal cohort filters (fees, attendance, results grouped by cohort).
- K-12 academic calendar (terms / grades) and terminology (class / grade / division labels).
