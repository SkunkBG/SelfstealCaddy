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
HTTP_PORT="${HTTP_PORT:-$((PORT + 100))}"
CADDY="${3:-$(command -v caddy || echo ./caddy)}"
DOMAIN="${DOMAIN:-check.example.com}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'kill "${CADDY_PID:-0}" 2>/dev/null || true; rm -rf "$WORK"' EXIT

[[ -x "$CADDY" ]] || { echo "caddy binary not found: $CADDY" >&2; exit 127; }

echo "==> generating ($THEME)"
python3 -m selfsteal generate \
    --domain "$DOMAIN" --theme "$THEME" \
    --webroot "$WORK/site" --caddyfile "$WORK/Caddyfile" >"$WORK/summary.txt"
cat "$WORK/summary.txt"

echo "==> offline validation"
python3 -m selfsteal validate --webroot "$WORK/site" --domain "$DOMAIN"

echo "==> rewriting config for local listeners"
python3 - "$WORK/Caddyfile" "$WORK/Caddyfile.local" "$DOMAIN" "$PORT" "$HTTP_PORT" <<'REWRITE'
import re, sys
src, dst, domain, port, http_port = sys.argv[1:6]
text = open(src, encoding="utf-8").read()
# Move both listeners to unprivileged local ports and issue a self-signed
# certificate instead of talking to ACME. The :80 block is relocated rather
# than deleted: it is the only surface a real prober can reach, so the checks
# that it strips Server and keeps the backend port out of Location need
# something to run against. The hostname site address is kept on purpose --
# probes must exercise the same SNI-matched vhost the installer checks in
# production.
text = text.replace("\thttp_port 80\n", f"\thttp_port {http_port}\n")
text = text.replace(f"{domain}:80 {{", f"{domain}:{http_port} {{")
text = text.replace(f"{domain}:8443 {{", f"{domain}:{port} {{")
text = re.sub(r"\ttls \{\n\t\tissuer acme \{\n.*?\n\t\t\}\n\t\}\n",
              "\ttls internal\n", text, flags=re.S)
text = text.replace("\tadmin unix//run/caddy/admin.sock", "\tadmin off")
open(dst, "w", encoding="utf-8").write(text)
REWRITE

"$CADDY" validate --config "$WORK/Caddyfile.local" >/dev/null 2>&1 \
    || { "$CADDY" validate --config "$WORK/Caddyfile.local"; exit 1; }

echo "==> starting caddy on :$PORT (https) and :$HTTP_PORT (redirect)"
"$CADDY" run --config "$WORK/Caddyfile.local" >"$WORK/caddy.log" 2>&1 &
CADDY_PID=$!
for _ in $(seq 1 40); do
    curl -fsSk --resolve "$DOMAIN:$PORT:127.0.0.1" \
        -o /dev/null "https://$DOMAIN:$PORT/" 2>/dev/null && break
    sleep 0.4
done

echo "==> live probes"
cd "$ROOT"
python3 -m selfsteal validate \
    --webroot "$WORK/site" --domain "$DOMAIN" \
    --base-url "https://$DOMAIN:$PORT" \
    --http-url "http://$DOMAIN:$HTTP_PORT" \
    --https-port "$PORT" --connect 127.0.0.1

echo "==> all checks passed"
