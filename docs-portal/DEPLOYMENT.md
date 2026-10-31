# Deploying to docs.clasflow.io

Recommended: connect this GitHub repository to Cloudflare Pages and choose the `docs-portal` root directory.

- Node version: 20+
- Working directory: `docs-portal`
- Build command: `npm install --no-audit && npm run build`
- Output directory from the working directory: `build`
- Custom domain: `docs.clasflow.io`

If your provider builds from repository root, use `cd docs-portal && npm install --no-audit && npm run build` and output path `docs-portal/build`.

Publishing requires repository review, verified build, hosting provider connection and ownership of the domain's DNS. Those are **not** configured automatically by this PR. Keep production ERP secrets out of the documentation host.

Before making the site public, audit content for private data, security findings, inaccurate steps and unverified claims.
