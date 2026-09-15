/** @odoo-module **/
// Forge Studio — Automation Builder (Sprint 11)
// Visual sentence builder: WHEN → IS → THEN
import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const TRIGGER_OPTIONS = [
    { value: "create", label: "Record is created" },
    { value: "write", label: "Record is updated" },
    { value: "create_or_write", label: "Record is created or updated" },
    { value: "unlink", label: "Record is deleted" },
    { value: "cron", label: "On a schedule" },
    { value: "button", label: "Button click" },
];

const CONDITION_FIELDS = [
    { value: "attendance_pct", label: "Attendance Percentage" },
    { value: "fee_balance", label: "Fee Balance" },
    { value: "status", label: "Status" },
    { value: "admission_date", label: "Admission Date" },
    { value: "grade", label: "Grade" },
];

const CONDITION_OPERATORS = [
    { value: "less_than", label: "is less than" },
    { value: "greater_than", label: "is greater than" },
    { value: "equals", label: "equals" },
    { value: "not_equals", label: "does not equal" },
    { value: "contains", label: "contains" },
    { value: "not_contains", label: "does not contain" },
    { value: "is_set", label: "is set" },
    { value: "is_not_set", label: "is not set" },
];

const ACTION_TYPES = [
    { value: "send_notification", label: "Send Notification", icon: "fa-bell" },
    { value: "send_email", label: "Send Email", icon: "fa-envelope" },
    { value: "create_activity", label: "Create Activity", icon: "fa-calendar-check-o" },
    { value: "update_record", label: "Update Record", icon: "fa-refresh" },
    { value: "create_record", label: "Create Record", icon: "fa-plus" },
    { value: "webhook", label: "Webhook", icon: "fa-globe" },
    { value: "generate_report", label: "Generate Report", icon: "fa-file-pdf-o" },
];

const ACTION_RECIPIENTS = [
    { value: "teacher", label: "Teacher" },
    { value: "parent", label: "Parent" },
    { value: "principal", label: "Principal" },
    { value: "admin", label: "Administrator" },
    { value: "student", label: "Student" },
];

export class StudioAutomationBuilder extends Component {
    static template = "oacis_studio.StudioAutomationBuilder";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            automations: [],
            selectedAutomation: null,
            showNewForm: false,
            newAutomation: {
                name: "",
                model: "",
                trigger: "write",
                conditions: [{ field: "attendance_pct", operator: "less_than", value: "75" }],
                actions: [{ type: "send_notification", recipient: "teacher", message: "Attendance is below threshold" }],
            },
        });

        this._loadAutomations();
    }

    async _loadAutomations() {
        try {
            const autos = await this.orm.searchRead(
                "studio.automation",
                [],
                ["name", "trigger_type", "active", "model_id"],
                { limit: 20 }
            );
            this.state.automations = autos;
        } catch (e) { /* ignore */ }
    }

    selectAutomation(auto) {
        this.state.selectedAutomation = auto;
        this.state.showNewForm = false;
    }

    showNew() {
        this.state.showNewForm = true;
        this.state.selectedAutomation = null;
    }

    addCondition() {
        this.state.newAutomation.conditions.push({ field: "status", operator: "equals", value: "" });
    }

    removeCondition(index) {
        this.state.newAutomation.conditions.splice(index, 1);
    }

    addAction() {
        this.state.newAutomation.actions.push({ type: "send_notification", recipient: "teacher", message: "" });
    }

    removeAction(index) {
        this.state.newAutomation.actions.splice(index, 1);
    }

    async saveAutomation() {
        const a = this.state.newAutomation;
        if (!a.name) {
            this.notification.add("Name is required", { type: "warning" });
            return;
        }
        try {
            await this.orm.create("studio.automation", [{
                name: a.name,
                trigger_type: a.trigger,
                condition_json: { conditions: a.conditions },
                action_json: { actions: a.actions },
            }]);
            this.notification.add("Automation created", { type: "success" });
            this.state.showNewForm = false;
            await this._loadAutomations();
        } catch (e) {
            this.notification.add("Failed: " + (e.message || e), { type: "danger" });
        }
    }

    get triggerLabel() {
        return TRIGGER_OPTIONS.find((t) => t.value === this.state.newAutomation.trigger)?.label || "";
    }
}

registry.category("actions").add("studio.automation_builder", StudioAutomationBuilder);
