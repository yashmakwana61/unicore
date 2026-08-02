/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { FormRenderer } from "@web/views/form/form_renderer";
import { FormController } from "@web/views/form/form_controller";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { View } from "@web/views/view";
import { Component, useState, reactive, useEffect, onWillUnmount } from "@odoo/owl";
import { useBus } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { browser } from "@web/core/browser/browser";
import { Chatter } from "@mail/chatter/web_portal/chatter";

// Make unicore_theme_config reactive so layout changes trigger updates reactively in OWL
if (session.unicore_theme_config && !session.unicore_theme_config.__owl_reactive__) {
    session.unicore_theme_config = reactive(session.unicore_theme_config);
}

/**
 * KanbanFlyout Component
 * A sliding side-panel overlaid on the right side of the screen loading a quick-read version of form view.
 */
export class KanbanFlyout extends Component {
    static template = "unicore_design.KanbanFlyout";
    static components = { View };
    static props = {
        resModel: String,
        resId: [Number, String],
        title: { type: String, optional: true },
        onClose: Function,
    };
}

// Register KanbanFlyout on KanbanRenderer components registry
KanbanRenderer.components = {
    ...KanbanRenderer.components,
    KanbanFlyout,
};

// Patch ListRenderer for Ctrl+Click multitasking and Custom View Density
patch(ListRenderer.prototype, {
    get className() {
        const result = super.className || "";
        const density = session.unicore_theme_config?.theme_list_density || "default";
        return `${result} o_theme_density_${density}`;
    },

    async onCellClicked(record, column, ev, newWindow) {
        if (ev && (ev.ctrlKey || ev.metaKey)) {
            if (ev.preventDefault) ev.preventDefault();
            if (ev.stopPropagation) ev.stopPropagation();
            const url = `${window.location.origin}/odoo/${record.resModel}/${record.resId}`;
            window.open(url, "_blank");
            return;
        }
        return super.onCellClicked(record, column, ev, newWindow);
    },
});

// Patch KanbanRecord for Ctrl+Click opening in new tab and Shift+Click Flyout trigger
patch(KanbanRecord.prototype, {
    onGlobalClick(ev, newWindow) {
        if (ev && (ev.ctrlKey || ev.metaKey)) {
            if (ev.preventDefault) ev.preventDefault();
            if (ev.stopPropagation) ev.stopPropagation();
            const record = this.props.record;
            const url = `${window.location.origin}/odoo/${record.resModel}/${record.resId}`;
            window.open(url, "_blank");
            return;
        }
        if (ev && ev.shiftKey) {
            if (ev.preventDefault) ev.preventDefault();
            if (ev.stopPropagation) ev.stopPropagation();
            const record = this.props.record;
            this.env.bus.trigger("open-kanban-flyout", {
                resModel: record.resModel,
                resId: record.resId,
                title: record.data.display_name || record.data.name || "Quick View",
            });
            return;
        }
        return super.onGlobalClick(ev, newWindow);
    },
});

// Patch KanbanRenderer to listen for open-kanban-flyout events
patch(KanbanRenderer.prototype, {
    setup() {
        super.setup();
        this.unicoreState = useState({
            flyoutData: null,
        });
        useBus(this.env.bus, "open-kanban-flyout", (ev) => {
            this.unicoreState.flyoutData = ev.detail;
        });
    },

    closeKanbanFlyout() {
        this.unicoreState.flyoutData = null;
    },
});

// Patch FormRenderer to force chatter at the bottom inside Kanban Flyout
patch(FormRenderer.prototype, {
    mailLayout(hasAttachmentContainer) {
        if (this.rootRef?.el?.closest(".o_unicore_flyout_panel")) {
            return "BOTTOM_CHATTER";
        }
        return super.mailLayout(hasAttachmentContainer);
    },
});

// Patch ControlPanel for Smart Refresher button
patch(ControlPanel.prototype, {
    setup() {
        super.setup();
        this.unicoreRefresherState = useState({
            isRefreshing: false,
        });
    },

    async onSmartRefresh() {
        this.unicoreRefresherState.isRefreshing = true;
        try {
            if (typeof this.env.config?.reload === "function") {
                await this.env.config.reload();
            } else if (this.env.searchModel?.reload) {
                await this.env.searchModel.reload();
            } else if (this.env.bus) {
                this.env.bus.trigger("reload");
            }
        } finally {
            setTimeout(() => {
                this.unicoreRefresherState.isRefreshing = false;
            }, 300);
        }
    },
});

