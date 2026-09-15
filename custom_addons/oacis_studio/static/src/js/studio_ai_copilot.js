/** @odoo-module **/
// Forge Studio — AI Copilot (contextual, inline panel)
// Integrates with the shell's built-in AI panel, also works standalone
import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class StudioAICopilot extends Component {
    static template = "oacis_studio.StudioAICopilot";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            prompt: "",
            loading: false,
            result: null,
            error: null,
            checklist: [],
            dsl: null,
            preview: null,
            requestId: null,
            contextModel: null,
        });
        const ctx = this.props.action?.context || {};
        this.state.contextModel = ctx.active_model || ctx.activeModel || null;
        if (this.state.contextModel) {
            this.state.prompt = `For ${this.state.contextModel}, `;
        }
    }

    get isReady() { return this.state.prompt.trim().length > 3; }

    onKeydown(ev) {
        if (ev.key === "Enter") this.askForge();
    }

    async askForge() {
        if (!this.isReady) return;
        this.state.loading = true;
        this.state.error = null;
        this.state.result = null;
        try {
            const ctx = this.props.action?.context || {};
            const appId = ctx.active_app_id || ctx.app_id;
            const res = await this.orm.call("studio.ai.copilot", "chat", [this.state.prompt, appId]);
            if (res.error) {
                this.state.error = res.error;
                this.notification.add(res.error, { type: "danger" });
            } else {
                this.state.result = res;
                this.state.checklist = res.checklist || [];
                this.state.dsl = res.dsl;
                this.state.preview = res.preview;
                this.state.requestId = res.request_id;
                this.notification.add(`Proposal ready — ${this.state.checklist.length} items`, { type: "success" });
            }
        } catch (e) {
            this.state.error = e.message || String(e);
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async applyToPreview() {
        if (!this.state.result || !this.state.dsl) return;
        try {
            sessionStorage.setItem("forge_ai_preview_dsl", JSON.stringify(this.state.dsl));
            this.notification.add("Applied to preview — check Studio shell canvas.", { type: "info" });
        } catch (e) {
            this.notification.add("Preview apply failed: " + (e.message || String(e)), { type: "danger" });
        }
    }

    async publish() {
        if (!this.state.requestId) return;
        this.state.loading = true;
        try {
            const res = await this.orm.call("studio.ai.copilot", "publish", [this.state.requestId]);
            if (res.error) {
                this.notification.add(res.error, { type: "danger" });
            } else {
                this.notification.add(`Published app ${res.app_key}`, { type: "success" });
                this.state.result = null;
                this.state.prompt = "";
            }
        } catch (e) {
            this.notification.add(e.message || String(e), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    goToShell() {
        const ctx = this.props.action?.context || {};
        this.action.doAction("oacis_studio.action_studio_shell", {
            additionalContext: {
                active_app_id: ctx.active_app_id,
                active_model_id: ctx.active_model_id,
                active_view_id: ctx.active_view_id,
                active_model: ctx.active_model,
            },
        });
    }

    get dslJson() {
        try { return JSON.stringify(this.state.dsl, null, 2); } catch (e) { return String(this.state.dsl); }
    }
    get previewJson() {
        try { return JSON.stringify(this.state.preview, null, 2); } catch (e) { return String(this.state.preview); }
    }
}

registry.category("actions").add("studio.ai_copilot", StudioAICopilot);
