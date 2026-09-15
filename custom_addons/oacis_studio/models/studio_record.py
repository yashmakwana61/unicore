# docs/studio_plan.md §4 — Hybrid JSONB runtime (no registry reload for V1)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StudioRecord(models.Model):
    _name = "studio.record"
    _description = "Studio Record — JSONB runtime row (docs/studio_plan.md §4)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    model_id = fields.Many2one("studio.model", required=True, ondelete="cascade", index=True)
    name = fields.Char(compute="_compute_name", store=True, index=True, tracking=True)
    values_json = fields.Json(required=True, default=dict, help="All field values as JSONB, GIN indexed", tracking=True)
    state = fields.Char(default="draft", index=True, help="Workflow state", tracking=True)
    campus_id = fields.Many2one("oacis.campus", index=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)

    @api.depends("values_json", "model_id")
    def _compute_name(self):
        for rec in self:
            vals = rec.values_json or {}
            # try display_name, name, title, code, then fallback
            rec.name = vals.get("display_name") or vals.get("name") or vals.get("title") or vals.get("code") or f"{rec.model_id.key}#{rec.id}"

    @api.constrains("model_id", "app_id")
    def _check_model_app(self):
        for rec in self:
            if rec.model_id.app_id != rec.app_id:
                raise ValidationError(_("Record model must belong to the same app"))

    @api.constrains("values_json")
    def _check_required_fields(self):
        for rec in self:
            if not rec.model_id:
                continue
            fields = self.env["studio.field"].search([("model_id", "=", rec.model_id.id), ("required", "=", True), ("active", "=", True)])
            missing = []
            for f in fields:
                v = (rec.values_json or {}).get(f.key)
                if v in (False, None, "", []):
                    # allow 0 for integer
                    if v == 0 and f.ttype in ("integer", "float", "decimal", "monetary"):
                        continue
                    missing.append(f.label or f.key)
            if missing:
                raise ValidationError(_("Missing required fields for %s: %s") % (rec.model_id.label, ", ".join(missing)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # auto-fill app_id from model_id if not provided
            if not vals.get("app_id") and vals.get("model_id"):
                m = self.env["studio.model"].browse(vals["model_id"])
                if m.exists():
                    vals["app_id"] = m.app_id.id
            # ensure values_json is dict
            if "values_json" not in vals or not isinstance(vals.get("values_json"), dict):
                vals["values_json"] = vals.get("values_json") or {}
        recs = super().create(vals_list)
        # post-create: handle chatter opts + Phase 4 triggers
        for rec in recs:
            if rec.model_id.opts and rec.model_id.opts.get("chatter"):
                rec.message_post(body=_("Record created for %s") % rec.model_id.label)
        # Phase 4: trigger workflows & automations (skip if context flag)
        if not self.env.context.get("studio_no_trigger"):
            for rec in recs:
                self.env["studio.workflow"]._trigger_for_record("on_create", rec)
                self.env["studio.automation"]._trigger_for_record("on_create", rec)
        return recs

    def write(self, vals):
        # Determine fields being updated for trigger (for JSONB, keys inside values_json)
        trigger_fields = set()
        if "values_json" in vals and isinstance(vals["values_json"], dict):
            trigger_fields.update(vals["values_json"].keys())
        # merge instead of replace for partial updates (also captures trigger fields)
        if "values_json" in vals:
            if isinstance(vals["values_json"], dict):
                # For single record, merge; for multi, collect all
                for rec in self:
                    if isinstance(rec.values_json, dict):
                        merged = dict(rec.values_json)
                        merged.update(vals["values_json"])
                        # for multi-record, last merged wins for vals; handle per-rec later
                        vals["values_json"] = merged
                        trigger_fields.update(vals["values_json"].keys())
                        break
        res = super().write(vals)
        # Phase 4: on_write triggers per field
        if not self.env.context.get("studio_no_trigger"):
            for rec in self:
                for field in (trigger_fields or vals.keys()):
                    # normalize field name for JSONB vs regular
                    self.env["studio.automation"]._trigger_for_record("on_write", rec, field=field)
                    self.env["studio.workflow"]._trigger_for_record("on_write", rec, field=field)
        return res

    def unlink(self):
        # Phase 4: on_unlink automations
        if not self.env.context.get("studio_no_trigger"):
            for rec in self:
                self.env["studio.automation"]._trigger_for_record("on_unlink", rec)
        return super().unlink()

    def get_field_defs(self):
        self.ensure_one()
        return self.env["studio.field"].search([("model_id", "=", self.model_id.id), ("active", "=", True)], order="sequence, id")

    def get_display_values(self):
        """Resolve many2one display names for UI."""
        self.ensure_one()
        out = dict(self.values_json or {})
        for f in self.get_field_defs():
            if f.ttype == "many2one" and out.get(f.key):
                try:
                    # relation_model may be oacis.student etc.
                    rel = self.env[f.relation_model].browse(int(out[f.key]))
                    if rel.exists():
                        out[f.key + "_display"] = rel.display_name
                except Exception:
                    pass
        return out

    def action_archive(self):
        self.write({"active": False})

class StudioRecordValue(models.Model):
    _name = "studio.record.value"
    _description = "Studio Record Value (optional normalized index for query perf)"
    _order = "record_id"

    record_id = fields.Many2one("studio.record", required=True, ondelete="cascade", index=True)
    field_id = fields.Many2one("studio.field", required=True, ondelete="cascade")
    value_char = fields.Char(index=True)
    value_text = fields.Text()
    value_integer = fields.Integer(index=True)
    value_float = fields.Float()
    value_boolean = fields.Boolean()
    value_date = fields.Date()
    value_datetime = fields.Datetime()
    value_selection = fields.Char()
