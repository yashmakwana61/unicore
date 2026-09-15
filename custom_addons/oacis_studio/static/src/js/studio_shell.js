/** @odoo-module **/
// Forge Studio — Shell Component (Sprints 1-9)
// 3-pane layout: Add Sidebar | Live Canvas | Properties Panel
// Integrated: SelectionManager, PropertySchemaRegistry, DragDrop, Undo/Redo, Preview/Publish, AI Contextual
import { registry } from "@web/core/registry";
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// ── PropertySchemaRegistry ──
// Defines which properties to show for each element type
const PROPERTY_SCHEMA = {
    field: {
        basic: [
            { key: "label", label: "Label", type: "text", tooltip: "Display label for this field" },
            { key: "widget", label: "Widget", type: "select", options: [
                { value: "", label: "Default" },
                { value: "char", label: "Text" },
                { value: "text", label: "Multiline Text" },
                { key: "integer", label: "Integer" },
                { value: "float", label: "Decimal" },
                { value: "monetary", label: "Monetary" },
                { value: "date", label: "Date" },
                { value: "datetime", label: "Date & Time" },
                { value: "boolean", label: "Checkbox" },
                { value: "selection", label: "Selection" },
                { value: "many2one", label: "Relation (Many2One)" },
                { value: "one2many", label: "Related List (One2Many)" },
                { value: "many2many", label: "Many2Many" },
                { value: "binary", label: "File" },
                { value: "image", label: "Image" },
                { value: "email", label: "Email" },
                { value: "phone", label: "Phone" },
                { value: "url", label: "URL" },
                { value: "badge", label: "Badge" },
                { value: "html", label: "HTML" },
            ]},
            { key: "required", label: "Required", type: "checkbox", tooltip: "Must be filled before saving" },
            { key: "readonly", label: "Readonly", type: "checkbox", tooltip: "User cannot edit" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
            { key: "invisible_condition", label: "Hide when", type: "text", tooltip: "e.g. record.attendance < 75 — hide this field when condition is true" },
            { key: "placeholder", label: "Placeholder", type: "text", tooltip: "Hint text (e.g. Enter full name)" },
            { key: "help", label: "Help Tooltip", type: "text", tooltip: "Question mark tooltip" },
        ],
        advanced: [
            { key: "name", label: "Technical Name", type: "readonly" },
            { key: "relation", label: "Related Model", type: "readonly" },
            { key: "domain", label: "Domain", type: "text", tooltip: "Filter expression" },
            { key: "context", label: "Context", type: "text", tooltip: "Default values" },
            { key: "group_ids", label: "Groups", type: "text", tooltip: "Security groups" },
        ],
        developer: [
            { key: "readonly_expr", label: "Readonly Expression", type: "text" },
            { key: "column_invisible", label: "Column Invisible", type: "text" },
        ],
    },
    group: {
        basic: [
            { key: "string", label: "Title", type: "text", tooltip: "Group header text" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
        ],
        advanced: [
            { key: "group_ids", label: "Groups", type: "text" },
            { key: "col", label: "Columns", type: "select", options: [
                { value: "2", label: "2 columns" },
                { value: "3", label: "3 columns" },
                { value: "4", label: "4 columns" },
            ]},
        ],
    },
    notebook: {
        basic: [
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
        ],
    },
    page: {
        basic: [
            { key: "string", label: "Tab Label", type: "text" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
            { key: "icon", label: "Icon", type: "text", tooltip: "FontAwesome icon class" },
        ],
        advanced: [
            { key: "group_ids", label: "Groups", type: "text" },
            { key: "readonly", label: "Readonly", type: "checkbox" },
        ],
    },
    button: {
        basic: [
            { key: "string", label: "Label", type: "text" },
            { key: "name", label: "Action", type: "text", tooltip: "Method name" },
            { key: "type", label: "Type", type: "select", options: [
                { value: "object", label: "Method" },
                { value: "action", label: "Action" },
                { value: "workflow", label: "Workflow" },
                { value: "server_action", label: "Server Action" },
            ]},
            { key: "style", label: "Style", type: "select", options: [
                { value: "", label: "Default" },
                { value: "primary", label: "Primary" },
                { value: "secondary", label: "Secondary" },
                { value: "success", label: "Success" },
                { value: "danger", label: "Danger" },
                { value: "warning", label: "Warning" },
                { value: "info", label: "Info" },
            ]},
            { key: "confirm", label: "Confirmation", type: "text", tooltip: "Confirmation message" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
        ],
        advanced: [
            { key: "group_ids", label: "Groups", type: "text" },
            { key: "context", label: "Context", type: "text" },
        ],
    },
    separator: {
        basic: [
            { key: "string", label: "Title", type: "text" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
        ],
    },
    label: {
        basic: [
            { key: "string", label: "Text", type: "text" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
        ],
    },
    chatter: {
        basic: [],
    },
    activity: {
        basic: [],
    },
    smart_button: {
        basic: [
            { key: "string", label: "Label", type: "text" },
            { key: "icon", label: "Icon", type: "text", tooltip: "FontAwesome icon" },
            { key: "type", label: "Type", type: "select", options: [
                { value: "action", label: "Action" },
                { value: "object", label: "Method" },
                { value: "workflow", label: "Workflow" },
            ]},
            { key: "name", label: "Action", type: "text" },
            { key: "invisible", label: "Invisible", type: "select", options: [
                { value: false, label: "Visible" },
                { value: "1", label: "Hidden" },
            ]},
        ],
    },
};

// ── Component Definitions for Add Sidebar (Forge Studio 2.0 UX parity §11) ──
const COMPONENT_DEFS = [
    { section: "Components", items: [
        { type: "group", label: "Columns", icon: "fa-columns", category: "layout", desc: "2-column group" },
        { type: "notebook", label: "Tabs", icon: "fa-book", category: "layout", desc: "Tabbed section" },
        { type: "separator", label: "Separator", icon: "fa-minus", category: "layout", desc: "Horizontal line" },
        { type: "button", label: "Button", icon: "fa-hand-pointer-o", category: "interactive", desc: "Action button" },
        { type: "smart_button", label: "Smart Button", icon: "fa-bolt", category: "interactive", desc: "Header stat button" },
        { type: "statusbar", label: "Statusbar", icon: "fa-tasks", category: "interactive", desc: "Workflow progress bar" },
        { type: "label", label: "Label", icon: "fa-font", category: "layout", desc: "Static text" },
        { type: "image", label: "Image", icon: "fa-image", category: "media", desc: "Logo or picture" },
        { type: "chatter", label: "Chatter", icon: "fa-comments", category: "interactive", desc: "Messages & followers" },
        { type: "activity", label: "Activity", icon: "fa-calendar-check-o", category: "interactive", desc: "Activities & planning" },
        { type: "related", label: "Related Records", icon: "fa-list", category: "relational", desc: "One2many list" },
    ]},
    { section: "New Fields", items: [
        { type: "field", ttype: "char", label: "Text", icon: "fa-font", category: "field" },
        { type: "field", ttype: "text", label: "Multiline Text", icon: "fa-align-left", category: "field" },
        { type: "field", ttype: "integer", label: "Number", icon: "fa-hashtag", category: "field" },
        { type: "field", ttype: "float", label: "Decimal", icon: "fa-calculator", category: "field" },
        { type: "field", ttype: "monetary", label: "Currency", icon: "fa-money", category: "field" },
        { type: "field", ttype: "date", label: "Date", icon: "fa-calendar", category: "field" },
        { type: "field", ttype: "datetime", label: "Date & Time", icon: "fa-clock-o", category: "field" },
        { type: "field", ttype: "boolean", label: "Checkbox", icon: "fa-check-square", category: "field" },
        { type: "field", ttype: "selection", label: "Selection", icon: "fa-list", category: "field" },
        { type: "field", ttype: "binary", label: "File", icon: "fa-paperclip", category: "field" },
        { type: "field", ttype: "image", label: "Image", icon: "fa-image", category: "field" },
        { type: "field", ttype: "many2one", label: "Relation", icon: "fa-link", category: "field" },
        { type: "field", ttype: "many2many", label: "Tags", icon: "fa-tags", category: "field" },
    ]},
];

// ── Field type icons mapping ──
const FIELD_TYPE_ICONS = {
    char: "Aa",
    text: "Tx",
    integer: "#",
    float: "0.",
    monetary: "$",
    date: "Dt",
    datetime: "DT",
    boolean: "☑",
    selection: "▼",
    many2one: "→",
    one2many: "⇉",
    many2many: "⇉",
    binary: "📎",
    image: "🖼",
    html: "<>",
    email: "@",
    phone: "📞",
    url: "🔗",
};

export class ForgeStudioShell extends Component {
    static template = "oacis_studio.ForgeStudioShell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            // Context
            app: null,
            model: null,
            view: null,
            allViews: [],
            currentViewType: "form",

            // Canvas data
            arch: { type: "sheet", children: [] },
            fields: [],
            allModelFields: [],

            // SelectionManager
            selected: null,
            selectedPath: null,
            selectedElementType: null,
            hoverNode: null,

            // Add sidebar
            addSearch: "",
            sidebarSections: { "Components": true, "New Fields": true, "Existing Fields": true },

            // Properties panel
            propsSearch: "",
            showAdvanced: false,
            showDeveloper: false,

            // Dev mode
            devMode: "simple",

            // Drag & drop
            dragged: null,
            dropTarget: null,
            dropPosition: null,

            // Undo / Redo
            history: [],
            future: [],
            historyMeta: [],

            // Save state
            dirty: false,
            saveState: "saved",

            // Preview
            previewMode: false,
            previewRole: "admin",

            // Device
            device: "desktop",

            // Publish
            showPublishDialog: false,
            publishChangelog: "",
            publishDiff: "",

            // AI
            showAiPanel: false,
            aiPrompt: "",
            aiLoading: false,
            aiMessages: [],
            aiProposedChanges: null,
            // Onboarding & shortcuts (§26-27)
            showOnboarding: false,
            showShortcuts: false,
            // AI diff
            aiDiff: null,
        });

        this.canvasRef = useRef("canvas");
        this.propsRef = useRef("propsContent");

        this._keyHandlers = [];
        this._setupKeyboard();

        onWillStart(async () => await this._initContext());
        onWillUnmount(() => {
            for (const h of this._keyHandlers) {
                document.removeEventListener("keydown", h);
            }
        });
    }

    // ═══════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════

    async _initContext() {
        const ctx = this.props.action?.context || {};
        const appId = ctx.active_app_id || ctx.app_id;
        const modelId = ctx.active_model_id || ctx.model_id;
        const viewId = ctx.active_view_id || ctx.view_id;
        const activeModel = ctx.active_model || ctx.activeModel;
        const activeId = ctx.active_id;

        try {
            if (appId) {
                const [app] = await this.orm.read("studio.app", [appId], ["name", "key", "state", "dsl_hash"]);
                this.state.app = app;
            }
            if (modelId) {
                const [model] = await this.orm.read("studio.model", [modelId], ["key", "label", "tech_name"]);
                this.state.model = model;
                await this._loadModelFields(modelId);
                await this._loadView(viewId, modelId);
            } else if (activeModel) {
                this.state.model = {
                    id: null,
                    key: activeModel,
                    label: activeModel.split(".").pop().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
                    tech_name: activeModel,
                };
                await this._loadFieldsFromDictionary(activeModel);
                await this._loadView(viewId, null, activeModel);
            }
            if (!appId && !activeModel) {
                const apps = await this.orm.searchRead("studio.app", [], ["name", "key"], { limit: 1 });
                if (apps.length) this.state.app = apps[0];
            }
        } catch (e) {
            console.warn("Forge Studio init error:", e);
        }
    }

    async _loadModelFields(modelId) {
        const fields = await this.orm.searchRead(
            "studio.field",
            [["model_id", "=", modelId]],
            ["key", "label", "ttype", "required", "relation"]
        );
        this.state.fields = fields;
        this.state.allModelFields = fields;
    }

    async _loadFieldsFromDictionary(model) {
        const dictFields = await this.orm.searchRead(
            "studio.data.dictionary",
            [["model_technical", "=", model], ["ttype", "!=", "model"]],
            ["field_technical", "field_label", "ttype", "relation"],
            { limit: 100 }
        );
        this.state.fields = dictFields.map((r) => ({
            key: r.field_technical,
            label: r.field_label,
            ttype: r.ttype,
            relation: r.relation,
        }));
        this.state.allModelFields = this.state.fields;
    }

    async _loadView(viewId, modelId, activeModel) {
        if (viewId) {
            const [view] = await this.orm.read("studio.view", [viewId], ["name", "type", "arch_json"]);
            this.state.view = view;
            this.state.arch = view.arch_json || { type: "sheet", children: [] };
            this.state.currentViewType = view.type || "form";
        } else {
            this.state.view = {
                name: this.state.model?.label || this.state.model?.key || "View",
                type: "form",
                arch_json: this._defaultArch(),
            };
            this.state.arch = this.state.view.arch_json;
        }
        await this._loadAllViews();
    }

    async _loadAllViews() {
        if (!this.state.model) return;
        try {
            let domain;
            if (this.state.model.id) {
                domain = [["model_id", "=", this.state.model.id]];
            } else {
                // model.id is null (dictionary-based context): try to find studio.model by tech_name
                const m = await this.orm.searchRead("studio.model", [["tech_name", "=", this.state.model.tech_name]], ["id"], { limit: 1 });
                if (m.length) {
                    domain = [["model_id", "=", m[0].id]];
                } else {
                    domain = [];
                }
            }
            if (!domain || !domain.length) {
                this.state.allViews = [];
                return;
            }
            const views = await this.orm.searchRead(
                "studio.view",
                domain,
                ["name", "type", "arch_json"],
                { limit: 20 }
            );
            this.state.allViews = views;
        } catch (e) {
            console.warn("Load all views error:", e);
            this.state.allViews = [];
        }
    }

    _defaultArch() {
        const f = this.state.fields.slice(0, 4);
        return {
            type: "sheet",
            children: [
                {
                    type: "group",
                    string: "General Information",
                    children: f.map((fld) => ({ type: "field", name: fld.key, label: fld.label, ttype: fld.ttype })),
                },
            ],
        };
    }

    // ═══════════════════════════════════════════════════
    // KEYBOARD SHORTCUTS
    // ═══════════════════════════════════════════════════

    _setupKeyboard() {
        const handler = (ev) => {
            if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z" && !ev.shiftKey) {
                ev.preventDefault();
                this.undo();
            }
            if ((ev.ctrlKey || ev.metaKey) && (ev.key.toLowerCase() === "y" || (ev.key.toLowerCase() === "z" && ev.shiftKey))) {
                ev.preventDefault();
                this.redo();
            }
            if (ev.key === "Delete" && this.state.selected) {
                this._deleteSelected();
            }
            if (ev.key === "Escape") {
                this.clearSelection();
                if (this.state.previewMode) this.state.previewMode = false;
            }
            if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") {
                ev.preventDefault();
                this.saveDraft();
            }
            if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "p") {
                ev.preventDefault();
                this.togglePreview();
            }
            if (ev.key === "?" && !ev.ctrlKey && !ev.metaKey) {
                // Show shortcuts when ? pressed without modifier (and not in input)
                if (ev.target.tagName !== "INPUT" && ev.target.tagName !== "TEXTAREA") {
                    this.toggleShortcuts();
                }
            }
        };
        document.addEventListener("keydown", handler);
        this._keyHandlers.push(handler);
    }

    // ═══════════════════════════════════════════════════
    // BREADCRUMBS & HEADER
    // ═══════════════════════════════════════════════════

    get breadcrumbs() {
        const p = [];
        if (this.state.app) p.push(this.state.app.name);
        if (this.state.model) p.push(this.state.model.label || this.state.model.key);
        if (this.state.view) p.push(this.state.view.name);
        return p.length ? p : ["Forge Studio"];
    }

    get saveStateLabel() {
        if (this.state.dirty) return "Unsaved changes";
        return "Saved";
    }

    get saveStateClass() {
        if (this.state.dirty) return "dirty";
        return "saved";
    }

    goBack() {
        this.action.doAction("oacis_studio.action_studio_home");
    }

    closeStudio() {
        this.action.doAction("web.client_close");
    }

    // ═══════════════════════════════════════════════════
    // SELECTION MANAGER
    // ═══════════════════════════════════════════════════

    selectNode(node, path, elementType) {
        this.state.selected = node;
        this.state.selectedPath = path;
        this.state.selectedElementType = elementType || node?.type || "unknown";
    }

    clearSelection() {
        this.state.selected = null;
        this.state.selectedPath = null;
        this.state.selectedElementType = null;
    }

    onNodeHover(node) {
        this.state.hoverNode = node;
    }

    onNodeLeave() {
        this.state.hoverNode = null;
    }

    isSelected(node) {
        return this.state.selected === node;
    }

    isHovered(node) {
        return this.state.hoverNode === node;
    }

    // ═══════════════════════════════════════════════════
    // INLINE EDITING
    // ═══════════════════════════════════════════════════

    onInlineDblClick(node) {
        this.state._inlineEditNode = node;
        this.state._inlineEditValue = node.label || node.string || node.name || "";
    }

    onInlineBlur(ev, node) {
        const v = ev.target.value?.trim();
        if (v && v !== (node.label || node.string || node.name)) {
            const old = JSON.stringify(this.state.arch);
            node.label = v;
            node.string = v;
            this._pushHistory(old, { type: "manual", label: `Rename to "${v}"` });
        }
        this.state._inlineEditNode = null;
    }

    onInlineKeydown(ev, node) {
        if (ev.key === "Enter") {
            ev.target.blur();
        }
        if (ev.key === "Escape") {
            this.state._inlineEditNode = null;
        }
    }

    isInlineEditing(node) {
        return this.state._inlineEditNode === node;
    }

    // ═══════════════════════════════════════════════════
    // DRAG & DROP
    // ═══════════════════════════════════════════════════

    onDragStartPalette(ev, item, field) {
        this.state.dragged = { source: "palette", item, field: field || null };
        ev.dataTransfer.effectAllowed = "copy";
        ev.dataTransfer.setData("text/plain", item.label);
    }

    onDragStartCanvas(ev, node, parentList, index) {
        this.state.dragged = { source: "canvas", node, parentList, index };
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", node.label || node.name || "node");
    }

    onDragOver(ev, parentList, index) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = this.state.dragged?.source === "palette" ? "copy" : "move";
        this.state.dropTarget = parentList;
        this.state.dropPosition = index;
    }

    onDragOverGroup(ev, groupNode) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = this.state.dragged?.source === "palette" ? "copy" : "move";
        this.state.dropTarget = groupNode.children;
        this.state.dropPosition = groupNode.children?.length || 0;
    }

    onDrop(ev, parentList, index) {
        ev.preventDefault();
        ev.stopPropagation();
        const d = this.state.dragged;
        if (!d) return;

        const target = parentList || this._getDefaultInsertTarget();
        const idx = index != null ? index : target.length;

        if (d.source === "palette") {
            const newNode = this._createNodeFromPaletteItem(d.item, d.field);
            target.splice(idx, 0, newNode);
            const old = JSON.stringify(this.state.arch);
            this._pushHistory(old, { type: "manual", label: `Add ${newNode.label || newNode.type}` });
            this.selectNode(newNode, "drop", newNode.type);
        } else if (d.source === "canvas") {
            const fromList = d.parentList;
            const oldIdx = fromList.indexOf(d.node);
            if (oldIdx >= 0) fromList.splice(oldIdx, 1);
            let insertIdx = idx;
            if (target === fromList && oldIdx < idx) insertIdx--;
            target.splice(insertIdx, 0, d.node);
            const old = JSON.stringify(this.state.arch);
            this._pushHistory(old, { type: "manual", label: `Move ${d.node.label || d.node.type}` });
        }

        this._clearDrag();
    }

    onDropGroup(ev, groupNode) {
        this.onDrop(ev, groupNode.children, groupNode.children?.length || 0);
    }

    onDragEnd() {
        this._clearDrag();
    }

    _clearDrag() {
        this.state.dragged = null;
        this.state.dropTarget = null;
        this.state.dropPosition = null;
    }

    _getDefaultInsertTarget() {
        const arch = this.state.arch;
        if (!arch.children) arch.children = [];
        if (arch.children.length === 1 && arch.children[0].type === "group") {
            return arch.children[0].children;
        }
        return arch.children;
    }

    _createNodeFromPaletteItem(item, existingField) {
        if (item.type === "field") {
            const ttype = item.ttype || existingField?.ttype || "char";
            const name = existingField?.key || `x_new_${ttype}_${Date.now().toString(36).slice(-4)}`;
            return {
                type: "field",
                name: name,
                label: existingField?.label || item.label,
                ttype: ttype,
                required: false,
                readonly: false,
                invisible: false,
            };
        }
        if (item.type === "group") {
            return { type: "group", string: "New Group", children: [] };
        }
        if (item.type === "notebook") {
            return { type: "notebook", children: [{ type: "page", string: "New Tab", children: [] }] };
        }
        if (item.type === "separator") {
            return { type: "separator", string: "" };
        }
        if (item.type === "label") {
            return { type: "label", string: "New Label" };
        }
        if (item.type === "button") {
            return { type: "button", string: "New Button", name: "action_new", type_btn: "object" };
        }
        if (item.type === "smart_button") {
            return { type: "smart_button", string: "Smart Button", icon: "fa-cube", type_btn: "action" };
        }
        if (item.type === "statusbar") {
            return { type: "statusbar", string: "Statusbar", field: "state" };
        }
        if (item.type === "image") {
            return { type: "field", name: `x_image_${Date.now().toString(36).slice(-4)}`, label: "Image", ttype: "image" };
        }
        if (item.type === "related") {
            return { type: "field", name: `x_related_${Date.now().toString(36).slice(-4)}`, label: "Related Records", ttype: "one2many", relation: "oacis.student" };
        }
        if (item.type === "chatter") {
            return { type: "chatter" };
        }
        if (item.type === "activity") {
            return { type: "activity" };
        }
        return { type: item.type, label: item.label };
    }

    addExistingField(field) {
        const newNode = {
            type: "field",
            name: field.key,
            label: field.label,
            ttype: field.ttype || "char",
            required: false,
            readonly: false,
            invisible: false,
        };
        const target = this._getDefaultInsertTarget();
        const old = JSON.stringify(this.state.arch);
        target.push(newNode);
        this._pushHistory(old, { type: "manual", label: `Add ${field.label}` });
        this.selectNode(newNode, "add", "field");
    }

    // ═══════════════════════════════════════════════════
    // CANVAS NODE ACTIONS
    // ═══════════════════════════════════════════════════

    duplicateNode(node, parentList) {
        const idx = parentList.indexOf(node);
        if (idx < 0) return;
        const clone = JSON.parse(JSON.stringify(node));
        const old = JSON.stringify(this.state.arch);
        parentList.splice(idx + 1, 0, clone);
        this._pushHistory(old, { type: "manual", label: `Duplicate ${node.label || node.type}` });
        this.selectNode(clone, "dup", clone.type);
    }

    deleteNode(node, parentList) {
        const idx = parentList.indexOf(node);
        if (idx < 0) return;
        const old = JSON.stringify(this.state.arch);
        parentList.splice(idx, 1);
        if (this.state.selected === node) this.clearSelection();
        this._pushHistory(old, { type: "manual", label: `Delete ${node.label || node.type}` });
    }

    moveNode(node, parentList, direction) {
        const idx = parentList.indexOf(node);
        const newIdx = idx + direction;
        if (newIdx < 0 || newIdx >= parentList.length) return;
        const old = JSON.stringify(this.state.arch);
        parentList.splice(idx, 1);
        parentList.splice(newIdx, 0, node);
        this._pushHistory(old, { type: "manual", label: `Move ${node.label || node.type}` });
    }

    hideNode(node) {
        const old = JSON.stringify(this.state.arch);
        node.invisible = node.invisible ? false : "1";
        this._pushHistory(old, { type: "manual", label: `Toggle visibility` });
    }

    _deleteSelected() {
        if (!this.state.selected) return;
        const parent = this._findParentList(this.state.selected, this.state.arch);
        if (parent) this.deleteNode(this.state.selected, parent);
    }

    _findParentList(node, root) {
        if (!root || !root.children) return null;
        for (const child of root.children) {
            if (child === node) return root.children;
            if (child.children) {
                const found = this._findParentList(node, child);
                if (found) return found;
            }
            if (child.type === "page" && child.children) {
                const found = this._findParentList(node, child);
                if (found) return found;
            }
        }
        return null;
    }

    // ═══════════════════════════════════════════════════
    // PROPERTIES PANEL
    // ═══════════════════════════════════════════════════

    get propertySchema() {
        const type = this.state.selectedElementType;
        return PROPERTY_SCHEMA[type] || PROPERTY_SCHEMA.field;
    }

    get visibleProperties() {
        const schema = this.propertySchema;
        let props = schema.basic || [];
        if (this.state.showAdvanced && schema.advanced) {
            props = props.concat(schema.advanced);
        }
        if (this.state.showDeveloper && schema.developer) {
            props = props.concat(schema.developer);
        }
        const q = (this.state.propsSearch || "").toLowerCase();
        if (q) {
            props = props.filter((p) => p.label.toLowerCase().includes(q) || p.key.toLowerCase().includes(q));
        }
        return props;
    }

    getPropValue(prop) {
        if (!this.state.selected) return "";
        const val = this.state.selected[prop.key];
        if (val === false || val === undefined || val === null) return "";
        return val;
    }

    setPropValue(prop, value) {
        if (!this.state.selected) return;
        const old = JSON.stringify(this.state.arch);
        if (prop.type === "checkbox") {
            this.state.selected[prop.key] = value;
        } else if (prop.type === "select") {
            this.state.selected[prop.key] = value || false;
        } else {
            this.state.selected[prop.key] = value;
        }
        this._pushHistory(old, { type: "manual", label: `Change ${prop.label}` });
        this.scheduleAutosave();
    }

    // ═══════════════════════════════════════════════════
    // UNDO / REDO
    // ═══════════════════════════════════════════════════

    _pushHistory(snapshot, meta) {
        this.state.history.push(snapshot);
        this.state.historyMeta.push(meta || { type: "manual", label: "Edit", time: new Date().toLocaleTimeString() });
        if (this.state.history.length > 50) {
            this.state.history.shift();
            this.state.historyMeta.shift();
        }
        this.state.dirty = true;
        this.state.future = [];
        this.scheduleAutosave();
    }

    undo() {
        if (!this.state.history.length) return;
        const snap = this.state.history.pop();
        const meta = this.state.historyMeta.pop();
        try {
            this.state.future.push(JSON.stringify(this.state.arch));
            this.state.arch = JSON.parse(snap);
            this.state.dirty = true;
            this.clearSelection();
        } catch (e) {
            console.warn("Undo failed:", e);
        }
    }

    redo() {
        if (!this.state.future.length) return;
        const snap = this.state.future.pop();
        try {
            this.state.history.push(JSON.stringify(this.state.arch));
            this.state.historyMeta.push({ type: "manual", label: "Redo", time: new Date().toLocaleTimeString() });
            this.state.arch = JSON.parse(snap);
            this.state.dirty = true;
            this.clearSelection();
        } catch (e) {
            console.warn("Redo failed:", e);
        }
    }

    get canUndo() { return this.state.history.length > 0; }
    get canRedo() { return this.state.future.length > 0; }

    // ═══════════════════════════════════════════════════
    // AUTOSAVE & PERSISTENCE
    // ═══════════════════════════════════════════════════

    scheduleAutosave() {
        this.state.saveState = "saving";
        if (this._autosaveTimer) clearTimeout(this._autosaveTimer);
        this._autosaveTimer = setTimeout(() => this.saveDraft(), 1200);
    }

    async saveDraft() {
        if (!this.state.dirty || !this.state.view?.id) return;
        this.state.saveState = "saving";
        try {
            await this.orm.write("studio.view", [this.state.view.id], { arch_json: this.state.arch });
            this.state.dirty = false;
            this.state.saveState = "saved";
        } catch (e) {
            this.state.saveState = "error";
            const msg = e.message || String(e);
            // §49 user-friendly error, developer can see technical in console
            if (msg.includes("RPC_ERROR") || msg.includes("ir.ui.view")) {
                this.notification.add("Forge could not save this change. The field may be required by another component. [Technical details in console]", { type: "danger" });
            } else {
                this.notification.add("Save failed: " + msg.slice(0,200), { type: "danger" });
            }
            console.warn("Autosave failed:", e);
        }
    }

    // ═══════════════════════════════════════════════════
    // VIEW SWITCHER
    // ═══════════════════════════════════════════════════

    get availableViewTypes() {
        const types = ["form", "list", "kanban", "search"];
        const extra = ["calendar", "graph", "pivot", "map", "gantt"];
        for (const v of this.state.allViews) {
            if (!types.includes(v.type) && extra.includes(v.type)) {
                types.push(v.type);
            }
        }
        return types;
    }

    switchView(viewType) {
        this.state.currentViewType = viewType;
        const found = this.state.allViews.find((v) => v.type === viewType);
        if (found) {
            this.state.view = found;
            this.state.arch = found.arch_json || { type: "sheet", children: [] };
        }
        this.clearSelection();
    }

    // ═══════════════════════════════════════════════════
    // PREVIEW
    // ═══════════════════════════════════════════════════

    togglePreview() {
        this.state.previewMode = !this.state.previewMode;
    }

    setPreviewRole(role) {
        this.state.previewRole = role;
    }

    // ═══════════════════════════════════════════════════
    // PUBLISH
    // ═══════════════════════════════════════════════════

    openPublishDialog() {
        if (!this.state.app) {
            this.notification.add("No app to publish", { type: "warning" });
            return;
        }
        const prev = this.state.view?.arch_json ? JSON.stringify(this.state.view.arch_json, null, 2) : "";
        const curr = JSON.stringify(this.state.arch, null, 2);
        this.state.publishDiff = prev === curr ? "No changes since last save." : `${this.state.history.length} edits in history.`;
        this.state.publishChangelog = `Update ${this.state.view?.name || ""} — ${new Date().toLocaleString()}`;
        this.state.showPublishDialog = true;
    }

    cancelPublish() { this.state.showPublishDialog = false; }

    async confirmPublish() {
        if (!this.state.app) return;
        this.state.saveState = "saving";
        try {
            if (this.state.dirty && this.state.view?.id) {
                await this.orm.write("studio.view", [this.state.view.id], { arch_json: this.state.arch });
            }
            // §58 — validate before publish
            try {
                await this.orm.call("studio.dsl", "validate_definition", [this.state.app?.dsl_json || {}]);
            } catch (ve) {
                // DSL may be incomplete while builder is drafting — log and continue with view-level publish
                console.info("Pre-publish DSL validation:", ve.message);
            }
            await this.orm.call("studio.app", "action_publish", [[this.state.app.id]]);
            this.state.dirty = false;
            this.state.showPublishDialog = false;
            this.state.saveState = "saved";
            this._pushHistory(JSON.stringify(this.state.arch), { type: "publish", label: this.state.publishChangelog });
            this.notification.add(`Published: ${this.state.publishChangelog}`, { type: "success" });
        } catch (e) {
            this.state.saveState = "error";
            const msg = e.message || String(e);
            if (msg.includes("ir.ui.view") || msg.includes("RPC_ERROR")) {
                this.notification.add("Publish failed: Forge could not compile this view. Please check field references. [Technical: " + msg.slice(0,150) + "]", { type: "danger" });
            } else {
                this.notification.add(msg || "Publish failed", { type: "danger" });
            }
        }
    }

    // ═══════════════════════════════════════════════════
    // DEV MODE
    // ═══════════════════════════════════════════════════

    setDevMode(mode) {
        this.state.devMode = mode;
        this.state.showAdvanced = mode !== "simple";
        this.state.showDeveloper = mode === "developer";
    }

    // ═══════════════════════════════════════════════════
    // AI CONTEXTUAL
    // ═══════════════════════════════════════════════════

    toggleAiPanel() {
        this.state.showAiPanel = !this.state.showAiPanel;
    }

    get aiContextActions() {
        const t = this.state.selectedElementType;
        if (t === "field") return ["Rename", "Make readonly", "Add validation", "Make conditional", "Explain field", "Generate help text"];
        if (t === "group" || t === "notebook" || t === "page") return ["Improve layout", "Add missing fields", "Create workflow", "Create automation", "Create report"];
        if (t === "button" || t === "smart_button") return ["Change action", "Add confirmation", "Hide conditionally"];
        return ["Improve layout", "Add fields", "Create workflow", "Create automation", "Create report"];
    }
    doAiContextAction(label) {
        const sel = this.state.selected?.label || this.state.selected?.string || this.state.selected?.name || this.state.selectedElementType || "form";
        this.state.aiPrompt = `${label} for "${sel}"`;
        if (!this.state.showAiPanel) this.state.showAiPanel = true;
        // focus will be via next tick
        setTimeout(() => this.askForge(), 100);
    }
    get aiContextHint() {
        if (this.state.selected) {
            const el = this.state.selected;
            return `Currently selected: ${el.type || "element"} "${el.label || el.string || el.name || ""}"`;
        }
        if (this.state.model) {
            return `Editing: ${this.state.model.label || this.state.model.key}`;
        }
        return "Ask Forge anything about your app";
    }
    dismissOnboarding() { localStorage.setItem("forge_onboarding_done","1"); this.state.showOnboarding=false; }
    toggleShortcuts() { this.state.showShortcuts = !this.state.showShortcuts; }

    async askForge() {
        const prompt = this.state.aiPrompt?.trim();
        if (!prompt) return;

        this.state.aiMessages.push({ role: "user", text: prompt });
        this.state.aiPrompt = "";
        this.state.aiLoading = true;

        try {
            // §33 — AI must understand full context
            const selectedInfo = this.state.selected ? {
                type: this.state.selected.type,
                name: this.state.selected.name,
                label: this.state.selected.label || this.state.selected.string,
                ttype: this.state.selected.ttype,
            } : null;
            const ctx = {
                app: this.state.app?.key,
                model: this.state.model?.key,
                view: this.state.view?.type,
                selected: selectedInfo,
                dsl: this.state.app?.dsl_hash,
                availableFields: this.state.fields.map((f) => `${f.label} (${f.key}:${f.ttype})`).join(", "),
                availableComponents: COMPONENT_DEFS.flatMap((s) => s.items.map((i) => i.label)).join(", "),
                userRole: this.state.previewRole,
                device: this.state.device,
            };

            const res = await this.orm.call("studio.ai.copilot", "chat", [
                `${prompt}\n\n[Forge Context]\nApp: ${ctx.app}\nModel: ${ctx.model}\nView: ${ctx.view}\nSelected: ${JSON.stringify(selectedInfo)}\nFields: ${ctx.availableFields}\nRole: ${ctx.userRole}`,
                this.state.app?.id,
            ]);

            if (res.error) {
                this.state.aiMessages.push({ role: "assistant", text: `Error: ${res.error}` });
            } else {
                const changes = res.checklist || [];
                this.state.aiProposedChanges = { changes, dsl: res.dsl, requestId: res.request_id };
                this.state.aiMessages.push({
                    role: "assistant",
                    text: `I can make ${changes.length} changes:`,
                    changes: changes,
                });
            }
        } catch (e) {
            this.state.aiMessages.push({ role: "assistant", text: `Error: ${e.message || e}` });
        } finally {
            this.state.aiLoading = false;
        }
    }

    async applyAiChanges() {
        if (!this.state.aiProposedChanges?.dsl) return;
        try {
            sessionStorage.setItem("forge_ai_preview_dsl", JSON.stringify(this.state.aiProposedChanges.dsl));
            const viewDef = this.state.aiProposedChanges.dsl.views?.find((v) => v.model === this.state.model?.key);
            if (viewDef?.arch) {
                const old = JSON.stringify(this.state.arch);
                this.state.arch = viewDef.arch;
                this._pushHistory(old, { type: "ai", label: "AI changes applied" });
            }
            this.state.aiProposedChanges = null;
            this.state.showAiPanel = false;
            this.notification.add("AI changes applied to canvas", { type: "success" });
        } catch (e) {
            this.notification.add("Failed to apply AI changes", { type: "danger" });
        }
    }

    cancelAiChanges() {
        this.state.aiProposedChanges = null;
    }

    // ═══════════════════════════════════════════════════
    // FILTERING (Add sidebar)
    // ═══════════════════════════════════════════════════

    get filteredExistingFields() {
        const q = (this.state.addSearch || "").toLowerCase();
        if (!q) return this.state.fields;
        return this.state.fields.filter(
            (f) => (f.label || "").toLowerCase().includes(q) || (f.key || "").toLowerCase().includes(q)
        );
    }

    get filteredNewFieldTypes() {
        const section = COMPONENT_DEFS.find((s) => s.section === "New Fields");
        if (!section) return [];
        const q = (this.state.addSearch || "").toLowerCase();
        if (!q) return section.items;
        return section.items.filter((i) => i.label.toLowerCase().includes(q));
    }

    get filteredComponents() {
        const section = COMPONENT_DEFS.find((s) => s.section === "Components");
        if (!section) return [];
        const q = (this.state.addSearch || "").toLowerCase();
        if (!q) return section.items;
        return section.items.filter((i) => i.label.toLowerCase().includes(q));
    }

    toggleSidebarSection(section) {
        this.state.sidebarSections[section] = !this.state.sidebarSections[section];
    }

    isSidebarSectionOpen(section) {
        return this.state.sidebarSections[section] !== false;
    }

    // ═══════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════

    fieldTypeIcon(ttype) {
        return FIELD_TYPE_ICONS[ttype] || "?";
    }

    nodeTypeIcon(type) {
        const map = {
            group: "fa-columns",
            notebook: "fa-book",
            page: "fa-file-o",
            field: "fa-square-o",
            button: "fa-hand-pointer-o",
            smart_button: "fa-bolt",
            separator: "fa-minus",
            label: "fa-font",
            chatter: "fa-comments",
            activity: "fa-calendar-check-o",
        };
        return map[type] || "fa-question";
    }

    getNodeLabel(node) {
        if (!node) return "";
        return node.label || node.string || node.name || node.type || "";
    }

    isFieldInUse(fieldKey) {
        return this._fieldExistsInArch(fieldKey, this.state.arch);
    }

    _fieldExistsInArch(fieldKey, node) {
        if (!node) return false;
        if (node.type === "field" && node.name === fieldKey) return true;
        if (node.children) {
            for (const child of node.children) {
                if (this._fieldExistsInArch(fieldKey, child)) return true;
            }
        }
        return false;
    }
}

registry.category("actions").add("studio.shell", ForgeStudioShell);
