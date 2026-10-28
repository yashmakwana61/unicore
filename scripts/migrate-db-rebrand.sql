-- migrate-db-rebrand.sql
-- Renames all oacis_* module references inside an EXISTING Odoo database to edicai_*,
-- so a database created before the rebrand matches the renamed module directories.
--
-- RUN ORDER: after restoring the database into the container, BEFORE starting odoo web.
-- Usage (from the unicore/ directory on the server):
--   docker compose exec -T db psql -U "$EDICAI_DB_USER" -d "$EDICAI_DB_NAME" < scripts/migrate-db-rebrand.sql
--
-- ALWAYS have a pg_dump backup of the database before running this.

BEGIN;

-- 1) ir_module_module: the module registry itself.
UPDATE ir_module_module
SET name = 'edicai' || substring(name from 6)
WHERE name LIKE 'oacis%';

-- 2) ir_model_data: XML IDs are namespaced by module (module.name).
--    This fixes menus, views, actions, cron, groups, etc.
UPDATE ir_model_data
SET module = 'edicai_' || substring(module from 7)
WHERE module LIKE 'oacis_%';

UPDATE ir_model_data
SET module = 'edicai'
WHERE module = 'oacis';

-- 3) Module dependency rows reference module names.
UPDATE ir_module_module_dependency
SET name = 'edicai_' || substring(name from 7)
WHERE name LIKE 'oacis_%';

-- 4) Asset bundles stored with old static paths (/oacis_x/static/...).
UPDATE ir_asset
SET url = '/edicai_' || substring(url from 8)
WHERE url LIKE '/oacis_%';

-- 5) Any leftover view/action definitions that hardcode old module-prefixed IDs
--    (rare, but keeps custom references consistent).
UPDATE ir_ui_view
SET arch_db = replace(arch_db, 'oacis_', 'edicai_')
WHERE arch_db LIKE '%oacis_%';

COMMIT;

-- After this script, start odoo with an upgrade of the base custom module:
--   docker compose run --rm --no-deps web odoo -c /etc/odoo/odoo.conf -d "$EDICAI_DB_NAME" -u edicai_base --stop-after-init
