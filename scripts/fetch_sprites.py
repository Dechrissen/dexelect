#!/usr/bin/env python3
"""
fetch_sprites.py

Downloads front-facing Pokémon sprites from the PokeAPI sprites GitHub repo
for Gen 1 (Red/Blue), Gen 2 (Gold/Silver), Gen 3 (Ruby/Sapphire), and Gen 4 (Diamond/Pearl).

Output structure:
  assets/sprites/
    gen1/   # Red/Blue,  Pokémon #001 – #151
    gen2/   # Gold,      Pokémon #001 – #251
    gen3/   # Ruby,      Pokémon #001 – #386
    gen4/   # Diamond/Pearl, Pokémon #001 – #493

Usage:
  python fetch_sprites.py

Optional flags:
  --gens 1 2 3 4    Download only specific generations (default: all)
"""

import argparse
import time
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions"

GENS = {
    1: {
        "folder": "gen1",
        "url_path": "generation-i/red-blue",
        "range": range(1, 152),          # 001 – 151
        "label": "Gen 1 (Red/Blue)",
    },
    2: {
        "folder": "gen2",
        "url_path": "generation-ii/gold",
        "range": range(1, 252),          # 001 – 251
        "label": "Gen 2 (Gold)",
    },
    3: {
        "folder": "gen3",
        "url_path": "generation-iii/ruby-sapphire",
        "range": range(1, 387),          # 001 – 386
        "label": "Gen 3 (Ruby/Sapphire)",
    },
    4: {
        "folder": "gen4",
        "url_path": "generation-iv/diamond-pearl",
        "range": range(1, 494),          # 001 – 493
        "label": "Gen 4 (Diamond/Pearl)",
    },
}

RETRY_ATTEMPTS = 3
RETRY_DELAY    = 2   # seconds between retries
REQUEST_DELAY  = 0.05  # seconds between successful downloads (be polite)

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, attempts: int = RETRY_ATTEMPTS) -> bool:
    """Download a single file with retries. Returns True on success."""
    for attempt in range(1, attempts + 1):
        try:
            urllib.request.urlretrieve(url, dest)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False   # sprite simply doesn't exist — not a real error
            print(f"  HTTP {e.code} on attempt {attempt}/{attempts}: {url}")
        except Exception as e:
            print(f"  Error on attempt {attempt}/{attempts}: {e}")
        if attempt < attempts:
            time.sleep(RETRY_DELAY)
    return False


def fetch_gen(gen_num: int, cfg: dict, out_root: Path) -> None:
    gen_dir = out_root / cfg["folder"]
    gen_dir.mkdir(parents=True, exist_ok=True)

    total      = len(cfg["range"])
    downloaded = 0
    skipped    = 0
    missing    = 0

    print(f"\n{'='*55}")
    print(f"  {cfg['label']}  ({total} Pokémon)")
    print(f"{'='*55}")

    for dex_id in cfg["range"]:
        filename = f"{dex_id:03d}.png"
        dest     = gen_dir / filename

        if dest.exists():
            skipped += 1
            continue

        url = f"{BASE_URL}/{cfg['url_path']}/{dex_id}.png"
        ok  = download_file(url, dest)

        if ok:
            downloaded += 1
            print(f"  [{downloaded+skipped:>3}/{total}] OK #{dex_id:03d}")
            time.sleep(REQUEST_DELAY)
        else:
            missing += 1
            print(f"  [{downloaded+skipped+missing:>3}/{total}] -- #{dex_id:03d}  (not found, skipped)")

    print(f"\n  Done — {downloaded} downloaded, {skipped} already existed, {missing} not found.")


def main():
    parser = argparse.ArgumentParser(description="Download Pokémon sprites from PokeAPI.")
    parser.add_argument(
        "--gens", nargs="+", type=int, choices=[1, 2, 3, 4], default=[1, 2, 3, 4],
        metavar="N", help="Generations to download (e.g. --gens 1 3)"
    )
    args = parser.parse_args()

    out_root = Path(__file__).parent.parent / "assets/sprites"
    print(f"Output directory : {out_root.resolve()}")
    print(f"Generations      : {args.gens}")

    for gen_num in sorted(args.gens):
        fetch_gen(gen_num, GENS[gen_num], out_root)

    print("\nAll done! 🎉")


if __name__ == "__main__":
    main()
