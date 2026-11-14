#!/bin/bash
# Compile the small AppKit front end and embed an independently checksum-verified
# prebuilt, hardware-scoped driver release. No GPU code is compiled here.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${1:-$ROOT/build/apps}"
DRIVER="${2:-}"
CHECKSUMS="${3:-}"
APP="$DEST/NullArcInstaller.app"
SDK="$(xcrun --sdk macosx --show-sdk-path)"

if [[ -e "$APP" ]]; then
  echo "Refusing to overwrite existing app: $APP" >&2
  exit 1
fi
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$ROOT/apps/NullArcInstaller/Info.plist" "$APP/Contents/Info.plist"
if [[ -n "$DRIVER" || -n "$CHECKSUMS" ]]; then
  [[ -f "$DRIVER" && -f "$CHECKSUMS" ]] || { echo "Specify both existing release ZIP and checksum" >&2; exit 1; }
  [[ "$(basename "$DRIVER")" == "nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip" ]] || {
    echo "Unrecognized pinned compiled driver ZIP" >&2; exit 1;
  }
  [[ "$(basename "$CHECKSUMS")" == "SHA256SUMS-startup-readiness" ]] || {
    echo "Unexpected compiled release checksum filename" >&2; exit 1;
  }
  expected="$(awk '$2 == "nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip" {print $1}' "$CHECKSUMS")"
  [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || { echo "Invalid release SHA256" >&2; exit 1; }
  actual="$(shasum -a 256 "$DRIVER" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || { echo "Compiled driver release checksum mismatch" >&2; exit 1; }
  cp "$DRIVER" "$APP/Contents/Resources/"
  cp "$CHECKSUMS" "$APP/Contents/Resources/"
  echo "Bundled independently verified precompiled 0.2.0 driver release."
else
  echo "Development GUI only: driver ZIP not embedded. Use the official precompiled app release."
fi
xcrun swiftc -swift-version 5 -O -target x86_64-apple-macos12.0 -sdk "$SDK" \
  -framework AppKit "$ROOT/apps/NullArcInstaller/main.swift" \
  -o "$APP/Contents/MacOS/NullArcInstaller"
chmod 755 "$APP/Contents/MacOS/NullArcInstaller"
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --strict "$APP"
echo "Built $APP (x86_64) — GUI and optional precompiled driver; no native GPU code compiled."
