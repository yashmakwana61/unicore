# Edicai feature intelligence

Run: python3 docs-portal/engine/feature_intelligence.py --output docs-portal/audit

This read-only static analyzer extracts module manifests, Odoo models and inherited classes, fields, common action methods, XML menus/actions/views/record rules/groups/reports, and ACL CSV rows. Each finding retains source provenance. It runs as a GitHub Action, producing private-to-the-build audit artifacts; source audit JSON is not copied to the public website. A source declaration is not proof of an installed or correctly functioning UI feature. Runtime docs require a disposable Odoo database with synthetic users and data.
