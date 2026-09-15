# docs/studio_plan.md §6, §17 — Workflow Engine (Phase 4)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
import logging

_logger = logging.getLogger(__name__)

WORKFLOW_NODE_TYPES = [
    ("trigger", "Trigger"),
    ("condition", "Condition"),
    ("approval", "Approval"),
    ("create_record", "Create Record"),
    ("update_record", "Update Record"),
    ("delete_record", "Delete/Archive"),
    ("assign", "Assign User"),
    ("email", "Send Email"),
    ("notify", "Send Notification"),
    ("report", "Generate Report"),
    ("activity", "Create Activity"),
    ("delay", "Wait/Delay"),
    ("webhook", "Webhook"),
    ("api", "API Call"),
    ("ai_action", "AI Action"),
]

WORKFLOW_TRIGGERS = [
    ("on_create", "On Create"),
    ("on_write", "On Write"),
    ("on_state_change", "On State Change"),
    ("manual", "Manual"),
    ("scheduled", "Scheduled (Cron)"),
]

class StudioWorkflow(models.Model):
    _name = "studio.workflow"
    _description = "Studio Workflow (docs/studio_plan.md §6)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "app_id, name"

    name = fields.Char(required=True)
    key = fields.Char(required=True, help="Semantic key, e.g. scholarship_approval")
    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    model_id = fields.Many2one("studio.model", required=True, ondelete="cascade", index=True, help="Subject model for workflow")
    description = fields.Text()
    trigger_type = fields.Selection(WORKFLOW_TRIGGERS, default="on_create", required=True)
    trigger_field = fields.Char(help="For on_write: field name to watch, e.g. status")
    active = fields.Boolean(default=True)
    state = fields.Selection([("draft", "Draft"), ("active", "Active"), ("archived", "Archived")], default="draft")
    node_ids = fields.One2many("studio.workflow.node", "workflow_id", string="Nodes")
    transition_ids = fields.One2many("studio.workflow.transition", "workflow_id", string="Transitions")
    instance_ids = fields.One2many("studio.workflow.instance", "workflow_id", string="Instances")
    max_retries = fields.Integer(default=3, help="Max retries per node on failure")
    company_id = fields.Many2one(related="app_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("app_key_uniq", "unique(app_id, key)", "Workflow key must be unique per app"),
    ]

    def action_activate(self):
        for rec in self:
            if not rec.node_ids:
                raise ValidationError(_("Workflow must have at least one node"))
            # validate no cycles without condition? basic
            rec.state = "active"

    def action_archive(self):
        self.write({"state": "archived", "active": False})

    def action_open_builder(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "studio.workflow_builder",
            "params": {"workflow_id": self.id},
            "context": {"active_id": self.id},
        }

    def _get_start_node(self):
        self.ensure_one()
        # Trigger node is start, else lowest sequence
        trigger = self.node_ids.filtered(lambda n: n.node_type == "trigger")
        return trigger[:1] or self.node_ids.sorted("sequence")[:1]

    @api.model
    def _trigger_for_record(self, trigger_type, record, field=None):
        """Create workflow instance for matching workflows (Phase 4: studio.record only)."""
        # Only handle studio.record for now; extends via oacis.* uses same pattern but via base_automation hook (future)
        if record._name != "studio.record":
            return
        # record is studio.record, need to match workflow.model_id == record.model_id
        domain = [
            ("trigger_type", "=", trigger_type),
            ("model_id", "=", record.model_id.id),
            ("active", "=", True),
            ("state", "=", "active"),
        ]
        if trigger_type == "on_write" and field:
            domain.append(("trigger_field", "in", [False, field]))
        workflows = self.search(domain)
        for wf in workflows:
            # Check existing instance (unique constraint) — skip if already exists and not done
            existing = self.env["studio.workflow.instance"].search([
                ("workflow_id", "=", wf.id),
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ], limit=1)
            if existing:
                # if done/failed, allow new? For now skip to avoid duplicate
                if existing.state not in ("done", "failed", "cancelled"):
                    continue
                else:
                    # allow new instance by cancelling old? For simplicity create new only if old done
                    # Remove unique constraint by deleting old done? Keep old, create new with different res? For Phase4, skip new if done exists
                    continue
            try:
                inst = self.env["studio.workflow.instance"].create({
                    "workflow_id": wf.id,
                    "res_model": record._name,
                    "res_id": record.id,
                    "state": "pending",
                })
                # Execute immediately (sync) for Phase4; in production would queue
                inst._execute()
            except Exception as e:
                _logger.exception("Workflow trigger failed for %s", wf.name)

