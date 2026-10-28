# docs/studio_plan.md §10, §17 — Dashboard Builder (Phase 6)
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
import time

_logger = logging.getLogger(__name__)

WIDGET_TYPES = [
    ("kpi", "KPI Card"),
    ("chart_bar", "Bar Chart"),
    ("chart_line", "Line Chart"),
    ("chart_pie", "Pie/Donut Chart"),
    ("chart_donut", "Donut Chart"),
    ("table", "Table"),
    ("pivot", "Pivot"),
    ("gauge", "Gauge"),
    ("ranking", "Ranking"),
    ("progress", "Progress Indicator"),
    ("map", "Map"),
    ("activity", "Activity Widget"),
]

class StudioDashboard(models.Model):
    _name = "studio.dashboard"
    _description = "Studio Dashboard (docs/studio_plan.md §10)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "app_id, name"

    name = fields.Char(required=True, help="Dashboard title, e.g. Admissions Overview")
    key = fields.Char(required=True, help="Semantic key, e.g. dash_admissions")
    app_id = fields.Many2one("studio.app", required=True, ondelete="cascade", index=True)
    description = fields.Text()
    layout_json = fields.Json(default=dict, help="Grid layout {cols:12, rows:[...]} — for future drag-drop")
    widget_ids = fields.One2many("studio.dashboard.widget", "dashboard_id", string="Widgets")
    active = fields.Boolean(default=True)
    state = fields.Selection([("draft", "Draft"), ("published", "Published"), ("archived", "Archived")], default="draft", tracking=True)
    company_id = fields.Many2one(related="app_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("app_key_uniq", "unique(app_id, key)", "Dashboard key must be unique per app"),
    ]

    def action_preview(self):
        self.ensure_one()
        # Return sample data via notification
        sample = self.get_dashboard_data(sample_limit=5)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.name, "message": f"Dashboard has {len(self.widget_ids)} widgets, sample data keys: {list(sample.keys())[:5]}", "type": "info"},
        }

    def action_publish(self):
        for rec in self:
            if not rec.widget_ids:
                raise ValidationError(_("Dashboard must have at least one widget"))
            rec.state = "published"
        return True

    def action_export_pdf(self):
        self.ensure_one()
        # Stub — Phase 6 PDF via wkhtmltopdf off-screen HTML
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.name, "message": f"PDF export stub — {len(self.widget_ids)} widgets, layout {self.layout_json or {}}", "type": "success"},
        }

    @api.model
    def get_dashboard_data(self, dashboard_id=None, sample_limit=100):
        """Fetch data for all widgets in dashboard. Cached 5m via ir.cache."""
        dashboard = self
        if dashboard_id:
            dashboard = self.browse(dashboard_id)
        if not dashboard.exists():
            # if called via model method without record, return empty
            return {}
        # Simple cache via ir.cache? For Phase 6, use in-memory time-based dict (no Redis)
        # For now, no cache — direct fetch
        result = {}
        for w in dashboard.widget_ids:
            try:
                result[w.id] = w.get_widget_data(sample_limit=sample_limit)
            except Exception as e:
                _logger.exception("Widget data failed %s", w.name)
                result[w.id] = {"error": str(e), "name": w.name, "type": w.widget_type}
        return result

    def get_widget_data(self, widget_id, sample_limit=100):
        w = self.env["studio.dashboard.widget"].browse(widget_id)
        if not w.exists():
            raise ValidationError(_("Widget not found"))
        return w.get_widget_data(sample_limit=sample_limit)


