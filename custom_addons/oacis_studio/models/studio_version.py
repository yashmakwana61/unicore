# docs/studio_plan.md §13 — Phase 8 hardening: branching, diff, changelog, rollback to any
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import json
import difflib
import logging

_logger = logging.getLogger(__name__)

class StudioVersion(models.Model):
    _name = "studio.version"
    _description = "Studio Version Snapshot (docs/studio_plan.md §13 Phase 8)"
    _order = "app_id, create_date desc"

    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    dsl_json = fields.Json(required=True)
    dsl_hash = fields.Char(index=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    parent_id = fields.Many2one("studio.version", string="Parent Version", ondelete="set null", help="Previous version for diff/branch")
    branch = fields.Char(default="main", help="Branch name, e.g. main, feature/scholarship")
    changelog = fields.Text(help="Human-readable diff vs parent")
    diff_json = fields.Json(help="Structured diff: {added:[], removed:[], changed:[]}")
    active = fields.Boolean(default=True)

    def action_rollback(self):
        self.ensure_one()
        if not self.dsl_json:
            raise ValidationError(_("Version has no DSL"))
        # Rollback app to this version's DSL (creates new version for audit)
        self.app_id.write({"dsl_json": self.dsl_json, "state": "draft"})
        self.app_id.action_sync_from_dsl()
        # Create new version as rollback marker
        self.env["studio.version"].create({
            "app_id": self.app_id.id,
            "name": _("Rollback to %s") % self.name,
            "dsl_json": self.dsl_json,
            "dsl_hash": self.dsl_hash,
            "parent_id": self.app_id.version_ids[:1].id if self.app_id.version_ids else False,
            "changelog": f"Rollback to {self.name} ({self.dsl_hash})",
        })
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Rolled back", "message": f"App {self.app_id.key} rolled back to {self.name}", "type": "success"}}

    def action_compare(self):
        self.ensure_one()
        if not self.parent_id or not self.parent_id.dsl_json or not self.dsl_json:
            raise ValidationError(_("Need parent version to compare"))
        diff = self._diff_dsl(self.parent_id.dsl_json, self.dsl_json)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": f"Diff {self.parent_id.name} → {self.name}", "message": json.dumps(diff, indent=2)[:4000], "type": "info"},
        }

    def action_view_diff(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "studio.version",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def create(self, vals):
        # Auto-compute parent, diff, changelog
        if "parent_id" not in vals and vals.get("app_id"):
            last = self.search([("app_id", "=", vals["app_id"])], order="create_date desc", limit=1)
            if last:
                vals["parent_id"] = last.id
                # Compute diff if both have DSL
                if last.dsl_json and vals.get("dsl_json"):
                    diff = self._diff_dsl(last.dsl_json, vals["dsl_json"])
                    vals["diff_json"] = diff
                    # Changelog: summarize
                    added = len(diff.get("added", []))
                    removed = len(diff.get("removed", []))
                    changed = len(diff.get("changed", []))
                    vals["changelog"] = f"{added} added, {removed} removed, {changed} changed vs {last.name}"
        return super().create(vals)

    @api.model
    def _diff_dsl(self, old, new):
        # Very light diff: compare top-level keys and model/field lists
        def normalize(dsl):
            out = {}
            for k in ("models", "fields", "views", "workflows", "reports", "dashboards"):
                out[k] = sorted([json.dumps(v, sort_keys=True) for v in dsl.get(k, [])])
            for k in ("app",):
                out[k] = json.dumps(dsl.get(k, {}), sort_keys=True)
            return out
        n_old = normalize(old or {})
        n_new = normalize(new or {})
        added, removed, changed = [], [], []
        for k in set(list(n_old.keys()) + list(n_new.keys())):
            o, n = n_old.get(k, []), n_new.get(k, [])
            if isinstance(o, list):
                for v in n:
                    if v not in o:
                        added.append(f"{k}:{v[:80]}")
                for v in o:
                    if v not in n:
                        removed.append(f"{k}:{v[:80]}")
            else:
                if o != n:
                    changed.append(k)
        return {"added": added[:10], "removed": removed[:10], "changed": changed}

class StudioDependency(models.Model):
    _name = "studio.dependency"
    _description = "Studio Dependency DAG (docs/studio_plan.md §13)"
    _order = "app_id, source_type"

    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    source_type = fields.Selection([("model", "Model"), ("field", "Field"), ("view", "View"), ("report", "Report"), ("workflow", "Workflow"), ("dataset", "Dataset"), ("security", "Security")], required=True)
    source_key = fields.Char(required=True)
    depends_on = fields.Char(required=True, help="e.g. oacis.student, studio.field:scholarship.amount")
    active = fields.Boolean(default=True)
