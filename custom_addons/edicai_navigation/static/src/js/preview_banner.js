/** @odoo-module **/
import { Component, xml, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";

/** Permanent experimental-layout indicator (Phase 3 req 10). */
class EdicaiNavPreviewBadge extends Component {
    static props = {};
    static template = xml`
        <div t-if="state.on" class="o_edicai_nav_preview_badge"
             style="position:fixed;bottom:4px;left:4px;z-index:1050;
                    background:#714B67;opacity:.72;color:#fff;border-radius:4px;
                    padding:1px 6px;font-size:10px;font-weight:500;
                    letter-spacing:.2px;pointer-events:none;">
            🧪 NAVIGATION PREVIEW (experimental)
        </div>`;
    setup() {
        this.state = useState({ on: false });
        onWillStart(async () => {
            // never let a slow/missing endpoint stall the webclient boot:
            // race the HTTP call against a hard 2-second cut-off — the flag
            // simply stays off when the endpoint is unreachable.
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), 2000);
            try {
                const resp = await fetch("/edicai_navigation/preview_state",
                    { method: "GET", headers: { "Accept": "application/json" },
                      signal: ctrl.signal });
                const data = await resp.json();
                this.state.on = data && data.state === "on";
            } catch {
                this.state.on = false;
            } finally {
                clearTimeout(timer);
            }
        });
    }
}

registry.category("main_components").add(
    "EdicaiNavPreviewBadge", { Component: EdicaiNavPreviewBadge });

