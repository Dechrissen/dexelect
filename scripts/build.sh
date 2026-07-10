#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "Building Dexelect..."

# Create venv if missing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

.venv/bin/pip install -r requirements.txt

# Fetch sprites (idempotent — skips ones that already exist)
.venv/bin/python scripts/fetch_sprites.py

.venv/bin/pyinstaller --clean --noconfirm dexelect.spec

# Stage install.sh alongside the built binary, same as the release zip does,
# so it can be run from dist/dexelect/ to register a desktop launcher entry.
cp scripts/install.sh dist/dexelect/install.sh
chmod +x dist/dexelect/install.sh

echo ""
echo "Built: $REPO_ROOT/dist/dexelect/"
echo "To register a desktop launcher entry: cd dist/dexelect && ./install.sh"
