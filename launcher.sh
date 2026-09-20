#!/bin/bash
# Supremo app launcher for macOS .app bundle
# Run with: python3 main.py  (from the app bundle's Resources directory)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES_DIR="$(dirname "$SCRIPT_DIR")/Contents/Resources"

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$RESOURCES_DIR"

# Prefer Python 3.10+ (system python3 on macOS 26+ crashes on 3.9)
if [ -x "/usr/local/bin/python3" ]; then
    PYTHON="/usr/local/bin/python3"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON="/opt/homebrew/bin/python3"
else
    PYTHON="python3"
fi

exec "$PYTHON" "$RESOURCES_DIR/main.py" "$@"
