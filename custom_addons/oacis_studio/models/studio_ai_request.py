# docs/studio_plan.md §11
from odoo import fields, models

class StudioAIRequest(models.Model):
    _name = "studio.ai.request"
    _description = "AI Copilot Request Audit (docs/studio_plan.md §11)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(required=True, help="NL prompt, e.g. Create scholarship management")
    app_id = fields.Many2one("studio.app", ondelete="set null")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    prompt = fields.Text(required=True)
    tool_calls_json = fields.Json(help="List of tool calls + results")
    dsl_proposed = fields.Json(help="DSL produced by LLM")
    dsl_valid = fields.Boolean(default=False)
    state = fields.Selection([("draft", "Draft"), ("previewed", "Previewed"), ("approved", "Approved"), ("rejected", "Rejected")], default="draft")
    cost_tokens = fields.Integer(help="Total tokens, for cost tracking §19")
    active = fields.Boolean(default=True)

class StudioAIOperation(models.Model):
    _name = "studio.ai.operation"
    _description = "AI Operation (single tool call, docs/studio_plan.md §11)"

    request_id = fields.Many2one("studio.ai.request", required=True, ondelete="cascade")
    tool = fields.Char(required=True, help="e.g. discover_models, validate_definition")
    args_json = fields.Json()
    result_json = fields.Json()
    latency_ms = fields.Integer()
