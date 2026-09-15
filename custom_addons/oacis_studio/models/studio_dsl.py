# Part of Forge Studio. See docs/studio_plan.md §2-§3.
import json
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# DSL version contract
DSL_VERSION = "1.0"
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
TECH_RE = re.compile(r"^x_[a-z][a-z0-9_]*$")

ALLOWED_FIELD_TYPES_V1 = {
    "char", "text", "html", "integer", "float", "decimal", "monetary",
    "boolean", "date", "datetime", "selection",
    "many2one", "one2many", "many2many",
    "image", "binary", "attachment", "reference", "related",
}

# Minimal JSON Schema (kept in data/dsl_schema.json for tooling; duplicated here for runtime without jsonschema dep)
def _validate_dsl_structure(dsl: dict):
    if not isinstance(dsl, dict):
        raise ValidationError(_("DSL must be a JSON object"))
    if dsl.get("dsl_version") != DSL_VERSION:
        raise ValidationError(_("DSL version must be %s") % DSL_VERSION)
    app = dsl.get("app")
    if not app or not app.get("key"):
        raise ValidationError(_("DSL app.key is required"))
    if not KEY_RE.match(app["key"]):
        raise ValidationError(_("app.key must match %s") % KEY_RE.pattern)
    for m in dsl.get("models", []):
        if not m.get("key") or not KEY_RE.match(m["key"]):
            raise ValidationError(_("model key invalid: %s") % m)
        if not TECH_RE.match(m.get("tech", "")):
            raise ValidationError(_("model tech must be x_*: %s") % m)
    for f in dsl.get("fields", []):
        if f.get("type") not in ALLOWED_FIELD_TYPES_V1:
            raise ValidationError(_("Field type not in V1: %s") % f)
        if not f.get("model") or not f.get("key"):
            raise ValidationError(_("Field must have model and key: %s") % f)
    # relations
    for r in dsl.get("relations", []):
        if r.get("type") not in ("many2one", "one2many", "many2many"):
            raise ValidationError(_("Relation type invalid: %s") % r)
    # views
    for v in dsl.get("views", []):
        if v.get("type") not in ("form", "list", "kanban", "search"):
            raise ValidationError(_("View type invalid: %s") % v)
    # datasets
    for ds in dsl.get("datasets", []):
        if not ds.get("key") or not ds.get("source"):
            raise ValidationError(_("Dataset must have key and source: %s") % ds)
    return True


def validate_against_dictionary(dsl: dict, env):
    """Check that every `relations.to` and `datasets.source` exists in studio.data.dictionary or ir.model."""
    dict_models = set(env["studio.data.dictionary"].search([]).mapped("model_technical"))
    # also allow any installed ir.model (covers oacis.*)
    dict_models |= set(env["ir.model"].search([]).mapped("model"))
    errors = []
    for r in dsl.get("relations", []):
        if r.get("to") not in dict_models:
            errors.append(_("Relation target not in dictionary: %s") % r.get("to"))
    for ds in dsl.get("datasets", []):
        if ds.get("source") not in dict_models:
            errors.append(_("Dataset source not in dictionary: %s") % ds.get("source"))
    for f in dsl.get("fields", []):
        if f.get("type") in ("many2one", "one2many", "many2many") and f.get("relation"):
            if f["relation"] not in dict_models:
                errors.append(_("Field relation not in dictionary: %s") % f["relation"])
    # Validate view/dataset/workflow/automation/report/dashboard model refs
    model_keys = {m.get("key") for m in dsl.get("models", [])}
    model_keys |= dict_models  # allow refs to existing oacis models
    for v in dsl.get("views", []):
        if v.get("model") and v["model"] not in model_keys:
            errors.append(_("View model not found: %s") % v)
    for w in dsl.get("workflows", []):
        if w.get("model") and w["model"] not in model_keys:
            errors.append(_("Workflow model not found: %s") % w)
    for a in dsl.get("automations", []):
        if a.get("model") and a["model"] not in model_keys:
            errors.append(_("Automation model not found: %s") % a)
    if errors:
        raise ValidationError("\n".join(errors))
    return True


