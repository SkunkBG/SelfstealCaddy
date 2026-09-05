#!/usr/bin/env bash
# Run the live end-to-end check across every registered theme.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
CADDY="${CADDY:-$(command -v caddy || echo ./caddy)}"
PORT="${PORT:-8300}"
FAIL=0
THEMES="${*:-$(python3 -m selfsteal themes --json | python3 -c 'import json,sys; print(" ".join(sorted(json.load(sys.stdin))))')}"
for theme in $THEMES; do
    out="$(timeout 120 bash scripts/live-check.sh "$theme" "$PORT" "$CADDY" 2>&1)"
    if grep -q "all checks passed" <<<"$out"; then
        printf "%-15s OK   %s   %s\n" "$theme" \
            "$(grep -m1 -o 'Variant: .*' <<<"$out")" \
            "$(grep -m1 -oE '[0-9]+ checks, [0-9]+ failed' <<<"$(tail -3 <<<"$out")")"
    else
        printf "%-15s FAIL\n" "$theme"
        grep -E '^FAIL|Error|error:' <<<"$out" | head -8
        FAIL=1
    fi
    PORT=$((PORT + 1))
    export HTTP_PORT=$((PORT + 400))
done
exit "$FAIL"
