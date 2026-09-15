/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class ModernBadge extends Component {
    static template = "odoo_modern_backend.ModernBadge";
    static props = {
        label: { type: String },
        variant: { type: String, optional: true },
    };
}

export class ModernStat extends Component {
    static template = "odoo_modern_backend.ModernStat";
    static props = {
        label: { type: String },
        value: { type: [String, Number] },
    };
}

export class ModernEmptyState extends Component {
    static template = "odoo_modern_backend.ModernEmptyState";
    static props = {
        title: { type: String },
        description: { type: String },
        icon: { type: String, optional: true },
    };
}

export class ModernSectionHeader extends Component {
    static template = "odoo_modern_backend.ModernSectionHeader";
    static props = {
        title: { type: String },
        eyebrow: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
}

registry.category("components").add("odoo_modern_backend.ModernBadge", ModernBadge);
registry.category("components").add("odoo_modern_backend.ModernStat", ModernStat);
registry.category("components").add("odoo_modern_backend.ModernEmptyState", ModernEmptyState);
registry.category("components").add("odoo_modern_backend.ModernSectionHeader", ModernSectionHeader);
