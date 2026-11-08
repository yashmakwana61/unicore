---
id: overview
title: "Student Management overview"
sidebar_position: 1
---
# Student Management overview

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

Edicai tracks student records through admission, enrollment, activity, completion and alumni transitions. The source defines the main `edicai.student` model with linked campus, program, academic history, documents, guardians and portal contact.

## Source navigation

The base menu declares **Edicai → Students → All Students**, **Documents**, and **Academic History**. The deployed navigation may differ if an institution-specific menu preview is active.

## Core records

| Area | Source model |
|---|---|
| Student master | `edicai.student` |
| Student documents | `edicai.student.document` |
| Academic history | `edicai.student.academic.history` |
| Emergency contacts | `edicai.student.emergency.contact` |

## Next guides

- [Student profiles](./profiles.md)
- [Student status transitions](./lifecycle.md)
- [Student documents](./documents.md)
- [Academic history and cohorts](./academic-history.md)
- [Runtime verification checklist](./verification.md)

:::caution
Student data contains personally identifying and potentially sensitive information. Do not use real records for screenshot capture, previews or demonstrations. The existence of code does not confirm production deployment behavior.
:::

**Source:** [Student model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/models/edicai_student.py) and [menus](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/menus/edicai_student_menus.xml).
