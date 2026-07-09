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
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions"
REPO_URL = "https://github.com/PokeAPI/sprites.git"

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
SOCKET_TIMEOUT = 30  # seconds; a stalled connection must not hang forever (CI)
MIN_PRESENT_FRACTION = 0.95  # below this per gen, exit nonzero so CI fails loudly

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def fetch_via_git(gens: list[int], out_root: Path) -> bool:
    """Fetch sprites for all requested gens with a single shallow, sparse,
    blob-filtered clone of the PokeAPI sprites repo, then copy the files out.

    One network operation over the git protocol instead of ~1300 individual
    raw.githubusercontent.com requests, which get rate-limited/stalled from
    shared CI runner IPs. Returns False if git is unavailable or the clone
    fails, so the caller can fall back to per-file HTTP.
    """
    paths = [f"sprites/pokemon/versions/{GENS[g]['url_path']}" for g in gens]
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--filter=blob:none",
                 "--sparse", "--quiet", REPO_URL, tmp],
                check=True, timeout=600)
            subprocess.run(
                ["git", "-C", tmp, "sparse-checkout", "set", *paths],
                check=True, timeout=600)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError) as e:
            print(f"\nSparse git clone failed ({e}); falling back to per-file download.")
            return False

        for gen_num in gens:
            cfg     = GENS[gen_num]
            src_dir = Path(tmp) / "sprites/pokemon/versions" / cfg["url_path"]
            gen_dir = out_root / cfg["folder"]
            gen_dir.mkdir(parents=True, exist_ok=True)

            copied = skipped = missing = 0
            for dex_id in cfg["range"]:
                dest = gen_dir / f"{dex_id:03d}.png"
                if dest.exists():
                    skipped += 1
                    continue
                src = src_dir / f"{dex_id}.png"
                if src.exists():
                    shutil.copyfile(src, dest)
                    copied += 1
                else:
                    missing += 1
            print(f"  {cfg['label']}: {copied} copied, {skipped} already existed, {missing} not found.")
    return True


def verify_counts(gens: list[int], out_root: Path) -> None:
    """Exit nonzero if any gen folder is short on sprites, so a throttled or
    partial fetch fails the build loudly instead of shipping without sprites."""
    shortfalls = []
    for gen_num in gens:
        cfg     = GENS[gen_num]
        gen_dir = out_root / cfg["folder"]
        present = sum(1 for dex_id in cfg["range"] if (gen_dir / f"{dex_id:03d}.png").exists())
        total   = len(cfg["range"])
        if present < total * MIN_PRESENT_FRACTION:
            shortfalls.append(f"{cfg['label']}: only {present}/{total} sprites present")
    if shortfalls:
        raise SystemExit("Sprite fetch incomplete:\n  " + "\n  ".join(shortfalls))


def fetch_sprites(gens: list[int], out_root: Path) -> None:
    """Fetch sprites for the requested gens: sparse git clone first, per-file
    HTTP as fallback. Exits nonzero if the result is incomplete."""
    if not fetch_via_git(gens, out_root):
        for gen_num in gens:
            fetch_gen(gen_num, GENS[gen_num], out_root)
    verify_counts(gens, out_root)


def download_file(url: str, dest: Path, attempts: int = RETRY_ATTEMPTS) -> bool:
    """Download a single file with retries. Returns True on success."""
    socket.setdefaulttimeout(SOCKET_TIMEOUT)  # urlretrieve has none by default
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

    fetch_sprites(sorted(set(args.gens)), out_root)

    print("\nAll done! 🎉")


if __name__ == "__main__":
    main()
