# Implementation Plan — `edicai_navigation`

Module shape per master prompt §5, adapted: single `views/workspaces_menus.xml` plus one file per workspace is unnecessary; verified scope fits three views files (workspaces_menus.xml, shortcuts_menus.xml, security/navigation_groups.xml) plus tests. Depends: all 31 apps owning reparented menus must be dependencies (auto-verified in implementation by `--stop-after-init` load order test).

## Steps

1. Create module skeleton with manifest listing all menu-owning custom modules as deps.
2. `security/navigation_groups.xml` — the 6 proposed groups.
3. `views/workspaces_menus.xml` — 11 workspace roots (stable XML IDs, web_icon assets can reuse module icons), then one `<menuitem id="existing_root_xmlid" parent="workspace_root"/>` reparent line per changed row in the manifest (36 reparents total), plus 2 shortcut menus.
4. Load order: groups → workspace roots → reparents → shortcuts (single file order).
5. Idempotency: all statements are declarative menuitem updates — safe across repeated `-u`.
6. Tests: XML-ID resolution, no new orphan roots, launcher shows exactly 11 custom apps + standard Odoo apps, role visibility per matrix, regression subset from existing suites.
7. Staging: backup → install → validate → second upgrade for idempotency → approvals.

## Counts (computed, not estimated)

- Inspected: 695 DB menus (268 custom in scope; 427 standard out of scope).
- Changed (reparent): **39**
- Retained unchanged: **228**
- Demoted-but-kept records: **1** (Edicai root)
- New shortcut rows: **2**
- New groups proposed: **6**
- Workspace roots created: **11**

## In-manifest pending approvals

- Grade Entry canonical placement (50 vs 40/both).
- Students section groups (self-service entries visible to internal students?).
- The inverted `edicai_api` implied chain — separate security fix, not part of navigation.