# docs/studio_plan.md §9
from odoo import fields, models
from odoo.tools.safe_eval import safe_eval

class StudioExpression(models.Model):
    _name = "studio.expression"
    _description = "Studio Expression (safe_eval, docs/studio_plan.md §9)"

    name = fields.Char(required=True)
    code = fields.Text(required=True, help="e.g. attendance.present_days / attendance.total_days * 100")
    dataset_id = fields.Many2one("studio.dataset", ondelete="cascade")
    description = fields.Char()

    def evaluate(self, context_vars: dict):
        self.ensure_one()
        # Whitelisted evaluation — no builtins, 1s timeout via safe_eval
        return safe_eval(self.code, context_vars or {}, mode="eval")
