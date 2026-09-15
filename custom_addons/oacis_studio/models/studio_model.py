# docs/studio_plan.md §17
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re

TECH_RE = re.compile(r"^x_[a-z][a-z0-9_]*$")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")

class StudioModel(models.Model):
    _name = "studio.model"
    _description = "Studio Model (docs/studio_plan.md §17)"
    _order = "app_id, key"

    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    key = fields.Char(required=True, help="Semantic key e.g. scholarship.application")
    tech_name = fields.Char(required=True, help="x_ prefixed, e.g. x_scholarship_application", index=True, copy=False)
    label = fields.Char(required=True, translate=True)
    extends_model_id = fields.Many2one("ir.model", string="Extends (null = new model)", help="If set, this customizes an existing oacis.* model")
    opts = fields.Json(default=lambda self: {"chatter": True, "track": True, "archive": True, "activity": True})
    field_ids = fields.One2many("studio.field", "model_id", string="Fields")
    view_ids = fields.One2many("studio.view", "model_id", string="Views")
    company_id = fields.Many2one(related="app_id.company_id", store=True, readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("tech_uniq", "unique(tech_name)", "Technical name must be unique"),
        ("key_app_uniq", "unique(app_id, key)", "Key must be unique per app"),
    ]

    @api.constrains("tech_name", "key")
    def _check_names(self):
        for rec in self:
            if not TECH_RE.match(rec.tech_name or ""):
                raise ValidationError(_("tech_name must be x_*: %s") % rec.tech_name)
            if not KEY_RE.match(rec.key or ""):
                raise ValidationError(_("key must match %s") % rec.key)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("tech_name") and vals.get("key"):
                vals["tech_name"] = "x_" + vals["key"].replace(".", "_")
        recs = super().create(vals_list)
        for rec in recs:
            rec._update_app_dsl()
        return recs

    def write(self, vals):
        if "key" in vals and "tech_name" not in vals:
            # auto-sync tech_name if key changes and tech still default
            for rec in self:
                if rec.tech_name == "x_" + rec.key.replace(".", "_"):
                    vals["tech_name"] = "x_" + vals["key"].replace(".", "_")
                    break
        res = super().write(vals)
        self._update_app_dsl()
        return res

    def unlink(self):
        apps = self.mapped("app_id")
        res = super().unlink()
        for app in apps:
            app._update_dsl_from_models()
        return res

    def _update_app_dsl(self):
        for rec in self:
            rec.app_id._update_dsl_from_models()

    def action_open_fields(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Fields — {self.label}",
            "res_model": "studio.field",
            "view_mode": "list,form",
            "domain": [("model_id", "=", self.id)],
            "context": {"default_model_id": self.id},
        }

    def action_open_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Records — {self.label}",
            "res_model": "studio.record",
            "view_mode": "list,form",
            "domain": [("model_id", "=", self.id)],
            "context": {"default_model_id": self.id, "default_app_id": self.app_id.id},
        }

    def action_open_view_builder(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Views — {self.label}",
            "res_model": "studio.view",
            "view_mode": "list,form",
            "domain": [("model_id", "=", self.id)],
            "context": {"default_model_id": self.id},
        }
