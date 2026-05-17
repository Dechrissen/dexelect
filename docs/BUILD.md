# Building the Dexelect GUI binary locally

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