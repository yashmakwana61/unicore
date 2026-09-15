/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class CommandPalette extends Component {
    static template = "odoo_modern_backend.CommandPalette";

    setup() {
        this.searchInput = useRef("search");
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.theme = useService("modern_theme");

        this.state = useState({
            open: false,
            query: "",
            selectedIndex: 0,
        });

        this.keyHandler = (ev) => {
            if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "k") {
                ev.preventDefault();
                if (this.state.open) {
                    this.close();
                } else {
                    this.open();
                }
            }
            if (this.state.open) {
                if (ev.key === "Escape") {
                    ev.preventDefault();
                    this.close();
                } else if (ev.key === "ArrowDown") {
                    ev.preventDefault();
                    this.moveSelection(1);
                } else if (ev.key === "ArrowUp") {
                    ev.preventDefault();
                    this.moveSelection(-1);
                } else if (ev.key === "Enter") {
                    ev.preventDefault();
                    this.executeSelected();
                }
            }
        };

        this.openHandler = () => this.open();

        onMounted(() => {
            window.addEventListener("keydown", this.keyHandler);
            window.addEventListener("odoo-modern:open-command", this.openHandler);
        });

        onWillUnmount(() => {
            window.removeEventListener("keydown", this.keyHandler);
            window.removeEventListener("odoo-modern:open-command", this.openHandler);
        });
    }

    open() {
        this.state.open = true;
        this.state.query = "";
        this.state.selectedIndex = 0;
        setTimeout(() => this.searchInput.el?.focus(), 50);
    }

    close() {
        this.state.open = false;
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        this.state.selectedIndex = 0;
    }

    get results() {
        const q = (this.state.query || "").trim().toLowerCase();
        const items = [];

        // 1. Built-in Quick Actions
        const quickActions = [
            {
                id: "act-search",
                type: "action",
                category: "Actions",
                icon: "fa-search",
                title: "Global View Search",
                subtitle: "Focus current view search bar",
                badge: "Action",
                handler: () => this.focusSearch(),
            },
            {
                id: "act-dashboard",
                type: "action",
                category: "Actions",
                icon: "fa-dashboard",
                title: "Open Modern Dashboard",
                subtitle: "View SaaS workspace overview & metrics",
                badge: "Workspace",
                handler: () => this.openDashboard(),
            },
            {
                id: "act-customize",
                type: "action",
                category: "Actions",
                icon: "fa-sliders",
                title: "Appearance & Theme Settings",
                subtitle: "Customize accents, dark mode, density and radius",
                badge: "Settings",
                handler: () => this.openCustomizer(),
            },
        ];

        // 2. Theme Quick Switches
        const themeActions = [
            {
                id: "theme-dark",
                type: "theme",
                category: "Appearance",
                icon: "fa-moon-o",
                title: "Theme: Dark Mode",
                subtitle: "Switch workspace to dark slate theme",
                badge: "Theme",
                handler: () => this.theme.set("theme", "dark"),
            },
            {
                id: "theme-light",
                type: "theme",
                category: "Appearance",
                icon: "fa-sun-o",
                title: "Theme: Light Mode",
                subtitle: "Switch workspace to clean light theme",
                badge: "Theme",
                handler: () => this.theme.set("theme", "light"),
            },
            {
                id: "theme-system",
                type: "theme",
                category: "Appearance",
                icon: "fa-desktop",
                title: "Theme: System Auto",
                subtitle: "Match your OS system preference",
                badge: "Theme",
                handler: () => this.theme.set("theme", "system"),
            },
            {
                id: "theme-accent-violet",
                type: "theme",
                category: "Accents",
                icon: "fa-circle",
                iconStyle: "color: #6366f1",
                title: "Accent: Violet / Indigo",
                subtitle: "Modern violet primary accent",
                badge: "Accent",
                handler: () => this.theme.set("accent", "violet"),
            },
            {
                id: "theme-accent-emerald",
                type: "theme",
                category: "Accents",
                icon: "fa-circle",
                iconStyle: "color: #059669",
                title: "Accent: Emerald Green",
                subtitle: "Fresh emerald primary accent",
                badge: "Accent",
                handler: () => this.theme.set("accent", "emerald"),
            },
            {
                id: "theme-accent-blue",
                type: "theme",
                category: "Accents",
                icon: "fa-circle",
                iconStyle: "color: #2563eb",
                title: "Accent: Sapphire Blue",
                subtitle: "Corporate sapphire blue accent",
                badge: "Accent",
                handler: () => this.theme.set("accent", "blue"),
            },
            {
                id: "theme-accent-rose",
                type: "theme",
                category: "Accents",
                icon: "fa-circle",
                iconStyle: "color: #e11d48",
                title: "Accent: Ruby Rose",
                subtitle: "Vibrant rose primary accent",
                badge: "Accent",
                handler: () => this.theme.set("accent", "rose"),
            },
            {
                id: "theme-accent-amber",
                type: "theme",
                category: "Accents",
                icon: "fa-circle",
                iconStyle: "color: #d97706",
                title: "Accent: Sunset Amber",
                subtitle: "Warm amber primary accent",
                badge: "Accent",
                handler: () => this.theme.set("accent", "amber"),
            },
            {
                id: "theme-accent-cyan",
                type: "theme",
                category: "Accents",
                icon: "fa-circle",
                iconStyle: "color: #06b6d4",
                title: "Accent: Cyber Cyan",
                subtitle: "Vivid cyan primary accent",
                badge: "Accent",
                handler: () => this.theme.set("accent", "cyan"),
            },
            {
                id: "theme-reset",
                type: "theme",
                category: "Appearance",
                icon: "fa-refresh",
                title: "Reset Theme Defaults",
                subtitle: "Restore standard theme styling & settings",
                badge: "Reset",
                handler: () => this.theme.reset(),
            },
        ];

        // 3. Dynamic Odoo Apps & Menus
        const menuItems = [];
        try {
            const apps = this.menuService.getApps() || [];
            for (const app of apps) {
                menuItems.push({
                    id: `menu-app-${app.id}`,
                    type: "menu",
                    category: "Apps",
                    icon: "fa-th-large",
                    title: app.name,
                    subtitle: `Application • ${app.xmlid || "app"}`,
                    badge: "App",
                    handler: () => this.menuService.selectMenu(app),
                });

                // Collect submenus
                const tree = this.menuService.getMenuAsTree(app.id);
                if (tree && tree.childrenTree) {
                    const walkTree = (nodes, path) => {
                        for (const node of nodes) {
                            const curPath = path ? `${path} / ${node.name}` : node.name;
                            if (node.actionID || node.actionPath) {
                                menuItems.push({
                                    id: `menu-item-${node.id}`,
                                    type: "menu",
                                    category: app.name,
                                    icon: "fa-folder-open-o",
                                    title: node.name,
                                    subtitle: curPath,
                                    badge: "Menu",
                                    handler: () => this.menuService.selectMenu(node),
                                });
                            }
                            if (node.childrenTree && node.childrenTree.length > 0) {
                                walkTree(node.childrenTree, curPath);
                            }
                        }
                    };
                    walkTree(tree.childrenTree, app.name);
                }
            }
        } catch (e) {
            console.warn("ModernCommandPalette: Could not load full menu tree", e);
        }

        const allCandidates = [...quickActions, ...menuItems, ...themeActions];

        if (!q) {
            return allCandidates.slice(0, 12);
        }

        return allCandidates.filter(item => {
            const titleMatch = item.title.toLowerCase().includes(q);
            const subMatch = item.subtitle ? item.subtitle.toLowerCase().includes(q) : false;
            const catMatch = item.category ? item.category.toLowerCase().includes(q) : false;
            return titleMatch || subMatch || catMatch;
        }).slice(0, 15);
    }

    moveSelection(delta) {
        const list = this.results;
        if (!list.length) return;
        const next = this.state.selectedIndex + delta;
        if (next < 0) {
            this.state.selectedIndex = list.length - 1;
        } else if (next >= list.length) {
            this.state.selectedIndex = 0;
        } else {
            this.state.selectedIndex = next;
        }
    }

    executeSelected() {
        const list = this.results;
        if (!list.length) return;
        const item = list[this.state.selectedIndex] || list[0];
        if (item && item.handler) {
            item.handler();
        }
        this.close();
    }

    selectItem(item) {
        if (item && item.handler) {
            item.handler();
        }
        this.close();
    }

    focusSearch() {
        const input = document.querySelector(".o_searchview_input, .o_searchview input, .o_search_panel input");
        if (input) {
            input.focus();
            input.select?.();
        }
        this.close();
    }

    openDashboard() {
        try {
            this.actionService.doAction("odoo_modern_backend.dashboard");
        } catch (e) {
            const dash = this.results.find(r => r.title.includes("Dashboard"));
            if (dash && dash.handler) dash.handler();
        }
        this.close();
    }

    openCustomizer() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-customizer"));
        this.close();
    }
}

registry.category("main_components").add("odoo_modern_backend.command_palette", {
    Component: CommandPalette,
    props: {},
    sequence: 10,
});
