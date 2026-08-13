/** @odoo-module **/

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { useRef } from "@odoo/owl";

/**
 * PATCH TARGET: @web/webclient/navbar/navbar (NavBar component)
 * 
 * Extends the native NavBar to convert the standard App Dropdown into a 
 * searchable "mega-menu" with fuzzy searching and keyboard grid-navigation.
 * 
 * ROLLBACK SAFETY:
 * If this patch causes the navbar or app menu to break, remove this file's
 * entry from 'web.assets_backend' in __manifest__.py and restart the container:
 * docker compose exec odoo odoo -d unicore_production -u unicore_theme --stop-after-init
 */

patch(NavBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.appsSearchInput = useRef("appsSearchInput");
        
        // Add new state properties for mega-menu functionality
        this.state.appsSearchQuery = "";
        this.state.focusedAppIndex = -1;
        this._appsSearchTimeout = null;
    },

    _onAppsSearchInput(ev) {
        const query = ev.target.value;
        if (this._appsSearchTimeout) {
            clearTimeout(this._appsSearchTimeout);
        }
        
        // ~150ms debounce
        this._appsSearchTimeout = setTimeout(() => {
            this.state.appsSearchQuery = query;
            this.state.focusedAppIndex = 0; // Reset focus to first item when searching
        }, 150);
    },

    _onAppsSearchKeydown(ev) {
        const apps = this.getDisplayedApps(this.menuService.getApps());
        if (!apps.length) return;

        // Dynamically calculate columns based on the CSS grid auto-fill
        let cols = 6; // default fallback
        if (this.appsSearchInput.el) {
            const gridEl = this.appsSearchInput.el.closest('.o_apps_mega_menu').querySelector('.o_apps_menu_grid');
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
                ev.stopPropagation(); // Prevent native Dropdown from interfering
                this.state.focusedAppIndex = Math.min(this.state.focusedAppIndex + cols, apps.length - 1);
                break;
            case "ArrowUp":
                ev.preventDefault();
                ev.stopPropagation();
                this.state.focusedAppIndex = Math.max(this.state.focusedAppIndex - cols, 0);
                break;
            case "ArrowRight":
                ev.preventDefault();
                ev.stopPropagation();
                this.state.focusedAppIndex = Math.min(this.state.focusedAppIndex + 1, apps.length - 1);
                break;
            case "ArrowLeft":
                ev.preventDefault();
                ev.stopPropagation();
                this.state.focusedAppIndex = Math.max(this.state.focusedAppIndex - 1, 0);
                break;
            case "Enter":
                ev.preventDefault();
                ev.stopPropagation();
                if (this.state.focusedAppIndex >= 0 && this.state.focusedAppIndex < apps.length) {
                    const app = apps[this.state.focusedAppIndex];
                    this.onNavBarDropdownItemSelection(app);
                }
                break;
            case "Escape":
                // Intentionally let it bubble up so the native Dropdown close logic handles it.
                break;
        }
    },

    getDisplayedApps(apps) {
        const query = (this.state.appsSearchQuery || "").toLowerCase();
        if (!query) {
            return apps;
        }
        
        // Subsequence fuzzy match (typo-tolerant)
        return apps.filter(app => {
            const name = app.name.toLowerCase();
            let queryIndex = 0;
            for (let i = 0; i < name.length; i++) {
                if (name[i] === query[queryIndex]) {
                    queryIndex++;
                }
                if (queryIndex === query.length) {
                    return true;
                }
            }
            return false;
        });
    }
});
