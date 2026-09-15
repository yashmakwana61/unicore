import { useState, useRef } from '@odoo/owl';
import { patch } from '@web/core/utils/patch';
import { browser } from '@web/core/browser/browser';
import { SIZES } from '@web/core/ui/ui_service';

import { FormRenderer } from '@web/views/form/form_renderer';

/** Track and persist the side chatter width and wire its drag-resize handle. */
patch(FormRenderer.prototype, {
    setup() {
        super.setup();
        this.chatterState = useState({
            width: browser.localStorage.getItem('muk_web_chatter.width'),
        });
        this.chatterContainer = useRef('chatterContainer');
    },
    get isChatterBottom() {
        // If sidebar is open/uncollapsed, chatter MUST shift to bottom in every form view
        const isSidebarLarge = document.body.classList.contains('mk_sidebar_type_large');
        if (isSidebarLarge) {
            return true;
        }
        // If sidebar is collapsed (small), chatter is on the right side as default on desktop screens (>= 992px)
        const isDesktop = (this.uiService?.size >= SIZES.LG) || (typeof window !== 'undefined' && window.innerWidth >= 992);
        return !isDesktop;
    },
    mailLayout(hasAttachmentContainer) {
        const hasChatter = !!this.mailStore;
        if (!hasChatter) {
            return "NONE";
        }
        if (this.isChatterBottom) {
            return "BOTTOM_CHATTER";
        }
        const hasFile = this.hasFile();
        const hasExternalWindow = !!this.mailPopoutService?.externalWindow;
        if (hasExternalWindow && hasFile && hasAttachmentContainer) {
            return "EXTERNAL_COMBO_XXL";
        }
        if (hasAttachmentContainer && hasFile) {
            return "COMBO";
        }
        return "SIDE_CHATTER";
    },
    onStartChatterResize(ev) {
        if (ev.button !== 0) {
            return;
        }
        const initialX = ev.pageX;
        const chatterElement = this.chatterContainer.el;
        const initialWidth = chatterElement.offsetWidth;
        const resizeStoppingEvents = ['keydown', 'mousedown', 'mouseup'];
        const resizePanel = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const newWidth = Math.min(
                Math.max(50, initialWidth - (ev.pageX - initialX)),
                Math.max(chatterElement.parentElement.offsetWidth - 250, 250),
            );
            browser.localStorage.setItem('muk_web_chatter.width', newWidth);
            this.chatterState.width = newWidth;
        };
        const stopResize = (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.type === 'mousedown' && ev.button === 0) {
                return;
            }
            document.removeEventListener('mousemove', resizePanel, true);
            resizeStoppingEvents.forEach((stoppingEvent) => {
                document.removeEventListener(stoppingEvent, stopResize, true);
            });
            document.activeElement.blur();
        };
        document.addEventListener('mousemove', resizePanel, true);
        resizeStoppingEvents.forEach((stoppingEvent) => {
            document.addEventListener(stoppingEvent, stopResize, true);
        });
    },
    onDoubleClickChatterResize() {
        browser.localStorage.removeItem('muk_web_chatter.width');
        this.chatterState.width = false;
    },
});
