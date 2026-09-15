/** @odoo-module **/
// Forge Studio 2.1 — Model Builder Wizard (Phase 10)
// Guided AI wizard: Describe → Forge proposes model/fields/views/workflow/report/dashboard → Preview → Create
import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const FIELD_PRESETS = [
    { key: "name", label: "Name", ttype: "char", required: true },
    { key: "amount", label: "Amount", ttype: "monetary", required: false },
    { key: "start_date", label: "Start Date", ttype: "date", required: false },
    { key: "end_date", label: "End Date", ttype: "date", required: false },
    { key: "status", label: "Status", ttype: "selection", required: true, selection: [["draft","Draft"],["approved","Approved"]] },
    { key: "documents", label: "Documents", ttype: "binary", required: false },
    { key: "student_id", label: "Student", ttype: "many2one", relation: "oacis.student", required: true },
];

export class StudioModelBuilder extends Component {
    static template = "oacis_studio.StudioModelBuilder";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            step: 1,
            appName: "",
            appKey: "",
            prompt: "I want to manage student scholarships with approval workflow",
            loading: false,
            proposal: null, // {app, models, fields, views, workflows, reports, dashboards}
            dsl: null,
            requestId: null,
            error: null,
        });
    }
    get canNext() { return this.state.appName.trim().length > 1 && this.state.appKey.match(/^[a-z][a-z0-9_]*$/); }
    get appKeyHint() { return this.state.appName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24); }
    useHint() { this.state.appKey = this.appKeyHint || this.state.appKey; }
    async generate() {
        if (!this.canNext) { this.notification.add("App name and key (lowercase, underscore) required", {type:"warning"}); return; }
        this.state.loading = true; this.state.error = null;
        try {
            const prompt = `Create application "${this.state.appName}" (${this.state.appKey}): ${this.state.prompt}`;
            const res = await this.orm.call("studio.ai.copilot", "chat", [prompt, null]);
            if (res.error) { this.state.error = res.error; }
            else {
                this.state.proposal = res;
                this.state.dsl = res.dsl;
                this.state.requestId = res.request_id;
                // Fallback proposal if AI returns minimal
                if (!this.state.proposal.checklist) this.state.proposal.checklist = ["App: " + this.state.appName, "Fields: " + FIELD_PRESETS.map(f=>f.label).join(", "), "Views: Form, List, Kanban", "Workflow: Approval", "Report: Scholarship Statement"];
                this.state.step = 2;
            }
        } catch (e) { this.state.error = e.message || String(e); }
        finally { this.state.loading = false; }
    }
    async create() {
        if (!this.state.dsl && !this.state.requestId) {
            // Manual fallback: create app without AI DSL
            try {
                this.state.loading = true;
                const appId = await this.orm.create("studio.app", [{ name: this.state.appName, key: this.state.appKey, category: "education" }]);
                this.notification.add(`App created: ${this.state.appName}`, {type:"success"});
                this.action.doAction("oacis_studio.action_studio_app");
            } catch (e) { this.notification.add("Create failed: " + (e.message||e), {type:"danger"}); }
            finally { this.state.loading = false; }
            return;
        }
        this.state.loading = true;
        try {
            if (this.state.requestId) {
                const res = await this.orm.call("studio.ai.copilot", "publish", [this.state.requestId]);
                if (res.error) throw new Error(res.error);
                this.notification.add(`Published: ${res.app_key || this.state.appKey}`, {type:"success"});
                this.action.doAction("oacis_studio.action_studio_app");
            } else if (this.state.dsl) {
                // Direct DSL publish via validation then app creation
                await this.orm.call("studio.dsl", "validate_definition", [this.state.dsl]);
                this.notification.add("DSL validated — creating app…", {type:"info"});
                // Use import wizard flow: store DSL and create app
                const appId = await this.orm.create("studio.app", [{ name: this.state.appName, key: this.state.appKey, category: "education", dsl_json: this.state.dsl }]);
                this.notification.add(`App ${this.state.appKey} created`, {type:"success"});
                this.action.doAction("oacis_studio.action_studio_app");
            }
        } catch (e) { this.notification.add("Create failed: " + (e.message||String(e)), {type:"danger"}); }
        finally { this.state.loading = false; }
    }
    get previewChecklist() { return this.state.proposal?.checklist || []; }
    get previewDslJson() { try { return JSON.stringify(this.state.dsl, null, 2); } catch(e){return String(this.state.dsl);} }
}
registry.category("actions").add("studio.model_builder", StudioModelBuilder);