class StudioDashboardWidget(models.Model):
    _name = "studio.dashboard.widget"
    _description = "Studio Dashboard Widget"
    _order = "dashboard_id, sequence"

    dashboard_id = fields.Many2one("studio.dashboard", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True, help="Widget title, e.g. Total Students")
    widget_type = fields.Selection(WIDGET_TYPES, required=True, default="kpi")
    dataset_id = fields.Many2one("studio.dataset", string="Dataset (data source)")
    config_json = fields.Json(default=dict, help="Widget-specific config: {metrics:[], group_by:[], filters:[], visual:{}}")
    sequence = fields.Integer(default=10)
    # Layout for grid (12-col)
    col_span = fields.Integer(default=4, help="Grid width 1-12")
    row_span = fields.Integer(default=2, help="Grid height in rows")
    active = fields.Boolean(default=True)

    def get_widget_data(self, sample_limit=100):
        self.ensure_one()
        start = time.time()
        dataset = self.dataset_id
        # If no dataset, try to infer from dashboard app's first model
        if not dataset:
            # fallback: count studio.records for dashboard app
            count = self.env["studio.record"].search_count([("app_id", "=", self.dashboard_id.app_id.id)])
            return {
                "type": self.widget_type,
                "name": self.name,
                "data": {"count": count},
                "config": self.config_json or {},
                "elapsed_ms": int((time.time() - start) * 1000),
            }
        source_model = dataset.source_model
        if not source_model:
            return {"error": "No source_model", "name": self.name}
        try:
            Model = self.env[source_model]
        except Exception as e:
            return {"error": f"Model not found {source_model}: {e}", "name": self.name}
        # Build domain from dataset.domain_json + widget filters
        domain = list(dataset.domain_json or [])
        # Add widget-specific filters if any
        extra_filters = (self.config_json or {}).get("filters") or []
        if extra_filters:
            domain.extend(extra_filters)
        # Metrics: for KPI, count; for chart/table, read_group
        wtype = self.widget_type
        config = self.config_json or {}
        try:
            if wtype == "kpi":
                # Simple count or sum
                metric = config.get("metric") or "count"
                if metric == "count":
                    count = Model.search_count(domain)
                    return {"type": "kpi", "name": self.name, "data": {"value": count, "metric": "count"}, "domain": domain}
                else:
                    # sum of field, e.g. "amount" — Odoo 19 uses _read_group
                    field = config.get("field") or metric
                    try:
                        # Try new _read_group API
                        gb = Model._read_group(domain, aggregates=[f"{field}:sum"], groupby=[])
                        val = gb[0][field] if gb and len(gb[0]) > 0 else 0
                    except Exception:
                        # Fallback to old read_group for backward compat
                        group_data = Model.read_group(domain, [f"{field}:sum"], [])
                        val = group_data[0].get(f"{field}", 0) if group_data else 0
                    return {"type": "kpi", "name": self.name, "data": {"value": val or 0, "metric": metric, "field": field}}
            elif wtype in ("chart_bar", "chart_line", "chart_pie", "chart_donut", "chart_bar", "pivot", "table", "ranking"):
                group_by = config.get("group_by") or dataset.group_by or []
                if isinstance(group_by, str):
                    group_by = [group_by]
                if not group_by:
                    count = Model.search_count(domain)
                    return {"type": wtype, "name": self.name, "data": {"count": count}, "group_by": group_by}
                fields_to_group = group_by
                aggregations = dataset.aggregations or {}
                # Odoo 19: use _read_group with groupby and aggregates
                try:
                    gb_data_raw = Model._read_group(domain, aggregates=["__count"], groupby=fields_to_group)
                    # Convert _read_group result (list of tuples) to dict format for frontend
                    # _read_group returns [(group_value, count), ...] where group_value may be tuple
                    gb_data = []
                    for row in gb_data_raw:
                        # row is like ((program_id, count), ...) — handle varying
                        if len(row) == 2 and isinstance(row[0], tuple):
                            # grouped value and count
                            gval, cnt = row
                            gb_data.append({fields_to_group[0]: gval, "__count": cnt})
                        else:
                            # fallback: try to parse
                            gb_data.append({fields_to_group[0]: row[0] if row else None, "__count": row[1] if len(row) > 1 else 0})
                except Exception:
                    # Fallback to old read_group
                    gb_data = Model.read_group(domain, ["__count"], fields_to_group, lazy=False)
                # Format for chart: labels and values
                labels = [g.get(fields_to_group[0]) for g in gb_data]
                # labels may be many2one tuples (id, name)
                labels = [l[1] if isinstance(l, (list, tuple)) and len(l) == 2 else str(l) for l in labels]
                values = [g.get("__count", 0) for g in gb_data]
                return {
                    "type": wtype,
                    "name": self.name,
                    "data": {"labels": labels, "values": values, "raw": gb_data},
                    "group_by": group_by,
                    "domain": domain,
                    "elapsed_ms": int((time.time() - start) * 1000),
                }
            elif wtype in ("gauge", "progress"):
                # Example: attendance percentage
                # Use dataset aggregations or simple count
                count = Model.search_count(domain)
                total = Model.search_count([])
                pct = (count / total * 100) if total else 0
                return {"type": wtype, "name": self.name, "data": {"value": round(pct, 2), "count": count, "total": total}}
            else:
                # Generic
                count = Model.search_count(domain)
                return {"type": wtype, "name": self.name, "data": {"count": count}}
        except Exception as e:
            _logger.exception("Widget %s failed", self.name)
            return {"error": str(e), "name": self.name, "type": wtype}
