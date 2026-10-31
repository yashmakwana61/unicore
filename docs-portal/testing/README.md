# Edicai Odoo documentation testing: deployment readiness

**Current state: Prepared in GitHub only — NOT RUNNING, NOT DEPLOYED.**

This directory contains a separate, resource-limited Compose design for screenshot and
workflow verification. The production Compose file at repository root is **not modified**.

## Verified account context

- Hostinger VPS: KVM 4, Ubuntu 24.04, 4 vCPU / 16 GB RAM / ~200 GB disk.
- Monitored usage is low, but actual running Odoo and PostgreSQL processes remain unverified.
- Hostinger API reports no managed Docker Compose projects and no Hostinger firewall group.
  These statements do **not** imply Docker, existing services or OS-level firewall is absent.
- VPS backups exist; restore reliability is not established.

## Mandatory operator preflight BEFORE running Compose

Use Hostinger hPanel VPS Browser Terminal, SSH, or another approved shell session.
Run the read-only script **on the VPS**:

```bash
bash docs-portal/testing/preflight-readonly.sh
```

Do not expose passwords, private keys, JWTs or full internal config files when sharing output.
Review RAM, disk free space/inodes, existing ports, systemd services, Docker availability,
reverse proxy and firewall. Confirm current production Odoo is healthy.

**Stop deployment** if Docker is absent, an existing database is unhealthy, port 18069
is in use, available RAM is below 6 GiB, available disk is below 30 GiB,
backup/rollback is unclear, or production health is degraded. These are conservative
planning gates, not definitive workload benchmarks.

## Test-stack isolation

- Unique Compose project `edicai_docs_testing`, database `edicai_docs_test`.
- Isolated named volumes and Docker-internal network.
- No host PostgreSQL port published.
- Odoo binds only to `127.0.0.1:18069` by default; no public domain or DNS changes.
- Maximum aggregate container memory 4 GiB and CPU reservations are **not** implied;
  these are runtime limits. Host and Docker overhead need additional headroom.
- Only synthetic data. NEVER mount, restore or copy the production Odoo database,
  attachments, or filestore.
- No production credentials, SMTP settings, API keys, payment credentials or integrations.
- Cron workers disabled in the Odoo config; still verify whether custom modules initiate
  external effects independently. Docker `internal: true` is a defense in depth, not
  an independent guarantee of all host-level egress controls.

## Proposed operator deployment sequence — DO NOT EXECUTE without approval

1. Inspect host via `preflight-readonly.sh` and confirm rollback/backup.
2. Clone an approved Edicai source commit into a new isolated directory.
3. From this directory create a local `.env` (never commit), with a **new**
   strong database password; keep permissions restrictive.
4. Run `docker compose --env-file .env -f compose.yaml config` to validate.
5. Build the Odoo image only after capacity and security approval. Builds need memory,
   disk and network; keep them outside production peak hours.
6. Start database, initialize base and selected modules **only on**
   `edicai_docs_test`. Review installed addon dependencies and order first.
7. Verify that Odoo is reachable only locally through an SSH tunnel or approved
   authenticated internal proxy.
8. Create synthetic institution profiles, campus, academic calendar, programs,
   registrar/faculty/student/finance roles and synthetic records.
9. Disable outbound email/SMS/payment/integration calls at both application
   and infrastructure boundaries; test that they are blocked.
10. Run a safe Playwright smoke test and have a reviewer approve screenshots.

Do not execute the root `docker-compose.yml` for this experiment.
The `edicai_demo` addon contains reusable dataset seeds, but review its
side effects and dependency installation before enabling it.

## Browser access

Prefer an operator-controlled SSH tunnel from a local computer, e.g. binding
localhost 18069 on the operator machine to localhost 18069 on the VPS.
Do not create a public `testing.edicai.com` record until firewall,
authentication and privacy have been verified.

## Current blocking checks

- Host-level process list, port listeners, OS firewall and true free disk not inspected.
- Isolated Odoo image build, init and synthetic-data validation not performed.
- Docker `internal` networking and localhost-only browser reachability not tested.
- Production service configuration and outbound integrations not verified.
