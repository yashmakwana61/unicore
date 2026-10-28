/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Edicai Web Theme — applies the stored color scheme before first paint.
 *
 * Order:
 *   1. module import time  → apply from localStorage (no flash),
 *   2. boot-service start  → confirm with the server and re-apply if the
 *      admin changed the setting meanwhile.
 *
 * The scheme is a system parameter, presentation only; it never gates
 * permissions and the route leaks nothing beyond "light" / "dark".
 */

const LS_KEY = "edicai.theme.scheme";
const PARAM_KEY = "edicai.web.color_scheme";

function applyScheme(scheme) {
    const html = document.documentElement;
    if (scheme === "dark") {
        html.setAttribute("data-edicai-scheme", "dark");
        html.setAttribute("data-bs-theme", "dark");
        html.classList.add("o_edicai_dark");
    } else {
        html.removeAttribute("data-edicai-scheme");
        html.removeAttribute("data-bs-theme");
        html.classList.remove("o_edicai_dark");
    }
}

// 1. instant, cache-first application (module load is synchronous)
try {
    applyScheme(localStorage.getItem(LS_KEY) || "light");
} catch {
    applyScheme("light");
}

// 2. server-confirmed application on webclient boot
const edicaiThemeService = {
    dependencies: [],
    start() {
        fetch("/edicai_web_theme/scheme", { credentials: "same-origin" })
            .then((r) => (r.ok ? r.json() : null))
            .then((data) => {
                const scheme =
                    data && data.scheme === "dark" ? "dark"
                    : data && data.scheme === "light" ? "light"
                    : "light";
                applyScheme(scheme);
                try {
                    localStorage.setItem(LS_KEY, scheme);
                } catch {
                    /* private mode — cache-first simply stays off */
                }
            })
            .catch(() => {
                /* server hiccup: keep the cached scheme, never break boot */
            });
    },
};

registry.category("services").add("edicai_theme", edicaiThemeService);

export { applyScheme, PARAM_KEY };
