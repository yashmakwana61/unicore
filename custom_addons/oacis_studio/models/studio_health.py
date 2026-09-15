# docs/studio_plan.md §13, §26 — Health checks + dependency tracking
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StudioHealth(models.AbstractModel):
    _name = "studio.health"
    _description = "Studio Health & Dependency (docs/studio_plan.md §13)"

    @api.model
    def check_app(self, app):
        """Return list of issues for DSL vs dictionary; used on publish and admin view."""
        dsl = app.dsl_json or {}
        issues = []
        try:
            self.env["studio.dsl"].validate_definition(dsl)
        except ValidationError as e:
            issues.append(str(e))
        # Dependency tracking: collect all referenced models/fields
        deps = []
        for m in dsl.get("models", []):
            deps.append(f"model:{m.get('key')}")
        for f in dsl.get("fields", []):
            deps.append(f"field:{f.get('model')}.{f.get('key')}")
        for ds in dsl.get("datasets", []):
            deps.append(f"dataset:{ds.get('key')}->{ds.get('source')}")
        return {"valid": len(issues) == 0, "issues": issues, "deps": deps}

    @api.model
    def rebuild_dependencies(self, app):
        self.env["studio.dependency"].search([("app_id", "=", app.id)]).unlink()
        check = self.check_app(app)
        for dep in check.get("deps", []):
            parts = dep.split(":", 1)
            self.env["studio.dependency"].create({
                "app_id": app.id,
                "source_type": "model" if dep.startswith("model:") else "field" if dep.startswith("field:") else "dataset",
                "source_key": parts[1] if len(parts) > 1 else dep,
                "depends_on": dep,
            })
        return check
