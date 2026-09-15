# docs/studio_plan.md §9, §14
from odoo import api, fields, models, _

class StudioDataDictionary(models.Model):
    _name = "studio.data.dictionary"
    _description = "Semantic Data Dictionary over oacis_* + ir.model (docs/studio_plan.md §9)"
    _order = "model_technical"

    model_technical = fields.Char(required=True, index=True, help="e.g. oacis.student, x_scholarship_application")
    model_label = fields.Char(required=True)
    field_technical = fields.Char(index=True, help="Null = model row; else field row")
    field_label = fields.Char()
    ttype = fields.Char(help="Odoo ttype or 'model'")
    relation = fields.Char(help="comodel_name if many2one")
    help_text = fields.Char()
    tags = fields.Char(help="Comma tags: reportable,workflow_subject,dashboard_source")
    sample = fields.Char(help="Sample value, for LLM prompt")
    is_studio = fields.Boolean(default=False, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("model_field_uniq", "unique(model_technical, field_technical)", "Model/field must be unique"),
    ]

    @api.model
    def crawl(self):
        """Rebuild dictionary from ir.model/ir.model.fields. Called nightly + on module install."""
        self.search([]).unlink()
        # Curated set: all oacis.* + studio.* + base res.* needed for reports
        models = self.env["ir.model"].search([("model", "like", "oacis.%")])
        models |= self.env["ir.model"].search([("model", "like", "x_%")])
        models |= self.env["ir.model"].search([("model", "like", "studio.%")])
        # Always include core education + account for fees
        for mname in ["res.partner", "res.company", "oacis.student", "oacis.campus", "account.move"]:
            m = self.env["ir.model"].search([("model", "=", mname)], limit=1)
            if m:
                models |= m
        for m in models:
            self.create({
                "model_technical": m.model,
                "model_label": m.name or m.model,
                "ttype": "model",
                "tags": "reportable,dashboard_source" if "oacis" in m.model else "reportable",
            })
            for f in self.env["ir.model.fields"].search([("model_id", "=", m.id)]):
                self.create({
                    "model_technical": m.model,
                    "model_label": m.name or m.model,
                    "field_technical": f.name,
                    "field_label": f.field_description or f.name,
                    "ttype": f.ttype,
                    "relation": f.relation or False,
                    "help_text": (f.help or "")[:500],
                    "tags": "",
                })
        return True

    @api.model
    def search_for_ai(self, query: str, limit=20):
        """RAG retrieval: simple ILIKE, upgraded to pgvector in Phase 7."""
        domain = ["|", ("model_label", "ilike", query), ("field_label", "ilike", query)]
        return self.search(domain, limit=limit)
