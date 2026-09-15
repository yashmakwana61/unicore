/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class ModernThemeSystray extends Component {
    static template = "odoo_modern_backend.ModernThemeSystray";
    openCustomizer() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-customizer"));
    }
    openCommands() {
        window.dispatchEvent(new CustomEvent("odoo-modern:open-command"));
    }
}

registry.category("systray").add("odoo_modern_backend.theme", {
    Component: ModernThemeSystray,
}, { sequence: 60 });
