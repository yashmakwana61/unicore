/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

/**
 * Top-bar companion button beside the profile cluster:
 *  - Calendar: opens calendar.action_calendar_event (all users)
 * Shown as a transparent line glyph; Calendar leaves the sidebar while the
 * navigation preview is ON (relocated here by design). Settings stays in the
 * sidebar (Administration workspace).
 */
class NavCompanionButton extends Component {
    setup() {
        this.action = useService("action");
        this.state = useState({ ready: false, allowed: false });
    }

    async willStart() {
        this.state.allowed = await this.checkVisible();
        this.state.ready = true;
    }
}

const CAL_ACTION = "calendar.action_calendar_event";

class NavCalendarButton extends NavCompanionButton {
    static template = "edicai_nav_ui.NavCalendarButton";
    async checkVisible() {
        // mentor internal users: same audience as the sidebar app had
        return await user.hasGroup("base.group_user");
    }
    onClick() {
        this.action.doAction(CAL_ACTION, { clearBreadcrumbs: true });
    }
}

registry.category("systray").add("edicai_nav_ui.calendar", {
    Component: NavCalendarButton,
    getProps: () => ({}),
}, { sequence: 5 });
