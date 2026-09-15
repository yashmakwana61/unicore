/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class ThemeCustomizer extends Component {
    static template = "odoo_modern_backend.ThemeCustomizer";

    setup() {
        this.state = useState({ open: false });
        this.theme = this.env.services.modern_theme;
        this.handler = () => { this.state.open = true; };
        onMounted(() => window.addEventListener("odoo-modern:open-customizer", this.handler));
        onWillUnmount(() => window.removeEventListener("odoo-modern:open-customizer", this.handler));
    }

    close() { this.state.open = false; }
    set(key, value) { this.theme.set(key, value); }
    reset() { this.theme.reset(); }
}

registry.category("main_components").add("odoo_modern_backend.customizer", {
    Component: ThemeCustomizer,
    props: {},
    sequence: 20,
});
