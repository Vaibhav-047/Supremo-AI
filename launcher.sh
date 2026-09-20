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

# On Apple Silicon, ensure Python matches system architecture to avoid
# arm64/x86_64 mismatch with compiled C extensions (e.g., pyaudio, audioop-lts).
# When .app bundles launch, macOS may run Python under Rosetta (x86_64),
# but packages like pyaudio are compiled for native arm64.
if [ "$SYS_ARCH" = "arm64" ]; then
    PY_ARCH=$("$PYTHON" -c "import platform; print(platform.machine())" 2>/dev/null)
    if [ "$PY_ARCH" = "x86_64" ]; then
        # Python is x86_64 under Rosetta; try forcing arm64
        if arch -arm64 "$PYTHON" -c "pass" 2>/dev/null; then
            exec arch -arm64 "$PYTHON" "$RESOURCES_DIR/main.py" "$@"
        fi
        # Fallback: try arm64 Homebrew Python if available
        if [ -x "/opt/homebrew/bin/python3" ]; then
            HB_ARCH=$(/opt/homebrew/bin/python3 -c "import platform; print(platform.machine())" 2>/dev/null)
            if [ "$HB_ARCH" = "arm64" ]; then
                PYTHON="/opt/homebrew/bin/python3"
            fi
        fi
    fi
fi

exec "$PYTHON" "$RESOURCES_DIR/main.py" "$@"
