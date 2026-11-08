# Edicai screenshot verification harness

The screenshot harness is **read-only** and requires an explicit declaration that the environment contains no production/student data. It does not perform workflow transitions, doesn't upload images to the docs site and doesn't claim UI verification.

The current implementation captures the login page and Odoo web shell only. Admission action screenshots require a separately reviewed synthetic-data test script and role-specific permissions. Odoo commonly makes initial navigation/data requests with POST; the read-only harness blocks those requests, so it is **not sufficient to inspect authenticated model screens** without an additional risk-reviewed capture mechanism.

Commands:

```bash
cd docs-portal
npm install --no-save playwright
npx playwright install chromium
EDICAI_DEMO_ORIGIN=https://your-isolated-demo.example \
EDICAI_DEMO_OK=I_CONFIRM_SYNTHETIC_ISOLATED_ENV \
EDICAI_STORAGE_STATE=/secure/path/demo-session.json \
node verification/capture.mjs
```

Do not commit session state, demo credentials, or generated screenshots. Only open it against an isolated and synthetic Odoo environment. The screenshots are placed in `verification/output/` and await human review.

The snapshot tool is *not* an Odoo workflow test runner. Admission workflow verification requires a test DB, representative roles, and explicit restrictions on external side effects.
