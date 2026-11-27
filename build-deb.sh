#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VERSION=2.0.1
PACKAGE=kimi-code-arm64
OUTPUT="$ROOT/dist/${PACKAGE}_${VERSION}_arm64.deb"
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

install -Dm755 "$ROOT/kimi_code_arm64.py" "$STAGING/usr/lib/kimi-code-arm64/kimi_code_arm64.py"
install -Dm755 "$ROOT/cdp_bridge.py" "$STAGING/usr/lib/kimi-code-arm64/cdp_bridge.py"
install -Dm644 "$ROOT/cdp_bridge.js" "$STAGING/usr/lib/kimi-code-arm64/cdp_bridge.js"
install -Dm755 "$ROOT/packaging/kimi-code-arm64" "$STAGING/usr/bin/kimi-code-arm64"
install -Dm644 "$ROOT/kimi-code-arm64.desktop" "$STAGING/usr/share/applications/kimi-code-arm64.desktop"
install -Dm644 "$ROOT/kimi-code-arm64.svg" "$STAGING/usr/share/icons/hicolor/scalable/apps/kimi-code-arm64.svg"
install -Dm644 "$ROOT/packaging/control" "$STAGING/DEBIAN/control"

mkdir -p "$ROOT/dist"
dpkg-deb --root-owner-group --build "$STAGING" "$OUTPUT"
printf '%s\n' "$OUTPUT"
