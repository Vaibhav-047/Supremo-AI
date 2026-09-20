#!/bin/bash
# Build the Supremo DMG app bundle
# Run: bash build_dmg.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Downloads/Supremo.app"
DMG_PATH="$HOME/Downloads/Supremo.dmg"

# Step 1: Clean and create app bundle structure
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Step 2: Copy Python source files
cp "$SCRIPT_DIR/supremo.py"  "$APP_DIR/Contents/Resources/"
cp "$SCRIPT_DIR/jarvis.py"  "$APP_DIR/Contents/Resources/"
cp "$SCRIPT_DIR/main.py"    "$APP_DIR/Contents/Resources/"
cp "$SCRIPT_DIR/config.py"  "$APP_DIR/Contents/Resources/"
cp "$SCRIPT_DIR/requirements.txt" "$APP_DIR/Contents/Resources/"

# Step 3: Copy launcher script with EXECUTE permissions
cp "$SCRIPT_DIR/launcher.sh" "$APP_DIR/Contents/MacOS/Supremo"
chmod 755 "$APP_DIR/Contents/MacOS/Supremo"

# Step 4: Copy Info.plist
cp "$SCRIPT_DIR/Info.plist" "$APP_DIR/Contents/Info.plist"

# Step 5: Clean any __pycache__
find "$APP_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Step 6: Remove old DMG
rm -f "$DMG_PATH"

# Step 7: Build DMG
hdiutil create -volname "Supremo AI" \
    -srcfolder "$APP_DIR" \
    -srcfolder "$SCRIPT_DIR/README.md" \
    -fs HFS+ -fsargs "-c c=64,a=16,e=16" \
    -format UDBZ -size 100m "$DMG_PATH"

echo "✅ DMG built: $DMG_PATH ($(stat -f%z "$DMG_PATH") bytes)"
