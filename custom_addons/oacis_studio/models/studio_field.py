# docs/studio_plan.md §17
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

ALLOWED_TTYPES = [
    ("char", "Text"), ("text", "Long Text"), ("html", "HTML"),
    ("integer", "Integer"), ("float", "Decimal"), ("decimal", "Decimal(precision)"), ("monetary", "Monetary"),
    ("boolean", "Boolean"), ("date", "Date"), ("datetime", "Datetime"),
    ("selection", "Selection"), ("many2one", "Many2one"), ("one2many", "One2many"), ("many2many", "Many2many"),
    ("image", "Image"), ("binary", "Binary"), ("attachment", "Attachment"), ("reference", "Reference"), ("related", "Related"),
    # V2 planned
    ("formula", "Formula"), ("auto_number", "Auto Number"), ("signature", "Signature"), ("qr_code", "QR Code"), ("barcode", "Barcode"), ("geo", "Geo"),
]

class StudioField(models.Model):
    _name = "studio.field"
    _description = "Studio Field (docs/studio_plan.md §17)"
    _order = "model_id, sequence, key"

    model_id = fields.Many2one("studio.model", required=True, ondelete="cascade", index=True)
    key = fields.Char(required=True, help="Semantic key e.g. amount")
    tech_name = fields.Char(required=True, help="Column name, e.g. x_amount")
    label = fields.Char(required=True, translate=True)
    ttype = fields.Selection(ALLOWED_TTYPES, required=True, default="char", string="Type")
    required = fields.Boolean(default=False)
    readonly = fields.Boolean(default=False)
    store = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    relation_model = fields.Char(help="For many2one/one2many/many2many: e.g. oacis.student or studio.app's tech_name")
    selection_json = fields.Json(help="[['draft','Draft'],['done','Done']]")
    compute_expr = fields.Text(help="For formula/related: e.g. attendance.present/total*100")
    help_text = fields.Char(translate=True)
    groups = fields.Char(help="Comma-separated field-level groups, e.g. oacis_studio.group_studio_admin")
    app_id = fields.Many2one(related="model_id.app_id", store=True, readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("model_key_uniq", "unique(model_id, key)", "Field key must be unique per model"),
        ("model_tech_uniq", "unique(model_id, tech_name)", "Tech name must be unique per model"),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("tech_name") and vals.get("key"):
                vals["tech_name"] = "x_" + vals["key"].replace(".", "_").replace("-", "_")
            # auto-fill label from key if missing
            if not vals.get("label") and vals.get("key"):
                vals["label"] = vals["key"].replace("_", " ").title()
        recs = super().create(vals_list)
        for rec in recs:
            rec.model_id._update_app_dsl()
        return recs

    def write(self, vals):
        if "key" in vals and "tech_name" not in vals:
            for rec in self:
                if rec.tech_name == "x_" + rec.key.replace(".", "_").replace("-", "_"):
                    vals["tech_name"] = "x_" + vals["key"].replace(".", "_").replace("-", "_")
                    break
        res = super().write(vals)
        self.mapped("model_id")._update_app_dsl()
        return res

    def unlink(self):
        models = self.mapped("model_id")
        res = super().unlink()
        for m in models:
            m._update_app_dsl()
        return res

    @api.onchange("key")
    def _onchange_key(self):
        if self.key and not self.tech_name:
            self.tech_name = "x_" + self.key.replace(".", "_").replace("-", "_")
        if self.key and not self.label:
            self.label = self.key.replace("_", " ").title()

    @api.onchange("ttype")
    def _onchange_ttype(self):
        if self.ttype not in ("many2one", "one2many", "many2many"):
            self.relation_model = False

    @api.constrains("ttype", "relation_model", "selection_json")
    def _check_relation(self):
        for rec in self:
            if rec.ttype in ("many2one", "one2many", "many2many") and not rec.relation_model:
                raise ValidationError(_("Relation model required for %s") % rec.ttype)
            if rec.ttype == "selection" and not rec.selection_json:
                raise ValidationError(_("Selection options required for selection field"))
            if rec.selection_json:
                import json as _json
                try:
                    data = rec.selection_json if isinstance(rec.selection_json, list) else _json.loads(rec.selection_json or "[]")
                    if not isinstance(data, list):
                        raise ValidationError(_("selection_json must be a list of [value,label]"))
                except Exception as e:
                    if "selection_json" in str(e):
                        raise
                    raise ValidationError(_("Invalid selection_json: %s") % e)
