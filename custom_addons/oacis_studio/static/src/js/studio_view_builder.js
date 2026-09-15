/** @odoo-module **/
// docs/studio_plan.md §5 — View Builder OWL (Phase 3)
// Three-pane: Components | Canvas | Properties, live arch_json → XML preview
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const COMPONENT_PALETTE = {
    form: [
        { type: "sheet", label: "Sheet", icon: "fa-file-o" },
        { type: "group", label: "Group (2-col)", icon: "fa-columns" },
        { type: "field", label: "Field", icon: "fa-tag" },
        { type: "notebook", label: "Notebook", icon: "fa-book" },
        { type: "button", label: "Button", icon: "fa-hand-pointer-o" },
        { type: "header", label: "Header", icon: "fa-header" },
        { type: "chatter", label: "Chatter", icon: "fa-comments" },
        { type: "separator", label: "Separator", icon: "fa-minus" },
    ],
    list: [
        { type: "field", label: "Column", icon: "fa-columns" },
    ],
    kanban: [
        { type: "field", label: "Field", icon: "fa-tag" },
        { type: "kanban_box", label: "Box", icon: "fa-square-o" },
    ],
    search: [
        { type: "field", label: "Search Field", icon: "fa-search" },
        { type: "filter", label: "Filter", icon: "fa-filter" },
    ],
};

export class StudioViewBuilder extends Component {
    static template = "oacis_studio.StudioViewBuilder";
    static props = ["*"];

    get archJsonStr() {
        try {
            return JSON.stringify(this.state.arch, null, 2);
        } catch (e) {
            return String(this.state.arch);
        }
    }

    stringify(value) {
        try {
            return JSON.stringify(value, null, 2);
        } catch (e) {
            return String(value);
        }
    }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            palette: [],
            arch: { type: "sheet", children: [{ type: "group", children: [{ type: "field", name: "name" }] }] },
            xml: "<!-- preview -->",
            modelFields: [],
            selected: null,
        });
        onWillStart(async () => {
            const viewId = this.props.action?.context?.active_id;
            if (viewId) {
                try {
                    const [rec] = await this.orm.read("studio.view", [viewId], ["arch_json", "type", "model_id"]);
                    if (rec) {
                        this.state.arch = rec.arch_json || this.state.arch;
                        this.state.palette = COMPONENT_PALETTE[rec.type] || COMPONENT_PALETTE.form;
                        // load fields for palette
                        if (rec.model_id) {
                            const fields = await this.orm.searchRead("studio.field", [["model_id", "=", rec.model_id[0]]], ["key", "label", "ttype"]);
                            this.state.modelFields = fields;
                        }
                        const xmlRes = await this.orm.call("studio.view", "generate_xml", [[viewId]]);
                        // generate_xml is per-record, use call with ids? fallback client generation
                    }
                } catch (e) { console.warn(e); }
            } else {
                this.state.palette = COMPONENT_PALETTE.form;
            }
        });
    }

    addComponent(comp) {
        if (comp.type === "field") {
            const f = this.state.modelFields[0];
            const name = f ? f.key : "name";
            this.state.arch.children.push({ type: "field", name });
        } else if (comp.type === "group") {
            this.state.arch.children.push({ type: "group", string: "Group", children: [{ type: "field", name: "name" }] });
        } else {
            this.state.arch.children.push({ type: comp.type, string: comp.label });
        }
        this.updateXml();
    }

    async updateXml() {
        // naive client preview — server will re-render on save
        this.state.xml = JSON.stringify(this.state.arch, null, 2);
    }

    async save() {
        const viewId = this.props.action?.context?.active_id;
        if (viewId) {
            await this.orm.write("studio.view", [viewId], { arch_json: this.state.arch });
            this.notification.add("View saved — arch_json updated", { type: "success" });
        } else {
            this.notification.add("No view to save (open from Studio Views list)", { type: "warning" });
        }
    }
}

registry.category("actions").add("studio.view_builder", StudioViewBuilder);
console.log("Forge Studio View Builder — Phase 3 loaded (Components|Canvas|Properties)");
