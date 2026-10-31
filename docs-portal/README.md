# Clasflow Documentation Portal

Docusaurus documentation under `docs-portal/` for the source-backed Odoo 19 Clasflow project.

## Implemented

- 70 module reference pages
- 11 proposed workspace overview guides
- Getting started, validation, role and student-lifecycle reference pages
- Responsive Docusaurus portal with working local module search
- Static analyzer (`engine/audit.py`) and CI workflow

**Not yet verified:** running Odoo behavior, screenshot workflows, installed module list, full user training articles and production domain. Source references must not be mistaken for working user procedures.

## Run locally

```bash
cd docs-portal
python3 engine/audit.py --check
npm install
npm run start
```

Update source-backed docs with `python3 engine/audit.py --write`; review the generated diff.

See [DEPLOYMENT.md](./DEPLOYMENT.md) for hosting setup.
