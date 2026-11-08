#!/usr/bin/env bash
# Purpose-built, isolated Odoo 19 documentation test deployment.
# This script does NOT touch the existing systemd Odoo/Postgres/Nginx services.
# Run manually on the Hostinger VPS as root after reviewing the source.
set -Eeuo pipefail
umask 077

SOURCE_REPO="https://github.com/yashmakwana61/unicore.git"
SOURCE_SHA="ec4a9de74b2c2961faecb649d1f84417f31002d4"
TARGET="/opt/edicai-docs-lab"
PROJECT="edicai_docs_lab"
PORT="18069"

note() { printf '[Edicai docs lab] %s\n' "$*"; }
fail() { printf '[Edicai docs lab] BLOCKED: %s\n' "$*" >&2; exit 1; }
command -v docker >/dev/null || fail "Docker must be installed."
command -v git >/dev/null || fail "Git must be installed."
command -v openssl >/dev/null || fail "OpenSSL must be installed."
command -v curl >/dev/null || fail "Curl must be installed."
command -v ss >/dev/null || fail "ss utility must be installed."
[ "$(id -u)" -eq 0 ] || fail "Run as root to install under /opt."
docker info >/dev/null 2>&1 || fail "Docker daemon is inaccessible."
docker compose version >/dev/null || fail "Docker Compose is inaccessible."

for svc in odoo19.service postgresql@16-main.service nginx.service; do
  [ "$(systemctl is-active "$svc")" = "active" ] || fail "Production service $svc is not active."
done
HTTP="$(curl -sS -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8069/web/login)" || fail "Production Odoo health request failed."
[ "$HTTP" = "200" ] || fail "Production Odoo health returned HTTP $HTTP instead of 200."

if ss -ltn | grep -Eq '([.:]18069)[[:space:]]'; then
  fail "Port 18069 is occupied."
fi
AVAILABLE_KIB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
[ "$AVAILABLE_KIB" -ge 6291456 ] || fail "Less than 6 GiB of available RAM."
AVAILABLE_DISK_KIB="$(df -Pk / | awk 'NR==2 {print $4}')"
[ "$AVAILABLE_DISK_KIB" -ge 31457280 ] || fail "Less than 30 GiB of disk free."
[ ! -e "$TARGET" ] || fail "Destination already exists at $TARGET; refusing to overwrite."
[ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")" ] || fail "Test project $PROJECT already has containers."

note "Production status, port, memory, disk and project isolation checks passed."
note "Cloning an independent source checkout into $TARGET (production checkout remains untouched)."
git clone --quiet "$SOURCE_REPO" "$TARGET"
git -C "$TARGET" -c advice.detachedHead=false checkout --quiet "$SOURCE_SHA"
[ "$(git -C "$TARGET" rev-parse HEAD)" = "$SOURCE_SHA" ] || fail "Unexpected Git revision."
[ -d "$TARGET/custom_addons/edicai_admission" ] || fail "Expected Edicai admission addon missing."
cd "$TARGET"

SECRET="$(openssl rand -hex 32)"
ENVFILE="$TARGET/docs-portal/testing/.env"
printf 'EDICAI_DOCS_DB_PASSWORD=%s\nEDICAI_DOCS_PORT=%s\n' "$SECRET" "$PORT" > "$ENVFILE"
chmod 600 "$ENVFILE"
unset SECRET
compose() {
  docker compose --project-name "$PROJECT" --env-file "$ENVFILE" -f docs-portal/testing/compose.yaml "$@"
}

note "Validating Compose structure and test-only environment."
compose config --quiet
note "Building isolated Edicai Odoo 19 image from pinned source (no production image changes)."
compose build odoo
note "Starting independent synthetic-data PostgreSQL container."
compose up -d database
for attempt in $(seq 1 60); do
  if compose exec -T database pg_isready -U docs_odoo -d edicai_docs_test >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose exec -T database pg_isready -U docs_odoo -d edicai_docs_test >/dev/null || fail "Test database not ready."

note "Installing Edicai Admissions and its dependency addons into the NEW test database only."
compose run --rm --no-deps odoo \
  odoo -c /etc/odoo/odoo.conf -d edicai_docs_test \
    -i edicai_admission --without-demo=all --stop-after-init

note "Starting isolated Odoo service on 127.0.0.1:$PORT."
compose up -d odoo
READY=0
for attempt in $(seq 1 60); do
  STATUS="$(curl -s -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/web/login" || true)"
  if [ "$STATUS" = "200" ]; then READY=1; break; fi
  sleep 3
done
[ "$READY" = "1" ] || fail "Test Odoo login did not become HTTP 200; inspect Compose logs."

note "Rechecking production Odoo login."
STATUS="$(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8069/web/login)" || fail "Production health check failed after testing deployment."
[ "$STATUS" = "200" ] || fail "Production login returned HTTP $STATUS after deployment."
note "SUCCESS: test Odoo is reachable on 127.0.0.1:$PORT; production Odoo still HTTP 200."
note "Access only using an operator-controlled SSH tunnel. No public DNS added."
note "Change any default Odoo database administrator credentials before sharing access."
