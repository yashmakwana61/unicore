/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AppsBar } from "@muk_web_appsbar/webclient/appsbar/appsbar";
import { useService } from "@web/core/utils/hooks";

/**
 * Accordion on the muk AppsBar sidebar: apps with first-level children gain a
 * rotating chevron and slide-open submenu. Expansion state lives here, never
 * in the parent module, so unloading this module restores stock behavior.
 */
patch(AppsBar.prototype, {
    setup() {
        super.setup();
        this.menuService = useService("menu");
        Object.assign(this.state, { expandedApp: null });
    },

    hasChildren(app) {
        const menu = this.menuService.getMenu(app.id);
        return Boolean(menu && menu.children && menu.children.length);
    },

    appChildren(app) {
        const menu = this.menuService.getMenu(app.id);
        if (!menu) {
            return [];
        }
        return menu.children.map((mid) => this.menuService.getMenu(mid));
    },

    toggleExpanded(app) {
        this.state.expandedApp =
            this.state.expandedApp === app.id ? null : app.id;
    },

    selectChild(child) {
        this.menuService.selectMenu(child);
        this.state.expandedApp = null;
    },
});
