---
id: automation
title: "Documentation Automation"
sidebar_position: 6
---
# Documentation Automation

A static source analyzer lives at `docs-portal/engine/audit.py`. It reads manifests with `ast.literal_eval` and scans Python models and XML declarations without importing ERP code.

```bash
cd docs-portal
python3 engine/audit.py --check
python3 engine/audit.py --write
npm install
npm run build
```

The `--write` operation rebuilds only the generated addon reference files and search data. Review generated diffs before merging. This is not an AI content publisher.
