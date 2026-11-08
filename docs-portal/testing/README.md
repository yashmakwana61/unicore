# Edicai Odoo documentation testing: deployment readiness

**Current state: VPS Edicai docs lab is running, with localhost web login verified.**
The reverse-proxy topology below is a proposed hardening change and is **not applied to VPS until operator update**.

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
- Odoo and PostgreSQL attach **only** to the internal `sandbox` network. Odoo publishes **no** host ports.
- An Nginx `gateway` container joins both `sandbox` and the existing external `edicai_docs_lab_access` bridge and publishes only `127.0.0.1:18069` to the VPS.
- The gateway is a **network proxy** only: it must never receive credentials or integration secrets. Verify actual egress denial from Odoo after applying the change.
- No public domain or DNS changes.
- Maximum aggregate container memory 4.125 GiB and CPU reservations are **not** implied;
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
   Create the network with `docker network create edicai_docs_lab_access` if it does not exist.
   Inspect this network before first use; never connect production services or the test DB to it.
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


## Hardening an existing lab with the gateway network topology

**Precondition:** `docker network inspect edicai_docs_lab_access` exists.
**Scope:** test-only containers under the `edicai_docs_lab` Compose project.

1. Review the exact `compose.yaml` and `nginx-docs.conf` from the approved Git commit. Copy them into `docs-portal/testing/` on the VPS; make `nginx-docs.conf` readable (mode 644). Keep the database credentials file mode 600.
2. Before running any Compose command, verify `docker compose --project-name edicai_docs_lab --env-file docs-portal/testing/.env -f docs-portal/testing/compose.yaml config --quiet`.
3. `docker compose --project-name edicai_docs_lab --env-file docs-portal/testing/.env -f docs-portal/testing/compose.yaml up -d --no-deps --force-recreate odoo` to disconnect only Odoo from the access network and remove its direct host published port.
4. `docker compose --project-name edicai_docs_lab --env-file docs-portal/testing/.env -f docs-portal/testing/compose.yaml up -d --no-deps gateway` to launch the reverse proxy. This pulls an official Nginx image if not available locally.
5. Verify the Odoo container is on `sandbox` only, PostgreSQL on `sandbox` only, gateway on both `sandbox` and `access`.
6. Verify that only the gateway publishes `127.0.0.1:18069`, Odoo still responds through that port, and production Odoo remains HTTP 200 on `127.0.0.1:8069`.
7. Verify Odoo **cannot** make `https://example.com` requests. A timeout or DNS failure is not definitive proof, so inspect network attachments and check DNS and network routing too.
8. Do not begin any automated workflows until direct integration egress is confirmed blocked, Odoo business modules are tested and student-document constraint issues reviewed.

Caution: the Nginx gateway itself has internet access, though it holds no ERP integration credentials. Keep it at the documented localhost binding. The gateway must not be configured as an open forward proxy.
