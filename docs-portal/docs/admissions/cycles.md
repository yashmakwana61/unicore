---
id: cycles
title: "Admission cycles & seat allocation"
sidebar_position: 2
---
# Admission cycles & seat allocation

> **Review status: Source-reviewed draft.** Exact UI routes, behaviors and screenshots require isolated runtime verification.

An admission cycle identifies the intake window, institution, campus and academic year, and defines capacity and scoring rules.

## Source-declared fields

- Cycle name and code
- Campus and academic year
- Start and end dates
- Seat allocation by program
- Aggregate, entrance and interview scoring weights (defaults: 40%, 40%, 20%)

### Cycle states

| State | Meaning in source |
|---|---|
| Draft | Initial state |
| Active | Cycle can process merit selection |
| Closed | Intake closed after outstanding applicants are resolved |
| Archived | Closed cycle hidden through archival |

## Suggested UI verification procedure

*Draft for verification, not approved operational instructions.*

1. In an isolated Edicai demo, sign in with an authorized registrar account.
2. Find **Admissions → Admission Cycles** (the exact path may differ under the workspace preview).
3. Create a cycle and populate name, code, campus, academic year, start/end dates and program seat allocations.
4. Confirm scoring weights add up to **100%** and each value is between 0 and 100.
5. Save the cycle, then use the **Activate** button.
6. Confirm state changes from Draft to Active. In a disposable demo only, validate **Generate Merit List** once synthetic applicants have scores.
7. Check the **Close Cycle** and **Archive** actions only after clearing test applicants.

### Validation rules in source

- Activation is rejected unless the cycle is **Draft** and at least one seat allocation exists.
- Merit-list generation requires an **Active** cycle with seat allocations.
- Closing requires an **Active** cycle and no applicants left in pending statuses.
- Archival requires the cycle to be **Closed**.
- The selection logic groups eligible applicants by program, ranks them by composite score and places beyond-capacity applicants on the waitlist.

:::caution Merit list safety
Generating a merit list mutates applicant states. Execute it only on synthetic test records in a disposable database. Capacity outcomes require verification, including reserved seats and ties.
:::

**Source evidence:** [Cycle model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/models/admission_cycle.py) and [cycle form](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_admission/views/admission_cycle_views.xml).
