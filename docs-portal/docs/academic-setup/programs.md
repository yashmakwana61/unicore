---
id: programs
title: "Faculties, departments and programs"
sidebar_position: 3
---
# Faculties, departments and programs

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

The academic structure addon declares **Faculties**, **Departments**, **Programs** and **Specialisations** as separate menu destinations.

## Program information

The `edicai.program` model tracks the program's institution-related structure, coordinator, accreditation, entry qualification, tuition reference, learning outcomes and cohort type.

## Source-derived administrative flow

1. Configure the institution profile and campus.
2. Choose the appropriate academic unit hierarchy. For legacy university mode, faculty and department structure remains mandatory according to source notes.
3. Configure faculties and departments if the selected institution structure requires them.
4. Create programs with the appropriate academic-unit anchors, cohort kind and course structure.
5. Add specialisations when applicable.

This is a conceptual setup sequence. It is not an approved UI walkthrough.

## Program actions and validations

The program model declares approval, activation, discontinuation and draft-reset actions. Its constraints include program-anchor and cohort-kind checks, duration/credit validation, and accreditation expiry checks. The program code is declared unique per institution.

:::warning
Program activation may affect student enrollment and downstream reporting. Verify state transitions and dependencies with a synthetic database before approving procedures.
:::

**Sources:** [Program model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_academic/models/edicai_program.py), [Academic menus](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_academic/menus/edicai_academic_menus.xml).
