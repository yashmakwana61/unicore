/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState, useRef, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { fuzzyLookup } from "@web/core/utils/search";

export class AppsLandingScreen extends Component {
    static template = "oacis_theme.AppsLandingScreen";

    setup() {
        this.menuService = useService("menu");
        this.appsSearchInput = useRef("appsSearchInput");
        
        // Use standard service to get accessible apps
        this.allApps = this.menuService.getApps();
        
        this.state = useState({
            searchQuery: "",
            focusedAppIndex: 0,
        });

        // Lifecycle hooks to toggle the full-screen mode safely
        onMounted(() => {
            document.body.classList.add("o_oacis_apps_landing_active");
            if (this.appsSearchInput.el) {
                this.appsSearchInput.el.focus();
            }
        });

        onWillUnmount(() => {
            document.body.classList.remove("o_oacis_apps_landing_active");
        });
        
        useExternalListener(window, "keydown", this.onGlobalKeydown);
    }

    get displayedApps() {
        if (!this.state.searchQuery) {
            return this.allApps;
        }
        return fuzzyLookup(
            this.state.searchQuery,
            this.allApps,
            (app) => app.name
        );
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        this.state.focusedAppIndex = 0; // Reset focus on search
    }

    onGlobalKeydown(ev) {
        const apps = this.displayedApps;
        if (!apps.length) return;

        // Dynamic column calculation for keyboard nav since layout is responsive
        let cols = 6;
        if (this.appsSearchInput.el) {
            const gridEl = this.appsSearchInput.el.closest('.o_apps_landing_screen').querySelector('.o_apps_landing_grid');
            if (gridEl) {
                const gridStyle = window.getComputedStyle(gridEl);
                const columns = gridStyle.getPropertyValue('grid-template-columns');
                if (columns) {
                    cols = columns.split(' ').length;
                }
            }
        }

        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                this.state.focusedAppIndex = Math.min(this.state.focusedAppIndex + cols, apps.length - 1);
                break;
            case "ArrowUp":
                ev.preventDefault();
                this.state.focusedAppIndex = Math.max(this.state.focusedAppIndex - cols, 0);
                break;
            case "ArrowRight":
                ev.preventDefault();
                this.state.focusedAppIndex = Math.min(this.state.focusedAppIndex + 1, apps.length - 1);
                break;
            case "ArrowLeft":
                ev.preventDefault();
                this.state.focusedAppIndex = Math.max(this.state.focusedAppIndex - 1, 0);
                break;
            case "Enter":
                ev.preventDefault();
                if (this.state.focusedAppIndex >= 0 && this.state.focusedAppIndex < apps.length) {
                    this.openApp(apps[this.state.focusedAppIndex]);
                }
                break;
        }
    }

    openApp(app) {
        // Delegate to Odoo's core menu service. This handles standard app loading
        // logic and automatically unmounts this component.
        this.menuService.selectMenu(app);
    }
}

// Register as a standard client action
registry.category("actions").add("oacis_apps_landing", AppsLandingScreen);
