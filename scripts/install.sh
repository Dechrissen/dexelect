#!/bin/bash
set -e

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/.local/share/dexelect"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "Installing Dexelect..."

mkdir -p "$APP_DIR" "$BIN_DIR" "$ICON_DIR" "$DESKTOP_DIR"

# Wipe old install and replace — this is also how updates work
rm -rf "$APP_DIR"
cp -r "$SRC_DIR/." "$APP_DIR"
chmod +x "$APP_DIR/dexelect"

# Symlink into ~/.local/bin so it's runnable from a terminal
ln -sf "$APP_DIR/dexelect" "$BIN_DIR/dexelect"

# Install icon into the hicolor theme
cp "$APP_DIR/assets/icons/256.png" "$ICON_DIR/dexelect.png"

# Write .desktop file pointing at the stable installed location
cat > "$DESKTOP_DIR/dexelect.desktop" << EOF
[Desktop Entry]
Name=Dexelect
Comment=Progression-aware Pokémon party generator
Exec=$APP_DIR/dexelect
Icon=dexelect
Type=Application
Categories=Utility;
Terminal=false
StartupWMClass=dexelect
EOF

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "Installed to: $APP_DIR"
echo "You can delete the downloaded folder."
echo ""
echo "To update: download the new version, run ./install.sh from it — done."
echo ""
echo "To uninstall:"
echo "  rm -rf ~/.local/share/dexelect"
echo "  rm -f ~/.local/bin/dexelect ~/.local/share/applications/dexelect.desktop ~/.local/share/icons/hicolor/256x256/apps/dexelect.png"
