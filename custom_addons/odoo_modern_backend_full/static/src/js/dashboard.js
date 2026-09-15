/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

class KPI extends Component {
    static template = "odoo_modern_backend.KPI";
    static props = {
        label: { type: String },
        value: { type: String },
        delta: { type: String },
        icon: { type: String },
        trend: { type: String, optional: true },
    };
}

class ProgressCard extends Component {
    static template = "odoo_modern_backend.ProgressCard";
    static props = {
        label: { type: String },
        value: { type: Number },
        meta: { type: String },
        color: { type: String, optional: true },
    };
}

class ActivityCard extends Component {
    static template = "odoo_modern_backend.ActivityCard";
    static props = {
        title: { type: String },
        text: { type: String },
        time: { type: String },
        icon: { type: String },
        type: { type: String, optional: true },
    };
}

class QuickAction extends Component {
    static template = "odoo_modern_backend.QuickAction";
    static props = {
        icon: { type: String },
        label: { type: String },
        action: { type: Function, optional: true },
    };

    onClick() {
        if (this.props.action) {
            this.props.action();
        }
    }
}

export class ModernDashboard extends Component {
    static template = "odoo_modern_backend.ModernDashboard";
    static components = { KPI, ProgressCard, ActivityCard, QuickAction };

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.menuService = useService("menu");

        this.state = useState({
            period: "month", // "today", "week", "month", "year"
            isLoading: false,
        });
    }

    get greeting() {
        const hour = new Date().getHours();
        let timeGreet = "Good evening";
        if (hour < 12) timeGreet = "Good morning";
        else if (hour < 17) timeGreet = "Good afternoon";
        return `${timeGreet}, ${user.name || "User"}`;
    }

    get periods() {
        return [
            { id: "today", label: "Today" },
            { id: "week", label: "This week" },
            { id: "month", label: "This month" },
            { id: "year", label: "This year" },
        ];
    }

    setPeriod(periodId) {
        this.state.period = periodId;
    }

    get kpis() {
        const p = this.state.period;
        if (p === "today") {
            return [
                { label: "Daily Revenue", value: "₹ 84,200", delta: "+12.4%", icon: "fa-line-chart", trend: "up" },
                { label: "New Leads", value: "14", delta: "+4.1%", icon: "fa-bullseye", trend: "up" },
                { label: "Orders Today", value: "62", delta: "+8.9%", icon: "fa-shopping-bag", trend: "up" },
                { label: "Active Users", value: "28", delta: "+2.0%", icon: "fa-users", trend: "up" },
            ];
        } else if (p === "week") {
            return [
                { label: "Weekly Revenue", value: "₹ 5.82L", delta: "+15.8%", icon: "fa-line-chart", trend: "up" },
                { label: "Qualified Leads", value: "48", delta: "+11.2%", icon: "fa-bullseye", trend: "up" },
                { label: "Orders Delivered", value: "418", delta: "+9.5%", icon: "fa-shopping-bag", trend: "up" },
                { label: "Avg Response Time", value: "18 min", delta: "-24.0%", icon: "fa-clock-o", trend: "up" },
            ];
        } else if (p === "year") {
            return [
                { label: "Annual ARR", value: "₹ 2.94 Cr", delta: "+34.2%", icon: "fa-line-chart", trend: "up" },
                { label: "Won Deals", value: "1,240", delta: "+28.6%", icon: "fa-trophy", trend: "up" },
                { label: "Total Invoices", value: "18,920", delta: "+19.4%", icon: "fa-file-text-o", trend: "up" },
                { label: "Customer Retention", value: "96.4%", delta: "+3.2%", icon: "fa-heart", trend: "up" },
            ];
        }
        // default "month"
        return [
            { label: "Monthly Revenue", value: "₹ 24.8L", delta: "+18.4%", icon: "fa-line-chart", trend: "up" },
            { label: "Open Opportunities", value: "128", delta: "+9.2%", icon: "fa-bullseye", trend: "up" },
            { label: "Orders Placed", value: "1,842", delta: "+12.8%", icon: "fa-shopping-bag", trend: "up" },
            { label: "Payment Collection", value: "₹ 18.2L", delta: "+6.4%", icon: "fa-credit-card", trend: "up" },
        ];
    }

    get chartBars() {
        const p = this.state.period;
        if (p === "today") return [20, 35, 45, 60, 50, 75, 80, 65, 90, 85, 95, 70];
        if (p === "week") return [45, 55, 65, 80, 70, 92, 88];
        if (p === "year") return [50, 58, 64, 72, 68, 85, 90, 84, 95, 92, 98, 100];
        return [38, 54, 46, 73, 61, 82, 68, 89, 76, 94, 84, 96];
    }

    get chartLabels() {
        const p = this.state.period;
        if (p === "today") return ["9am", "11am", "1pm", "3pm", "5pm", "7pm"];
        if (p === "week") return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        if (p === "year") return ["Q1", "Q2", "Q3", "Q4"];
        return ["Jan", "Mar", "May", "Jul", "Sep", "Nov"];
    }

    get progress() {
        return [
            { label: "Monthly Target", value: 78, meta: "₹ 19.5L / ₹ 25L achieved" },
            { label: "Milestones Delivered", value: 64, meta: "16 of 25 active tasks" },
            { label: "Support SLA Met", value: 94, meta: "94% within 1 hour target" },
        ];
    }

    get activities() {
        return [
            { title: "Quotation confirmed", text: "Acme Corporation — ₹ 1,45,000", time: "8 min ago", icon: "fa-check", type: "success" },
            { title: "Invoice posted", text: "INV/2026/0418 — Northstar LLC", time: "32 min ago", icon: "fa-file-text-o", type: "primary" },
            { title: "New opportunity", text: "High-priority inquiry from Zenith Inc.", time: "1 hr ago", icon: "fa-bullseye", type: "warning" },
            { title: "Support ticket solved", text: "#4821 SLA resolved in 24m", time: "2 hr ago", icon: "fa-life-ring", type: "info" },
        ];
    }

    async createContact() {
        try {
            await this.actionService.doAction({
                name: "New Contact",
                type: "ir.actions.act_window",
                res_model: "res.partner",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (e) {
            this.notification.add("Could not open contact form: " + e.message, { type: "warning" });
        }
    }

    async createQuotation() {
        try {
            await this.actionService.doAction({
                name: "New Quotation",
                type: "ir.actions.act_window",
                res_model: "sale.order",
                views: [[false, "form"]],
                target: "current",
            });
        } catch (e) {
            // If sale module is not installed, fallback to partner or info
            this.createContact();
        }
    }

    async openSettings() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-customizer"));
    }

    async openSearch() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-command"));
    }
}

registry.category("actions").add("odoo_modern_backend.dashboard", ModernDashboard);

registry.category("components").add("odoo_modern_backend.KPI", KPI);
registry.category("components").add("odoo_modern_backend.ProgressCard", ProgressCard);
registry.category("components").add("odoo_modern_backend.ActivityCard", ActivityCard);
registry.category("components").add("odoo_modern_backend.QuickAction", QuickAction);
