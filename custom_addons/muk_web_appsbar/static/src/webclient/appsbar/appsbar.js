import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';
import { user } from '@web/core/user';

import { Component, onWillUnmount, useState } from '@odoo/owl';

/**
 * Modernized sidebar with reactive collapse/expand toggle, localStorage persistence,
 * floating tooltips for compact mode, and smooth state transitions.
 */
export class AppsBar extends Component {
    static template = 'muk_web_appsbar.AppsBar';
    static props = {};

    setup() {
        this.appMenuService = useService('app_menu');
        
        // Check saved preference or initial body class
        const storedMode = localStorage.getItem('mk_sidebar_type');
        const initialIsCollapsed = storedMode === 'small' || 
            (!storedMode && document.body.classList.contains('mk_sidebar_type_small'));

        this.state = useState({
            isCollapsed: initialIsCollapsed,
        });

        // Ensure body classes match state on load
        if (storedMode) {
            if (storedMode === 'small') {
                document.body.classList.remove('mk_sidebar_type_large');
                document.body.classList.add('mk_sidebar_type_small');
            } else if (storedMode === 'large') {
                document.body.classList.remove('mk_sidebar_type_small');
                document.body.classList.add('mk_sidebar_type_large');
            }
        }

        if (user.activeCompany.has_appsbar_image) {
            this.sidebarImageUrl = url('/web/image', {
                model: 'res.company',
                field: 'appbar_image',
                id: user.activeCompany.id,
            });
        }

        const renderAfterMenuChange = () => {
            this.render();
        };

        this.env.bus.addEventListener('MENUS:APP-CHANGED', renderAfterMenuChange);
        onWillUnmount(() => {
            this.env.bus.removeEventListener(
                'MENUS:APP-CHANGED',
                renderAfterMenuChange,
            );
        });
    }

    _onAppClick(app) {
        return this.appMenuService.selectApp(app);
    }

    toggleSidebar() {
        if (this.state.isCollapsed) {
            document.body.classList.remove('mk_sidebar_type_small');
            document.body.classList.add('mk_sidebar_type_large');
            localStorage.setItem('mk_sidebar_type', 'large');
            this.state.isCollapsed = false;
        } else {
            document.body.classList.remove('mk_sidebar_type_large');
            document.body.classList.add('mk_sidebar_type_small');
            localStorage.setItem('mk_sidebar_type', 'small');
            this.state.isCollapsed = true;
        }
        window.dispatchEvent(new Event('resize'));
    }
}
