#!/usr/bin/env python3
"""Verify the UniCore Start Menu (two-list layout + pin persistence).

Checks, on a real headless Chromium:
  * the Start button is present in the navbar and opens the full-screen menu
  * the menu is a full-screen overlay with a blurred backdrop and theme CSS vars
  * the two-list layout (Favourites + All Apps) is rendered
  * pinning an app moves it to Favourites and persists to the DB
    (ir_ui_menu_res_users_rel via res.users.theme_toggle_pinned_app)
  * the pinned app survives a page reload (read back from session_info)
  * search filters the All Apps list
  * Escape closes the menu and clicking an app navigates
  * cleanup: the pinned app is unpinned again

Usage:
  python tools/start_menu_check.py [--base-url URL] [--db odoo] [--headful]

Notes:
  * Run with the Odoo venv: /root/odoo/odoo19/venv/bin/python
  * Relies on psql being reachable to inspect/clean the pin table.
"""
import argparse
import json
import os
import subprocess
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE = os.environ.get("UNICORE_BASE_URL", "http://127.0.0.1:8069")
DEFAULT_DB = os.environ.get("ODOO_DB", "odoo")
PSQL = os.environ.get("PSQL", "psql")

PIN_TABLE = "ir_ui_menu_res_users_rel"
results = []
js_errors = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def db_clear_pins(db):
    subprocess.run([PSQL, "-U", "root", "-d", db, "-c", f"DELETE FROM {PIN_TABLE};"],
                   capture_output=True, check=False)


