/** @odoo-module **/

import { registry } from "@web/core/registry";

// Adds a "Home" entry to the user menu so the redesigned landing can be
// reached at any time (no duplicate app root menu).
registry.category("user_menuitems").add("edicai_home", (env) => ({
    description: "Home",
    callback: () => {
        const action = env.services.action;
        action.doAction("edicai_home.action_edicai_home")
            .catch((err) => console.warn("edicai_home: open failed", err));
    },
}));