class StudioWorkflowNode(models.Model):
    _name = "studio.workflow.node"
    _description = "Studio Workflow Node"
    _order = "workflow_id, sequence"

    workflow_id = fields.Many2one("studio.workflow", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, help="Node label, e.g. Document Verification")
    key = fields.Char(help="Semantic key")
    node_type = fields.Selection(WORKFLOW_NODE_TYPES, required=True, default="condition")
    sequence = fields.Integer(default=10)
    config_json = fields.Json(default=dict, help="Node-type specific config. See docs §6")
    # Config examples:
    # condition: {"expression": "record.values_json.get('amount',0) > 5000"}
    # approval: {"group_id": 123, "auto_approve": false}
    # email: {"template": "scholarship_approved", "to_field": "student_id"}
    # notify: {"message": "Approved", "partner_field": "student_id"}
    # delay: {"minutes": 60}
    # webhook: {"url": "https://...", "method": "POST"}
    description = fields.Text()
    active = fields.Boolean(default=True)

    @api.constrains("config_json", "node_type")
    def _check_config(self):
        for rec in self:
            if rec.node_type == "condition" and not rec.config_json.get("expression"):
                # allow empty for now, but warn
                pass

class StudioWorkflowTransition(models.Model):
    _name = "studio.workflow.transition"
    _description = "Studio Workflow Transition"
    _order = "workflow_id, sequence"

    workflow_id = fields.Many2one("studio.workflow", required=True, ondelete="cascade", index=True)
    name = fields.Char(help="Transition label")
    from_node_id = fields.Many2one("studio.workflow.node", required=True, ondelete="cascade")
    to_node_id = fields.Many2one("studio.workflow.node", required=True, ondelete="cascade")
    condition = fields.Char(help="Python safe_eval condition, e.g. state=='approved' or result==True")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

