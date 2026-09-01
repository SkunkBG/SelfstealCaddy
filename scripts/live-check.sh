#!/usr/bin/env bash
# End-to-end check: generate a site, serve it with a real Caddy on a local
# port, and run the HTTP contract probes against it.
#
#   scripts/live-check.sh [theme] [port] [caddy-binary]
#
# Requires a caddy binary on PATH (or passed as $3). Exits non-zero on the
# first failed probe, so it is usable as a CI gate.

set -euo pipefail

THEME="${1:-random}"
PORT="${2:-8099}"
CADDY="${3:-$(command -v caddy || echo ./caddy)}"
DOMAIN="${DOMAIN:-check.example.com}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'kill "${CADDY_PID:-0}" 2>/dev/null || true; rm -rf "$WORK"' EXIT

[[ -x "$CADDY" ]] || { echo "caddy binary not found: $CADDY" >&2; exit 127; }

echo "==> generating ($THEME)"
python3 -m selfsteal generate \
    --domain "$DOMAIN" --theme "$THEME" \
    --webroot "$WORK/site" --caddyfile "$WORK/Caddyfile" \
    --dry-run >"$WORK/summary.txt"
cat "$WORK/summary.txt"

echo "==> offline validation"
python3 -m selfsteal validate --webroot "$WORK/site" --domain "$DOMAIN"

echo "==> rewriting config for a local plaintext listener"
python3 - "$WORK/Caddyfile" "$WORK/Caddyfile.local" "$DOMAIN" "$PORT" <<'PY'
import re, sys
src, dst, domain, port = sys.argv[1:5]
text = open(src, encoding="utf-8").read()
# Drop the :80 redirect block and bind the site block to a plain local port so
# the probes exercise the same routes without ACME or TLS in the way.
text = re.sub(rf"^# Public :80.*?^}}\n\n", "", text, flags=re.S | re.M)
text = text.replace(f"{domain}:8443 {{", f":{port} {{")
text = text.replace("\tadmin unix//run/caddy/admin.sock", "\tadmin off")
text = text.replace("{\n\tadmin off", "{\n\tadmin off\n\tauto_https off")
open(dst, "w", encoding="utf-8").write(text)
PY

"$CADDY" validate --config "$WORK/Caddyfile.local" >/dev/null 2>&1 \
    || { "$CADDY" validate --config "$WORK/Caddyfile.local"; exit 1; }

echo "==> starting caddy on :$PORT"
"$CADDY" run --config "$WORK/Caddyfile.local" >"$WORK/caddy.log" 2>&1 &
CADDY_PID=$!
for _ in $(seq 1 30); do
    curl -fsS -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null && break
    sleep 0.3
done

echo "==> live probes"
cd "$ROOT"
python3 -m selfsteal validate \
    --webroot "$WORK/site" --domain "$DOMAIN" \
    --base-url "http://127.0.0.1:$PORT"

echo "==> all checks passed"