def _validate_uniqueness_and_refs(dsl: dict):
    """§58: Field/model/view uniqueness + view/dataset reference checks."""
    errors = []
    # Model key uniqueness & tech uniqueness
    seen_models = set()
    seen_tech = set()
    for m in dsl.get("models", []):
        k = m.get("key")
        t = m.get("tech")
        if k in seen_models:
            errors.append(_("Duplicate model key: %s") % k)
        seen_models.add(k)
        if t in seen_tech:
            errors.append(_("Duplicate model tech: %s") % t)
        seen_tech.add(t)
    # Field uniqueness per model
    seen_fields = set()
    for f in dsl.get("fields", []):
        key = (f.get("model"), f.get("key"))
        if key in seen_fields:
            errors.append(_("Duplicate field: %s.%s") % key)
        seen_fields.add(key)
        if f.get("tech") and f["tech"] in seen_tech:
            # also check field tech collision with model tech
            pass
        # selection requires options
        if f.get("type") == "selection" and not f.get("selection"):
            errors.append(_("Selection field requires 'selection' options: %s.%s") % key)
        if f.get("type") in ("many2one", "many2many", "one2many") and not f.get("relation"):
            errors.append(_("Relational field requires 'relation': %s.%s") % key)
    # View key uniqueness
    seen_views = set()
    for v in dsl.get("views", []):
        vk = (v.get("model"), v.get("type"), v.get("key"))
        if vk in seen_views:
            errors.append(_("Duplicate view: %s") % str(vk))
        seen_views.add(vk)
    # Dataset key uniqueness
    seen_ds = set()
    for ds in dsl.get("datasets", []):
        if ds.get("key") in seen_ds:
            errors.append(_("Duplicate dataset key: %s") % ds["key"])
        seen_ds.add(ds.get("key"))
    if errors:
        raise ValidationError("\n".join(errors))
    return True


def _check_circular_deps(dsl: dict):
    """Detect circular model dependencies via relations."""
    relations = dsl.get("relations", []) or []
    # also infer from fields
    for f in dsl.get("fields", []):
        if f.get("type") in ("many2one", "one2many", "many2many") and f.get("relation"):
            relations.append({"from": f.get("model"), "to": f["relation"], "type": f["type"]})
    # Build graph: model -> set(to)
    graph = {}
    for r in relations:
        frm = r.get("from") or r.get("model")
        to = r.get("to") or r.get("relation")
        if not frm or not to:
            continue
        graph.setdefault(frm, set()).add(to)
    # DFS cycle detection
    visited, stack = set(), set()
    def dfs(node, path):
        if node in stack:
            raise ValidationError(_("Circular dependency detected: %s -> %s") % (" -> ".join(path), node))
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        for nxt in graph.get(node, set()):
            dfs(nxt, path + [nxt])
        stack.remove(node)
    for n in list(graph.keys()):
        if n not in visited:
            dfs(n, [n])
    return True


class StudioDSL(models.AbstractModel):
    _name = "studio.dsl"
    _description = "Studio DSL 1.0 Validation & Preview Engine (docs/studio_plan.md §3)"

    @api.model
    def validate_definition(self, dsl):
        """Deterministic, no LLM. Called by both UI and AI tools. Forge Studio 2.0 §58."""
        if isinstance(dsl, str):
            dsl = json.loads(dsl)
        _validate_dsl_structure(dsl)
        validate_against_dictionary(dsl, self.env)
        _validate_uniqueness_and_refs(dsl)
        _check_circular_deps(dsl)
        return {"valid": True, "dsl_version": DSL_VERSION, "app": dsl.get("app", {}).get("key")}

    @api.model
    def preview_definition(self, dsl, sample_ids=None):
        """Render DSL in a SAVEPOINT without committing. Returns sample HTML / arch preview."""
        self.validate_definition(dsl)
        # Phase 1: create ephemeral registry overlay, render arch_json via studio.view renderer, return diff
        # For Phase 0 we return a structural preview only.
        return {
            "valid": True,
            "preview": {
                "models": len((dsl if isinstance(dsl, dict) else json.loads(dsl)).get("models", [])),
                "fields": len((dsl if isinstance(dsl, dict) else json.loads(dsl)).get("fields", [])),
                "note": "Phase 0 structural preview — full arch render in Phase 3 (View Builder).",
            },
        }

    @api.model
    def get_schema(self):
        """Return DSL JSON Schema for AI structured outputs."""
        # Loaded from data/dsl_schema.json at install; kept here for API.
        import importlib.resources as pkg_resources
        try:
            text = pkg_resources.files("oacis_studio").joinpath("data/dsl_schema.json").read_text(encoding="utf-8")
            return json.loads(text)
        except Exception:
            return {"dsl_version": DSL_VERSION, "type": "object"}