class StudioWorkflowInstance(models.Model):
    _name = "studio.workflow.instance"
    _description = "Studio Workflow Instance (per record execution)"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    workflow_id = fields.Many2one("studio.workflow", required=True, ondelete="cascade", index=True, tracking=True)
    res_model = fields.Char(required=True, help="e.g. studio.record", index=True)
    res_id = fields.Integer(required=True, index=True)
    res_display = fields.Char(compute="_compute_res_display", store=False)
    state = fields.Selection([
        ("pending", "Pending"), ("running", "Running"),
        ("waiting_approval", "Waiting Approval"), ("waiting_delay", "Waiting Delay"),
        ("done", "Done"), ("failed", "Failed"), ("cancelled", "Cancelled")
    ], default="pending", tracking=True, index=True)
    current_node_id = fields.Many2one("studio.workflow.node", string="Current Node")
    history_json = fields.Json(default=list, help="List of visited nodes {node_id, status, timestamp}")
    attempts = fields.Integer(default=0)
    log_ids = fields.One2many("studio.workflow.log", "instance_id", string="Logs")
    company_id = fields.Many2one(related="workflow_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("res_uniq", "unique(workflow_id, res_model, res_id)", "One running instance per record per workflow"),
    ]

    def _compute_res_display(self):
        for rec in self:
            try:
                if rec.res_model == "studio.record":
                    r = self.env["studio.record"].browse(rec.res_id)
                    rec.res_display = r.display_name if r.exists() else f"{rec.res_model}#{rec.res_id}"
                else:
                    obj = self.env[rec.res_model].browse(rec.res_id)
                    rec.res_display = obj.display_name if obj.exists() else f"{rec.res_model}#{rec.res_id}"
            except Exception:
                rec.res_display = f"{rec.res_model}#{rec.res_id}"

    def action_run_next(self):
        """Manual step: used for approval or retry."""
        for rec in self:
            rec.with_context(studio_cron=False)._execute()
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def _execute(self):
        """Core execution engine: walk nodes until waiting/done/failed. Handles retries, logging."""
        for inst in self:
            if inst.state in ("done", "cancelled"):
                continue
            workflow = inst.workflow_id
            if not workflow.active or workflow.state != "active":
                inst._log("Workflow not active", status="failed")
                inst.state = "failed"
                continue
            # pick start if pending
            if inst.state == "pending" or not inst.current_node_id:
                start = workflow._get_start_node()
                if not start:
                    inst._log("No start node", status="failed")
                    inst.state = "failed"
                    continue
                inst.current_node_id = start.id
                inst.state = "running"
            # loop with guard against infinite
            visited = 0
            max_steps = 50
            while inst.state == "running" and visited < max_steps:
                visited += 1
                node = inst.current_node_id
                if not node:
                    inst.state = "done"
                    break
                try:
                    result = inst._execute_node(node)
                except Exception as e:
                    _logger.exception("Workflow node failed")
                    inst._log(f"Node {node.name} failed: {e}", node=node, status="failed")
                    inst.attempts += 1
                    if inst.attempts >= workflow.max_retries:
                        inst.state = "failed"
                    else:
                        inst.state = "running"  # retry next cron
                    break
                # handle waiting nodes
                if result == "waiting_approval":
                    inst.state = "waiting_approval"
                    break
                if result == "waiting_delay":
                    inst.state = "waiting_delay"
                    break
                # move to next via transitions
                nxt = inst._next_node(node, result)
                if nxt:
                    inst.current_node_id = nxt.id
                    inst.history_json = (inst.history_json or []) + [{"node_id": node.id, "status": "done", "result": str(result)}]
                else:
                    # no outgoing -> done
                    inst.history_json = (inst.history_json or []) + [{"node_id": node.id, "status": "done"}]
                    inst.state = "done"
                    inst._log(f"Workflow done at {node.name}", node=node, status="done")
                    break

    def _execute_node(self, node):
        """Return result or waiting signal. All side-effects logged."""
        # get record
        try:
            if self.res_model == "studio.record":
                record = self.env["studio.record"].browse(self.res_id)
            else:
                record = self.env[self.res_model].browse(self.res_id)
            if not record.exists():
                raise ValidationError(_("Record not found"))
        except Exception as e:
            raise e

        cfg = node.config_json or {}
        if node.node_type == "trigger":
            self._log(f"Trigger {node.name}", node=node, status="done")
            return True
        elif node.node_type == "condition":
            expr = cfg.get("expression", "True")
            # safe_eval with record, state, values_json
            ctx = {
                "record": record,
                "values": getattr(record, "values_json", {}) or {},
                "state": getattr(record, "state", None),
                "env": self.env,
            }
            try:
                res = safe_eval(expr, ctx, mode="eval")
                self._log(f"Condition {node.name}: {expr} => {res}", node=node, status="done")
                return bool(res)
            except Exception as e:
                self._log(f"Condition eval failed: {e}", node=node, status="failed")
                return False
        elif node.node_type == "approval":
            # create activity for group
            group_id = cfg.get("group_id")
            # In real: create mail.activity; for Phase4 create a log and set waiting
            self._log(f"Approval waiting: {node.name} (group {group_id})", node=node, status="waiting_approval")
            # create activity on record if supports
            try:
                if hasattr(record, "activity_ids"):
                    record.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=f"Approval: {node.name}",
                        note=cfg.get("note", ""),
                        user_id=self.env.user.id,
                    )
            except Exception:
                pass
            return "waiting_approval"
        elif node.node_type == "create_record":
            # cfg: {"model": "x_demo", "values": {"name": "..."}}
            model = cfg.get("model")
            values = cfg.get("values", {})
            # simple template: allow {{record.field}} substitution (very basic)
            if model and model.startswith("x_"):
                # for studio.record JSONB we would need to resolve, but keep generic
                self._log(f"Create record {model} skipped (Phase4 stub, values {values})", node=node, status="done")
            elif model:
                try:
                    # very naive: create with values
                    self.env[model].create(values)
                    self._log(f"Created {model} {values}", node=node, status="done")
                except Exception as e:
                    self._log(f"Create failed: {e}", node=node, status="failed")
                    raise
            return True
        elif node.node_type == "update_record":
            field = cfg.get("field")
            value = cfg.get("value")
            if field and hasattr(record, field):
                try:
                    # handle JSONB record: update values_json
                    if self.res_model == "studio.record" and field not in record._fields:
                        vals = dict(record.values_json or {})
                        vals[field] = value
                        record.write({"values_json": vals})
                    else:
                        record.write({field: value})
                    self._log(f"Updated {field}={value}", node=node, status="done")
                except Exception as e:
                    self._log(f"Update failed: {e}", node=node, status="failed")
                    raise
            return True
        elif node.node_type == "email":
            # stub: log, in real use mail.template
            to = cfg.get("to_field") or cfg.get("to") or "user"
            self._log(f"Email to {to}: {node.name}", node=node, status="done")
            return True
        elif node.node_type == "notify":
            msg = cfg.get("message", node.name)
            self._log(f"Notify: {msg}", node=node, status="done")
            return True
        elif node.node_type == "activity":
            summary = cfg.get("summary", node.name)
            try:
                if hasattr(record, "activity_ids"):
                    record.activity_schedule("mail.mail_activity_data_todo", summary=summary)
            except Exception:
                pass
            self._log(f"Activity {summary}", node=node, status="done")
            return True
        elif node.node_type == "delay":
            mins = int(cfg.get("minutes", 0) or cfg.get("delay_minutes", 0))
            self._log(f"Delay {mins}m", node=node, status="waiting_delay")
            # In real, set scheduled time; for Phase4 just mark waiting
            return "waiting_delay"
        elif node.node_type in ("webhook", "api"):
            url = cfg.get("url", "")
            self._log(f"Webhook {url} (stub)", node=node, status="done")
            return True
        elif node.node_type == "ai_action":
            self._log(f"AI action {node.name} (stub)", node=node, status="done")
            return True
        else:
            self._log(f"Unhandled node type {node.node_type}", node=node, status="done")
            return True

    def _next_node(self, node, result):
        """Find next node via transitions. Condition eval determines path."""
        workflow = self.workflow_id
        candidates = workflow.transition_ids.filtered(lambda t: t.from_node_id.id == node.id and t.active).sorted("sequence")
        for tr in candidates:
            if not tr.condition or not tr.condition.strip():
                return tr.to_node_id
            ctx = {"result": result, "state": getattr(self.env[self.res_model].browse(self.res_id), "state", None)}
            try:
                if safe_eval(tr.condition, ctx, mode="eval"):
                    return tr.to_node_id
            except Exception as e:
                self._log(f"Transition condition failed: {e}", status="failed")
                continue
        # if only one outgoing, take it (already handled); if condition filtered all, none
        return None

    def _log(self, message, node=None, status="done"):
        self.env["studio.workflow.log"].create({
            "instance_id": self.id,
            "node_id": node.id if node else False,
            "message": message[:2000],
            "status": status,
        })

class StudioWorkflowLog(models.Model):
    _name = "studio.workflow.log"
    _description = "Studio Workflow Log (audit trail)"
    _order = "create_date desc"

    instance_id = fields.Many2one("studio.workflow.instance", required=True, ondelete="cascade", index=True)
    node_id = fields.Many2one("studio.workflow.node", ondelete="set null")
    message = fields.Text(required=True)
    status = fields.Selection([
        ("pending", "Pending"), ("done", "Done"), ("waiting_approval", "Waiting Approval"),
        ("waiting_delay", "Waiting Delay"), ("failed", "Failed")
    ], default="done", index=True)
    create_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
