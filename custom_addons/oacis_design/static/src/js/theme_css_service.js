/** @odoo-module */

import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { FormRenderer } from "@web/views/form/form_renderer";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { SIZES } from "@web/core/ui/ui_service";

const FONT_CSS_URL = {
    inter: "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap",
    roboto: "https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap",
    outfit: "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap",
};

function ensureLink(id, rel, href) {
    let link = document.getElementById(id);
    if (!link) {
        link = document.createElement("link");
        link.rel = rel;
        link.type = "text/css";
        link.id = id;
        document.head.appendChild(link);
    }
    link.href = href;
    return link;
}

// Injected dynamic CSS loader service
export const oacisThemeCssService = {
    dependencies: ["lazy_session"],
    start(env, { lazy_session }) {
        // Retrieve the cache-busting theme hash from the lazy-loaded session config
        lazy_session.getValue("oacis_theme_hash", (hash) => {
            let url = "/oacis_design/theme.css";
            if (hash) {
                url += `?v=${encodeURIComponent(hash)}`;
            }
            ensureLink("oacis-theme-stylesheet", "stylesheet", url);
        });
        // Load web fonts through a dedicated <link> so theme.css never blocks
        // on the Google Fonts response (a CSS @import would delay the whole
        // stylesheet). Expose the effective config on <html> too, for CSS/UI tests.
        const config = session.oacis_theme_config;
        if (config) {
            document.documentElement.dataset.oacisChatter =
                config.theme_chatter_position || "bottom";
            const fontUrl = FONT_CSS_URL[config.theme_font_family];
            if (fontUrl) {
                // Separate <link>, not a CSS @import: theme.css then applies
                // immediately even if the Google Fonts response is slow.
                ensureLink("oacis-theme-font", "stylesheet", fontUrl);
            }
        }
    },
};

registry.category("services").add("oacis_theme_css", oacisThemeCssService);

// Add a marker class on the form root (`.o_form_view`) so the theme CSS can
// target the layout without relying on `:has()`. The CSS in
// /oacis_design/theme.css then switches the renderer to a row (side) or
// column (bottom) layout.
patch(FormController.prototype, {
    get className() {
        const result = super.className;
        const config = session.oacis_theme_config;
        if (config && config.theme_chatter_position) {
            result[
                config.theme_chatter_position === "side"
                    ? "o_oacis_chatter_side"
                    : "o_oacis_chatter_bottom"
            ] = true;
        }
        return result;
    },
});

// Patch the FormRenderer mailLayout method to respect the user/company preference.
//
// mailLayout drives both the `o-aside` / bottom classes and the chatter "aside"
// flag, so forcing SIDE_CHATTER / BOTTOM_CHATTER is what actually moves the
// chatter.
patch(FormRenderer.prototype, {
    mailLayout(hasAttachmentContainer) {
        const config = session.oacis_theme_config;
        if (!config || !config.theme_chatter_position) {
            return super.mailLayout(hasAttachmentContainer);
        }

        const position = config.theme_chatter_position; // 'side' or 'bottom'
        const hasFile = this.hasFile();
        const hasChatter = !!this.mailStore;
        const hasExternalWindow = !!this.mailPopoutService.externalWindow;

        if (hasExternalWindow && hasFile && hasAttachmentContainer) {
            if (position === 'side') {
                return "EXTERNAL_COMBO_XXL";
            }
            return "EXTERNAL_COMBO";
        }
        if (hasChatter) {
            if (position === 'side') {
                // At the native XXL size Odoo shows the attachment preview aside
                // (COMBO: chatter bottom + attachments side). Preserve that.
                if (this.uiService.size >= SIZES.XXL && hasAttachmentContainer && hasFile) {
                    return "COMBO";
                }
                return "SIDE_CHATTER"; // force chatter to side
            }
            return "BOTTOM_CHATTER"; // force chatter to bottom
        }
        return "NONE";
    }
});
