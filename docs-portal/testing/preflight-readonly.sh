#!/usr/bin/env bash
# Read-only host inspection: intentionally no install, write, docker up, or service restart.
set -u
printf '%s\n' '===== Edicai docs test: VPS read-only preflight ====='
date -u || true
printf '\n[Hostname / uptime]\n'
hostname || true
uptime || true
printf '\n[Memory]\n'
free -h || true
printf '\n[Storage / inodes]\n'
df -hT || true
df -ih || true
printf '\n[Block devices]\n'
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS || true
printf '\n[Running services]\n'
systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | sed -n '1,100p' || true
printf '\n[TCP listeners; verify no conflict on 18069/8069/8072/5432/80/443]\n'
ss -lnt 2>/dev/null || true
printf '\n[Firewall status - read only]\n'
if command -v ufw >/dev/null 2>&1; then ufw status 2>/dev/null || true; fi
if command -v nft >/dev/null 2>&1; then nft list ruleset 2>/dev/null | sed -n '1,140p' || true; fi
printf '\n[Docker availability and running containers]\n'
if command -v docker >/dev/null 2>&1; then
  docker --version || true
  docker compose version || true
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || true
else
  echo 'Docker executable not installed or not on PATH'
fi
printf '\n[Odoo / Postgres / reverse proxy services by name]\n'
systemctl list-unit-files --type=service --no-pager 2>/dev/null | grep -Ei 'odoo|postgres|nginx|caddy|traefik' || true
printf '\n[Kernel OOM events, last 7 days, if accessible]\n'
journalctl -k --since '7 days ago' --no-pager 2>/dev/null | grep -Ei 'oom-killer|out of memory|killed process' | tail -n 20 || true
printf '\n[Preflight complete: NO changes made]\n'
