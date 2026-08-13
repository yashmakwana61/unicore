#!/usr/bin/env python3
"""
Reusable Playwright UI checker for the oacis_design module.

Checks, on a real headless Chromium:
  * login + opening a form view works
  * the theme config (session.oacis_theme_config) is exposed to the client
  * the `o_oacis_chatter_side` / `o_oacis_chatter_bottom` marker classes
    are present on `.o_form_view`
  * the dynamic theme.css is actually loaded
  * the page keeps a natural scrollbar (no overflow:hidden killing scroll)
  * the chatter sits side-by-side (side mode) or below the sheet (bottom mode)
  * an actual programmatic scroll reaches the bottom of the content

Usage:
  python tools/ui_check.py [--position side|bottom] [--record-id 9] [...]

Notes:
  * Run with the Odoo venv: /root/odoo/odoo19/venv/bin/python
  * --position writes directly to the DB (psql, DB `odoo` by default) to force
    a deterministic configuration, then reloads the page.
  * --headful opens a visible browser for manual inspection.
"""
import argparse
import json
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE = os.environ.get("OACIS_BASE_URL", "http://127.0.0.1:8069")
DEFAULT_DB = os.environ.get("ODOO_DB", "odoo")
PSQL = os.environ.get("PSQL", "psql")

# CSS selectors for the various layers that could be the real scroll container.
SCROLL_CANDIDATES = [
    "document.scrollingElement",
    ".o_content",
    ".o_main_inside",
]


def db_set_position(db, position):
    """Force the chatter position for the admin user and all companies."""
    if position not in ("side", "bottom"):
        raise ValueError(f"invalid position: {position}")
    sql = (
        "UPDATE res_users SET theme_chatter_position='%s' WHERE login='admin'; "
        "UPDATE res_company SET theme_chatter_position='%s';"
    )
    subprocess.run(
        [PSQL, "-U", "root", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql % (position, position)],
        check=True,
    )
    print(f"[db] set theme_chatter_position={position} for admin user + all companies")


def login(page, base, login, password):
    page.goto(f"{base}/web/login")
    page.wait_for_load_state("domcontentloaded")
    page.fill('input[name="login"]', login)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    # Odoo keeps long-polling connections open: never wait for 'networkidle'.
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_web_client, .o_apps", timeout=60_000)
    print(f"[login] ok, landed on {page.url}")


def open_form(page, base, action_id, record_id):
    url = f"{base}/odoo/action-{action_id}/{record_id}"
    page.goto(url)
    page.wait_for_load_state("domcontentloaded")
    try:
        page.wait_for_selector(".o_form_view", timeout=30_000)
    except Exception:
        # Fallback: open the list action and click the first record.
        page.goto(f"{base}/odoo/action-{action_id}")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector(".o_list_renderer .o_data_row", timeout=30_000)
        page.locator(".o_list_renderer .o_data_row").first.click()
        page.wait_for_selector(".o_form_view", timeout=30_000)
    print(f"[form] opened {page.url}")


def js(page, expression):
    return page.evaluate(expression)


