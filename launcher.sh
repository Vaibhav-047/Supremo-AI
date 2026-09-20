#!/bin/bash
# Supremo app launcher for macOS .app bundle
# Run with: python3 main.py  (from the app bundle's Resources directory)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOURCES_DIR="$(dirname "$SCRIPT_DIR")/Resources"

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$RESOURCES_DIR"

# Detect system architecture
SYS_ARCH=$(uname -m)

# Prefer Python 3.10+ (system python3 on macOS 26+ crashes on 3.9)
if [ -x "/usr/local/bin/python3" ]; then
    PYTHON="/usr/local/bin/python3"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON="/opt/homebrew/bin/python3"
else
    PYTHON="python3"
fi

# On Apple Silicon, force native arm64 to match installed packages.
# Without this, Python may launch under Rosetta (x86_64) and fail to load
# arm64 C extensions like pyaudio/audioop-lts.
if [ "$SYS_ARCH" = "arm64" ]; then
    PY_ARCH=$("$PYTHON" -c "import platform; print(platform.machine())" 2>/dev/null)
    if [ "$PY_ARCH" = "x86_64" ]; then
        # Python is running under Rosetta; force native arm64
        exec arch -arm64 "$PYTHON" "$RESOURCES_DIR/main.py" "$@"
    fi
fi

exec "$PYTHON" "$RESOURCES_DIR/main.py" "$@"
