/** @odoo-module **/

import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { computeAppsAndMenuItems } from "@web/webclient/menus/menu_helpers";

/**
 * Edicai sidebar (accordion) — replaces the muk AppsBar entirely so the
 * navigation UI layer owns the chrome without template inheritance.
 *
 * Behavior: apps without first-level children navigate directly; apps with
 * children expand/collapse in place with an animated chevron; expand state
 * is local (never persisted), matched to the approved UX.
 */
export class EdicaiAppsBar extends Component {
    static template = "edicai_nav_ui.EdicaiAppsBar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.action = useService("action");
        this.state = useState({
            apps: [],
            activeAppId: null,
            expandedAppId: null,
            isCollapsed:
                localStorage.getItem("edicai_sidebar_collapsed") === "1",
        });

        onWillStart(async () => {
            await this._loadApps();
        });
        onMounted(() => {
            this.env.bus.addEventListener("MENUS:APP-CHANGED", () => {
                this._loadApps();
            });
        });

        // collapse toggle persisted in localStorage, like the stock behavior
        if (this.state.isCollapsed) {
            document.body.classList.add("e_sidebar_type_small");
        } else {
            document.body.classList.add("e_sidebar_type_large");
        }
    }

    async _loadApps() {
        const menus = this.menuService.getMenuAsTree("root");
        const items = computeAppsAndMenuItems(menus);
        this.state.apps = items.apps;
        const cur = this.menuService.getCurrentApp();
        this.state.activeAppId = cur ? cur.id : null;
    }

    /** toggle collapse/expand of the whole sidebar */
    toggleSidebar() {
        this.state.isCollapsed = !this.state.isCollapsed;
        localStorage.setItem("edicai_sidebar_collapsed",
            this.state.isCollapsed ? "1" : "0");
        document.body.classList.toggle("e_sidebar_type_small",
            this.state.isCollapsed);
        document.body.classList.toggle("e_sidebar_type_large",
            !this.state.isCollapsed);
        window.dispatchEvent(new Event("resize"));
    }

    appHasChildren(app) {
        const menu = this.menuService.getMenu(app.id);
        return Boolean(menu && menu.children && menu.children.length);
    }

    appChildren(app) {
        if (!app.libChildren) {
            const menu = this.menuService.getMenu(app.id);
            app.libChildren = (menu && menu.children
                ? menu.children.map((mid) => this.menuService.getMenu(mid))
                : []);
        }
        return app.libChildren;
    }

    onAppClick(app) {
        if (this.appHasChildren(app)) {
            if (app.id === this.state.activeAppId) {
                // already inside this app: just toggle the accordion
                this.state.expandedAppId =
                    this.state.expandedAppId === app.id ? null : app.id;
                return;
            }
            // entering a section app: expand its children instead of pressing
            // a (section-only) menu with no action
            const menu = this.menuService.getMenu(app.id);
            if (menu && !menu.actionID) {
                this.state.expandedAppId = app.id;
                const first = this.appChildren(app)[0];
                if (first && first.actionID) {
                    this.menuService.selectMenu(first);
                }
                return;
            }
        }
        this.menuService.selectMenu(app);
    }

    onChildClick(child) {
        if (child && child.actionID) {
            this.menuService.selectMenu(child);
            return;
        }
        const grand = child && child.children && child.children.length
            ? this.menuService.getMenu(child.children[0])
            : null;
        if (grand && grand.actionID) {
            this.menuService.selectMenu(grand);
        }
    }
}

// SAFEGUARD: only register the sidebar when its dependencies resolve;
// never let a chrome issue kill the webclient boot.
try {
    registry.category("main_components").add("edicai_nav_ui.EdicaiAppsBar", {
        Component: EdicaiAppsBar,
    });
} catch (err) {
    console.error("edicai_nav_ui sidebar registration failed", err);
}
