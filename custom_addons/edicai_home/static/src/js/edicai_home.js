/** @odoo-module **/

import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const BADGE_TYPES = ['info', 'warning', 'success', 'danger'];

export class EdicaiHome extends Component {
    static template = "edicai_home.Home";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            tab: sessionStorage.getItem("edicai_home_tab") || "dashboard",
            perWidgetError: {},
            showCustomize: false,
            availableWidgets: [],
            widgetPrefs: null,
        });
        onWillStart(async () => {
            await this.loadData();
            await this.loadWidgetPrefs();
        });
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "edicai.home.data", "get_home_data", [], {});
        } catch (err) {
            this.state.error = (err && err.message) || "Failed to load Home";
            this.notification.add(this.state.error, { type: "danger" });
        }
        this.state.loading = false;
        sessionStorage.setItem("edicai_home_tab", this.state.tab);
    }

    async loadWidgetPrefs() {
        try {
            this.state.availableWidgets = await this.orm.call(
                "edicai.home.data", "get_available_widgets", [], {});
            this.state.widgetPrefs = null;
        } catch (err) {
            console.warn("edicai_home: could not load widget prefs", err);
        }
    }

    toggleCustomize() {
        this.state.showCustomize = !this.state.showCustomize;
    }

    isWidgetEnabled(key) {
        if (!this.state.widgetPrefs) return true;
        return this.state.widgetPrefs.includes(key);
    }

    async toggleWidget(key) {
        const comp = this;
        if (!comp.state.widgetPrefs) {
            comp.state.widgetPrefs = [...comp.state.availableWidgets];
        }
        const idx = comp.state.widgetPrefs.indexOf(key);
        if (idx >= 0) {
            comp.state.widgetPrefs.splice(idx, 1);
        } else {
            comp.state.widgetPrefs.push(key);
        }
    }

    async saveWidgetPrefs() {
        try {
            await this.orm.call("edicai.home.data", "save_widget_prefs",
                [this.state.widgetPrefs || this.state.availableWidgets], {});
            this.state.showCustomize = false;
            await this.loadData();
            this.notification.add("Dashboard preferences saved", { type: "success" });
        } catch (err) {
            this.notification.add("Could not save preferences", { type: "danger" });
        }
    }

    async resetWidgetPrefs() {
        try {
            await this.orm.call("edicai.home.data", "reset_widget_prefs", [], {});
            this.state.widgetPrefs = null;
            this.state.showCustomize = false;
            await this.loadData();
            this.notification.add("Dashboard reset to defaults", { type: "success" });
        } catch (err) {
            this.notification.add("Could not reset preferences", { type: "danger" });
        }
    }

    widgetLabel(key) {
        const labels = {
            'enrollment_overview': 'Enrollment Overview',
            'admissions_pipeline': 'Admissions Pipeline',
            'fee_collection': 'Fee Collection',
            'attendance_overview': 'Attendance Overview',
            'pending_approvals': 'Pending Approvals',
            'overdue_alerts': 'Overdue Alerts',
            'recent_payments': 'Recent Payments',
            'today_classes_faculty': "Today's Classes (Faculty)",
            'assignments_review': 'Assignments to Review',
            'pending_grading': 'Pending Grading',
            'today_classes_student': "Today's Classes (Student)",
            'my_attendance': 'My Attendance',
            'my_assignments': 'My Assignments',
            'my_results': 'My Results',
            'library_overdue': 'Overdue Books',
            'library_activity': 'Library Activity',
            'placement_overview': 'Placement Overview',
            'website_shortcuts': 'Website Shortcuts',
            'institution_notices': 'Announcements',
            'quick_links': 'Quick Links',
            'upcoming_schedule': 'Upcoming Schedule',
        };
        return labels[key] || key;
    }

    selectTab(ev) {
        const tab = ev.currentTarget.dataset.tab;
        this.state.tab = tab;
        sessionStorage.setItem("edicai_home_tab", tab);
    }

    continueSetup() {
        this.state.tab = "getting-started";
        sessionStorage.setItem("edicai_home_tab", "getting-started");
    }

    // ---- record / list navigation (no hardcoded action XML IDs) ------
    openRow(row) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: row.res_model,
                res_id: row.id,
                views: [[false, "form"]],
                target: "current",
            });
        } catch (err) {
            console.warn("edicai_home: cannot open record", err);
        }
    }

    openList(widget) {
        const view = widget.view_all;
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: view.res_model,
                name: view.name || widget.title,
                views: [[false, "list"], [false, "form"]],
                target: "current",
                domain: view.domain || undefined,
            });
        } catch (err) {
            console.warn("edicai_home: cannot open list", err);
        }
    }

    openQuickLink(link) {
        if (link.action_xmlid) {
            this.action.doAction(link.action_xmlid).catch((err) => {
                console.warn("edicai_home: action open failed", err);
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: link.res_model,
            name: link.label,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        }).catch((err) => console.warn("edicai_home: link open failed", err));
    }

    openItemLink(item) {
        if (item.link_action) {
            this.action.doAction(item.link_action)
                .catch((err) => console.warn("edicai_home: link failed", err));
        }
    }

    async setItemState(item, state) {
        try {
            await this.orm.call("edicai.onboarding.state", "set_state",
                [item.id, state], {});
            await this.loadData();
        } catch (err) {
            this.notification.add((err && err.message) || "Could not save progress",
                { type: "danger" });
        }
    }

    badgeClass(badgeType) {
        return "badge badge-pill bg-" + (BADGE_TYPES.includes(badgeType)
            ? badgeType : "secondary");
    }

    widgetsIn(section) {
        return (this.state.data && this.state.data.widgets || [])
            .filter((w) => w.section === section && !w.empty);
    }

    nextOnboardingStep() {
        const ob = this.state.data && this.state.data.onboarding;
        if (!ob || !ob.items) {
            return null;
        }
        const next = ob.items.find((it) => it.state === "todo");
        return next ? next.name : null;
    }

    noticeIcon(type) {
        const icons = {
            general: "fa-bullhorn", academic: "fa-graduation-cap",
            exam: "fa-file-text-o", fee: "fa-money", event: "fa-calendar",
        };
        return icons[type] || "fa-bullhorn";
    }

    updateIcon(type) {
        const icons = {
            new_feature: "fa-star-o", improvement: "fa-arrow-up",
            bugfix: "fa-wrench", service: "fa-info-circle",
        };
        return icons[type] || "fa-info-circle";
    }
}

registry.category("actions").add("edicai_home.home", EdicaiHome);
