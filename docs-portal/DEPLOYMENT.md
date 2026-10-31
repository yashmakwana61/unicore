# Deploying to docs.edicai.com

Recommended: deploy the Docusaurus static build on a separate Hostinger website for `docs.edicai.com`, without overwriting any existing site. Inspect current hosting capacity and DNS first.

- Node version: 20+
- Working directory: `docs-portal`
- Build command: `npm install --no-audit && npm run build`
- Output directory from the working directory: `build`
- Custom domain: `docs.edicai.com`

If your provider builds from repository root, use `cd docs-portal && npm install --no-audit && npm run build` and output path `docs-portal/build`.

Publishing requires repository review, verified build, hosting provider connection and ownership of the domain's DNS. Those are **not** configured automatically by this PR. Keep production ERP secrets out of the documentation host.

Before making the site public, audit content for private data, security findings, inaccurate steps and unverified claims.

## Hostinger production checklist

1. Inspect the existing Hostinger websites and DNS zone and preserve all mail and verification records.
2. Confirm whether `docs.edicai.com` is already serving another website; do not overwrite without explicit approval.
3. Create a separate website/subdomain only on an appropriate existing plan.
4. Build from an approved Git commit; deploy only the static `build/` output, not Odoo source code.
5. Configure the required DNS for `docs`, enable SSL and HTTPS and verify search, article pages and sitemap.
6. Record rollback instructions and confirm that `edicai.com` remains unchanged.

This configuration change does not modify live DNS or hosting.
