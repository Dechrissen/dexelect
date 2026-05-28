# Building the Dexelect GUI binary locally

## Building

Prerequisites:
- Python 3.10+

Steps to build:
1. `git clone https://github.com/Dechrissen/dexelect.git`
2. `cd dexelect`
3. Create a virtual environment (`python -m venv .venv`)
4. Activate it (`source .venv/bin/activate`)
5. `pip install -r requirements.txt` — installs everything including PyInstaller
6. `python scripts/fetch_sprites.py` — downloads sprites into `assets/sprites/`
7. `pyinstaller dexelect.spec` — builds the executable

Output binary will be in `dist/dexelect/` (`dexelect` on Linux; `dexelect.exe` on Windows).

## Installing into your desktop environment (Linux only)

After building, you can integrate the app into your desktop environment manually:

```bash
APP_DIR="$HOME/.local/share/dexelect"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$APP_DIR" "$BIN_DIR" "$ICON_DIR" "$DESKTOP_DIR"

cp -r dist/dexelect/. "$APP_DIR"
chmod +x "$APP_DIR/dexelect"
ln -sf "$APP_DIR/dexelect" "$BIN_DIR/dexelect"
cp "$APP_DIR/assets/icons/256.png" "$ICON_DIR/dexelect.png"

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
```

This copies the built app to `~/.local/share/dexelect/`, symlinks the binary onto your `$PATH` via `~/.local/bin/`, and registers a `.desktop` entry so the app appears in launchers.