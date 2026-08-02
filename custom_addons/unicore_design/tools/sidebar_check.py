#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the UniCore dual-tier sidebar in headless Chromium (desktop + mobile).

Checks, on a real headless Chromium:
  * the sidebar is rendered, fixed left (280px) and full-height, and the
    webclient is padded accordingly
  * the navbar holds the sidebar toggle (the old apps-menu burger moved here)
  * tier 1 is the icon rail listing the apps; tier 2 is the tabbed submenu
    panel showing the selected app's menu groups
  * hovering an app switches the panel content (auto-expand on hover)
  * the App & Menu Finder filters the rail and shows grouped results
    (no keyboard shortcut required)
  * Mini Mode collapses the sidebar to a 64px rail, hides the panel and
    shrinks the webclient padding; hovering reveals a fly-out panel
  * clicking a submenu item navigates
  * on a phone viewport the sidebar is an off-canvas drawer opened by the
    navbar burger, with a backdrop, no webclient padding and no mini mode

Usage:
  python tools/sidebar_check.py [--base-url URL] [--headful]

Notes:
  * Run with the Odoo venv: /root/odoo/odoo19/venv/bin/python
"""
import argparse
import os
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE = os.environ.get("UNICORE_BASE_URL", "http://127.0.0.1:8069")
results = []
js_errors = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def login(page, base, login, password):
    page.goto(f"{base}/web/login")
    page.wait_for_load_state("domcontentloaded")
    page.fill('input[name="login"]', login)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_web_client", timeout=90_000)
    page.wait_for_timeout(2500)
    print(f"[login] ok -> {page.url}")


def close_technical_modal(page):
    modal = page.locator(".o_technical_modal")
    if modal.count():
        modal.locator("button").first.click()
        page.wait_for_timeout(400)


def desktop_checks(page):
    sidebar = page.locator(".o_unicore_sidebar")

    # 1. Sidebar rendered, fixed on the left
    check("sidebar rendered", sidebar.count() == 1)
    rect = page.evaluate(
        """() => { const e = document.querySelector('.o_unicore_sidebar');
                   const r = e.getBoundingClientRect();
                   return { x: Math.round(r.x), w: Math.round(r.width),
                            h: Math.round(r.height) }; }"""
    )
    check("sidebar fixed left", rect["x"] == 0 and rect["w"] == 280,
          f"rect={rect}")
    check("sidebar full height", rect["h"] >= 900, f"h={rect['h']}")

    # 2. Webclient pushed right by the sidebar width
    wc_pad = page.evaluate(
        """() => getComputedStyle(document.querySelector('.o_web_client')).paddingLeft""")
    check("webclient padded for sidebar", wc_pad == "280px", f"paddingLeft={wc_pad}")

    # 3. Navbar toggle button
    check("navbar sidebar toggle",
          page.locator(".o_navbar .o_unicore_sidebar_toggle").count() == 1)

    # 4. Tier 1: icon rail with apps
    rail = page.locator(".o_unicore_sidebar_rail")
    check("rail present", rail.count() == 1)
    apps = rail.locator(".o_unicore_sidebar_app")
    check("rail lists apps", apps.count() > 0, f"apps={apps.count()}")

    # 5. Tier 2: submenu panel with sections
    panel = page.locator(".o_unicore_sidebar_panel")
    check("panel present", panel.count() == 1)
    check("panel visible", panel.is_visible())
    groups = page.locator(".o_unicore_sidebar_group")
    check("panel has menu groups", groups.count() > 0, f"groups={groups.count()}")

    # 6. Hover an app switches the panel content (auto-expand on hover)
    second = apps.nth(1)
    second_name = second.get_attribute("title")
    second.hover()
    page.wait_for_timeout(400)
    title_after = page.locator(".o_unicore_sidebar_panel_title").inner_text()
    check("hover switches panel", title_after == second_name,
          f"title={title_after!r} vs app={second_name!r}")
    check("hovered app active in rail", second.get_attribute("data-active") is not None)

    # 7. Search filters the rail + panel (no keyboard shortcut needed)
    page.fill(".o_unicore_sidebar_search", "inv")
    page.wait_for_timeout(400)
    filtered = [a.get_attribute("title") for a in apps.all()]
    check("search filters rail",
          len(filtered) > 0 and any("inv" in n.lower() for n in filtered),
          f"filtered={filtered}")
    group_titles = [g.inner_text().strip()
                    for g in page.locator(".o_unicore_sidebar_group_title").all()]
    check("search shows grouped results", len(group_titles) > 0, f"groups={group_titles}")
    page.fill(".o_unicore_sidebar_search", "")
    page.wait_for_timeout(300)

    # 8. Mini mode toggle collapses to icons + shrinks webclient padding
    page.locator(".o_unicore_sidebar_mini").click()
    page.wait_for_timeout(500)
    check("mini data attribute", sidebar.get_attribute("data-mini") is not None)
    rect2 = page.evaluate(
        """() => { const e = document.querySelector('.o_unicore_sidebar');
                   const r = e.getBoundingClientRect();
                   return { w: Math.round(r.width) }; }""")
    check("mini collapses width to rail", rect2["w"] == 64, f"w={rect2['w']}")
    wc_pad2 = page.evaluate(
        """() => getComputedStyle(document.querySelector('.o_web_client')).paddingLeft""")
    check("mini shrinks webclient padding", wc_pad2 == "64px", f"paddingLeft={wc_pad2}")
    panel_hidden = page.evaluate(
        """() => { const e = document.querySelector('.o_unicore_sidebar_panel');
                   const cs = getComputedStyle(e);
                   return cs.visibility === 'hidden' || cs.opacity === '0'; }""")
    check("mini hides panel", panel_hidden)

    # 9. Hover reveals the fly-out panel in mini mode
    apps.nth(1).hover()
    page.wait_for_timeout(400)
    panel_visible = page.evaluate(
        """() => { const e = document.querySelector('.o_unicore_sidebar_panel');
                   const cs = getComputedStyle(e);
                   return cs.visibility === 'visible' && cs.opacity === '1'; }""")
    check("mini hover shows fly-out", panel_visible)

    # 10. Toggle back to standard
    page.locator(".o_unicore_sidebar_mini").click()
    page.wait_for_timeout(500)
    check("expand back to standard", sidebar.get_attribute("data-mini") is None)
    check("webclient padding restored",
          page.evaluate(
              """() => getComputedStyle(document.querySelector('.o_web_client')).paddingLeft""")
          == "280px")

    # 11. Clicking a submenu navigates
    first_item = page.locator(".o_unicore_sidebar_panel .o_unicore_sidebar_item").first
    item_text = first_item.inner_text().strip()
    first_item.click()
    page.wait_for_timeout(1500)
    check("submenu click navigates", "/odoo" in page.url, f"url={page.url}")

    page.screenshot(path="/tmp/opencode/sidebar_check.png", full_page=True)


def clickability_checks(page):
    """Sections without children render as clickable items; parents and group
    headers are clickable too (falling back to the first actionable child)."""
    apps = page.locator(".o_unicore_sidebar_rail .o_unicore_sidebar_app")
    panel = page.locator(".o_unicore_sidebar_panel")

    # An app whose direct children are all leaf actions (Admission) must show
    # clickable items instead of empty group headers.
    apps.nth(2).hover()
    page.wait_for_timeout(400)
    items = panel.locator(".o_unicore_sidebar_item")
    titles = panel.locator(".o_unicore_sidebar_group_title").count()
    check("leaf-only app shows clickable items", items.count() >= 3,
          f"items={items.count()}")
    check("leaf-only app has no empty headers", titles == 0, f"titles={titles}")
    before = page.url
    items.first.click()
    page.wait_for_timeout(1500)
    check("leaf-only app item navigates", page.url != before, f"{before} -> {page.url}")

    # An app with nested groups (Invoicing) must have clickable parent items.
    apps.nth(5).hover()
    page.wait_for_timeout(400)
    parents = panel.locator(".o_unicore_sidebar_item_parent")
    check("app with children shows parent items", parents.count() > 0,
          f"parents={parents.count()}")
    before = page.url
    parents.first.click()
    page.wait_for_timeout(1500)
    check("parent item navigates", page.url != before, f"{before} -> {page.url}")

    # Group headers are clickable as well.
    apps.first.hover()
    page.wait_for_timeout(400)
    gh = panel.locator(".o_unicore_sidebar_group_title").first
    check("group header present", gh.count() == 1)
    before = page.url
    gh.click()
    page.wait_for_timeout(1500)
    check("group header navigates", page.url != before, f"{before} -> {page.url}")


def mobile_checks(page):
    sidebar = page.locator(".o_unicore_sidebar")
    check("sidebar present on mobile", sidebar.count() == 1)
    off = page.evaluate(
        """() => { const e = document.querySelector('.o_unicore_sidebar');
                   const t = getComputedStyle(e).transform;
                   return t !== 'none' && t.includes('-'); }""")
    check("sidebar off-canvas initially", off)
    check("no webclient padding on mobile",
          page.evaluate(
              """() => getComputedStyle(document.querySelector('.o_web_client')).paddingLeft""")
          == "0px")

    page.locator(".o_menu_toggle").first.click()
    page.wait_for_timeout(600)
    check("burger opens drawer",
          sidebar.get_attribute("data-open") is not None)
    check("backdrop appears", page.locator(".o_unicore_sidebar_backdrop").is_visible())
    check("webclient padded when open",
          page.evaluate(
              """() => getComputedStyle(document.querySelector('.o_web_client')).paddingLeft""")
          != "0px")
    check("no mini on mobile", sidebar.get_attribute("data-mini") is None)

    page.locator(".o_unicore_sidebar_panel .o_unicore_sidebar_item").first.click()
    page.wait_for_timeout(1500)
    check("submenu click navigates", "/odoo" in page.url)
    check("drawer closes after nav", sidebar.get_attribute("data-open") is None)

    page.screenshot(path="/tmp/opencode/sidebar_mobile.png")


def main():
    ap = argparse.ArgumentParser(description="UniCore sidebar checker (Playwright)")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--login", default="admin")
    ap.add_argument("--password", default="admin")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)

        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        login(page, args.base_url, args.login, args.password)
        close_technical_modal(page)
        desktop_checks(page)
        clickability_checks(page)

        mobile = browser.new_page(viewport={"width": 414, "height": 896})  # phone
        mobile.on("pageerror", lambda e: js_errors.append(str(e)))
        login(mobile, args.base_url, args.login, args.password)
        close_technical_modal(mobile)
        mobile_checks(mobile)

        browser.close()

    print()
    print("=" * 64)
    ok = all(r[1] for r in results)
    print("RESULT:", "PASS" if ok else "FAIL", f"({len(results)} checks)")
    if js_errors:
        print("JS page errors:")
        for e in js_errors[:8]:
            print("  ", e)
    print("=" * 64)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
