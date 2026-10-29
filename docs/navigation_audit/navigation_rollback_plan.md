# Navigation Rollback Plan

## Hard rule

**Do NOT uninstall `edicai_navigation` to roll back.** Uninstalling deletes the workspace root menus; children reparented onto them ARE DELETED CASCADE (`ir.ui.menu.parent_id` is ondelete=cascade). The reparented app roots (their top records) were MODIFIED, not created — Odoo does not auto-revert modified records on uninstall and cascading deletion would then destroy them.

## Safe rollback ladder

1. **Preferred** — revert the module data: restore the previous `workspaces_menus.xml` (or disable the reparent section) and `-u edicai_navigation`; every original parent/sequence is recorded in `menu_migration_manifest.csv` columns `current_*` (source of truth = pre-migration `current_menu_inventory.csv`).
2. **Mechanical** — scripted restore: for each changed row set parent back to current_parent_xmlid and sequence back to current_sequence via a generated "revert" data XML in the same module (additive, reversible by design).
3. **Last resort** — full `pg_dump` restore taken immediately before staging/production installation, plus filestore copy.

## Preservation requirements

- Pre-migration inventory: `current_menu_inventory.csv` (695 rows, all fields).
- DB snapshots: staging + production pre-install dumps (named, timestamped).
- New artifacts introduced: 11 workspace roots, 6 groups, 2 shortcuts — all owned exclusively by `edicai_navigation` for clean identification.
- Partially-applied migration handling: module `-u` is idempotent; re-run completes the same end-state (declarative menuitems).