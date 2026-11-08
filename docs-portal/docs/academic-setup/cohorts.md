---
id: cohorts
title: "Cohorts, calendar and grading"
sidebar_position: 4
---
# Cohorts, calendar and grading

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

Edicai's `edicai.program` model defines three methods of grouping student cohorts: **Academic Year / Batch**, **Grade-Level Batch**, and **Rolling Intake**.

| Cohort kind | Intended institutional context in source |
|---|---|
| Academic Year / Batch | University cohorts grouped by intake year |
| Grade-Level Batch | K-12 grade and batch groupings |
| Rolling Intake | Training and coaching intakes |

Institution profiles separately offer six calendar modes: semester, trimester, quarter, annual, term-based and rolling-batch. Calendar choice and cohort kind are different configuration dimensions.

## Grading configuration

An institution profile may select an explicit grading scheme record. When configured, its scheme type takes precedence over the legacy grading selection.

## Verification

Check that the cohort model, academic-year dates, grade levels and term assignments agree in an isolated school and university demonstration. A configuration value being present does not establish that every downstream enrollment/reporting module handles it correctly.

**Sources:** [Program model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_academic/models/edicai_program.py), [Institution profile](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_institution_profile/models/edicai_institution_profile.py).