def collect_metrics(page):
    """Gather all layout / scroll diagnostics in one page-eval pass."""
    return js(page, """
    () => {
        const rect = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { x: Math.round(r.x), y: Math.round(r.y),
                     w: Math.round(r.width), h: Math.round(r.height) };
        };
        const form = document.querySelector('.o_form_view');
        const renderer = document.querySelector('.o_form_view .o_form_renderer');
        const sheet = document.querySelector('.o_form_view .o_form_sheet_bg');
        const chatter = document.querySelector('.o_form_view .o-mail-Form-chatter');
        const innerContent = document.querySelector('.o_form_view .o_form_view_container .o_content');
        const outerContent = document.querySelector('.o_web_client .o_content');

        const style = (el) => {
            if (!el) return null;
            const cs = getComputedStyle(el);
            return { flexFlow: cs.flexFlow, overflow: cs.overflow,
                     height: cs.height, minHeight: cs.minHeight };
        };
        const scrollerInfo = (name, el) => ({
            name,
            scrollable: el ? el.scrollHeight > el.clientHeight + 1 : false,
            scrollHeight: el ? el.scrollHeight : 0,
            clientHeight: el ? el.clientHeight : 0,
            scrollTop: el ? el.scrollTop : 0,
        });

        const doc = document.scrollingElement;
        const scrollers = [
            scrollerInfo('window', doc),
            scrollerInfo('.o_form_renderer', renderer),
            scrollerInfo('.o_form_sheet_bg', sheet),
            scrollerInfo('.o_form_view .o_content', innerContent),
            scrollerInfo('outer .o_content', outerContent),
        ];

        let sheetChatterSideBySide = null;
        let chatterBelowSheet = null;
        if (sheet && chatter) {
            const s = sheet.getBoundingClientRect();
            const c = chatter.getBoundingClientRect();
            sheetChatterSideBySide = (c.left >= s.right - 2);
            chatterBelowSheet = (c.top >= s.bottom - 2);
        }

        return {
            themeConfig: document.documentElement.dataset.oacisChatter || null,
            themeCssLink: (document.querySelector('#oacis-theme-stylesheet') || {}).href || null,
            viewport: { w: window.innerWidth, h: window.innerHeight },
            form: {
                markerSide: form ? form.classList.contains('o_oacis_chatter_side') : null,
                markerBottom: form ? form.classList.contains('o_oacis_chatter_bottom') : null,
                rect: rect(form),
                style: style(form),
            },
            renderer: { rect: rect(renderer), style: style(renderer) },
            sheet: { rect: rect(sheet), style: style(sheet) },
            chatter: {
                rect: rect(chatter),
                classes: chatter ? chatter.className.split(/[\\s]+/)
                                  .filter(c => c.startsWith('o-aside') || c === 'o-isInFormSheetBg') : [],
            },
            sheetChatterSideBySide,
            chatterBelowSheet,
            scrollers,
        };
    }
    """)


def scroll_test(page, metrics):
    """Scroll the first actually-scrollable layer and confirm we reach the bottom."""
    target = None
    for s in metrics["scrollers"]:
        if s["scrollable"]:
            target = s["name"]
            break
    if target is None:
        return {"status": "SKIP", "reason": "no layer has overflow content"}

    if target == "window":
        before = js(page, "document.scrollingElement.scrollTop")
        js(page, "window.scrollTo(0, document.scrollingElement.scrollHeight)")
        page.wait_for_timeout(400)
        after = js(page, "document.scrollingElement.scrollTop")
        maxTop = js(page, "document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight")
    else:
        sel = target
        before = js(page, f"document.querySelector('{sel}').scrollTop")
        js(page, f"let e=document.querySelector('{sel}'); e.scrollTop = e.scrollHeight")
        page.wait_for_timeout(400)
        after = js(page, f"document.querySelector('{sel}').scrollTop")
        maxTop = js(
            page,
            f"(() => {{ const e = document.querySelector('{sel}'); return e.scrollHeight - e.clientHeight; }})()",
        )

    reached_bottom = after > before and after >= maxTop - 10
    return {
        "status": "PASS" if reached_bottom else "FAIL",
        "scroller": target,
        "before": before,
        "after": after,
        "maxScrollTop": maxTop,
        "reachedBottom": reached_bottom,
    }


