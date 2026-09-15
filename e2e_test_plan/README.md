# OACIS E2E Test Plan — Execution Guide

Stack locked: **Odoo native + Playwright**. Data: **oacis_demo (PreciseFect) on staging**.
Matrix: `test_plan_matrix.csv` — columns TC_ID | Module | Scenario | Type | Role | Priority | Automation | Phase.

## Run backend (Odoo native)

```bash
# from odoo repo root, staging DB with oacis_demo installed
python3 odoo-bin -c unicore/unicore/config/odoo-staging.conf \
  -d oacis_staging -u oacis_demo --test-tags oacis --test-enable --stop-after-init
# Phase 1 spine only:
python3 odoo-bin -c unicore/unicore/config/odoo-staging.conf \
  -d oacis_staging --test-tags oacis \
  --test-file unicore/unicore/custom_addons/oacis_timetable/tests/test_timetable_conflicts.py
```

Existing suites to run first (21 modules): admission (8 files), api (20 tests),
website (2 files), student, attendance, fees, grading, gradebook, analytics, scholarship.

## Run frontend (Playwright)

```bash
cd unicore/unicore/e2e_test_plan/playwright
npm install && npx playwright install --with-deps chromium
cp .env.example .env   # set ODOO_BASE_URL, STUDENT/ FACULTY/ GUARDIAN creds
npx playwright test --project=chromium
```

## Phase 1 stubs (copy-in ready)

`phase1_stubs/odoo/` contains 4 drop-in test files for the zero-coverage spine gap:
`timetable→attendance→exam`. Copy each into its module's `tests/` dir and register
in that module's `tests/__init__.py`, e.g.:

```bash
cp e2e_test_plan/phase1_stubs/odoo/test_timetable_conflicts.py \
   custom_addons/oacis_timetable/tests/
# then add `from . import test_timetable_conflicts` to oacis_timetable/tests/__init__.py
```

Stubs: `test_timetable_conflicts.py`, `test_attendance_exam_chain.py`,
`test_assignment_gradebook_chain.py`, `test_progression_decision.py`.
All follow the `SingleTransactionCase` + `@tagged('oacis',...)` pattern used by
`oacis_admission/tests/test_admission_to_enrollment_workflow.py`.

## Phases

- Phase 0: SMOKE-01..05 + FND-01 (install, menus, roles)
- Phase 1 (P0 spine): ACD/ADM/TT/ATT/EXM/ASN/GRD/PRG/FEE/PAY/NTF/API/PS/PF
- Phase 2: guardians, grievance/leave/notices, scholarship/finance-report/analytics, transcript/LMS
- Phase 3: hostel/transport/library/ops + AI/theme + PERF-01 + full SEC sweep

Known risks to assert explicitly: portal `.sudo()` bypass vs record rules,
`oacis_security` XML load check, guardian notice `_get_student_wards` bug,
gradebook write-guards, WhatsApp/payment sandboxing.
