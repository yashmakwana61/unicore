/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { session } from "@web/session";
import { imageUrl } from "@web/core/utils/urls";

export class ModernShell extends Component {
    static template = "odoo_modern_backend.ModernShell";

    setup() {
        this.theme = useService("modern_theme");
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.state = useState({
            mobileOpen: false,
            activeMenuId: null,
        });

        this.onAppChanged = () => {
            const currentApp = this.menuService.getCurrentApp();
            this.state.activeMenuId = currentApp ? currentApp.id : null;
        };

        onMounted(() => {
            this._markApp();
            this.onAppChanged();
            this.env.bus?.addEventListener("MENUS:APP-CHANGED", this.onAppChanged);
        });

        onWillUnmount(() => {
            this.env.bus?.removeEventListener("MENUS:APP-CHANGED", this.onAppChanged);
        });
    }

    get apps() {
        return this.menuService.getApps() || [];
    }

    get currentApp() {
        return this.menuService.getCurrentApp();
    }

    get isDashboardActive() {
        const currentApp = this.currentApp;
        return currentApp && (currentApp.xmlid === "odoo_modern_backend_full.menu_modern_dashboard" || currentApp.name === "Modern Dashboard");
    }

    get userName() {
        return user.name || "Administrator";
    }

    get userAvatar() {
        const { partnerId, writeDate } = user;
        if (partnerId) {
            return imageUrl("res.partner", partnerId, "avatar_128", { unique: writeDate });
        }
        return null;
    }

    get userInitial() {
        return (this.userName || "U").charAt(0).toUpperCase();
    }

    async selectApp(app) {
        if (!app) return;
        this.state.activeMenuId = app.id;
        await this.menuService.selectMenu(app);
        this.closeMobile();
    }

    async openDashboard() {
        try {
            await this.actionService.doAction("odoo_modern_backend.dashboard");
        } catch (e) {
            console.warn("ModernShell: Could not open dashboard action directly, selecting menu item", e);
            const dashApp = this.apps.find(a => a.xmlid?.includes("dashboard") || a.name?.includes("Dashboard"));
            if (dashApp) {
                await this.menuService.selectMenu(dashApp);
            }
        }
        this.closeMobile();
    }

    toggleSidebar() {
        const next = this.theme.state.sidebar === "collapsed" ? "expanded" : "collapsed";
        this.theme.set("sidebar", next);
    }

    toggleMobile() {
        this.state.mobileOpen = !this.state.mobileOpen;
    }

    closeMobile() {
        this.state.mobileOpen = false;
    }

    openCommands() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-command"));
        this.closeMobile();
    }

    openCustomizer() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-customizer"));
        this.closeMobile();
    }

    _markApp() {
        document.body.classList.add("ob-shell-ready");
    }
}

registry.category("main_components").add("odoo_modern_backend.shell", {
    Component: ModernShell,
    props: {},
    sequence: 5,
});
