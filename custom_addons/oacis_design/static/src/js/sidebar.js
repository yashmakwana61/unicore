/** @odoo-module */

import { Component, onWillUnmount, useExternalListener, useEffect, useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";
import { user } from "@web/core/user";

const TOGGLE_EVENT = "OACIS_TOGGLE_SIDEBAR";
const START_MENU_TOGGLE_EVENT = "OACIS_TOGGLE_START_MENU";
const MINI_STORAGE_KEY = "oacis_sidebar_mini";

// Deterministic pastel palette for app tiles that have no web icon.
const LETTER_COLORS = [
    "#4c6ef5",
    "#f76707",
    "#12b886",
    "#e64980",
    "#7950f2",
    "#fab005",
    "#339af0",
    "#f03e3e",
    "#20c997",
    "#748ffc",
];

/**
 * Dual-tier navigation sidebar that replaces Odoo's top apps menu.
 *
 * Tier 1 is a vertical icon rail (the apps). Tier 2 is a submenu panel that
 * auto-expands on hover: in standard mode it sits next to the rail, in mini
 * mode it appears as a fly-out. The "App & Menu Finder" input at the top
 * filters the whole menu tree as you type, with no keyboard shortcut needed.
 */
export class OacisSidebar extends Component {
    static template = "oacis_design.Sidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.ui = useState(useService("ui"));
        this._t = _t;
        this.searchInput = useRef("searchInput");
        this.state = useState({
            search: "",
            mini: browser.localStorage.getItem(MINI_STORAGE_KEY) === "1",
            open: false,
            focusSearch: false,
            activeAppId: (this.menuService.getCurrentApp() || {}).id,
        });

        useBus(this.env.bus, TOGGLE_EVENT, () => this.onToggle());
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            const current = this.menuService.getCurrentApp();
            if (current && current.id !== this.state.activeAppId) {
                this.state.activeAppId = current.id;
            }
        });
        useExternalListener(document, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.open) {
                this.state.open = false;
            }
        });

        // Keep the global width variable (drives .o_web_client padding) in sync.
        useEffect(
            () => this._applyRootState(),
            () => [this.state.mini, this.state.open, this.ui.isSmall]
        );

        // Focus the finder once the expanded layout has actually rendered, so
        // the input is visible (and its ref populated) when focus() runs.
        useEffect(
            () => {
                if (this.state.focusSearch) {
                    this.searchInput.el?.focus();
                    this.state.focusSearch = false;
                }
            },
            () => [this.state.focusSearch]
        );
        onWillUnmount(() =>
            document.documentElement.removeAttribute("data-oacis-sidebar")
        );
    }

    // ------------------------------------------------------------------
    // Menu accessors
    // ------------------------------------------------------------------

    get query() {
        return this.state.search.trim().toLowerCase();
    }

    get apps() {
        return this.menuService.getApps();
    }

    /** Primary tier: every app, filtered instantly by the finder input. */
    get visibleApps() {
        if (!this.query) {
            return this.apps;
        }
        return this.apps.filter((app) => this._appMatches(app, this.query));
    }

    get activeApp() {
        if (this.query) {
            return null;
        }
        const app = this.menuService.getMenu(this.state.activeAppId);
        return app || this.apps[0];
    }

    /** Secondary tier: top-level sections (tabs) of the active app. */
    get activeSections() {
        if (!this.activeApp) {
            return [];
        }
        return this.menuService.getMenuAsTree(this.activeApp.id).childrenTree || [];
    }

    /** Flat, app-grouped results for the finder. */
    get searchGroups() {
        const groups = [];
        for (const app of this.apps) {
            if (!this._appMatches(app, this.query)) {
                continue;
            }
            const menus = [];
            this._collectMatches(this.menuService.getMenuAsTree(app.id), this.query, menus);
            if (!menus.length && app.name.toLowerCase().includes(this.query)) {
                menus.push(app);
            }
            if (menus.length) {
                groups.push({ app, menus });
            }
        }
        return groups;
    }

    // ------------------------------------------------------------------
    // Event handlers
    // ------------------------------------------------------------------

    onToggle() {
        if (this.ui.isSmall) {
            this.state.open = !this.state.open;
        } else {
            this.toggleMini();
        }
    }

    toggleMini() {
        this.state.mini = !this.state.mini;
        browser.localStorage.setItem(MINI_STORAGE_KEY, this.state.mini ? "1" : "0");
    }

    closeMobile() {
        if (this.ui.isSmall) {
            this.state.open = false;
        }
    }

    /** Keep the full-screen Start Menu reachable from the sidebar logo. */
    toggleStartMenu() {
        this.env.bus.trigger(START_MENU_TOGGLE_EVENT);
    }

    onAppHover(app) {
        if (!this.query) {
            this.state.activeAppId = app.id;
        }
    }

    async onAppClick(ev, app) {
        ev.stopPropagation();
        this.state.activeAppId = app.id;
        await this.menuService.selectMenu(app);
        this.closeMobile();
    }

    async onMenuClick(ev, menu) {
        ev.stopPropagation();
        this.state.search = "";
        await this._selectMenuFallback(menu);
        this.closeMobile();
    }

    /**
     * Mini mode hides the search input (see sidebar.scss), so its search
     * button expands the sidebar back to the standard layout and focuses the
     * "App & Menu Finder". The actual focus() happens in a useEffect once the
     * expanded layout has rendered.
     */
    toggleFinder() {
        this.state.mini = false;
        browser.localStorage.setItem(MINI_STORAGE_KEY, "0");
        this.state.focusSearch = true;
    }

    /**
     * selectMenu() is a no-op for container menus that carry no action
     * (menu_service.js). Fall back to the first descendant that does have an
     * action, so that every visible submenu entry is clickable.
     */
    async _selectMenuFallback(menu) {
        const target = this._firstActionable(menu);
        if (target) {
            await this.menuService.selectMenu(target);
        }
    }

    _firstActionable(menu) {
        if (menu.actionID) {
            return menu;
        }
        for (const child of menu.childrenTree || []) {
            const found = this._firstActionable(child);
            if (found) {
                return found;
            }
        }
    }

    async onPanelHeaderClick() {
        if (this.activeApp) {
            await this.menuService.selectMenu(this.activeApp);
            this.closeMobile();
        }
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    letterColor(app) {
        let hash = 0;
        for (const ch of app.name) {
            hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
        }
        return LETTER_COLORS[hash % LETTER_COLORS.length];
    }

    isCurrent(menu) {
        const current = this.menuService.getCurrentApp();
        return !!current && menu.id === current.id;
    }

    _appMatches(app, query) {
        if (app.name.toLowerCase().includes(query)) {
            return true;
        }
        return this._treeMatches(this.menuService.getMenuAsTree(app.id), query);
    }

    _treeMatches(menu, query) {
        if (menu.name.toLowerCase().includes(query)) {
            return true;
        }
        return (menu.childrenTree || []).some((child) => this._treeMatches(child, query));
    }

    _collectMatches(menu, query, out) {
        const children = menu.childrenTree || [];
        if (!children.length) {
            if (menu.name.toLowerCase().includes(query)) {
                out.push(menu);
            }
            return;
        }
        for (const child of children) {
            this._collectMatches(child, query, out);
        }
    }

    _applyRootState() {
        const root = document.documentElement;
        if (this.ui.isSmall) {
            if (this.state.open) {
                root.setAttribute("data-oacis-sidebar", "open");
            } else {
                root.removeAttribute("data-oacis-sidebar");
            }
        } else if (this.state.mini) {
            root.setAttribute("data-oacis-sidebar", "mini");
        } else {
            root.removeAttribute("data-oacis-sidebar");
        }
    }
}

registry.category("main_components").add("OacisSidebar", {
    Component: OacisSidebar,
});

// NavBar entry points: the desktop apps-menu button and the mobile burger both
// toggle the sidebar (the burger is patched to open our drawer instead of the
// built-in one).
patch(NavBar.prototype, {
    _toggleOacisSidebar() {
        this.env.bus.trigger(TOGGLE_EVENT);
    },
    _openAppMenuSidebar() {
        this.env.bus.trigger(TOGGLE_EVENT);
    },
    get currentCompany() {
        return user.activeCompany;
    },
});
