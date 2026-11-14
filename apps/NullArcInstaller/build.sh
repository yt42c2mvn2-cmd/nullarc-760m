#!/bin/bash
# Small x86_64 AppKit app; no Xcode project, Swift packages, third-party
# frameworks, embedded drivers or privileged helper service.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${1:-$ROOT/build/apps}"
APP="$DEST/NullArcInstaller.app"
SDK="$(xcrun --sdk macosx --show-sdk-path)"
mkdir -p "$DEST"
if [[ -e "$APP" ]]; then
  echo "Refusing to overwrite existing app: $APP" >&2
  exit 1
fi
mkdir -p "$APP/Contents/MacOS"
cp "$ROOT/apps/NullArcInstaller/Info.plist" "$APP/Contents/Info.plist"
xcrun swiftc -swift-version 5 -O -target x86_64-apple-macos12.0 -sdk "$SDK" \
  -framework AppKit "$ROOT/apps/NullArcInstaller/main.swift" \
  -o "$APP/Contents/MacOS/NullArcInstaller"
chmod 755 "$APP/Contents/MacOS/NullArcInstaller"
codesign --force --sign - --timestamp=none "$APP"
codesign --verify --strict "$APP"
echo "Built $APP (x86_64). No GPU driver was built, installed or loaded."
