# docs/studio_plan.md §11 — AI Copilot (Phase 7) — tool-constrained, RAG, guardrails
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from odoo.tools.safe_eval import safe_eval
import logging
import time
import json
import re

_logger = logging.getLogger(__name__)

# Tool registry — maps tool name to handler
TOOL_SPECS = {
    "discover_models": {"desc": "Search data dictionary for relevant models", "args": ["query"]},
    "discover_fields": {"desc": "List fields for a model", "args": ["model"]},
    "discover_relationships": {"desc": "Show relations for a model", "args": ["model"]},
    "validate_definition": {"desc": "Validate DSL JSON", "args": ["dsl"]},
    "preview_definition": {"desc": "Preview DSL without committing", "args": ["dsl"]},
    "publish_definition": {"desc": "Publish DSL (requires human approval)", "args": ["dsl", "app_id"]},
    "diagnose_error": {"desc": "Diagnose last error", "args": ["log_id"]},
}

# Simple template registry for mock LLM — maps keywords to DSL skeletons
TEMPLATE_DSL = {
    "scholarship": {
        "app": {"key": "scholarship", "name": "Scholarship Management", "icon": "fa-graduation-cap"},
        "models": [{"key": "scholarship.application", "tech": "x_scholarship_application", "label": "Scholarship Application", "opts": {"chatter": True}}],
        "fields": [
            {"model": "scholarship.application", "key": "name", "type": "char", "label": "Title", "required": True},
            {"model": "scholarship.application", "key": "student_id", "type": "many2one", "label": "Student", "relation": "oacis.student"},
            {"model": "scholarship.application", "key": "amount", "type": "monetary", "label": "Amount", "required": True},
            {"model": "scholarship.application", "key": "type_id", "type": "many2one", "label": "Scholarship Type", "relation": "oacis.scholarship.program"},
        ],
        "views": [{"model": "scholarship.application", "type": "form", "arch": {"type": "sheet", "children": [{"type": "group", "children": [{"type": "field", "name": "name"}, {"type": "field", "name": "student_id"}]}]}}],
        "workflows": [{"model": "scholarship.application", "states": ["draft", "review", "approved"], "transitions": []}],
    },
    "transport": {
        "app": {"key": "transport_route", "name": "Transport Route", "icon": "fa-bus"},
        "models": [{"key": "transport.route", "tech": "x_transport_route", "label": "Transport Route"}],
        "fields": [
            {"model": "transport.route", "key": "name", "type": "char", "label": "Route Name", "required": True},
            {"model": "transport.route", "key": "student_id", "type": "many2one", "label": "Student", "relation": "oacis.student"},
        ],
    },
}

