---
id: verification
title: "Academic configuration verification"
sidebar_position: 5
---
# Academic configuration verification

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

This section describes source-defined configurations. **It is not a verified production setup guide**.

## Review matrix

| Scenario | Test evidence required |
|---|---|
| University profile | Faculty → department → program linking |
| K-12 profile | Grade-level academic unit hierarchy |
| Coaching profile | Rolling batches without unnecessary university structures |
| Calendar changes | Term dates and consistent course availability |
| Grading scheme changes | Correct selected grading logic |
| Program lifecycle | Authorized approvals, activation and discontinuation |

Test with separate synthetic databases when changes to institution type affect constraints or migration behavior. Confirm ACLs and UI actions for staff, registrar and academic managers.

## Publication gate

Source reviewed → synthetic Odoo checks → screenshots checked → reviewer approval. Until then, these descriptions should not be used to configure a real institution blindly.

**Source tests:** [Institution configuration tests](https://github.com/yashmakwana61/unicore/tree/main/custom_addons/edicai_institution_profile/tests) and [academic program tests](https://github.com/yashmakwana61/unicore/tree/main/custom_addons/edicai_academic/tests).
