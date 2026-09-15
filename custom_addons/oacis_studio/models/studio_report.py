# docs/studio_plan.md §8, §17 — Report Studio (Phase 5)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
import logging
import json

_logger = logging.getLogger(__name__)

REPORT_TYPES = [
    ("grade_report", "Grade Report"),
    ("progression_report", "Progression Report"),
    ("student_profile", "Student Profile"),
    ("academic_transcript", "Academic Transcript"),
    ("report_card", "Report Card"),
    ("attendance_report", "Attendance Report"),
    ("fee_statement", "Fee Statement"),
    ("behaviour_report", "Behaviour/Discipline Report"),
    ("assessment_analysis", "Assessment Analysis"),
    ("class_performance", "Class Performance Report"),
    ("teacher_performance", "Teacher Performance Report"),
    ("parent_report", "Parent Report"),
    ("admission_letter", "Admission Letter"),
    ("certificate", "Certificate"),
    ("recommendation_letter", "Recommendation Letter"),
    ("transfer_certificate", "Transfer Certificate"),
    ("invoice_receipt", "Invoice/Receipt"),
    ("school_leaving", "School Leaving Certificate"),
    ("custom_letter", "Custom Letter"),
    ("custom_analytics", "Custom Analytics Report"),
    ("custom_dashboard_pdf", "Dashboard Export (PDF)"),
    ("custom_document", "Completely Custom Document"),
]

