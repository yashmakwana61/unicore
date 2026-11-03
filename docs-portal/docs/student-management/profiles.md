---
id: profiles
title: "Create and manage student profiles"
sidebar_position: 2
---
# Create and manage student profiles

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

The student master record stores identity and contact information, institution and campus references, the linked program, cohort information and status.

## Source-defined required information

The source declares required values including **Full Name**, **Gender**, **Date of Birth**, **Personal Email**, **Mobile Number**, **Institution**, **Campus**, **Program** and **Batch Year**. Other required values and rules may be introduced by inherited modules or active database settings.

## Validation safeguards

- A student identifier must be unique globally according to its declared database constraint.
- The same email address must not be duplicated within a company according to its declared database constraint.
- Date-of-birth, passport, disability, graduation, visa expiry and cohort checks are implemented in the student model.

## Proposed verification steps

1. In a disposable Edicai test database, sign in as an authorized staff user.
2. Find **Students → All Students** in the base navigation.
3. Create a synthetic student with a test campus, program and valid cohort.
4. Save and confirm that the student reference and related model links are generated correctly.
5. Try invalid values in the disposable environment and compare validation results with code.

These steps have not yet passed an actual Odoo UI session. No production record creation is authorized by this guide.

**Sources:** [Student model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/models/edicai_student.py), [Student form](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_student/views/edicai_student_views.xml).
