#!/usr/bin/env bash
# Build a single-file release artifact.
#
#   scripts/bundle.sh [output]        # default: dist/selfsteal-setup.sh
#
# The result is the installer with a base64 tar.gz of the selfsteal package
# appended after a marker line. It runs anywhere `bash <(curl ...)` runs and
# needs nothing from the repository, which is what keeps the one-liner install
# working now that the source is multi-file.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/dist/selfsteal-setup.sh}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cd "$ROOT"
mkdir -p "$(dirname "$OUT")"

# Deterministic archive: identical sources must produce an identical artifact,
# so a release can be reproduced and diffed.
find selfsteal -name '__pycache__' -prune -o -type f -name '*.py' -print \
    | LC_ALL=C sort > "$WORK/files"

tar --create --gzip \
    --owner=0 --group=0 --numeric-owner --mtime='UTC 2020-01-01' \
    --format=gnu --files-from="$WORK/files" > "$WORK/payload.tar.gz"

{
    cat selfsteal-setup.sh
    printf '\n#__SELFSTEAL_PAYLOAD__\n'
    base64 -w 76 "$WORK/payload.tar.gz"
} > "$OUT"
chmod +x "$OUT"

# Verify the artifact actually self-extracts and generates, rather than
# shipping something that only looks right.
CHECK="$(mktemp -d)"
DRY_RUN=1 DOMAIN=bundle-check.example.com STUB_THEME=media-api \
    WEBROOT="$CHECK/site" CADDYFILE="$CHECK/Caddyfile" \
    bash "$OUT" >"$CHECK/log" 2>&1 || { cat "$CHECK/log"; rm -rf "$CHECK"; exit 1; }
grep -q "0 failed" "$CHECK/log" || { cat "$CHECK/log"; rm -rf "$CHECK"; exit 1; }
rm -rf "$CHECK"

printf 'built %s (%s bytes, sha256 %s)\n' \
    "$OUT" "$(stat -c%s "$OUT")" "$(sha256sum "$OUT" | cut -d' ' -f1)"
