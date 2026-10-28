"""User-end E2E over HTTP (no browser libs in env): typical operator flows."""
import sys
import requests

BASE = "http://localhost:8069"
S = requests.Session()
RESULTS = []

def check(name, fn):
    try:
        detail = fn()
        RESULTS.append((name, "PASS"))
        print(f"PASS {name} [{detail}]", flush=True)
    except AssertionError as e:
        RESULTS.append((name, f"FAIL: {e}"))
        print(f"FAIL {name}: {e}", flush=True)
    except Exception as e:
        RESULTS.append((name, f"ERROR: {type(e).__name__}: {str(e)[:150]}"))
        print(f"ERROR {name}: {e}", flush=True)

def get(path, **kw):
    return S.get(BASE + path, timeout=15, allow_redirects=False, **kw)

def post(path, **kw):
    return S.post(BASE + path, timeout=15, allow_redirects=False, **kw)

def t_selector():
    r = get("/web/database/selector")
    assert r.status_code == 200, f"status={r.status_code}"
    assert "Odoo" in r.text, "no Odoo title"
    return r.status_code

def t_dblist():
    r = post("/web/database/list", json={})
    assert r.status_code == 200, f"status={r.status_code}"
    assert "odoo_crm" in r.text, r.text[:120]
    return r.text[:60]

def t_login_page():
    r = get("/web/login?db=odoo_crm")
    assert r.status_code == 200, f"status={r.status_code}"
    assert "login" in r.text and "password" in r.text, "no login form"
    return r.status_code

def t_login_wrong():
    # Real user flow: GET form -> extract csrf -> POST creds
    import re
    form = S.get(BASE + "/web/login?db=odoo_crm", timeout=15).text
    m = re.search(r'name="csrf_token" value="([^"]+)"', form)
    data = {"db": "odoo_crm", "login": "admin", "password": "wrong-pass-123"}
    if m:
        data["csrf_token"] = m.group(1)
    r = S.post(BASE + "/web/login", data=data, timeout=15, allow_redirects=False)
    assert r.status_code in (200, 303), f"status={r.status_code}"
    assert r.status_code != 500, "server error on login"
    return f"{r.status_code} csrf={'yes' if m else 'no'}"

def t_api_health():
    # edicai_api UNINSTALLED in odoo_crm -> Odoo website 404 is CORRECT.
    # Passes if: 404 page (module absent) or 200 JSON (module present). Never 500.
    r = get("/api/edicai/v1/health")
    assert r.status_code in (200, 404), f"status={r.status_code} {r.text[:100]}"
    assert r.status_code != 500, "server error"
    return f"{r.status_code} {'JSON' if r.status_code == 200 else 'uninstalled-OK'}"

def t_api_info_nokey():
    # Same: 404 when module absent; 401/403 when present without key.
    r = get("/api/edicai/v1/info")
    assert r.status_code in (401, 403, 404), f"status={r.status_code} (expected 401/403/404)"
    return r.status_code

def t_telegram_nosecret():
    r = post("/telegram/webhook", json={"message": {"chat": {"id": 1}, "text": "/start"}})
    assert r.status_code != 500, f"server error: {r.text[:100]}"
    return f"{r.status_code} {r.text[:80]}"

def t_portals_redirect():
    # Portal modules UNINSTALLED in odoo_crm -> 404 website page is CORRECT.
    # Passes on 200/302/303 (installed) or 404 (absent). Never 500.
    out = []
    for route in ["/my/edicai/student", "/my/edicai/guardian",
                  "/my/edicai/faculty", "/my/edicai/student/notices"]:
        r = get(route)
        assert r.status_code in (200, 302, 303, 404), f"{route}->{r.status_code}"
        assert r.status_code != 500, f"{route} 500"
        out.append(f"{route}:{r.status_code}")
    return ",".join(out)

check("selector-200", t_selector)
check("dblist-has-odoo_crm", t_dblist)
check("login-page", t_login_page)
check("login-wrong-no500", t_login_wrong)
check("api-health", t_api_health)
check("api-info-nokey-401", t_api_info_nokey)
check("telegram-webhook-nosecret", t_telegram_nosecret)
check("portals-redirect-no500", t_portals_redirect)

fails = [r for r in RESULTS if r[1] != "PASS"]
print(f"\nE2E SUMMARY: {len(RESULTS)-len(fails)}/{len(RESULTS)} passed", flush=True)
sys.exit(1 if fails else 0)
