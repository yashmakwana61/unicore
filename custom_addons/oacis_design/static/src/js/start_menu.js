/** @odoo-module */

import { Component, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { session } from "@web/session";
import { NavBar } from "@web/webclient/navbar/navbar";

const TOGGLE_EVENT = "OACIS_TOGGLE_START_MENU";
const CLOSE_EVENT = "OACIS_CLOSE_START_MENU";

/**
 * Redesigned Start Menu with Apps grid, Workspace list, context menus,
 * search bar, and fullscreen toggle. Matches the design mockups with a
 * floating panel layout and two main tabs (Apps / Workspace).
 */
export class OacisStartMenu extends Component {
    static template = "oacis_design.StartMenu";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.searchInputRef = useRef("searchInput");

        this.state = useState({
            open: true,
            activeTab: "apps",       // "apps" | "workspace"
            appFilter: "all",     // "pinned" | "all"
            search: "",
            pinned: [...(session.oacis_theme_pinned_apps || [])],
            fullscreen: true,
            // Context menu state
            contextMenu: {
                visible: false,
                x: 0,
                y: 0,
                type: null,         // "app" | "workspace"
                target: null,       // app or workspace item
                targetIndex: -1,    // for workspace items
            },
            // Workspace data
            workspaceItems: [],
            recentMenus: [],
        });

        // Load workspace data from session
        const wsData = session.oacis_workspace_data || {};
        this.state.workspaceItems = wsData.workspace_items || [];
        this.state.recentMenus = wsData.recents || [];

        useBus(this.env.bus, TOGGLE_EVENT, () => {
            this.state.open = !this.state.open;
            this.state.search = "";
            this._closeContextMenu();
        });
        useBus(this.env.bus, CLOSE_EVENT, () => {
            this.state.open = false;
        });

        // Track menu selections for recent history
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            const current = this.menuService.getCurrentApp();
            if (current) {
                this._trackRecentMenu(current.id);
            }
        });

        useExternalListener(document, "keydown", this.onKeyDown);
        useExternalListener(document, "click", this._onGlobalClick);
    }

    // ------------------------------------------------------------------
    // Keyboard
    // ------------------------------------------------------------------

    onKeyDown(ev) {
        if (ev.key === "Escape") {
            if (this.state.contextMenu.visible) {
                this._closeContextMenu();
            } else if (this.state.open) {
                this.state.open = false;
            }
        }
    }

    _onGlobalClick(ev) {
        if (this.state.contextMenu.visible && !ev.target.closest(".o_oacis_ctx_menu")) {
            this._closeContextMenu();
        }
    }

    // ------------------------------------------------------------------
    // Tab and filter switching
    // ------------------------------------------------------------------

    setTab(tab) {
        this.state.activeTab = tab;
        this.state.search = "";
        this._closeContextMenu();
    }

    setAppFilter(filter) {
        this.state.appFilter = filter;
        this._closeContextMenu();
    }

    toggleFullscreen() {
        this.state.fullscreen = !this.state.fullscreen;
    }

    // ------------------------------------------------------------------
    // App accessors
    // ------------------------------------------------------------------

    get allApps() {
        return this.menuService.getApps();
    }

    get apps() {
        return this.allApps;
    }

    get pinnedApps() {
        const query = this.state.search.trim().toLowerCase();
        return this.apps.filter((app) => this.state.pinned.includes(app.id) && (!query || app.name.toLowerCase().includes(query)));
    }

    get unpinnedApps() {
        const query = this.state.search.trim().toLowerCase();
        return this.apps.filter((app) => !this.state.pinned.includes(app.id) && (!query || app.name.toLowerCase().includes(query)));
    }

    get filteredApps() {
        const query = this.state.search.trim().toLowerCase();
        let apps;
        if (this.state.appFilter === "pinned") {
            apps = this.allApps.filter((a) => this.state.pinned.includes(a.id));
        } else {
            apps = [...this.allApps];
        }
        if (query) {
            apps = apps.filter((a) => a.name.toLowerCase().includes(query));
        }
        return apps;
    }

    isPinned(app) {
        return this.state.pinned.includes(app.id);
    }

    get pinnedCount() {
        return this.state.pinned.length;
    }

    // ------------------------------------------------------------------
    // Workspace accessors
    // ------------------------------------------------------------------

    get workspaceGroups() {
        const query = this.state.search.trim().toLowerCase();
        // Group workspace items by category
        const groups = {};
        for (const item of this.state.workspaceItems) {
            const cat = item.category || "General";
            if (!groups[cat]) {
                groups[cat] = { category: cat, items: [] };
            }
            if (!query || item.name.toLowerCase().includes(query) || (item.app_name || "").toLowerCase().includes(query)) {
                groups[cat].items.push(item);
            }
        }

        // Add recents group
        const recents = query
            ? this.state.recentMenus.filter(
                (r) =>
                    r.name.toLowerCase().includes(query) ||
                    (r.app_name || "").toLowerCase().includes(query)
            )
            : this.state.recentMenus;

        const result = [];
        for (const key of Object.keys(groups)) {
            if (groups[key].items.length) {
                result.push(groups[key]);
            }
        }
        if (recents.length) {
            result.push({ category: "Recents", items: recents });
        }
        return result;
    }

    // ------------------------------------------------------------------
    // App actions
    // ------------------------------------------------------------------

    async onAppClick(ev, app) {
        ev.stopPropagation();
        this._closeContextMenu();
        this.state.open = false;
        await this.menuService.selectMenu(app);
        this._trackRecentMenu(app.id);
    }

    onAppContextMenu(ev, app) {
        ev.preventDefault();
        ev.stopPropagation();
        this._showContextMenu(ev, "app", app);
    }

    async togglePin(app) {
        this._closeContextMenu();
        await this.orm.call("res.users", "theme_toggle_pinned_app", [[user.userId], app.id]);
        if (this.isPinned(app)) {
            this.state.pinned = this.state.pinned.filter((id) => id !== app.id);
        } else {
            this.state.pinned = [...this.state.pinned, app.id];
        }
    }

    async setHomeAction(app) {
        this._closeContextMenu();
        if (app.actionID) {
            await this.orm.call("res.users", "theme_set_home_action", [[user.userId], app.actionID]);
            this.notification.add("Home action updated.", { type: "success" });
        }
    }

    openInNewTab(app) {
        this._closeContextMenu();
        if (app.actionID) {
            window.open(`/odoo/action-${app.actionID}`, "_blank");
        }
    }

    // ------------------------------------------------------------------
    // Workspace actions
    // ------------------------------------------------------------------

    async onWorkspaceItemClick(ev, item) {
        ev.stopPropagation();
        this._closeContextMenu();
        if (item.action_id) {
            await this.actionService.doAction(item.action_id, { clearBreadcrumbs: true });
            this.state.open = false;
        } else if (item.id) {
            // It's a menu entry from recents
            const menu = this.menuService.getMenu(item.id);
            if (menu) {
                await this.menuService.selectMenu(menu);
                this.state.open = false;
            }
        }
    }

    onWorkspaceContextMenu(ev, item, index) {
        ev.preventDefault();
        ev.stopPropagation();
        this._showContextMenu(ev, "workspace", item, index);
    }

    async openInMainView(item) {
        this._closeContextMenu();
        if (item.action_id) {
            await this.actionService.doAction(item.action_id, { clearBreadcrumbs: true });
            this.state.open = false;
        } else if (item.id) {
            const menu = this.menuService.getMenu(item.id);
            if (menu) {
                await this.menuService.selectMenu(menu);
                this.state.open = false;
            }
        }
    }

    async openInPopup(item) {
        this._closeContextMenu();
        if (item.action_id) {
            await this.actionService.doAction(item.action_id, { target: "new" });
        }
    }

    copyInfo(item) {
        this._closeContextMenu();
        const text = item.full_name || item.name || "";
        navigator.clipboard.writeText(text).then(() => {
            this.notification.add("Copied to clipboard.", { type: "info" });
        });
    }

    async deleteWorkspaceItem(item, index) {
        // If it's a recent, remove from recents
        if (this.state.contextMenu.type === "workspace" && item.id) {
            this.state.recentMenus = this.state.recentMenus.filter((r) => r.id !== item.id);
        }
        // If it's a workspace item with a stored index, delete from backend
        if (typeof index === "number" && index >= 0) {
            await this.orm.call("res.users", "theme_delete_workspace_item", [[user.userId], index]);
            this.state.workspaceItems = this.state.workspaceItems.filter((_, i) => i !== index);
        }
        this._closeContextMenu();
    }

    // ------------------------------------------------------------------
    // Context menu
    // ------------------------------------------------------------------

    _showContextMenu(ev, type, target, targetIndex = -1) {
        // Compute position within the start menu panel
        const rect = ev.currentTarget?.closest?.(".o_oacis_start_panel")?.getBoundingClientRect();
        const x = rect ? ev.clientX - rect.left : ev.clientX;
        const y = rect ? ev.clientY - rect.top : ev.clientY;
        this.state.contextMenu = {
            visible: true,
            x: ev.clientX,
            y: ev.clientY,
            type,
            target,
            targetIndex,
        };
    }

    _closeContextMenu() {
        this.state.contextMenu = {
            visible: false,
            x: 0,
            y: 0,
            type: null,
            target: null,
            targetIndex: -1,
        };
    }

    onContextMenuAction(ev, action) {
        ev.stopPropagation();
        const { type, target, targetIndex } = this.state.contextMenu;
        if (type === "app") {
            switch (action) {
                case "new_tab":
                    this.openInNewTab(target);
                    break;
                case "toggle_pin":
                    this.togglePin(target);
                    break;
                case "home_action":
                    this.setHomeAction(target);
                    break;
            }
        } else if (type === "workspace") {
            switch (action) {
                case "open_main":
                    this.openInMainView(target);
                    break;
                case "open_popup":
                    this.openInPopup(target);
                    break;
                case "copy_info":
                    this.copyInfo(target);
                    break;
                case "delete":
                    this.deleteWorkspaceItem(target, targetIndex);
                    break;
            }
        }
    }

    // ------------------------------------------------------------------
    // Search
    // ------------------------------------------------------------------

    onSearchInput(ev) {
        this.state.search = ev.target.value;
    }

    clearSearch() {
        this.state.search = "";
    }

    // ------------------------------------------------------------------
    // Close
    // ------------------------------------------------------------------

    close(ev) {
        if (!ev || ev.target === ev.currentTarget) {
            this.state.open = false;
            this._closeContextMenu();
        }
    }

    closePanel(ev) {
        ev.stopPropagation();
        this.state.open = false;
        this._closeContextMenu();
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    async _trackRecentMenu(menuId) {
        try {
            const recents = await this.orm.call("res.users", "theme_add_recent_menu", [
                [user.userId],
                menuId,
            ]);
            // We don't update state here to avoid UI jank; recents refresh on next open.
        } catch {
            // Silently ignore tracking errors
        }
    }

    get contextMenuStyle() {
        const { x, y } = this.state.contextMenu;
        // Ensure the menu doesn't overflow the viewport
        const maxX = window.innerWidth - 220;
        const maxY = window.innerHeight - 200;
        return `left: ${Math.min(x, maxX)}px; top: ${Math.min(y, maxY)}px;`;
    }
}

registry.category("main_components").add("OacisStartMenu", {
    Component: OacisStartMenu,
});

patch(NavBar.prototype, {
    _toggleOacisStartMenu() {
        this.env.bus.trigger(TOGGLE_EVENT);
    },
});
