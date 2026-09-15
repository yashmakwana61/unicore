# docs/studio_plan.md §13 — Export .studio JSON/ZIP
import base64
import json

from odoo import api, fields, models


class StudioExportWizard(models.TransientModel):
    _name = "studio.export.wizard"
    _description = "Studio DSL Export (.studio.json)"

    app_id = fields.Many2one("studio.app", required=True)
    filename = fields.Char(default=lambda self: "export.studio.json", readonly=True)
    preview = fields.Text(readonly=True)
    file = fields.Binary(readonly=True)
    filename_out = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        app_id = ctx.get("default_app_id") or ctx.get("active_id")
        if app_id:
            app = self.env["studio.app"].browse(app_id)
            if app.exists():
                res["app_id"] = app.id
                res["filename_out"] = f"{app.key}.studio.json"
                res["preview"] = json.dumps(app.dsl_json or {}, indent=2, ensure_ascii=False)[:8000]
        return res

    def action_generate(self):
        self.ensure_one()
        payload = json.dumps(self.app_id.dsl_json or {}, indent=2, ensure_ascii=False).encode()
        self.file = base64.b64encode(payload)
        self.filename_out = f"{self.app_id.key}.studio.json"
        self.preview = payload.decode()[:8000]
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
