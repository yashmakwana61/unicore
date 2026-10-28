# EDICAI — Docker Deployment Guide

Deploy the EDICAI (Odoo 19) system to any server with Docker and GitHub.

## Architecture

```
GitHub repo (this directory: unicore/)
  └── server: git clone → .env → docker compose up
        ├── caddy   (optional profile)  :80/:443 → automatic HTTPS
        ├── web     edicai-odoo:19      Odoo 19 + custom_addons baked in
        └── db      postgres:16         data in named volume
```

Custom addons are **baked into the image** at build time (no bind mounts in prod),
so what runs is exactly what's in the repo.

## 1. Server prerequisites (Ubuntu VPS)

```bash
# Install Docker Engine + compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # then re-login
```

## 2. First deployment

```bash
git clone git@github.com:<you>/<repo>.git edicai && cd edicai
cp .env.example .env
nano .env          # set EDICAI_DB_PASSWORD (openssl rand -base64 24), DOMAIN, ACME_EMAIL

# Fresh database (no data yet):
./init-db.sh       # installs all modules in dependency order, one-shot
docker compose --profile proxy up -d    # web + db + automatic HTTPS proxy
```

## 3. Point the domain (you do this)

1. DNS: create an `A` record for `your.domain.com` → server IP.
2. `.env` must have the same value in `DOMAIN=`.
3. `docker compose --profile proxy up -d` — Caddy obtains a Let's Encrypt
   certificate automatically on first request. Done: `https://your.domain.com`.

> If you already run your own reverse proxy (nginx/traefik), skip the `proxy`
> profile and set `HTTP_BIND=0.0.0.0` in `.env` instead; proxy to port 8069.

## 4. Migrating the existing database (has real data, pre-rebrand)

The old database was created when modules were named `oacis_*`. Its registry
rows must be renamed to match the new `edicai_*` module directories.

On the dev machine (WSL), dump it:

```bash
pg_dump -U yashmakwana -Fc oacis > oacis.dump     # local postgres
# or if it lived in docker: docker compose exec -T db pg_dump -U odoo -Fc oacis > oacis.dump
```

On the server:

```bash
docker compose up -d db
docker compose exec -T db pg_restore -U "$EDICAI_DB_USER" -d "$EDICAI_DB_NAME" --no-owner < oacis.dump
docker compose exec -T db psql -U "$EDICAI_DB_USER" -d "$EDICAI_DB_NAME" < scripts/migrate-db-rebrand.sql
# Rebuild the module registry view + upgrade base custom module:
docker compose run --rm --no-deps web odoo -c /etc/odoo/odoo.conf -d "$EDICAI_DB_NAME" -u edicai_base --stop-after-init
docker compose --profile proxy up -d
```

## 5. Deploying updates (CI-style flow)

```bash
cd edicai
git pull
docker compose build web
docker compose run --rm --no-deps web odoo -c /etc/odoo/odoo.conf -d "$EDICAI_DB_NAME" -u edicai_base --stop-after-init
docker compose up -d web      # swaps to the new image
```

## 6. Backups

```bash
# Dump (cron-able):
docker compose exec -T db pg_dump -U "$EDICAI_DB_USER" -Fc "$EDICAI_DB_NAME" > "backup_$(date +%F).dump"
# Filestore (attachments) lives in the odoo-web-data volume:
docker run --rm -v edicai_odoo-web-data:/data -v "$PWD":/out alpine \
  tar czf /out/filestore_$(date +%F).tgz -C /data filestore
```

Restore = `pg_restore` the dump + untar filestore into the volume.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `502` from Caddy | `docker compose logs web` — Odoo still starting (healthcheck start_period 90s) |
| Modules listed as "unavailable" | DB rows still say `oacis_*` → run `scripts/migrate-db-rebrand.sql` |
| Assets 404 / broken styling | Same cause (ir_asset URLs) → rerun the SQL + `-u edicai_base` |
| Let's Encrypt fails | DNS A record wrong, or port 80 blocked — Caddy needs both |
| Forgot admin master password | It's disabled in prod configs by design (`admin_passwd = False`) |

## Local development (this WSL machine)

Docker Desktop must share with this Ubuntu distro: Docker Desktop →
Settings → Resources → WSL Integration → enable `Ubuntu`. Then run the same
commands from `unicore/` (use the `dev` profile to live-mount addons).