def db_pins(db):
    out = subprocess.run(
        [PSQL, "-U", "root", "-d", db, "-t", "-A", "-c", f"SELECT * FROM {PIN_TABLE} ORDER BY 1;"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    return [tuple(r.split("|")) for r in out.splitlines() if r]


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


def open_start_menu(page):
    close_technical_modal(page)
    # The Start Menu is opened from the navbar hamburger button
    page.locator(".o_navbar .o_unicore_sidebar_toggle").first.click()
    page.wait_for_timeout(800)
    return page.locator(".o_unicore_start_menu")


def main():
    ap = argparse.ArgumentParser(description="UniCore Start Menu checker (Playwright)")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--login", default="admin")
    ap.add_argument("--password", default="admin")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    db_clear_pins(args.db)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        login(page, args.base_url, args.login, args.password)

        # 1. Sidebar replaces the top apps menu
        check("sidebar rendered", page.locator(".o_unicore_sidebar").count() == 1)
        check("navbar sidebar toggle", page.locator(".o_navbar .o_unicore_sidebar_toggle").count() == 1)
        check("two-tier sidebar", page.locator(".o_unicore_sidebar_rail .o_unicore_sidebar_app").count() > 0
              and page.locator(".o_unicore_sidebar_panel .o_unicore_sidebar_group").count() > 0)
        check("navbar app sections visible", page.evaluate(
            """() => { const s = document.querySelector('.o_navbar .o_menu_sections');
                       return !s || getComputedStyle(s).display !== 'none'; }"""))

        # 2. Theme CSS vars present
        vars_ok = page.evaluate(
            """() => {
                const s = getComputedStyle(document.documentElement);
                return { bg: s.getPropertyValue('--unicore-startmenu-bg').trim(),
                         blur: s.getPropertyValue('--unicore-startmenu-blur').trim() };
            }""",
        )
        check("start menu css vars", bool(vars_ok["bg"]) and bool(vars_ok["blur"]),
              json.dumps(vars_ok))

        # 3. Open the Start Menu (full-screen overlay)
        overlay = open_start_menu(page)
        check("start menu opens", overlay.count() == 1 and overlay.is_visible())
        check("full-screen overlay", page.evaluate(
            """() => { const e = document.querySelector('.o_unicore_start_menu');
                       if (!e) return false;
                       const r = e.getBoundingClientRect();
                       return r.width >= window.innerWidth * 0.98
                              && r.height >= window.innerHeight * 0.98; }"""))

        # 4. Two-list layout
        favs = page.locator(".o_unicore_start_favs")
        allcol = page.locator(".o_unicore_start_all")
        check("two lists present", favs.count() == 1 and allcol.count() == 1)

        # 5. Blur applied (backdrop-filter)
        check("backdrop blur applied", page.evaluate(
            """() => { const e = document.querySelector('.o_unicore_start_menu');
                       const s = getComputedStyle(e);
                       return s.backdropFilter && s.backdropFilter !== 'none'; }"""))

        # 6. App count in All Apps, favourites empty initially
        all_before = allcol.locator(".o_unicore_app").count()
        check("all apps listed", all_before > 0, f"apps={all_before}")
        check("favourites empty initially", favs.locator(".o_unicore_app").count() == 0)

        # 7. Pin the first app in All Apps
        first_app = allcol.locator(".o_unicore_app").first
        app_name = first_app.locator(".o_unicore_app_name").inner_text()
        first_app.locator(".o_unicore_pin").click()
        page.wait_for_timeout(1200)
        favs_after = favs.locator(".o_unicore_app").count()
        all_after = allcol.locator(".o_unicore_app").count()
        check("pin moves app to favourites", favs_after == 1 and all_after == all_before - 1,
              f"'{app_name}' favs={favs_after} all={all_after}")

        # 8. Persistence on the backend
        db_rows = db_pins(args.db)
        check("pin persisted in DB", len(db_rows) == 1, f"rows={db_rows}")

        # 9. Persistence across reload (read back from the eager session_info)
        page.reload()
        page.wait_for_selector(".o_web_client", timeout=90_000)
        page.wait_for_timeout(2500)
        favs_after_reload = open_start_menu(page).locator(
            ".o_unicore_start_favs .o_unicore_app_name").all_inner_texts()
        favs_after_reload = [t.strip() for t in favs_after_reload]
        check("pin survives reload", app_name in favs_after_reload,
              f"favs={favs_after_reload}")

        # 10. Unpin -> returns to All Apps
        for el in page.locator(".o_unicore_start_favs .o_unicore_app").all():
            if el.locator(".o_unicore_app_name").inner_text().strip() == app_name:
                el.locator(".o_unicore_pin").click()
                page.wait_for_timeout(1200)
                break
        check("unpin returns app to all",
              favs.locator(".o_unicore_app").count() == 0
              and allcol.locator(".o_unicore_app").count() == all_before,
              f"favs={favs.locator('.o_unicore_app').count()} all={allcol.locator('.o_unicore_app').count()}")
        check("unpin cleaned DB", len(db_pins(args.db)) == 0,
              f"rows={db_pins(args.db)}")

        # 11. Search filter
        page.fill(".o_unicore_start_search", "inv")
        page.wait_for_timeout(400)
        visible_all = page.evaluate(
            """() => [...document.querySelectorAll('.o_unicore_start_all .o_unicore_app_name')]
                      .map(e => e.textContent)""")
        check("search filters results",
              len(visible_all) >= 1 and all("inv" in n.lower() for n in visible_all),
              f"results={visible_all}")
        page.fill(".o_unicore_start_search", "")

        # 12. Escape closes
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        check("escape closes menu", overlay.count() == 0 or not overlay.is_visible())

        # 13. Clicking an app navigates
        open_start_menu(page)
        allcol.locator(".o_unicore_app").first.click()
        page.wait_for_timeout(1500)
        check("clicking app navigates", "/odoo" in page.url, f"url={page.url}")
        check("menu closed after nav", overlay.count() == 0 or not overlay.is_visible())

        page.screenshot(path="/root/odoo/odoo19/custom_addons/unicore_design/tools/start_menu_check.png", full_page=True)
        browser.close()

    print()
    print("=" * 64)
    ok = all(r[1] for r in results)
    print("RESULT:", "PASS" if ok else "FAIL")
    if js_errors:
        print("JS page errors:")
        for e in js_errors[:5]:
            print("  ", e)
    print("=" * 64)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
