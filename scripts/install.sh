#!/bin/bash
set -e

PROJECT_DIR="$HOME/workspace-manager"
VENV_DIR="$PROJECT_DIR/.venv"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== Workspace Manager Install ==="

# Create venv
echo "Creating Python venv..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install backend dependencies
echo "Installing backend dependencies..."
pip install -q -r "$PROJECT_DIR/backend/requirements.txt"

# Install menubar dependencies
echo "Installing menubar dependencies..."
pip install -q -r "$PROJECT_DIR/menubar/requirements.txt"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Install launchd plists
echo "Installing launchd agents..."

for plist in backend menubar; do
    SRC="$PROJECT_DIR/menubar/launchd/com.workspace-manager.${plist}.plist"
    DEST="$LAUNCH_AGENTS/com.workspace-manager.${plist}.plist"

    # Unload existing if present
    launchctl unload "$DEST" 2>/dev/null || true

    # Replace placeholders
    sed -e "s|__VENV_PATH__|$VENV_DIR|g" \
        -e "s|__PROJECT_PATH__|$PROJECT_DIR|g" \
        "$SRC" > "$DEST"

    # Load
    launchctl load "$DEST"
    echo "  Loaded com.workspace-manager.${plist}"
done

echo ""
echo "=== Installed ==="
echo ""
echo "Backend: http://localhost:8001"
echo "Menu bar: look for ⌂ in your menu bar"
echo "Shelve:   Cmd+Shift+K (global hotkey)"
echo ""
echo "IMPORTANT: You need to grant Accessibility access to Python"
echo "  System Settings > Privacy & Security > Accessibility"
echo "  Add: $VENV_DIR/bin/python3"
echo ""
echo "To name your Spaces, click ⌂ > Rename This Space"
