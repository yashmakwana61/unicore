"""User-end E2E smoke: typical operator flows against live Odoo."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8069"
RESULTS = []

def check(name, fn):
    try:
        fn()
        RESULTS.append((name, "PASS"))
        print(f"PASS {name}", flush=True)
    except Exception as e:
        RESULTS.append((name, f"FAIL: {type(e).__name__}: {str(e)[:200]}"))
        print(f"FAIL {name}: {e}", flush=True)

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        check("db-selector-loads", lambda: (
            page.goto(f"{BASE}/web/database/selector", wait_until="networkidle"),
            page.wait_for_selector("text=Odoo", timeout=15000),
        ))
        check("login-page-loads", lambda: (
            page.goto(f"{BASE}/web/login", wait_until="networkidle"),
            page.wait_for_selector("input[name='login']", timeout=15000),
        ))
        # Admin login (default odoo.conf admin? use admin/admin on odoo_crm if exists)
        def do_login():
            page.goto(f"{BASE}/web/login?db=odoo_crm", wait_until="networkidle")
            page.fill("input[name='login']", "admin")
            page.fill("input[name='password']", "admin")
            page.click("button[type='submit']")
            page.wait_for_timeout(4000)
        check("admin-login-attempt", do_login)
        check("apps-route-reachable", lambda: (
            page.goto(f"{BASE}/odoo/apps", wait_until="domcontentloaded"),
            page.wait_for_timeout(3000),
        ))
        # Portal routes should redirect to login (not 500) when unauthenticated
        for route in ["/my/edicai/student", "/my/edicai/guardian",
                      "/my/edicai/faculty", "/api/edicai/v1/health",
                      "/telegram/health", "/transcript/verify/abc"]:
            def make(r=route):
                resp = page.request.get(f"{BASE}{r}")
                assert resp.status in (200, 303, 302, 401, 403, 404), f"{r} -> {resp.status}"
            check(f"route-{route}", make)
        browser.close()
    fails = [r for r in RESULTS if r[1] != "PASS"]
    print(f"\nE2E SUMMARY: {len(RESULTS)-len(fails)}/{len(RESULTS)} passed", flush=True)
    for n, s in RESULTS:
        print(f"  {n}: {s}", flush=True)
    sys.exit(1 if fails else 0)

main()