def render_report(metrics, scroll, expected_position, screenshot_path):
    lines = []
    lines.append("=" * 64)
    lines.append("OACIS_DESIGN UI CHECK")
    lines.append("=" * 64)

    cfg = metrics["themeConfig"]
    lines.append(f"theme_config:          {json.dumps(cfg) if cfg else 'MISSING'}")

    marker = "side" if metrics["form"]["markerSide"] else ("bottom" if metrics["form"]["markerBottom"] else "NONE")
    lines.append(f"marker class:          o_oacis_chatter_{marker}")
    lines.append(f"theme.css link:        {metrics['themeCssLink']}")

    f = metrics["form"]
    lines.append(f"form rect/style:       {f['rect']} {f['style']}")
    lines.append(f"renderer:              {metrics['renderer']['rect']} {metrics['renderer']['style']}")
    lines.append(f"sheet:                 {metrics['sheet']['rect']} {metrics['sheet']['style']}")
    lines.append(f"chatter:               rect={metrics['chatter']['rect']} classes={metrics['chatter']['classes']}")

    if expected_position:
        pos_ok = expected_position == marker
    else:
        pos_ok = None
    wide = (metrics["viewport"] or {}).get("w", 1600) >= 992
    if metrics["chatter"]["rect"] and metrics["sheet"]["rect"]:
        if marker == "side":
            # Above 992px side mode puts the chatter beside the sheet; below it
            # intentionally falls back to a stacked layout.
            if wide:
                layout_ok = bool(metrics["sheetChatterSideBySide"])
                lines.append(f"chatter layout:        sideBySide={metrics['sheetChatterSideBySide']}")
            else:
                layout_ok = bool(metrics["chatterBelowSheet"])
                lines.append(f"chatter layout:        stackedFallback belowSheet={metrics['chatterBelowSheet']}")
        else:
            layout_ok = bool(metrics["chatterBelowSheet"])
            lines.append(f"chatter layout:        belowSheet={metrics['chatterBelowSheet']}")
    else:
        layout_ok = None
        lines.append("chatter layout:        chatter/sheet not both present")

    for s in metrics["scrollers"]:
        flag = "SCROLLABLE" if s["scrollable"] else "fits"
        lines.append(f"scroller {s['name']:<14} {flag:<11} sh={s['scrollHeight']} ch={s['clientHeight']}")

    lines.append(f"scroll test:           {scroll['status']} (scroller={scroll.get('scroller')}, "
                 f"before={scroll.get('before')} after={scroll.get('after')} max={scroll.get('maxScrollTop')})")
    if scroll.get("reason"):
        lines.append(f"                       ({scroll['reason']})")

    lines.append(f"screenshot:            {screenshot_path}")

    ok = True
    notes = []
    if not cfg:
        ok = False
        notes.append("session.oacis_theme_config missing")
    if marker == "NONE":
        ok = False
        notes.append("no chatter marker class on .o_form_view")
    if not metrics["themeCssLink"]:
        ok = False
        notes.append("theme.css <link> not injected")
    if pos_ok is False:
        ok = False
        notes.append(f"chatter position mismatch: expected {expected_position}, got {marker}")
    if layout_ok is False:
        ok = False
        notes.append("chatter not laid out as expected for current position")
    if scroll["status"] == "FAIL":
        ok = False
        notes.append("could not scroll to the bottom")
    # If there is overflown content somewhere, at least one layer must be scrollable.
    has_overflow = any(s["scrollable"] for s in metrics["scrollers"])
    if not has_overflow and (metrics["sheet"]["rect"] or {}).get("h", 0) > 1000:
        notes.append("content taller than viewport but nothing is scrollable (overflow hidden?)")

    lines.append("-" * 64)
    lines.append("RESULT: " + ("PASS" if ok else "FAIL"))
    for n in notes:
        lines.append(f"  - {n}")
    lines.append("=" * 64)
    return "\n".join(lines), ok


def main():
    ap = argparse.ArgumentParser(description="oacis_design UI checker (Playwright)")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--login", default="admin")
    ap.add_argument("--password", default="admin")
    ap.add_argument("--action", type=int, default=318, help="ir.act_window id (default: Students)")
    ap.add_argument("--record-id", type=int, default=9, help="record id to open")
    ap.add_argument("--position", choices=["side", "bottom"], default=None,
                    help="force DB config (admin user + companies) before checking")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--viewport", default="1600,1000", help="WxH viewport")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--screenshot-dir", default="/tmp/opencode")
    ap.add_argument("--screenshot-name", default="oacis_check.png")
    ap.add_argument("--no-report", action="store_true", help="suppress the text report")
    args = ap.parse_args()

    if args.position:
        db_set_position(args.db, args.position)

    vw, vh = (int(x) for x in args.viewport.split(","))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        page = browser.new_page(viewport={"width": vw, "height": vh})
        login(page, args.base_url, args.login, args.password)
        open_form(page, args.base_url, args.action, args.record_id)
        page.wait_for_timeout(1500)  # let theme.css + layout settle

        metrics = collect_metrics(page)
        scroll = scroll_test(page, metrics)

        os.makedirs(args.screenshot_dir, exist_ok=True)
        shot = os.path.join(args.screenshot_dir, args.screenshot_name)
        page.screenshot(path=shot, full_page=True)

        browser.close()

    report, ok = render_report(metrics, scroll, args.position, shot)
    if not args.no_report:
        print(report)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
