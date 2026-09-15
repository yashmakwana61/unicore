/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

const STORAGE_KEY = "odoo_modern_backend.settings";
const DEFAULTS = {
    accent: "violet",
    density: "comfortable",
    radius: "medium",
    sidebar: "expanded",
    theme: "light",
    motion: true,
    compactTopbar: false,
};

const ACCENTS = {
    violet: { name: "Violet", primary: "#6366f1", soft: "#eef2ff", stronger: "#4f46e5", glow: "rgba(99, 102, 241, 0.25)" },
    blue: { name: "Sapphire", primary: "#2563eb", soft: "#eff6ff", stronger: "#1d4ed8", glow: "rgba(37, 99, 235, 0.25)" },
    emerald: { name: "Emerald", primary: "#059669", soft: "#ecfdf5", stronger: "#047857", glow: "rgba(5, 150, 105, 0.25)" },
    rose: { name: "Rose", primary: "#e11d48", soft: "#fff1f2", stronger: "#be123c", glow: "rgba(225, 29, 72, 0.25)" },
    amber: { name: "Amber", primary: "#d97706", soft: "#fffbeb", stronger: "#b45309", glow: "rgba(217, 119, 6, 0.25)" },
    cyan: { name: "Cyan", primary: "#06b6d4", soft: "#ecfeff", stronger: "#0891b2", glow: "rgba(6, 182, 212, 0.25)" },
    indigo: { name: "Indigo", primary: "#4338ca", soft: "#e0e7ff", stronger: "#3730a3", glow: "rgba(67, 56, 202, 0.25)" },
};

function load() {
    try {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        return { ...DEFAULTS, ...(stored ? JSON.parse(stored) : {}) };
    } catch {
        return { ...DEFAULTS };
    }
}

function save(state) {
    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...state }));
    } catch (e) {
        console.warn("ModernTheme: Failed to save preferences to localStorage", e);
    }
}

function apply(state) {
    const root = document.documentElement;
    const body = document.body;
    const accent = ACCENTS[state.accent] || ACCENTS.violet;

    root.style.setProperty("--ob-primary", accent.primary);
    root.style.setProperty("--ob-primary-soft", accent.soft);
    root.style.setProperty("--ob-primary-strong", accent.stronger);
    root.style.setProperty("--ob-primary-glow", accent.glow || "rgba(99, 102, 241, 0.25)");

    root.setAttribute("data-ob-theme", state.theme);
    root.setAttribute("data-ob-density", state.density);
    root.setAttribute("data-ob-radius", state.radius);
    root.dataset.obTheme = state.theme;
    root.dataset.obDensity = state.density;
    root.dataset.obRadius = state.radius;

    body.classList.toggle("ob-sidebar-collapsed", state.sidebar === "collapsed");
    body.classList.toggle("ob-compact-topbar", !!state.compactTopbar);
    body.classList.toggle("ob-no-motion", !state.motion);
    body.classList.add("o_modern_backend");

    window.dispatchEvent(new CustomEvent("odoo-modern:theme-changed", { detail: state }));
}

const service = {
    dependencies: [],
    start() {
        const state = reactive(load());
        const api = {
            state,
            accents: ACCENTS,
            set(key, value) {
                state[key] = value;
                save(state);
                apply(state);
            },
            toggle(key) {
                api.set(key, !state[key]);
            },
            reset() {
                Object.assign(state, DEFAULTS);
                save(state);
                apply(state);
            },
            apply() {
                apply(state);
            },
        };
        apply(state);
        window.odooModernTheme = api;
        return api;
    },
};

registry.category("services").add("modern_theme", service);