// Patch FormController for Fullscreen form and Chatter layout toggling
patch(FormController.prototype, {
    setup() {
        super.setup();
        this.unicoreFormState = useState({
            isFullscreen: false,
        });
        onWillUnmount(() => {
            document.body.classList.remove("o_unicore_fullscreen");
        });
    },

    toggleFullscreen() {
        this.unicoreFormState.isFullscreen = !this.unicoreFormState.isFullscreen;
        if (this.unicoreFormState.isFullscreen) {
            document.body.classList.add("o_unicore_fullscreen");
        } else {
            document.body.classList.remove("o_unicore_fullscreen");
        }
    },

    get hasChatter() {
        return this.archInfo.arch && this.archInfo.arch.includes("<chatter");
    },

    get chatterToggleIcon() {
        const position = session.unicore_theme_config?.theme_chatter_position || "bottom";
        return position === "side" ? "fa-align-justify" : "fa-columns";
    },

    get chatterToggleTitle() {
        const position = session.unicore_theme_config?.theme_chatter_position || "bottom";
        return position === "side" ? "Move Chatter to Bottom" : "Move Chatter to Side";
    },

    async toggleChatterPosition() {
        const config = session.unicore_theme_config;
        if (!config) return;
        const current = config.theme_chatter_position || "bottom";
        const next = current === "side" ? "bottom" : "side";
        
        config.theme_chatter_position = next;
        document.documentElement.dataset.unicoreChatter = next;
        
        const userId = this.env.services.user?.userId || session.uid;
        if (userId) {
            try {
                await this.orm.write("res.users", [userId], {
                    theme_chatter_position: next,
                });
            } catch (err) {
                console.error("Failed to save theme_chatter_position preference:", err);
            }
        }
    }
});

// Patch Chatter component for Resizable Chatter container
patch(Chatter.prototype, {
    setup() {
        super.setup();
        
        // Retain and apply the browser localStorage chatter size on side-layout activation
        useEffect(
            () => {
                if (this.props.isChatterAside) {
                    const savedWidth = browser.localStorage.getItem("unicore_chatter_width");
                    const parentEl = this.rootRef.el?.parentElement;
                    if (savedWidth && parentEl) {
                        const width = parseInt(savedWidth, 10);
                        if (width && width > 200) {
                            parentEl.style.setProperty("width", `${width}px`, "important");
                            parentEl.style.setProperty("min-width", `${width}px`, "important");
                            parentEl.style.setProperty("max-width", `${width}px`, "important");
                            parentEl.style.setProperty("flex", `0 0 ${width}px`, "important");
                        }
                    }
                } else {
                    const parentEl = this.rootRef.el?.parentElement;
                    if (parentEl) {
                        parentEl.style.removeProperty("width");
                        parentEl.style.removeProperty("min-width");
                        parentEl.style.removeProperty("max-width");
                        parentEl.style.removeProperty("flex");
                    }
                }
            },
            () => [this.props.isChatterAside, this.rootRef.el]
        );
    },

    onChatterResizeMouseDown(ev) {
        if (ev.button !== 0) return;
        ev.preventDefault();
        const startX = ev.clientX;
        const parentEl = this.rootRef.el.parentElement;
        if (!parentEl) return;
        const startWidth = parentEl.getBoundingClientRect().width;
        
        document.body.classList.add("o_unicore_chatter_dragging");
        const dragHandle = ev.target;
        if (dragHandle) {
            dragHandle.classList.add("dragging");
        }

        const onMouseMove = (moveEv) => {
            const deltaX = moveEv.clientX - startX;
            // Limit minimum size to 250px and maximum to window width - 300px
            const newWidth = Math.max(250, Math.min(window.innerWidth - 300, startWidth - deltaX));
            
            parentEl.style.setProperty("width", `${newWidth}px`, "important");
            parentEl.style.setProperty("min-width", `${newWidth}px`, "important");
            parentEl.style.setProperty("max-width", `${newWidth}px`, "important");
            parentEl.style.setProperty("flex", `0 0 ${newWidth}px`, "important");
        };

        const onMouseUp = () => {
            document.body.classList.remove("o_unicore_chatter_dragging");
            if (dragHandle) {
                dragHandle.classList.remove("dragging");
            }
            window.removeEventListener("mousemove", onMouseMove);
            window.removeEventListener("mouseup", onMouseUp);
            
            const finalWidth = parentEl.getBoundingClientRect().width;
            browser.localStorage.setItem("unicore_chatter_width", finalWidth);
        };

        window.addEventListener("mousemove", onMouseMove);
        window.addEventListener("mouseup", onMouseUp);
    }
});
