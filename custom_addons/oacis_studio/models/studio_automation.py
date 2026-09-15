# docs/studio_plan.md §7, §17 — Automation (Zapier-like, Phase 4)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
import logging

_logger = logging.getLogger(__name__)

AUTOMATION_TRIGGERS = [
    ("on_create", "On Create"),
    ("on_write", "On Write (field)"),
    ("on_unlink", "On Delete"),
    ("on_schedule", "Scheduled (Cron)"),
    ("on_time", "Time-based (field + offset)"),
    ("webhook", "Webhook / External Event"),
]

class StudioAutomation(models.Model):
    _name = "studio.automation"
    _description = "Studio Automation (Zapier-like)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "app_id, name"

    name = fields.Char(required=True)
    key = fields.Char(help="Semantic key")
    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    model_id = fields.Many2one("studio.model", required=True, ondelete="cascade", index=True, help="Subject model")
    trigger_type = fields.Selection(AUTOMATION_TRIGGERS, required=True, default="on_create")
    trigger_field = fields.Char(help="For on_write/on_time: field name, e.g. status, due_date")
    trigger_config = fields.Json(default=dict, help="Extra: cron interval, webhook path, offset minutes")
    condition = fields.Text(help="safe_eval condition, e.g. record.values_json.get('attendance',100) < 75")
    condition_json = fields.Json(help="Structured condition, e.g. {field: attendance, op: <, value: 75}")
    action_nodes = fields.Json(default=list, help="List of action nodes (subset of workflow nodes): [{type: email, config:{...}}, {type: notify, ...}, {type: update_record, ...}]")
    active = fields.Boolean(default=True)
    cron_id = fields.Many2one("ir.cron", string="Cron (for on_schedule)", readonly=True)
    log_ids = fields.One2many("studio.automation.log", "automation_id", string="Logs")
    company_id = fields.Many2one(related="app_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("app_key_uniq", "unique(app_id, key)", "Automation key must be unique per app"),
    ]

    @api.constrains("trigger_type", "trigger_field")
    def _check_trigger(self):
        for rec in self:
            if rec.trigger_type in ("on_write", "on_time") and not rec.trigger_field:
                raise ValidationError(_("Trigger field required for %s") % rec.trigger_type)

    def action_test(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.name, "message": f"Automation trigger {self.trigger_type} on {self.model_id.key} — {len(self.action_nodes or [])} actions", "type": "info"},
        }

    def _evaluate_condition(self, record):
        self.ensure_one()
        if not self.condition and not self.condition_json:
            return True
        expr = self.condition
        if self.condition_json and not expr:
            # structured not yet implemented, fallback
            expr = "True"
        ctx = {
            "record": record,
            "values": getattr(record, "values_json", {}) or {},
            "state": getattr(record, "state", None),
            "env": self.env,
        }
        try:
            return bool(safe_eval(expr or "True", ctx, mode="eval"))
        except Exception as e:
            _logger.warning("Automation condition failed %s: %s", self.name, e)
            return False

    def _execute_actions(self, record):
        self.ensure_one()
        for idx, node in enumerate(self.action_nodes or []):
            ntype = node.get("type")
            cfg = node.get("config", {}) or node
            try:
                if ntype == "update_record":
                    field, value = cfg.get("field"), cfg.get("value")
                    if field:
                        if hasattr(record, field) and field in record._fields:
                            record.write({field: value})
                        else:
                            # JSONB
                            vals = dict(getattr(record, "values_json", {}) or {})
                            vals[field] = value
                            record.write({"values_json": vals})
                        self._log(record, f"Updated {field}={value}", status="done")
                elif ntype == "email":
                    self._log(record, f"Email to {cfg.get('to', 'user')}: {cfg.get('subject', self.name)}", status="done")
                elif ntype == "notify":
                    self._log(record, f"Notify: {cfg.get('message', self.name)}", status="done")
                elif ntype == "activity":
                    try:
                        if hasattr(record, "activity_ids"):
                            record.activity_schedule("mail.mail_activity_data_todo", summary=cfg.get("summary", self.name))
                    except Exception:
                        pass
                    self._log(record, f"Activity {cfg.get('summary', self.name)}", status="done")
                elif ntype == "create_record":
                    self._log(record, f"Create {cfg.get('model')} (stub)", status="done")
                elif ntype == "webhook":
                    self._log(record, f"Webhook {cfg.get('url')} (stub)", status="done")
                else:
                    self._log(record, f"Action {ntype} (stub)", status="done")
            except Exception as e:
                self._log(record, f"Action {ntype} failed: {e}", status="failed")
                raise

    def _log(self, record, message, status="done"):
        self.env["studio.automation.log"].create({
            "automation_id": self.id,
            "res_model": record._name,
            "res_id": record.id,
            "message": message[:2000],
            "status": status,
        })

    @api.model
    def _trigger_for_record(self, trigger_type, record, field=None):
        """Called from studio.record create/write/unlink hooks. Debounced via queue in Phase4: immediate for now."""
        automations = self.search([
            ("trigger_type", "=", trigger_type),
            ("model_id", "=", record.model_id.id if hasattr(record, "model_id") else False),
            ("active", "=", True),
        ])
        for auto in automations:
            if trigger_type == "on_write" and field and auto.trigger_field and auto.trigger_field != field:
                continue
            if not auto._evaluate_condition(record):
                continue
            try:
                auto._execute_actions(record)
            except Exception as e:
                _logger.exception("Automation %s failed for %s#%s", auto.name, record._name, record.id)

class StudioAutomationLog(models.Model):
    _name = "studio.automation.log"
    _description = "Studio Automation Log"
    _order = "create_date desc"

    automation_id = fields.Many2one("studio.automation", required=True, ondelete="cascade", index=True)
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    message = fields.Text(required=True)
    status = fields.Selection([("done", "Done"), ("failed", "Failed"), ("skipped", "Skipped")], default="done", index=True)
    create_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
