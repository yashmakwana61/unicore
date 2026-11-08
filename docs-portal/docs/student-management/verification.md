---
id: verification
title: "Student Management verification plan"
sidebar_position: 6
---
# Student Management verification plan

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

This documentation section is **source-reviewed only**. A production-ready manual requires a separate synthetic Edicai Odoo instance and role-appropriate browser tests.

## Screenshot targets

| Screen | Current evidence |
|---|---|
| Students list, filters and Kanban | Source view, screenshot pending |
| Student master form | Source view, screenshot pending |
| Student status buttons | XML-defined, runtime permission pending |
| Student document form | Source model, screenshot pending |
| Academic history form | Source model, screenshot pending |
| Cohort-members list | Source action, screenshot pending |

## Required controls

Use fake student names and test contact domains, never real documents, and never copy an institutional production database into the screenshot environment. Disable external mail, payments and notification endpoints. Browser capture must not cause real student status transitions.

**Review lifecycle:** Source draft → isolated runtime verification → privacy review → reviewer approval → publish verified instructions.

**Source:** [Student source tests](https://github.com/yashmakwana61/unicore/tree/main/custom_addons/edicai_student/tests).
