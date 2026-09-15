# docs/studio_plan.md §13 — Import .studio JSON
import base64
import json

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StudioImportWizard(models.TransientModel):
    _name = "studio.import.wizard"
    _description = "Studio DSL Import (.studio.json)"

    upload = fields.Binary(string="Upload .studio.json", required=True)
    filename = fields.Char(string="Filename")
    preview_json = fields.Text(readonly=True, help="Validated DSL preview")
    app_id = fields.Many2one("studio.app", string="Target App (empty = create new)", help="If set, update existing app's DSL")

    def action_preview(self):
        self.ensure_one()
        if not self.upload:
            raise ValidationError(_("Upload a file"))
        try:
            raw = base64.b64decode(self.upload).decode("utf-8")
            dsl = json.loads(raw)
        except Exception as e:
            raise ValidationError(_("Invalid JSON: %s") % e)
        self.env["studio.dsl"].validate_definition(dsl)
        self.preview_json = json.dumps(dsl, indent=2, ensure_ascii=False)[:8000]
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_import(self):
        self.ensure_one()
        raw = base64.b64decode(self.upload).decode("utf-8")
        dsl = json.loads(raw)
        self.env["studio.dsl"].validate_definition(dsl)
        app_key = dsl.get("app", {}).get("key")
        app_name = dsl.get("app", {}).get("name") or app_key
        if self.app_id:
            app = self.app_id
            app.write({"dsl_json": dsl, "name": app_name})
        else:
            existing = self.env["studio.app"].search([("key", "=", app_key)], limit=1)
            if existing:
                existing.write({"dsl_json": dsl, "name": app_name})
                app = existing
            else:
                app = self.env["studio.app"].create({
                    "name": app_name,
                    "key": app_key,
                    "dsl_json": dsl,
                })
        # Auto-create version snapshot for audit
        app.env["studio.version"].create({
            "app_id": app.id,
            "name": _("Import %s") % (self.filename or app_key),
            "dsl_json": dsl,
            "dsl_hash": app.dsl_hash,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "studio.app",
            "res_id": app.id,
            "view_mode": "form",
            "target": "current",
        }
