/** @odoo-module **/
import { Component, xml, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";

/** Permanent experimental-layout indicator (Phase 3 req 10). */
class EdicaiNavPreviewBadge extends Component {
    static props = {};
    static template = xml`
        <div t-if="state.on" class="o_edicai_nav_preview_badge"
             style="position:fixed;bottom:6px;left:6px;z-index:1050;
                    background:#714B67;color:#fff;border-radius:4px;
                    padding:2px 8px;font-size:11px;font-weight:500;
                    letter-spacing:.3px;pointer-events:none;">
            🧪 NAVIGATION PREVIEW (experimental)
        </div>`;
    setup() {
        this.state = useState({ on: false });
        onWillStart(async () => {
            try {
                const resp = await fetch("/edicai_navigation/preview_state",
                    { method: "GET", headers: { "Accept": "application/json" } });
                const data = await resp.json();
                this.state.on = data && data.state === "on";
            } catch {
                this.state.on = false;
            }
        });
    }
}

registry.category("main_components").add(
    "EdicaiNavPreviewBadge", { Component: EdicaiNavPreviewBadge });
