/** @odoo-module **/

import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Edicai sidebar (accordion, recursive) — replaces the muk AppsBar entirely.
 *
 * Behavior (user-approved UX):
 * - clicking a parent opens its children directly below it in the sidebar;
 * - children with their own children expand recursively the same way;
 * - clicking a leaf navigates;
 * - multiple branches may be open at once (open-set state, never persisted).
 */
export class EdicaiAppsBar extends Component {
    static template = "edicai_nav_ui.EdicaiAppsBar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.action = useService("action");
        this.state = useState({
            roots: [],
            activeAppId: null,
            openIds: new Set(),
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

        if (this.state.isCollapsed) {
            document.body.classList.add("e_sidebar_type_small");
        } else {
            document.body.classList.add("e_sidebar_type_large");
        }
    }

    _loadApps() {
        const tree = this.menuService.getMenuAsTree("root");
        const nodes = tree.childrenTree || [];
        this.state.roots = nodes.map((t) => this._toNode(t));
        const cur = this.menuService.getCurrentApp();
        this.state.activeAppId = cur ? cur.id : null;
    }

    _toNode(t) {
        return {
            id: t.id,
            xmlid: t.xmlid || "",
            label: t.name,
            actionID: (t.action_id !== undefined) ? t.action_id : t.actionID,
            webIconData: (t.web_icon_data !== undefined) ? t.web_icon_data
                : t.webIconData,
            children: (t.childrenTree || []).map((c) => this._toNode(c)),
        };
    }

    isOpen(node) {
        return this.state.openIds.has(node.id);
    }

    onNodeClick(node) {
        if (node.children.length) {
            const opening = !this.state.openIds.has(node.id);
            if (opening) {
                this.state.openIds.add(node.id);
                // a section-only parent (no action) still opens its first leaf
                if (!node.actionID) {
                    const first = this._firstLeaf(node);
                    if (first && first.actionID) {
                        this.menuService.selectMenu(
                            this.menuService.getMenuAsTree(first.id));
                    }
                }
            } else {
                this.state.openIds.delete(node.id);
            }
            return;
        }
        if (node.actionID) {
            this.menuService.selectMenu(this.menuService.getMenuAsTree(node.id));
            this.state.activeAppId = node.id;
        }
    }

    _firstLeaf(node) {
        if (node.actionID) {
            return node;
        }
        for (const child of node.children) {
            const leaf = this._firstLeaf(child);
            if (leaf) {
                return leaf;
            }
        }
        return null;
    }

    _iconSrc(node) {
        // load_menus returns either raw base64 (no data: prefix; svg files
        // base64 start with "P"/"PHN2Zy…, png with "iVBOR") or an URL
        // (e.g. /web/static/img/default_icon_app.png) — never prefix a URL.
        const raw = node.webIconData || "";
        if (!raw || raw.startsWith("/") || raw.startsWith("http")) {
            return "/edicai_nav_ui/static/src/icons/ic_apps.svg";
        }
        if (raw.startsWith("data:image")) {
            return raw;
        }
        const prefix = raw.startsWith("P")
            ? "data:image/svg+xml;base64," : "data:image/png;base64,";
        return prefix + raw.replace(/\s/g, "");
    }

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
}

registry.category("main_components").add("edicai_nav_ui.EdicaiAppsBar", {
    Component: EdicaiAppsBar,
});
