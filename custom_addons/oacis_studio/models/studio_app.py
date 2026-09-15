# docs/studio_plan.md §17
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

class StudioApp(models.Model):
    _name = "studio.app"
    _description = "Studio Application (docs/studio_plan.md §17)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    key = fields.Char(required=True, help="Semantic key, e.g. scholarship", index=True, copy=False)
    icon = fields.Char(default="fa-cube", help="FontAwesome icon")
    category = fields.Selection([("education", "Education"), ("admin", "Admin"), ("custom", "Custom")], default="education")
    state = fields.Selection([
        ("draft", "Draft"), ("preview", "Preview"), ("testing", "Testing"),
        ("published", "Published"), ("archived", "Archived"),
    ], default="draft", tracking=True, index=True)
    version = fields.Integer(default=1, readonly=True)
    dsl_json = fields.Json(string="DSL JSON (studio.dsl:1.0)", default=lambda self: {"dsl_version": "1.0"}, copy=False)
    dsl_hash = fields.Char(compute="_compute_dsl_hash", store=True, index=True)
    campus_ids = fields.Many2many("oacis.campus", string="Campuses", help="Empty = all campuses")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    model_ids = fields.One2many("studio.model", "app_id", string="Models")
    version_ids = fields.One2many("studio.version", "app_id", string="Versions")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("key_uniq", "unique(key)", "App key must be unique"),
    ]

    @api.constrains("key")
    def _check_key(self):
        for rec in self:
            if not KEY_RE.match(rec.key or ""):
                raise ValidationError(_("App key must match %s") % KEY_RE.pattern)

    @api.depends("dsl_json")
    def _compute_dsl_hash(self):
        import hashlib, json
        for rec in self:
            raw = json.dumps(rec.dsl_json or {}, sort_keys=True, ensure_ascii=False)
            rec.dsl_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]

    def action_validate(self):
        self.ensure_one()
        return self.env["studio.dsl"].validate_definition(self.dsl_json)

    def action_preview(self):
        self.ensure_one()
        return self.env["studio.dsl"].preview_definition(self.dsl_json)

    def action_publish(self):
        for rec in self:
            rec.env["studio.dsl"].validate_definition(rec.dsl_json)
            if not self.env.user.has_group("oacis_studio.group_studio_admin"):
                raise ValidationError(_("Only Studio Admin can publish"))
            rec.version += 1
            self.env["studio.version"].create({
                "app_id": rec.id,
                "name": _("Version %s") % rec.version,
                "dsl_json": rec.dsl_json,
                "dsl_hash": rec.dsl_hash,
            })
            rec.state = "published"
        return True

    def action_archive(self):
        self.write({"state": "archived", "active": False})

    # --- Phase 1: Home metrics, Export, Health ---
    @api.model
    def get_home_metrics(self):
        return {
            "apps_total": self.search_count([]),
            "apps_published": self.search_count([("state", "=", "published")]),
            "apps_draft": self.search_count([("state", "=", "draft")]),
            "models_total": self.env["studio.model"].search_count([]),
            "fields_total": self.env["studio.field"].search_count([]),
            "dictionary_models": self.env["studio.data.dictionary"].search_count([("ttype", "=", "model")]),
            "dictionary_total": self.env["studio.data.dictionary"].search_count([]),
            "records_total": self.env["studio.record"].search_count([]),
            "ai_requests": self.env["studio.ai.request"].search_count([]),
            "recent_apps": [
                {"id": r.id, "name": r.name, "key": r.key, "state": r.state, "version": r.version}
                for r in self.search([], order="write_date desc", limit=5)
            ],
            "recent_versions": [
                {"app": v.app_id.name, "name": v.name, "hash": v.dsl_hash, "date": str(v.create_date)}
                for v in self.env["studio.version"].search([], order="create_date desc", limit=5)
            ],
        }

    def action_export_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "studio.export.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_app_id": self.id},
        }

    def action_check_health(self):
        self.ensure_one()
        res = self.env["studio.health"].check_app(self)
        if not res["valid"]:
            raise ValidationError(_("Health check failed:\n") + "\n".join(res["issues"]))
        self.env["studio.health"].rebuild_dependencies(self)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Health OK"), "message": _("Dependencies rebuilt: %s") % ", ".join(res["deps"][:5]), "type": "success"},
        }

    def action_rollback(self):
        self.ensure_one()
        last = self.env["studio.version"].search([("app_id", "=", self.id)], order="create_date desc", limit=1, offset=1)
        if not last:
            raise ValidationError(_("No previous version to rollback"))
        self.write({"dsl_json": last.dsl_json, "state": "draft"})
        return True

    # --- Phase 2: DSL ↔ Models sync (hybrid runtime) ---
    def _update_dsl_from_models(self):
        """Models → DSL: keep dsl_json in sync when builder creates models/fields via UI."""
        for app in self:
            dsl = dict(app.dsl_json or {"dsl_version": "1.0"})
            dsl["dsl_version"] = "1.0"
            dsl["app"] = {"key": app.key, "name": app.name, "icon": app.icon, "category": app.category}
            # models
            dsl["models"] = []
            for m in app.model_ids:
                dsl["models"].append({
                    "key": m.key, "tech": m.tech_name, "label": m.label, "opts": m.opts or {},
                })
            # fields
            dsl["fields"] = []
            for f in self.env["studio.field"].search([("model_id.app_id", "=", app.id)], order="model_id, sequence"):
                dsl["fields"].append({
                    "model": f.model_id.key, "key": f.key, "type": f.ttype,
                    "label": f.label, "required": f.required, "readonly": f.readonly,
                    "relation": f.relation_model or None, "selection": f.selection_json or None,
                    "tech": f.tech_name,
                })
            # keep existing views/datasets etc. if not rebuilding from scratch
            # do not overwrite relations/views/datasets that may have been defined via DSL directly
            # ensure at least empty arrays
            for k in ("relations", "views", "datasets", "reports", "dashboards", "workflows", "automations"):
                dsl.setdefault(k, dsl.get(k, []))
            # avoid infinite recursion: write with bypass
            super(StudioApp, app).write({"dsl_json": dsl})

    def action_sync_from_dsl(self):
        """DSL → Models: rebuild studio.model/field from dsl_json (used after Import or manual JSON edit)."""
        for app in self:
            dsl = app.dsl_json or {}
            self.env["studio.dsl"].validate_definition(dsl)
            # keep existing models dict for diff
            existing_models = {m.key: m for m in app.model_ids}
            for mdef in dsl.get("models", []):
                key = mdef.get("key")
                if key in existing_models:
                    existing_models[key].write({
                        "tech_name": mdef.get("tech", existing_models[key].tech_name),
                        "label": mdef.get("label", existing_models[key].label),
                        "opts": mdef.get("opts", existing_models[key].opts),
                    })
                    del existing_models[key]
                else:
                    self.env["studio.model"].create({
                        "app_id": app.id, "key": key, "tech_name": mdef.get("tech"),
                        "label": mdef.get("label") or key, "opts": mdef.get("opts"),
                    })
            # remove models not in DSL? keep for safety — archive instead of unlink
            for m in existing_models.values():
                m.write({"active": False})
            # fields
            # Map (model_key, field_key) → record
            existing_fields = {(f.model_id.key, f.key): f for f in self.env["studio.field"].search([("model_id.app_id", "=", app.id)])}
            for fdef in dsl.get("fields", []):
                mk, fk = fdef.get("model"), fdef.get("key")
                key = (mk, fk)
                vals = {
                    "label": fdef.get("label") or fk,
                    "ttype": fdef.get("type") or "char",
                    "required": bool(fdef.get("required")),
                    "readonly": bool(fdef.get("readonly")),
                    "relation_model": fdef.get("relation"),
                    "selection_json": fdef.get("selection"),
                    "tech_name": fdef.get("tech") or "x_" + (fk or "").replace(".", "_"),
                }
                if key in existing_fields:
                    # find model id
                    m = self.env["studio.model"].search([("app_id", "=", app.id), ("key", "=", mk)], limit=1)
                    if m:
                        vals["model_id"] = m.id
                    existing_fields[key].write(vals)
                    del existing_fields[key]
                else:
                    m = self.env["studio.model"].search([("app_id", "=", app.id), ("key", "=", mk)], limit=1)
                    if not m:
                        continue
                    vals["model_id"] = m.id
                    vals["key"] = fk
                    self.env["studio.field"].create(vals)
            for f in existing_fields.values():
                f.write({"active": False})
        return True

    def write(self, vals):
        # If DSL is manually edited, sync models after
        res = super().write(vals)
        if "dsl_json" in vals:
            # avoid recursion when _update_dsl_from_models calls write
            if not self.env.context.get("studio_sync_skip"):
                for app in self:
                    try:
                        app.with_context(studio_sync_skip=True).action_sync_from_dsl()
                    except Exception:
                        # DSL may be incomplete during drafting — keep models as-is
                        pass
        return res
