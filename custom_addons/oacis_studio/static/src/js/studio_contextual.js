/** @odoo-module **/
// Forge Studio — Contextual Entry (patches every oacis.* form with "Customize with Forge")
// Uses OWL patching on FormController, but renders via OWL component for consistency
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

class ForgeContextualButton extends Component {
    static template = "oacis_studio.ForgeContextualButton";
    static props = ["*"];
    setup() {
        this.action = useService("action");
    }
    get model() { return this.props.record?.resModel || this.props.model || ""; }
    get isOacis() { return (this.model || "").startsWith("oacis."); }
    openForge() {
        const activeModel = this.model;
        const activeId = this.props.record?.resId || this.props.resId;
        this.action.doAction("oacis_studio.action_studio_shell", {
            additionalContext: {
                active_model: activeModel,
                active_id: activeId,
            },
        });
    }
}

patch(FormController.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            const model = this.props.resModel || this.model?.resModel || "";
            if (!model || !model.startsWith("oacis.")) return;
            if (this.__forgeInjected) return;
            this.__forgeInjected = true;
            setTimeout(() => {
                const formSheet = document.querySelector(".o_form_view .o_form_sheet_bg, .o_form_view .o_form_sheet, .o_form_view .o_form_statusbar");
                const existing = document.querySelector(".o_forge_contextual_bar");
                if (!formSheet || existing) return;

                const bar = document.createElement("div");
                bar.className = "o_forge_contextual_bar";
                bar.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:6px 16px;margin:0 12px 8px;background:linear-gradient(135deg,#f5f3ff 0%,#ede9fe 100%);border:1px solid #c4b5fd;border-radius:6px;font-size:13px;font-family:Inter,-apple-system,sans-serif;";
                bar.innerHTML = `
                    <span style="display:flex;align-items:center;gap:6px;color:#5b21b6;">
                        <span style="font-size:14px;">✨</span>
                        <span>Customize this <b>${model}</b> with Forge Studio</span>
                    </span>
                    <button class="btn btn-sm" style="background:#714B67;color:white;border:none;padding:4px 12px;border-radius:4px;font-size:12px;cursor:pointer;font-weight:500;">
                        ⚙ Customize with Forge
                    </button>
                `;
                const btn = bar.querySelector("button");
                btn.addEventListener("click", () => {
                    const actionService = this.env.services?.action;
                    if (actionService) {
                        actionService.doAction("oacis_studio.action_studio_shell", {
                            additionalContext: {
                                active_model: model,
                                active_id: this.model?.root?.resId || null,
                            },
                        });
                    }
                });
                formSheet.parentNode.insertBefore(bar, formSheet);
            }, 300);
        });
        onWillUnmount(() => {
            const el = document.querySelector(".o_forge_contextual_bar");
            if (el) el.remove();
        });
    },
});

console.log("Forge Studio — Contextual entry loaded (every oacis.* form)");
