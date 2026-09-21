#!/bin/bash
# Supremo — Linux build script
# Creates a distributable .tar.gz with a GUI launcher and CLI entry point

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_NAME="Supremo-Linux-v3.0"
DIST_DIR="$SCRIPT_DIR/$BUILD_NAME"
ARCHIVE="$SCRIPT_DIR/${BUILD_NAME}.tar.gz"

echo "=== Building Supremo for Linux ==="

# Clean previous build
rm -rf "$DIST_DIR" "$ARCHIVE"
mkdir -p "$DIST_DIR"

# Copy required files
cp supremo.py jarvis.py main.py config.py requirements.txt diagnose_voice.py "$DIST_DIR/"

# Create install script
cat > "$DIST_DIR/install.sh" << 'INSTALL'
#!/bin/bash
echo "Installing Supremo dependencies..."
pip3 install -r requirements.txt
echo "Done! Run with:"
echo "  python3 main.py        # GUI mode"
echo "  python3 main.py --cli  # CLI mode"
INSTALL
chmod +x "$DIST_DIR/install.sh"

# Create GUI launcher (desktop entry)
cat > "$DIST_DIR/Supremo.desktop" << 'DESKTOP'
[Desktop Entry]
Name=Supremo
Comment=Desktop Management AI
Exec=python3 /path/to/Supremo/main.py
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;
DESKTOP

# Create run script
cat > "$DIST_DIR/run.sh" << 'RUN'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
python3 main.py "$@"
RUN
chmod +x "$DIST_DIR/run.sh"

# Create tar.gz
cd "$SCRIPT_DIR"
tar czf "$ARCHIVE" "$BUILD_NAME"

echo ""
echo "=== Build complete ==="
echo "Archive: $ARCHIVE"
echo "Size: $(stat -c%s "$ARCHIVE" 2>/dev/null || stat -f%z "$ARCHIVE") bytes"
echo ""
echo "To install:"
echo "  tar xzf $ARCHIVE"
echo "  cd $BUILD_NAME"
echo "  ./install.sh"
echo "  ./run.sh        # GUI mode"
echo "  ./run.sh --cli  # CLI mode"
