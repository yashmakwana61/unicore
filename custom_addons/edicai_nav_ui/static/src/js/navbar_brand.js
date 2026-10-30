/** @odoo-module **/

const BRAND_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" class="e_brand_logo" aria-hidden="true">
  <rect x="4" y="8" width="26" height="26" rx="7" fill="#2E7BF6"/>
  <rect x="10" y="3" width="27" height="27" rx="8" fill="none" stroke="#ffffff" stroke-width="2.4"/>
</svg>`;

// Cache for company logo (base64 PNG or null)
let _companyLogo = null;
let _logoFetched = false;

async function fetchCompanyLogo() {
    if (_logoFetched) return _companyLogo;
    _logoFetched = true;
    try {
        const res = await fetch('/web/dataset/call_kw/res.company/search_read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    model: 'res.company',
                    method: 'search_read',
                    args: [[]],
                    kwargs: { fields: ['name', 'logo'], limit: 1 },
                },
            }),
            credentials: 'same-origin',
        });
        const j = await res.json();
        if (j.result && j.result.length > 0 && j.result[0].logo) {
            _companyLogo = 'data:image/png;base64,' + j.result[0].logo;
            return _companyLogo;
        }
    } catch (e) {
        console.warn('edicai_nav_ui: could not fetch company logo', e);
    }
    return null;
}

function brandHTML(logoUrl) {
    if (logoUrl) {
        return [
            '<span id="e_brand" class="e_brand">',
            '<img src="' + logoUrl + '" class="e_brand_logo" alt="Company Logo" style="width:100px;height:100px;object-fit:contain;border-radius:8px;"/>',
            '</span>',
        ].join('');
    }
    return [
        '<span id="e_brand" class="e_brand">',
        BRAND_SVG,
        '</span>',
    ].join('');
}

export function createNavbarEnhancer(env) {
    const obs = new MutationObserver(function () {
        applyTo(document.querySelector('nav.o_main_navbar'));
    });

    async function applyTo(navbar) {
        if (!navbar) return;
        navbar.style.setProperty('background-color', '#0d1a33', 'important');
        navbar.style.setProperty('background', '#0d1a33', 'important');

        // Fetch company logo if not yet fetched
        if (!_logoFetched) {
            await fetchCompanyLogo();
        }

        if (!navbar.querySelector('#e_brand')) {
            const toggle = navbar.querySelector('.o_menu_toggle');
            if (toggle) {
                toggle.classList.add('e_menu_toggle_hidden');
                toggle.removeAttribute('href');
                toggle.setAttribute('tabindex', '-1');
                toggle.setAttribute('aria-hidden', 'true');
                toggle.style.pointerEvents = 'none';
                toggle.innerHTML = brandHTML(_companyLogo);
                toggle.style.display = 'inline-flex';
                toggle.style.alignItems = 'center';
                toggle.style.background = 'transparent';
                toggle.style.border = '0';
                toggle.style.padding = '4px 10px';
            }
            const brandElCheck = navbar.querySelector('.o_menu_brand');
            if (!toggle && !brandElCheck) {
                const brand = document.createElement('span');
                brand.id = 'e_brand';
                brand.className = 'e_brand';
                if (_companyLogo) {
                    brand.innerHTML = '<img src="' + _companyLogo + '" class="e_brand_logo" alt="Company Logo" style="width:100px;height:100px;object-fit:contain;border-radius:8px;"/>';
                } else {
                    brand.innerHTML = BRAND_SVG;
                }
                brand.style.display = 'inline-flex';
                brand.style.alignItems = 'center';
                brand.style.padding = '4px 10px';
                navbar.insertBefore(brand, navbar.firstChild);
            }
        } else {
            // Update logo if company logo was fetched after initial render
            const brandEl = navbar.querySelector('#e_brand');
            const brandImg = brandEl ? brandEl.querySelector('img.e_brand_logo') : null;
            const brandSvg = brandEl ? brandEl.querySelector('svg.e_brand_logo') : null;
            if (_companyLogo) {
                if (brandImg) {
                    if (!brandImg.src.startsWith('data:image/png')) {
                        brandImg.src = _companyLogo;
                    }
                } else if (brandSvg) {
                    // Replace SVG with company logo img
                    const img = document.createElement('img');
                    img.src = _companyLogo;
                    img.className = 'e_brand_logo';
                    img.alt = 'Company Logo';
                    img.style.cssText = 'width:100px;height:100px;object-fit:contain;border-radius:8px;';
                    brandSvg.replaceWith(img);
                }
            }
        }

        // Universal search button (centered)
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
                    }
                } catch (err) {
                    console.warn('edicai_nav_ui: palette open failed', err);
                }
            });
            navbar.appendChild(btn);
        }

        // Hide .o_menu_brand (module name) — always
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
    }

    return async function start() {
        await fetchCompanyLogo();
        await applyTo(document.querySelector('nav.o_main_navbar'));
        if (!obs.__attached) {
            obs.observe(document.body, { childList: true, subtree: true });
            obs.__attached = true;
        }
    };
}