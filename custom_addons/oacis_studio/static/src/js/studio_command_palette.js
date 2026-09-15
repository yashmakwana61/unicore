/** @odoo-module **/
// Sprint 8 — Forge Command Palette (Ctrl+K) — Search Studio: Add field, Create report, Open security, etc. §32
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const COMMANDS = [
    { id: "add_field_text", label: "Add field — Text", action: "add_field", args: { ttype: "char" } },
    { id: "add_field_number", label: "Add field — Number", action: "add_field", args: { ttype: "integer" } },
    { id: "add_field_relation", label: "Add field — Relation (oacis.student)", action: "add_field", args: { ttype: "many2one" } },
    { id: "create_app", label: "Create app — New application", action: "create_app" },
    { id: "create_report", label: "Create report — Report Card", action: "open_report" },
    { id: "create_dashboard", label: "Create dashboard — KPI + Chart", action: "open_dashboard" },
    { id: "create_workflow", label: "Create workflow — Approval", action: "open_workflow" },
    { id: "create_automation", label: "Create automation — Notify on attendance <75%", action: "open_automation" },
    { id: "customize_form", label: "Customize form — Add Tab/Group", action: "customize_form" },
    { id: "preview", label: "Preview — Desktop / Mobile", action: "preview" },
    { id: "publish", label: "Publish — Save and publish", action: "publish" },
    { id: "rollback", label: "Rollback — Restore previous version", action: "rollback" },
    { id: "open_security", label: "Open security — Field Permissions", action: "open_security" },
    { id: "open_dictionary", label: "Open Data Dictionary — oacis.student", action: "open_dictionary" },
    { id: "ask_forge", label: "Ask Forge — Create scholarship system", action: "ask_forge" },
];

export class ForgeCommandPalette extends Component {
    static template = "oacis_studio.ForgeCommandPalette";
    static props = ["*"];
    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ open: false, query: "", filtered: COMMANDS });
        this._onKeydown = this._onKeydown.bind(this);
        onWillStart(() => {
            document.addEventListener("keydown", this._onKeydown);
        });
    }
    _onKeydown(ev) {
        if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
            ev.preventDefault();
            this.state.open = !this.state.open;
            if (this.state.open) this.state.filtered = COMMANDS;
        }
        if (ev.key === "Escape" && this.state.open) this.state.open = false;
    }
    get isOpen() { return this.state.open; }
    onInput(ev) {
        const q = ev.target.value.toLowerCase().trim();
        this.state.query = q;
        if (!q) { this.state.filtered = COMMANDS; return; }
        // Fuzzy scoring: chars of q must appear in order in label
        const score = (label, query) => {
            let li = 0, qi = 0, s = 0;
            label = label.toLowerCase();
            while (li < label.length && qi < query.length) {
                if (label[li] === query[qi]) { s += 2; qi++; } else if (qi > 0) s -= 0.1;
                li++;
            }
            return qi === query.length ? s - (label.length * 0.01) : -1;
        };
        this.state.filtered = COMMANDS.map(c => ({ ...c, _score: score(c.label, q) }))
            .filter(c => c._score >= 0)
            .sort((a, b) => b._score - a._score);
    }
    select(cmd) {
        this.state.open = false;
        this.state.query = "";
        // Map to Studio actions
        const map = {
            create_app: () => this.action.doAction("oacis_studio.action_studio_app"),
            open_report: () => this.action.doAction("oacis_studio.action_studio_report"),
            open_dashboard: () => this.action.doAction("oacis_studio.action_studio_dashboard"),
            open_workflow: () => this.action.doAction("oacis_studio.action_studio_workflow"),
            open_automation: () => this.action.doAction("oacis_studio.action_studio_automation"),
            open_security: () => this.action.doAction("oacis_studio.action_studio_security_rule"),
            open_dictionary: () => this.action.doAction("oacis_studio.action_studio_dd"),
            ask_forge: () => this.action.doAction("oacis_studio.view_studio_ai_copilot"),
            customize_form: () => this.action.doAction("oacis_studio.action_studio_shell"),
            preview: () => this.notification.add("Use Preview button in Studio header", { type: "info" }),
            publish: () => this.notification.add("Use Publish in Studio header", { type: "info" }),
            rollback: () => this.action.doAction("oacis_studio.action_studio_version"),
        };
        const fn = map[cmd.action];
        if (fn) fn();
        else this.notification.add(`Command: ${cmd.label} — add field via Add panel (Ctrl+K → type)`, { type: "info" });
    }
}

registry.category("actions").add("studio.command_palette", ForgeCommandPalette);
console.log("Forge Command Palette — Ctrl+K — Sprint 8 loaded");
