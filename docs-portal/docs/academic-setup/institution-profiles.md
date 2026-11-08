---
id: institution-profiles
title: "Institution types and profiles"
sidebar_position: 2
---
# Institution types and profiles

> **Documentation status: source-reviewed draft.** Exact UI paths, role permissions and screenshots still require isolated Odoo verification.

The institution profile controls how Edicai interprets academic structures, calendar types and grading strategies.

## Institution categories

The source identifies **University**, **College**, **K-12 School**, **Training Institute**, **Academy / Test-Prep** and **Coaching Center** as options.

## Configurable dimensions

| Setting | Declared options or behavior |
|---|---|
| Academic unit levels | Configurable hierarchy of unit types |
| Calendar | Semester, Trimester, Quarter, Annual, Term Based, Rolling Batch |
| Legacy university mode | Preserves the faculty → department → program arrangement |
| Grading | Credit GPA, weighted/simple percentage, rubric, pass/fail, certificate only |
| Linked grading scheme | Takes precedence when configured; legacy strategy remains fallback |

The institution model makes **Profile Name**, **Profile Code**, **Institution Type**, **Calendar Mode** and a grading selection required.

## Demo-only verification

1. Open **Configuration → Institution Profiles** with an authorized synthetic administrator.
2. Inspect a test institution profile, then inspect its academic hierarchy levels, calendar and grading.
3. Compare available models and menus between a K-12 configuration and a university profile.
4. Verify terminology, permissions and grading behavior before documenting exact user steps.

:::caution
Changing institution profile settings may alter model constraints and available user interfaces. Test only on an isolated synthetic database.
:::

**Sources:** [Institution profile model](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_institution_profile/models/edicai_institution_profile.py) and [configuration menu](https://github.com/yashmakwana61/unicore/blob/main/custom_addons/edicai_institution_profile/menus/edicai_institution_profile_menus.xml).
