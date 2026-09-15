/** @odoo-module **/
// Forge Studio 2.1 — Workflow Builder Visual Canvas (Phase 11)
// Nodes + Connections + Drag/Zoom/Pan/Mini-map + Right properties
import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const NODE_TYPES = [
    { value: "start", label: "Start", icon: "fa-play", color: "#10b981" },
    { value: "approval", label: "Approval", icon: "fa-check-circle", color: "#3b82f6" },
    { value: "condition", label: "Condition", icon: "fa-code-fork", color: "#f59e0b" },
    { value: "action", label: "Action", icon: "fa-cog", color: "#8b5cf6" },
    { value: "notification", label: "Notification", icon: "fa-bell", color: "#ec4899" },
    { value: "end", label: "End", icon: "fa-stop", color: "#ef4444" },
];

export class StudioWorkflowBuilder extends Component {
    static template = "oacis_studio.StudioWorkflowBuilder";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            workflow: null,
            nodes: [],
            transitions: [],
            selectedNode: null,
            selectedTransition: null,
            showNewNode: false,
            newNode: { name: "", node_type: "approval", config_json: { approver: "", message: "" } },
            zoom: 1,
            showConnect: false,
            connectFrom: null,
            connectTo: null,
            draggedNode: null,
            validation: [],
        });
        const ctx = this.props.action?.context || {};
        const wfId = ctx.active_id;
        if (wfId) this._loadWorkflow(wfId);
    }
    async _loadWorkflow(wfId) {
        try {
            const [w] = await this.orm.read("studio.workflow", [wfId], ["name", "trigger_type"]);
            this.state.workflow = w;
            const nodes = await this.orm.searchRead("studio.workflow.node", [["workflow_id", "=", wfId]], ["name", "node_type", "sequence", "config_json"], { order: "sequence asc" });
            this.state.nodes = nodes.map((n, i) => ({ ...n, _x: 240, _y: 40 + i * 110 }));
            const trs = await this.orm.searchRead("studio.workflow.transition", [["workflow_id", "=", wfId]], ["name", "from_node_id", "to_node_id", "condition"]);
            this.state.transitions = trs;
            this._validate();
        } catch (e) { console.warn("Workflow load error:", e); }
    }
    selectNode(node) { this.state.selectedNode = node; this.state.selectedTransition = null; }
    selectTransition(tr) { this.state.selectedTransition = tr; this.state.selectedNode = null; }
    nodeTypeInfo(type) { return NODE_TYPES.find((n) => n.value === type) || NODE_TYPES[1]; }
    // Zoom/Pan
    zoomIn() { this.state.zoom = Math.min(1.5, this.state.zoom + 0.1); }
    zoomOut() { this.state.zoom = Math.max(0.6, this.state.zoom - 0.1); }
    resetZoom() { this.state.zoom = 1; }
    // Drag
    onNodeDragStart(ev, node) { this.state.draggedNode = node; ev.dataTransfer.setData("text/plain", node.name); }
    onNodeDragOver(ev) { ev.preventDefault(); }
    onNodeDrop(ev, target) {
        ev.preventDefault();
        const dragged = this.state.draggedNode; if (!dragged || dragged === target) return;
        const fromIdx = this.state.nodes.indexOf(dragged); const toIdx = this.state.nodes.indexOf(target);
        if (fromIdx < 0 || toIdx < 0) return;
        const arr = this.state.nodes; arr.splice(fromIdx, 1); arr.splice(toIdx, 0, dragged);
        arr.forEach((n, i) => n.sequence = i + 1);
        this.state.draggedNode = null;
        this.notification.add("Reordered — drag to move, sequence updated", {type:"info"});
    }
    onNodeDragEnd() { this.state.draggedNode = null; }
    async addNode() {
        const n = this.state.newNode;
        if (!n.name) { this.notification.add("Name is required", { type: "warning" }); return; }
        try {
            const ctx = this.props.action?.context || {};
            const wfId = ctx.active_id;
            if (!wfId) { this.notification.add("Open a Workflow record first", { type: "warning" }); return; }
            await this.orm.create("studio.workflow.node", [{ workflow_id: wfId, name: n.name, node_type: n.node_type, sequence: this.state.nodes.length + 1, config_json: n.config_json }]);
            this.notification.add("Node added", { type: "success" });
            this.state.showNewNode = false;
            this.state.newNode = { name: "", node_type: "approval", config_json: { approver: "", message: "" } };
            await this._loadWorkflow(wfId);
        } catch (e) { this.notification.add("Failed: " + (e.message || e), { type: "danger" }); }
    }
    async duplicateNode(node) {
        try {
            await this.orm.create("studio.workflow.node", [{ workflow_id: this.props.action?.context?.active_id, name: node.name + " (Copy)", node_type: node.node_type, sequence: this.state.nodes.length + 1, config_json: node.config_json }]);
            await this._loadWorkflow(this.props.action.context.active_id);
            this.notification.add("Duplicated", {type:"success"});
        } catch(e){ this.notification.add(String(e), {type:"danger"}); }
    }
    async deleteNode(node) {
        try {
            await this.orm.unlink("studio.workflow.node", [node.id]);
            const ctx = this.props.action?.context || {};
            if (ctx.active_id) await this._loadWorkflow(ctx.active_id);
            this.state.selectedNode = null;
            this.notification.add("Node deleted", { type: "success" });
        } catch (e) { this.notification.add("Failed: " + (e.message || e), { type: "danger" }); }
    }
    // Connections
    openConnect() { this.state.showConnect = true; this.state.connectFrom = this.state.nodes[0]?.id || null; this.state.connectTo = this.state.nodes[1]?.id || null; }
    async createConnection() {
        if (!this.state.connectFrom || !this.state.connectTo || this.state.connectFrom === this.state.connectTo) { this.notification.add("Select different From/To", {type:"warning"}); return; }
        try {
            const wfId = this.props.action?.context?.active_id;
            await this.orm.create("studio.workflow.transition", [{ workflow_id: wfId, name: `${this.state.connectFrom}→${this.state.connectTo}`, from_node_id: this.state.connectFrom, to_node_id: this.state.connectTo, condition: "" }]);
            this.state.showConnect = false;
            await this._loadWorkflow(wfId);
            this.notification.add("Connection created", {type:"success"});
        } catch(e){ this.notification.add(String(e), {type:"danger"}); }
    }
    async deleteTransition(tr) {
        try { await this.orm.unlink("studio.workflow.transition", [tr.id]); await this._loadWorkflow(this.props.action.context.active_id); this.state.selectedTransition=null; this.notification.add("Connection deleted",{type:"success"});} catch(e){this.notification.add(String(e),{type:"danger"});}
    }
    _validate() {
        const issues = [];
        if (!this.state.nodes.length) issues.push("No nodes");
        else {
            const hasStart = this.state.nodes.some(n=>n.node_type==='start');
            const hasEnd = this.state.nodes.some(n=>n.node_type==='end');
            if (!hasStart) issues.push("Missing Start node");
            if (!hasEnd) issues.push("Missing End node");
            // disconnected nodes: no incoming/outgoing transition
            const connected = new Set();
            for (const t of this.state.transitions) { if (t.from_node_id) connected.add(t.from_node_id[0]); if (t.to_node_id) connected.add(t.to_node_id[0]); }
            for (const n of this.state.nodes) { if (n.node_type!=='start' && n.node_type!=='end' && !connected.has(n.id)) issues.push(`Node "${n.name}" disconnected`); }
        }
        this.state.validation = issues;
    }
    get validationIssues() { return this.state.validation; }
    get zoomPercent() { return Math.round(this.state.zoom * 100) + "%"; }
}
registry.category("actions").add("studio.workflow_builder", StudioWorkflowBuilder);
