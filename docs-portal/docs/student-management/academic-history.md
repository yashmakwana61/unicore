---
id: academic-history
title: "Academic history and cohorts"
sidebar_position: 5
---
# Academic history and cohorts

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

The `edicai.student.academic.history` model associates a student with an academic period and historical performance. The student master also exposes a related **Academic History** count and action.

## Source-evidenced concepts

- Academic year and study-year association
- Enrollment and results information
- Grade/GPA and credits validation
- Cohort membership linked to the student's program and institutional structure

The student source includes an academic cohort label and a cohort-member count; the academic program determines how cohorts are grouped.

## Cohort types

The `edicai.program` model defines **Academic Year / Batch**, **Grade-Level Batch**, and **Rolling Intake** cohort kinds. School and training institutions may therefore use different groupings from the university-oriented default.

## Verification checklist

- Verify the correct academic year and program are shown on a synthetic student.
- Check that grade/GPA and credits are constrained as intended.
- Confirm historical records belong to the correct institution and student.
- Compare cohort grouping across a university, a school and a training demonstration profile.

**Sources:** [Academic history](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/models/edicai_student_academic_history.py), [Program cohorts](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_academic/models/edicai_program.py).
