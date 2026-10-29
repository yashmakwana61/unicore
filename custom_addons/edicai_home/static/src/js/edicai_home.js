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
        });
        onWillStart(() => this.loadData());
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
