# Copyright 2026 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/
"""
Shared "Export Party" rendering for the desktop GUI and the web UI.

Turns a generated party blob into the export .txt content by filling
ui/export_template.txt ({{ placeholder }} substitution — no template-engine
dependency). The GUI writes the string wherever the save dialog points; the
web app pre-renders it into the /api/generate response so the browser's
Export Party button is a pure client-side download.
"""
import re
from datetime import datetime

from util import resource_path
from version import __version__

TEMPLATE_PATH = "ui/export_template.txt"


def _sort_key(member):
    """Starters first, then by earliest pool/sphere (mirrors the CLI/GUI/web order)."""
    entry = member["random_pool_entry_instance"]
    method = entry["acquisition_method"] if entry else None
    earliest_pool = member.get("earliest_pool", 9999) or 9999
    return (0 if method == "starter" else 1, earliest_pool)


def build_export_text(blob, game, mode, config_data, source):
    """Render the export .txt content for a generated party blob.

    `source` names the UI it was exported from ("desktop" / "web") for the
    template's footer line.
    """
    is_random = mode in ("Random (National Dex)", "Random (Obtainable)")

    # --- Party list ---
    sorted_party = sorted(blob["party_with_acquisition_data"], key=_sort_key)
    party_lines = []
    for i, member in enumerate(sorted_party, 1):
        mon   = member["party_member_obj"]
        entry = member["random_pool_entry_instance"]
        if entry is None:
            party_lines.append(f"{i}. {mon.name}")
        else:
            form     = member["earliest_form"].name
            method   = entry["acquisition_method"]
            location = entry["acquiring_location"]
            pool     = member["earliest_pool"]
            party_lines.append(
                f"{i}. {mon.name} — Acquire as {form} via {method} at {location} (Sphere {pool})"
            )
    party_str = "\n".join(party_lines)

    # --- HM Coverage ---
    hm_config = config_data.get("ensure_hm_coverage", {})
    hm_set = set(
        hm for m in blob["party_with_acquisition_data"]
        for hm in m["party_member_obj"].hm_learnset
    )
    if hm_config:
        hm_parts = [
            f"{hm}(Y)" if hm in hm_set else f"{hm}(N)"
            for hm in hm_config
        ]
        hm_str = "  ".join(hm_parts)
    else:
        hm_str = "—"

    # --- Balance Stats ---
    if not is_random and blob.get("lean") is not None:
        dist     = blob.get("party_distribution") or {}
        dist_str = "  ".join(f"S{s}: {dist[s]}" for s in dist) if dist else "—"
        pattern  = blob.get("pattern") or "—"
        balance_str = (
            f"Lean:         {blob.get('lean', '—')}\n"
            f"Spread:       {blob.get('spread', '—')}\n"
            f"Pattern:      {pattern}\n"
            f"Distribution: {dist_str}"
        )
    else:
        balance_str = "N/A"

    # --- Render template ---
    with open(resource_path(TEMPLATE_PATH), "r", encoding="utf-8") as f:
        template = f.read()

    ctx = {
        "game":          game,
        "mode":          mode,
        "party":         party_str,
        "hm_coverage":   hm_str,
        "balance_stats": balance_str,
        "version":       __version__,
        "source":        source,
        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return re.sub(
        r"\{\{\s*(\w+)\s*\}\}",
        lambda m: str(ctx.get(m.group(1), m.group(0))),
        template,
    )


def default_export_filename(game):
    """dexelect_v<version_slug>_generated_party_<game_slug>_<timestamp>.txt"""
    ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
    game_slug    = re.sub(r"[^\w]+", "_", game.lower()).strip("_")
    version_slug = re.sub(r"[^\w]+", "_", __version__.lower()).strip("_")
    return f"dexelect_v{version_slug}_generated_party_{game_slug}_{ts}.txt"