class StudioAICopilot(models.AbstractModel):
    _name = "studio.ai.copilot"
    _description = "AI Copilot — tool-constrained orchestrator"

    @api.model
    def _check_studio_access(self):
        if not self.env.user.has_group("oacis_studio.group_studio_user"):
            raise AccessError(_("Studio User access required for AI Copilot"))
        return True

    @api.model
    def discover_models(self, query, limit=10):
        self._check_studio_access()
        # RAG: search data_dictionary for models matching query
        domain = ["|", ("model_label", "ilike", query), ("model_technical", "ilike", query)]
        recs = self.env["studio.data.dictionary"].search(domain, limit=limit)
        # Deduplicate models
        models = {}
        for r in recs:
            if r.ttype == "model":
                models[r.model_technical] = r.model_label
            elif r.model_technical not in models:
                # add from field's model
                models[r.model_technical] = r.model_label
        # Filter by user's readable models (permission-aware) — Odoo 19 uses check_access
        readable = []
        for m, label in models.items():
            try:
                # Odoo 19: use check_access (check_access_rights is deprecated)
                has_access = False
                try:
                    # Try new API
                    has_access = self.env[m].check_access("read", raise_exception=False)
                except TypeError:
                    has_access = self.env[m].check_access_rights("read", raise_exception=False)
                if has_access:
                    readable.append({"model": m, "label": label})
            except Exception:
                # If model not in registry or access error, include oacis/studio
                if m.startswith("oacis.") or m.startswith("x_") or m.startswith("studio."):
                    readable.append({"model": m, "label": label})
        return readable[:limit]

    @api.model
    def discover_fields(self, model, limit=20):
        self._check_studio_access()
        recs = self.env["studio.data.dictionary"].search([("model_technical", "=", model), ("ttype", "!=", "model")], limit=limit)
        return [{"field": r.field_technical, "label": r.field_label, "ttype": r.ttype, "relation": r.relation} for r in recs]

    @api.model
    def discover_relationships(self, model):
        self._check_studio_access()
        recs = self.env["studio.data.dictionary"].search([("model_technical", "=", model), ("relation", "!=", False)], limit=20)
        return [{"field": r.field_technical, "relation": r.relation} for r in recs]

    @api.model
    def validate_definition(self, dsl):
        self._check_studio_access()
        if isinstance(dsl, str):
            dsl = json.loads(dsl)
        return self.env["studio.dsl"].validate_definition(dsl)

    @api.model
    def preview_definition(self, dsl):
        self._check_studio_access()
        if isinstance(dsl, str):
            dsl = json.loads(dsl)
        return self.env["studio.dsl"].preview_definition(dsl)

    @api.model
    def chat(self, prompt, app_id=None):
        """Main entry: NL -> RAG -> DSL proposal -> validate -> audit. Returns proposal checklist."""
        self._check_studio_access()
        start = time.time()
        prompt = prompt or ""
        # Create audit record
        req = self.env["studio.ai.request"].create({
            "name": prompt[:80],
            "prompt": prompt,
            "tool_calls_json": [],
            "state": "draft",
        })
        tool_calls = []
        # Step 1: RAG discover models for prompt keywords
        keywords = re.findall(r"[a-z]{3,}", prompt.lower())
        discovered = []
        for kw in keywords[:3]:
            try:
                res = self.discover_models(kw, limit=5)
                tool_calls.append({"tool": "discover_models", "args": {"query": kw}, "result": res})
                discovered.extend(res)
            except Exception as e:
                tool_calls.append({"tool": "discover_models", "args": {"query": kw}, "error": str(e)})
        # Step 2: Generate DSL proposal (mock LLM — template matching + RAG)
        dsl = self._mock_generate(prompt, discovered)
        # Step 3: Validate
        try:
            valid = self.validate_definition(dsl)
            tool_calls.append({"tool": "validate_definition", "args": {"dsl": dsl}, "result": valid})
            req.write({"tool_calls_json": tool_calls, "dsl_proposed": dsl, "dsl_valid": True, "cost_tokens": len(prompt) // 4})
        except Exception as e:
            tool_calls.append({"tool": "validate_definition", "args": {"dsl": dsl}, "error": str(e)})
            req.write({"tool_calls_json": tool_calls, "dsl_proposed": dsl, "dsl_valid": False, "cost_tokens": len(prompt) // 4})
            return {
                "request_id": req.id,
                "prompt": prompt,
                "discovered": discovered[:5],
                "dsl": dsl,
                "valid": False,
                "error": str(e),
                "checklist": self._checklist_from_dsl(dsl),
                "elapsed_ms": int((time.time() - start) * 1000),
            }
        # Preview (no commit)
        try:
            preview = self.preview_definition(dsl)
            tool_calls.append({"tool": "preview_definition", "args": {"dsl": dsl}, "result": preview})
            req.write({"tool_calls_json": tool_calls, "state": "previewed"})
        except Exception as e:
            tool_calls.append({"tool": "preview_definition", "error": str(e)})
            req.write({"tool_calls_json": tool_calls})
        elapsed = int((time.time() - start) * 1000)
        # Create operations audit
        for tc in tool_calls:
            self.env["studio.ai.operation"].create({
                "request_id": req.id,
                "tool": tc.get("tool"),
                "args_json": tc.get("args"),
                "result_json": tc.get("result") or {"error": tc.get("error")},
                "latency_ms": elapsed // max(len(tool_calls), 1),
            })
        return {
            "request_id": req.id,
            "prompt": prompt,
            "discovered": discovered[:5],
            "dsl": dsl,
            "valid": True,
            "checklist": self._checklist_from_dsl(dsl),
            "preview": preview if "preview" in locals() else {},
            "elapsed_ms": elapsed,
        }

    def _mock_generate(self, prompt, discovered):
        """Mock LLM: keyword template matching, falls back to generic app."""
        prompt_l = prompt.lower()
        # Check for scholarship
        for key, tmpl in TEMPLATE_DSL.items():
            if key in prompt_l:
                # Enrich with discovered relations if available
                dsl = json.loads(json.dumps(tmpl))  # deep copy
                dsl["dsl_version"] = "1.0"
                # Add discovered model as relation if relevant
                if discovered and "fields" in dsl:
                    # Add a relation field if not already present
                    pass
                return dsl
        # Generic fallback: create app from prompt title
        # Extract app name: first 3 words
        words = [w for w in re.findall(r"[A-Za-z]{3,}", prompt)][:4]
        app_key = "_".join(w.lower() for w in words)[:30] or "custom_app"
        app_key = re.sub(r"[^a-z0-9_]", "", app_key)
        app_name = " ".join(w.capitalize() for w in words) or "Custom App"
        return {
            "dsl_version": "1.0",
            "app": {"key": app_key, "name": app_name, "icon": "fa-cube"},
            "models": [{"key": f"{app_key}.record", "tech": f"x_{app_key}_record", "label": app_name}],
            "fields": [
                {"model": f"{app_key}.record", "key": "name", "type": "char", "label": "Name", "required": True},
                {"model": f"{app_key}.record", "key": "student_id", "type": "many2one", "label": "Student", "relation": "oacis.student"},
            ],
            "views": [{"model": f"{app_key}.record", "type": "form", "arch": {"type": "sheet", "children": [{"type": "field", "name": "name"}]}}],
            "workflows": [],
        }

    def _checklist_from_dsl(self, dsl):
        """Generate human checklist from DSL for approval UI."""
        checklist = []
        for m in dsl.get("models", []):
            checklist.append(f"✓ Model: {m.get('label')} ({m.get('key')})")
        for f in dsl.get("fields", []):
            checklist.append(f"✓ Field: {f.get('label')} ({f.get('key')} → {f.get('type')})")
        for v in dsl.get("views", []):
            checklist.append(f"✓ View: {v.get('type')} for {v.get('model')}")
        for w in dsl.get("workflows", []):
            checklist.append(f"✓ Workflow: {w.get('model')}")
        for r in dsl.get("reports", []):
            checklist.append(f"✓ Report: {r.get('name') or r.get('key')}")
        for d in dsl.get("dashboards", []):
            checklist.append(f"✓ Dashboard: {d.get('name') or d.get('key')}")
        if not checklist:
            checklist = ["✓ DSL generated — no components detected"]
        return checklist

    @api.model
    def publish(self, request_id, app_id=None):
        """Human approval: publish DSL to studio.app (creates/updates)."""
        self._check_studio_access()
        req = self.env["studio.ai.request"].browse(request_id)
        if not req.exists():
            raise ValidationError(_("Request not found"))
        if not req.dsl_valid:
            raise ValidationError(_("DSL not valid, cannot publish"))
        dsl = req.dsl_proposed
        # Security: check if user can create app
        if not self.env.user.has_group("oacis_studio.group_studio_builder"):
            raise AccessError(_("Studio Builder access required to publish"))
        # Create or update app
        app_key = dsl.get("app", {}).get("key")
        app = self.env["studio.app"].search([("key", "=", app_key)], limit=1)
        if app:
            app.write({"name": dsl["app"]["name"], "dsl_json": dsl})
            # Sync models from DSL
            app.action_sync_from_dsl()
        else:
            app = self.env["studio.app"].create({"name": dsl["app"]["name"], "key": app_key, "dsl_json": dsl})
            app.action_sync_from_dsl()
        req.write({"app_id": app.id, "state": "approved"})
        # Log publish
        self.env["studio.ai.operation"].create({
            "request_id": req.id,
            "tool": "publish_definition",
            "args_json": {"app_id": app.id},
            "result_json": {"app_key": app_key, "app_id": app.id},
        })
        return {"app_id": app.id, "app_key": app_key}
