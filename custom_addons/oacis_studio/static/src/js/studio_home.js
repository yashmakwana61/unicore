/** @odoo-module **/
// Forge Studio 2.0 — Home (docs/studio_plan.md §15, spec §8)
// Ask Forge + Quick Create + Apps + Recent Changes. No longer a metrics dashboard.
import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class StudioHome extends Component {
    static template = "oacis_studio.StudioHome";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            metrics: null,
            error: null,
            askPrompt: "",
            askLoading: false,
        });
        onWillStart(async () => {
            try {
                const res = await this.orm.call("studio.app", "get_home_metrics", []);
                this.state.metrics = res;
            } catch (e) {
                try {
                    const r = await fetch("/studio/metrics", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({jsonrpc:"2.0", method:"call", params:{}}) });
                    const j = await r.json();
                    this.state.metrics = j.result || j;
                } catch (e2) {
                    this.state.error = e.message || String(e);
                }
            } finally {
                this.state.loading = false;
            }
        });
    }

    // ——— Quick Create ———
    createApp() { this.action.doAction("oacis_studio.action_studio_app"); }
    customizeApp() { this.action.doAction("oacis_studio.action_studio_shell"); }
    createReport() { this.action.doAction("oacis_studio.view_studio_report_builder"); }
    createDashboard() { this.action.doAction("oacis_studio.view_studio_dashboard_builder"); }
    createAutomation() { this.action.doAction("oacis_studio.view_studio_automation_builder"); }

    openApps() { this.action.doAction("oacis_studio.action_studio_app"); }
    openImport() { this.action.doAction("oacis_studio.action_studio_import_wizard"); }
    openDictionary() { this.action.doAction("oacis_studio.action_studio_dd"); }

    openApp(app) {
        this.action.doAction("oacis_studio.action_studio_shell", {
            additionalContext: { active_app_id: app.id },
        });
    }

    // ——— Ask Forge ———
    async askForge() {
        const prompt = (this.state.askPrompt || "").trim();
        if (!prompt) {
            this.notification.add("Describe what you want to build", { type: "warning" });
            return;
        }
        this.state.askLoading = true;
        try {
            const res = await this.orm.call("studio.ai.copilot", "chat", [prompt, null]);
            if (res.error) {
                this.notification.add(res.error, { type: "danger" });
            } else {
                // Go to copilot with context, or show preview inline
                this.notification.add(`Forge ready — ${ (res.checklist||[]).length } proposed changes. Opening copilot…`, { type: "success" });
                this.action.doAction("oacis_studio.view_studio_ai_copilot", {
                    additionalContext: { forge_prompt: prompt },
                });
            }
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.askLoading = false;
        }
    }

    onAskKeydown(ev) {
        if (ev.key === "Enter") this.askForge();
    }
}

registry.category("actions").add("studio.home", StudioHome);
