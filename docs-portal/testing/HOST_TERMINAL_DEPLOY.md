# Approved host-terminal deployment path

Hostinger's Docker API cannot build the custom Edicai image from the repository, so the test
deployment must use Docker Compose directly **on the VPS**. This script is intended to be
reviewed and launched by the server owner through Hostinger's Browser Terminal.

- Read-only guards verify production health, available RAM/disk, port 18069 and project uniqueness.
- Clone source at an exact Git revision into `/opt/edicai-docs-lab`, never the production source directory.
- Generate a unique PostgreSQL password; do not print or commit it.
- Build a dedicated test image and use separate Compose project, database and volumes.
- Initialize only `edicai_docs_test` with the Admissions addon and declared dependencies.
- Run test Odoo on `127.0.0.1:18069` and recheck production Odoo HTTP 200 afterward.
- No public DNS, test domain, real data, production filestore or outbound integration credentials.

To execute from the host terminal, inspect the script first, then use its raw
GitHub URL from the approved commit. Do not launch this deployment through the
generic Hostinger Docker UI, which does not build local images.

## Recovery
If the build or module installation fails, **do not** delete or recreate production
services. Inspect `docker compose --project-name edicai_docs_lab --env-file
/opt/edicai-docs-lab/docs-portal/testing/.env -f
/opt/edicai-docs-lab/docs-portal/testing/compose.yaml logs`.
The test-only stack may be stopped using a matching Compose project name,
without invoking production service commands.

Note: container images and test data may exist after a partial run. Do not run the
script twice without inspecting or safely cleaning up the isolated project. Production
service health must remain the primary condition for continuation.