class StudioReport(models.Model):
    _name = "studio.report"
    _description = "Studio Report (docs/studio_plan.md §8)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "app_id, report_type, name"

    name = fields.Char(required=True, help="Report title, e.g. Semester Report Card")
    key = fields.Char(required=True, help="Semantic key, e.g. report_card_sem1")
    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    model_id = fields.Many2one("studio.model", help="Subject model (optional, for studio.record workflows)")
    report_type = fields.Selection(REPORT_TYPES, required=True, default="custom_document", tracking=True)
    description = fields.Text()
    dataset_id = fields.Many2one("studio.dataset", string="Dataset (data source)", help="Resolves records, joins, filters, aggregations")
    paperformat_id = fields.Many2one("report.paperformat", string="Paper Format", help="Odoo paperformat (A4, Letter, etc.)")
    layout_json = fields.Json(
        default=lambda self: {
            "header": [{"type": "text", "value": "{{company.name}}", "style": "text-align:center; font-weight:bold;"}],
            "body": [{"type": "field", "path": "record.display_name", "label": "Name"}],
            "footer": [{"type": "page_number"}],
        },
        help="Report layout DSL — see docs/studio_plan.md §8",
    )
    active = fields.Boolean(default=True)
    state = fields.Selection([("draft", "Draft"), ("published", "Published"), ("archived", "Archived")], default="draft", tracking=True)
    ir_report_id = fields.Many2one("ir.actions.report", string="Compiled Report Action", readonly=True, help="Generated qweb-pdf action for download")
    preview_html = fields.Html(compute="_compute_preview_html", store=False, help="Live HTML preview (first record)")
    company_id = fields.Many2one(related="app_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("app_key_uniq", "unique(app_id, key)", "Report key must be unique per app"),
    ]

    def action_preview(self):
        self.ensure_one()
        html = self._render_html(sample_limit=1)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.name, "message": html[:4000], "type": "info"},
        }

    def action_publish(self):
        for rec in self:
            rec._validate_layout()
            # Create ir.actions.report for PDF download (qweb-pdf)
            if not rec.ir_report_id:
                # Use studio_report_template as base QWeb
                vals = {
                    "name": rec.name,
                    "model": rec.dataset_id.source_model if rec.dataset_id else "studio.record",
                    "report_type": "qweb-pdf",
                    "report_name": f"oacis_studio.report_{rec.key}",
                    "paperformat_id": rec.paperformat_id.id if rec.paperformat_id else False,
                    "print_report_name": f"'{rec.key}_%s' % (object.display_name or object.id)",
                }
                # For Phase 5, we create a simple ir.actions.report that points to our controller
                # The actual QWeb template will be dynamically generated via studio.report.renderer
                rec.ir_report_id = self.env["ir.actions.report"].create(vals)
            rec.state = "published"
        return True

    def _validate_layout(self):
        for rec in self:
            layout = rec.layout_json or {}
            if not isinstance(layout, dict):
                raise ValidationError(_("layout_json must be an object with header/body/footer"))
            for section in ("header", "body", "footer"):
                if section in layout and not isinstance(layout[section], list):
                    raise ValidationError(_(f"layout.{section} must be a list"))

    def _compute_preview_html(self):
        for rec in self:
            try:
                rec.preview_html = rec._render_html(sample_limit=1)
            except Exception as e:
                rec.preview_html = f"<p class='text-danger'>Preview error: {e}</p>"

    def _render_html(self, record_ids=None, sample_limit=1):
        """Render HTML for given records (or sample from dataset). Returns full HTML string."""
        self.ensure_one()
        # Resolve dataset: for Phase 5, support studio.record model or oacis.* via dataset
        layout = self.layout_json or {}
        # Try to get sample records
        records = []
        if record_ids:
            if self.dataset_id and self.dataset_id.source_model:
                records = self.env[self.dataset_id.source_model].browse(record_ids)
            elif self.model_id:
                records = self.env["studio.record"].search([("model_id", "=", self.model_id.id), ("id", "in", record_ids)], limit=sample_limit)
            else:
                records = self.env["studio.record"].search([("app_id", "=", self.app_id.id)], limit=sample_limit)
        else:
            # sample from dataset or app
            if self.dataset_id and self.dataset_id.source_model:
                try:
                    records = self.env[self.dataset_id.source_model].search([], limit=sample_limit)
                except Exception:
                    records = []
            elif self.model_id:
                records = self.env["studio.record"].search([("model_id", "=", self.model_id.id)], limit=sample_limit)
            else:
                records = self.env["studio.record"].search([("app_id", "=", self.app_id.id)], limit=sample_limit)
            if not records and sample_limit:
                # fallback: create dummy context
                records = []
        # Build HTML
        parts = []
        parts.append("<div class='studio-report' style='font-family:Arial,sans-serif; font-size:10pt; color:#1e293b;'>")
        # Header
        if layout.get("header"):
            parts.append("<div class='report-header' style='border-bottom:2pt solid #2563eb; padding:8pt 0; margin-bottom:12pt; text-align:center;'>")
            for comp in layout["header"]:
                parts.append(self._render_component(comp, records, is_header=True))
            parts.append("</div>")
        # Body per record
        if not records:
            parts.append("<div class='report-body'>")
            for comp in layout.get("body", []):
                parts.append(self._render_component(comp, None, is_header=False))
            parts.append("</div>")
        else:
            for rec in records:
                parts.append("<div class='report-body' style='page-break-inside:avoid; margin-bottom:20pt;'>")
                for comp in layout.get("body", []):
                    parts.append(self._render_component(comp, rec, is_header=False))
                parts.append("</div>")
                if len(records) > 1:
                    parts.append("<div style='page-break-after:always;'></div>")
        # Footer
        if layout.get("footer"):
            parts.append("<div class='report-footer' style='border-top:1pt solid #cbd5e1; padding:6pt 0; margin-top:12pt; text-align:center; font-size:8pt; color:#64748b;'>")
            for comp in layout["footer"]:
                parts.append(self._render_component(comp, records[:1] if records else None, is_header=False))
            parts.append("</div>")
        parts.append("</div>")
        return "".join(parts)

    def _render_component(self, comp, record, is_header=False):
        ctype = comp.get("type") if isinstance(comp, dict) else "text"
        style = comp.get("style", "")
        if ctype == "text":
            val = comp.get("value", "")
            # simple mustache replace for {{field}} if record provided
            if record and "{{" in val:
                try:
                    # very naive: replace {{record.display_name}} etc.
                    import re
                    def repl(m):
                        path = m.group(1).strip()
                        # path like "record.display_name" or "company.name"
                        if path.startswith("record.") and record:
                            fld = path[7:]
                            if hasattr(record, fld):
                                return str(getattr(record, fld) or "")
                            elif isinstance(getattr(record, "values_json", None), dict):
                                return str((getattr(record, "values_json", {}) or {}).get(fld, ""))
                        if path.startswith("company."):
                            return str(getattr(self.env.company, path[8:], "") or "")
                        return ""
                    val = re.sub(r"\{\{([^}]+)\}\}", repl, val)
                except Exception:
                    pass
            return f"<div style='{style}'>{val}</div>"
        elif ctype == "field":
            path = comp.get("path") or comp.get("name") or ""
            label = comp.get("label", "")
            # path like "record.display_name" or "student.name" or just "name"
            val = ""
            if record:
                # handle studio.record values_json vs regular field
                key = path.split(".")[-1] if "." in path else path
                if hasattr(record, key):
                    try:
                        v = getattr(record, key)
                        if hasattr(v, "display_name"):
                            val = v.display_name
                        else:
                            val = str(v or "")
                    except Exception:
                        val = ""
                elif hasattr(record, "values_json") and isinstance(getattr(record, "values_json", None), dict):
                    val = str((record.values_json or {}).get(key, "") or "")
                else:
                    val = ""
            # handle many2one display
            if label:
                return f"<div style='{style}'><b>{label}:</b> {val}</div>"
            return f"<div style='{style}'>{val}</div>"
        elif ctype == "table":
            cols = comp.get("columns") or comp.get("fields") or []
            source = comp.get("source")
            # For studio, source is dataset key or relation; stub renders header + one row per record field
            html = [f"<table style='width:100%; border-collapse:collapse; {style}' border='1' cellpadding='6'>"]
            if cols:
                html.append("<thead><tr>")
                for col in cols:
                    label = col.get("label") or col.get("field") or col.get("name") or ""
                    html.append(f"<th style='background:#f1f5f9; text-align:left;'>{label}</th>")
                html.append("</tr></thead><tbody>")
                # one row per record or per values
                if record:
                    html.append("<tr>")
                    for col in cols:
                        field = col.get("field") or col.get("name")
                        key = field.split(".")[-1] if "." in field else field
                        v = ""
                        if hasattr(record, key):
                            try:
                                v = str(getattr(record, key) or "")
                            except Exception:
                                pass
                        elif hasattr(record, "values_json"):
                            v = str((record.values_json or {}).get(key, "") or "")
                        html.append(f"<td>{v}</td>")
                    html.append("</tr>")
                html.append("</tbody>")
            html.append("</table>")
            return "".join(html)
        elif ctype == "image":
            # field like "company.logo" or url
            url = comp.get("value") or comp.get("src") or ""
            field = comp.get("field")
            if field and record and hasattr(record, field.split(".")[-1]):
                # rarely used
                pass
            if url:
                return f"<img src='{url}' style='max-height:60px; {style}'/>"
            # company logo fallback
            if comp.get("field") == "company.logo":
                return f"<img t-att-src=\"'data:image/png;base64,%s' % (company.logo or '')\" style='max-height:40px;'/>"
            return f"<div style='{style}'>[Image: {field or url}]</div>"
        elif ctype == "page_number":
            return f"<span style='{style}'>Page <span class='page'/> / <span class='topage'/></span>"
        elif ctype == "page_break":
            return "<div style='page-break-after:always;'></div>"
        elif ctype == "conditional":
            cond = comp.get("condition") or comp.get("if") or "True"
            # evaluate safe_eval with record context
            ctx = {"record": record, "values": getattr(record, "values_json", {}) or {} if record else {}, "state": getattr(record, "state", None) if record else None}
            try:
                show = bool(safe_eval(cond, ctx, mode="eval"))
            except Exception:
                show = True
            if not show:
                return ""
            inner = "".join(self._render_component(c, record) for c in comp.get("children", []))
            return f"<div style='{style}'>{inner}</div>"
        elif ctype == "formula":
            expr = comp.get("expr") or comp.get("formula") or ""
            ctx = {"record": record, "values": getattr(record, "values_json", {}) or {} if record else {}, "state": getattr(record, "state", None) if record else None}
            try:
                val = safe_eval(expr, ctx, mode="eval")
                return f"<div style='{style}'><b>{comp.get('label','')}:</b> {val}</div>"
            except Exception as e:
                return f"<div style='color:red;'>{expr} error: {e}</div>"
        elif ctype == "repeater":
            source = comp.get("source")
            children = comp.get("children", [])
            # stub: repeat children once per record
            inner = "".join(self._render_component(c, record) for c in children)
            return f"<div style='{style}' class='repeater'>{inner}</div>"
        elif ctype == "qr":
            payload = comp.get("payload") or comp.get("value") or "QR"
            return f"<div style='text-align:center; {style}'>[QR: {payload}]</div>"
        elif ctype == "signature":
            who = comp.get("who") or comp.get("label") or "Authorized Signature"
            return f"<div style='text-align:right; margin-top:30pt; {style}'><div style='border-top:1pt solid #000; display:inline-block; padding-top:4pt;'>{who}</div></div>"
        else:
            # generic children
            inner = "".join(self._render_component(c, record) for c in comp.get("children", []))
            return f"<div style='{style}'>{inner or comp.get('value','')}</div>"

    def action_generate_pdf(self):
        self.ensure_one()
        # For Phase 5, generate PDF via qweb-pdf: use _render_html then wkhtmltopdf via ir.actions.report
        html = self._render_html()
        # In real, would call self.env["ir.actions.report"]._run_wkhtmltopdf — stub returns html for preview
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.name, "message": f"PDF generated (stub, {len(html)} bytes HTML). Use Preview for HTML.", "type": "success"},
        }

    def action_duplicate(self):
        self.ensure_one()
        new = self.copy({"name": f"{self.name} (Copy)", "key": f"{self.key}_copy", "state": "draft", "ir_report_id": False})
        return {"type": "ir.actions.act_window", "res_model": "studio.report", "res_id": new.id, "view_mode": "form"}

class StudioReportTemplate(models.Model):
    _name = "studio.report.template"
    _description = "Studio Report Template (marketplace, docs §21)"
    _order = "report_type, name"

    name = fields.Char(required=True)
    report_type = fields.Selection(REPORT_TYPES, required=True)
    description = fields.Text()
    layout_json = fields.Json(required=True)
    preview_image = fields.Binary()
    active = fields.Boolean(default=True)
