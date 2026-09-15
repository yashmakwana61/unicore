/** @odoo-module **/
// docs/studio_plan.md §10 — Dashboard Builder OWL (Phase 6)
// Grid 12-col, palette KPI/Chart/Table/Pivot/Gauge/Ranking, dataset binding, live preview, export PDF
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const WIDGET_PALETTE = [
    { type: "kpi", label: "KPI Card", icon: "fa-tachometer" },
    { type: "chart_bar", label: "Bar Chart", icon: "fa-bar-chart" },
    { type: "chart_line", label: "Line Chart", icon: "fa-line-chart" },
    { type: "chart_pie", label: "Pie/Donut", icon: "fa-pie-chart" },
    { type: "table", label: "Table", icon: "fa-table" },
    { type: "pivot", label: "Pivot", icon: "fa-th" },
    { type: "gauge", label: "Gauge", icon: "fa-dashboard" },
    { type: "ranking", label: "Ranking", icon: "fa-trophy" },
    { type: "progress", label: "Progress", icon: "fa-tasks" },
    { type: "activity", label: "Activity", icon: "fa-bell" },
];

export class StudioDashboardBuilder extends Component {
    static template = "oacis_studio.StudioDashboardBuilder";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ palette: WIDGET_PALETTE, layout: { cols: 12, widgets: [] }, preview: {}, loading: false });
        onWillStart(async () => {
            const dashId = this.props.action?.context?.active_id;
            if (dashId) {
                try {
                    const [dash] = await this.orm.read("studio.dashboard", [dashId], ["layout_json", "name"]);
                    if (dash && dash.layout_json) this.state.layout = dash.layout_json;
                    const data = await this.orm.call("studio.dashboard", "get_dashboard_data", [dashId]);
                    this.state.preview = data;
                } catch (e) { console.warn(e); }
            }
        });
    }
    get layoutJson() { try { return JSON.stringify(this.state.layout, null, 2); } catch (e) { return String(this.state.layout); } }
    get previewJson() { try { return JSON.stringify(this.state.preview, null, 2); } catch (e) { return String(this.state.preview); } }
    addWidget(w) {
        this.state.layout.widgets = this.state.layout.widgets || [];
        const span = w.type === "kpi" ? 3 : w.type === "table" ? 12 : 6;
        this.state.layout.widgets.push({ type: w.type, title: w.label, col_span: span, row_span: 2, config: { metric: "count" } });
        this.notification.add(`Added ${w.label} — drag to reorder, resize handles on hover`, { type: "success" });
    }
    moveWidget(idx, dir) {
        const w = this.state.layout.widgets;
        const nIdx = idx + dir;
        if (nIdx <0 || nIdx>=w.length) return;
        const moved = w.splice(idx,1)[0];
        w.splice(nIdx,0,moved);
    }
    resizeWidget(w, delta) {
        w.col_span = Math.max(2, Math.min(12, (w.col_span || 4) + delta));
    }
    async save() {
        const dashId = this.props.action?.context?.active_id;
        if (dashId) {
            await this.orm.write("studio.dashboard", [dashId], { layout_json: this.state.layout });
            this.notification.add("Dashboard layout saved — 12-col grid", { type: "success" });
        } else {
            this.notification.add("Open Dashboard form to save (need dashboard id)", { type: "warning" });
        }
    }
    exportPdf() {
        const dashId = this.props.action?.context?.active_id;
        if (!dashId) { this.notification.add("Open a Dashboard record to export", {type:"warning"}); return; }
        window.open(`/studio/dashboard/${dashId}/pdf`, "_blank");
        this.notification.add("Dashboard PDF — opening preview (print to PDF for download)", {type:"info"});
    }
    async refreshPreview() {
        const dashId = this.props.action?.context?.active_id;
        if (!dashId) return;
        try {
            const data = await this.orm.call("studio.dashboard", "get_dashboard_data", [dashId]);
            this.state.preview = data;
            this.notification.add("Preview refreshed — live read_group data", { type: "info" });
        } catch (e) { this.notification.add("Preview failed: " + (e.message || String(e)), { type: "danger" }); }
    }
}
registry.category("actions").add("studio.dashboard_builder", StudioDashboardBuilder);
console.log("Forge Studio Dashboard Builder — Phase 6 loaded");
