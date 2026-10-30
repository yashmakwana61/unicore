/** @odoo-module **/

/**
 * Navbar brand + universal search (no template inheritance — DOM surgery
 * inside the navbar element, idempotent via MutationObserver so webclient
 * re-renders can't wipe it).
 *
 * 1. The stock hamburger is replaced by the EdicAI brand (blue rounded
 *    square + white outline + "EdicAI" wordmark) on the selected navy.
 * 2. A centered search field opens the Odoo command palette (the platform
 *    universal search, Ctrl+K).
 */

const BRAND_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" class="e_brand_logo" aria-hidden="true">
  <rect x="4" y="8" width="26" height="26" rx="7" fill="#2E7BF6"/>
  <rect x="10" y="3" width="27" height="27" rx="8" fill="none" stroke="#ffffff" stroke-width="2.4"/>
</svg>`;

export function createNavbarEnhancer(env) {
    const observeBody = new MutationObserver(function () {
        // webclient re-renders regenerate the navbar DOM; re-assert.
        applyTo(document.querySelector('nav.o_main_navbar'));
    });

    function applyTo(navbar) {
        if (!navbar) {
            return;
        }
        navbar.style.setProperty('background-color', '#0d1a33', 'important');
        navbar.style.setProperty('background', '#0d1a33', 'important');
        if (!navbar.querySelector('#e_brand')) {
            // Case 1: home/dashboard view has .o_menu_toggle (hamburger)
            const toggle = navbar.querySelector('.o_menu_toggle');
            if (toggle) {
                toggle.classList.add('e_menu_toggle_hidden');
                toggle.removeAttribute('href');
                toggle.setAttribute('tabindex', '-1');
                toggle.setAttribute('aria-hidden', 'true');
                toggle.style.pointerEvents = 'none';
                toggle.innerHTML = [
                    '<span id="e_brand" class="e_brand">',
                    BRAND_SVG,
                    '<span class="e_brand_name">Edic<span class="e_brand_ai">AI</span></span>',
                    '</span>',
                ].join('');
                toggle.style.display = 'inline-flex';
                toggle.style.alignItems = 'center';
                toggle.style.background = 'transparent';
                toggle.style.border = '0';
                toggle.style.padding = '4px 10px';
            }
            // Case 3: neither exists — create a brand element at the start
            const brandElCheck = navbar.querySelector('.o_menu_brand');
            if (!toggle && !brandElCheck) {
                const brand = document.createElement('span');
                brand.id = 'e_brand';
                brand.className = 'e_brand';
                brand.innerHTML = BRAND_SVG + '<span class="e_brand_name">Edic<span class="e_brand_ai">AI</span></span>';
                brand.style.display = 'inline-flex';
                brand.style.alignItems = 'center';
                brand.style.padding = '4px 10px';
                navbar.insertBefore(brand, navbar.firstChild);
            }
        }
        // Hide .o_menu_brand (module name) — always, regardless of brand state
        const brandElHide = navbar.querySelector('.o_menu_brand');
        if (brandElHide) {
            brandElHide.style.setProperty('display', 'none', 'important');
            brandElHide.style.setProperty('visibility', 'hidden', 'important');
            brandElHide.style.setProperty('width', '0', 'important');
            brandElHide.style.setProperty('overflow', 'hidden', 'important');
        }
        // Hide .o_navbar_apps_menu (hamburger/apps grid) — always
        const appsMenu = navbar.querySelector('.o_navbar_apps_menu');
        if (appsMenu) {
            appsMenu.style.setProperty('display', 'none', 'important');
            appsMenu.style.setProperty('visibility', 'hidden', 'important');
            appsMenu.style.setProperty('width', '0', 'important');
            appsMenu.style.setProperty('overflow', 'hidden', 'important');
        }
        if (!navbar.querySelector('#e_universal_search')) {
            const btn = document.createElement('button');
            btn.id = 'e_universal_search';
            btn.className = 'e_searchbar';
            btn.type = 'button';
            btn.setAttribute('aria-label', 'Search (Ctrl+K)');
            btn.innerHTML = [
                '<i class="fa fa-search e_search_icon" aria-hidden="true"></i>',
                '<span class="e_search_ph">Search in EdicAI…</span>',
                '<span class="e_search_kbd">Ctrl K</span>',
            ].join('');
            btn.addEventListener('click', function () {
                try {
                    if (env && env.services && env.services.command) {
                        env.services.command.openMainPalette({ searchValue: '' });
                    } else if (window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.service) {
                    } else {
                        // try common command palette trigger
                        const cmd = document.querySelector('[data-hotkey="control+k"], [data-hotkey="ctrl+k"]');
                        if (cmd) { cmd.click(); }
                    }
                } catch (err) {
                    console.warn('edicai_nav_ui: palette open failed', err);
                }
            });
            navbar.appendChild(btn);
            btn.style.position = 'absolute';
            btn.style.left = '50%';
            btn.style.transform = 'translateX(-50%)';
            btn.style.top = '6px';
            btn.style.width = 'min(420px, 34vw)';
        }
    }

    return function start() {
        applyTo(document.querySelector('nav.o_main_navbar'));
        if (!observeBody.__attached) {
            observeBody.observe(document.body, {
                childList: true,
                subtree: true,
            });
            observeBody.__attached = true;
        }
    };
}
