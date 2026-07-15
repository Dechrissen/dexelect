# Building the Dexelect GUI binary locally

## Building

Prerequisites:
- Python 3.11+

Steps to build:
1. `git clone https://github.com/Dechrissen/dexelect.git`
2. `cd dexelect`
3. `./scripts/build.sh`

This creates a `.venv` (if one doesn't already exist), installs dependencies, downloads sprites into
`assets/sprites/` (skipping any that already exist), and builds the executable with PyInstaller.

Alternatively, as a single copy-pasteable command:
```bash
git clone https://github.com/Dechrissen/dexelect.git && cd dexelect && ./scripts/build.sh
```

Output binary will be in `dist/dexelect/` (run `./dexelect` on Linux; `dexelect.exe` on Windows).

## Installing into your desktop environment (Linux only)

`scripts/build.sh` stages a copy of `scripts/install.sh` into `dist/dexelect/` after building. Run it from
there to register Dexelect as a desktop launcher entry (e.g. rofi, wofi, dmenu):

```bash
cd dist/dexelect && ./install.sh
```

### One-liner
```bash
git clone https://github.com/Dechrissen/dexelect.git && cd dexelect && ./scripts/build.sh && cd dist/dexelect && ./install.sh
```

This copies the built app to `~/.local/share/dexelect/`, symlinks the binary onto your `$PATH` via
`~/.local/bin/`, and registers a `.desktop` entry so the app appears in launchers.