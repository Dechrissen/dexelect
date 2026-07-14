# Copyright 2026 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/
"""
Flask web UI for Dexelect — a third `--ui` option `web` alongside `cli` and `gui`.

Design: stateless and multi-game. Every request carries
its own game / config / sphere_mode, so no per-user working files are seeded and
nothing is written to disk. The read-only committed data + preset files are the
only shared state, which makes the app safe to run under multiple gunicorn
workers (`--preload` shares those pages copy-on-write).

The generation logic is reused verbatim from core.py — this module is only a
thin HTTP layer around build_game_data() + generate_*().
"""
import os

import yaml
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from util import resource_path
from core import (
    count_new_species_per_sphere,
    generate_final_party,
    generate_fully_randomized_party,
)
from version import __version__
from data.loader import (
    GLOBAL_SETTINGS_DEFAULTS,
    build_game_data,
    list_config_presets,
    load_preset_config,
)

# The three generation modes, mirrored from the CLI (ui/cli.py GENERATION_MODES).
GENERATION_MODES = ["Progression", "Random (Obtainable)", "Random (National Dex)"]

# Structural base preset. The form always POSTs a complete set of lever values,
# so we overlay them onto the 'default' preset's structure regardless of which
# preset the user started editing from — 'default' just supplies the shape.
BASE_PRESET = "default"


def _load_mappings():
    with open(resource_path("data/mappings.yaml")) as m:
        return yaml.safe_load(m)


class InvalidOverride(ValueError):
    """A client override value doesn't fit the preset's shape/vocabulary."""


def apply_overrides(base, overrides):
    """
    Overlay the user's in-memory lever values (`overrides`) onto a pristine
    preset config dict (`base`), matching each key's shape. Never trusts the
    client for structure/options — only values are taken from `overrides`, and
    each value is validated against the preset's shape/vocabulary; a value that
    doesn't fit raises InvalidOverride, which api_generate turns into a clean
    400. (The form can produce such values — e.g. junk text in a number field
    becomes null — and the user must see an error, not a party silently
    generated from the preset value they thought they'd overridden.)

      - {'value': [...], 'options': [...]} -> list drawn from options
      - {'value': x, 'options': [...]}     -> a member of options
      - {sub: bool, ...} (bool map)        -> dict with bool sub-values
      - bool / int scalar                  -> matching type
      - str scalar (e.g. bst 'none')       -> str or int (form coerces digits)
      - list (e.g. species_blacklist)      -> list of strings
    """
    for key, cur in base.items():
        if key not in overrides:
            continue
        ov = overrides[key]
        if isinstance(cur, dict) and "value" in cur and "options" in cur:
            if isinstance(cur["value"], list):
                if not isinstance(ov, list) or any(o not in cur["options"] for o in ov):
                    raise InvalidOverride(key)
                # preserve option order
                cur["value"] = [o for o in cur["options"] if o in ov]
            else:
                if ov not in cur["options"]:
                    raise InvalidOverride(key)
                cur["value"] = ov
        elif isinstance(cur, dict):
            if not isinstance(ov, dict):
                raise InvalidOverride(key)
            for subk in cur:
                if subk in ov:
                    if not isinstance(ov[subk], bool):
                        raise InvalidOverride(key)
                    cur[subk] = ov[subk]
        elif isinstance(cur, bool):  # before int: bool is a subclass of int
            if not isinstance(ov, bool):
                raise InvalidOverride(key)
            base[key] = ov
        elif isinstance(cur, int):
            if not isinstance(ov, int) or isinstance(ov, bool):
                raise InvalidOverride(key)
            base[key] = ov
        elif isinstance(cur, str):
            if not isinstance(ov, (str, int)) or isinstance(ov, bool):
                raise InvalidOverride(key)
            base[key] = ov
        elif isinstance(cur, list):
            if not isinstance(ov, list) or any(not isinstance(s, str) for s in ov):
                raise InvalidOverride(key)
            base[key] = list(ov)
    return base


def _sort_key(member):
    """Mirror the CLI ordering: starters first, then by earliest pool/sphere."""
    entry = member.get("random_pool_entry_instance")
    method = entry["acquisition_method"] if entry else None
    starter_rank = 0 if method == "starter" else 1
    earliest_pool = member.get("earliest_pool")
    pool_rank = earliest_pool if earliest_pool is not None else 9999
    return (starter_rank, pool_rank)


def _serialize_blob(blob, mappings, game, config_data):
    """Turn a party blob into JSON the front end can render (incl. sprite URLs)."""
    gen_folder = os.path.basename(mappings[game]["sprites"])
    members = []
    for member in sorted(blob["party_with_acquisition_data"], key=_sort_key):
        obj = member["party_member_obj"]
        entry = member.get("random_pool_entry_instance")
        acquisition = None
        if entry is not None:
            earliest_form = member.get("earliest_form")
            acquisition = {
                "method": entry["acquisition_method"],
                "location": entry["acquiring_location"],
                "sphere": member.get("earliest_pool"),
                "earliest_form": earliest_form.name if earliest_form else None,
            }
        members.append({
            "name": obj.name,
            "nat_dex_number": obj.nat_dex_number,
            "types": obj.types,
            "sprite_url": f"/sprites/{gen_folder}/{obj.nat_dex_number}.png",
            "acquisition": acquisition,
        })
    # HM coverage strip data: the game's full HM list (the config's
    # ensure_hm_coverage keys — the overlay can flip the bools but never the
    # keys) plus the subset this party can learn, mirroring the desktop GUI.
    party_hm_coverage = set(
        hm for m in blob["party_with_acquisition_data"]
        for hm in m["party_member_obj"].hm_learnset
    )
    hms = list(config_data.get("ensure_hm_coverage", {}))
    return {
        "party": members,
        "hm_coverage": {
            "hms": hms,
            "covered": [hm for hm in hms if hm in party_hm_coverage],
        },
        "stats": {
            "lean": blob.get("lean"),
            "spread": blob.get("spread"),
            "pattern": blob.get("pattern"),
            "score_median": blob.get("score_median"),
            "party_distribution": blob.get("party_distribution"),
        },
    }


def create_app():
    """App factory — also the gunicorn entry point: `ui.web.app:create_app()`."""
    app = Flask(__name__)
    # Trust the reverse proxy's X-Forwarded-Proto/Host (set in the nginx deploy
    # config) so url_for(_external=True) — used by the og: meta tags — builds
    # https:// URLs on the public host instead of the gunicorn-local ones.
    # Harmless in dev where the headers are simply absent.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    # Reject oversized request bodies before we parse them — the only POST
    # (/api/generate) carries a small config dict, so anything large is either a
    # mistake or an attempt to make the JSON parser do pointless work. 256 KB is
    # far more than a legitimate config (incl. blacklists) will ever need.
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
    mappings = _load_mappings()

    @app.route("/")
    def index():
        return render_template("index.html", version=__version__)

    @app.route("/api/games")
    def api_games():
        return jsonify({"games": list(mappings.keys())})

    @app.route("/api/game/<game>")
    def api_game(game):
        """Everything the form needs to render for a game, seeded from defaults."""
        if game not in mappings:
            return jsonify({"error": f"Unknown game: {game}"}), 404
        config = load_preset_config(mappings[game]["config"], BASE_PRESET)
        # Full data build so the Spheres tab can show per-sphere new-species
        # counts (config-agnostic, like the desktop GUI's Spheres tab). The
        # sphere pools themselves don't depend on the selected mode — the mode
        # only gates generation — so the client greys spheres locally from
        # sphere_mode_map without another round trip.
        all_pools, all_pokemon, meta, obtainable_pokemon = build_game_data(
            game, config, None, mappings
        )
        new_species = count_new_species_per_sphere(all_pools, obtainable_pokemon, all_pokemon)
        mode_map = meta.get("sphere_generation_modes", {})
        return jsonify({
            "presets": list_config_presets(mappings[game]["config"]),
            "sphere_modes": list(mode_map.keys()),
            "sphere_mode_map": mode_map,
            "suggested_sphere_mode": meta.get("suggested_sphere_mode"),
            "spheres": [
                {
                    "num": s["sphereNum"],
                    "new_species": new_species.get(s["sphereNum"], 0),
                    "contents": [
                        {"name": e["name"], "type": e["type"]}
                        for e in s.get("contents", [])
                    ],
                }
                for s in meta.get("spheres", [])
            ],
            "generation_modes": GENERATION_MODES,
            "defaults": {
                "party_size": GLOBAL_SETTINGS_DEFAULTS["party_size"],
                "generation_mode": GLOBAL_SETTINGS_DEFAULTS["generation_mode"],
            },
            "config": config,
        })

    @app.route("/api/game/<game>/preset/<preset>")
    def api_game_preset(game, preset):
        """Config for a specific preset — powers the preset dropdown and the
        Restore Defaults button (preset='default'). Read-only, no writes."""
        if game not in mappings:
            return jsonify({"error": f"Unknown game: {game}"}), 404
        # Whitelist the preset against the known slugs for this game. `preset`
        # comes straight from the URL and is joined into a filesystem path in
        # load_preset_config; without this a value like '..' escapes the presets
        # dir (and any unknown value would 500 on FileNotFoundError).
        valid_presets = {slug for slug, _ in list_config_presets(mappings[game]["config"])}
        if preset not in valid_presets:
            return jsonify({"error": f"Unknown preset: {preset}"}), 404
        return jsonify({"config": load_preset_config(mappings[game]["config"], preset)})

    @app.route("/api/generate", methods=["POST"])
    def api_generate():
        payload = request.get_json(force=True, silent=True) or {}
        # Type guards: every field below is attacker-controllable JSON, so pin
        # the types before using them (an unhashable `game`/`sphere_mode` would
        # otherwise TypeError on the dict lookups -> 500).
        game = payload.get("game")
        if not isinstance(game, str) or game not in mappings:
            return jsonify({"error": f"Unknown game: {game}"}), 400

        generation_mode = payload.get("generation_mode", GENERATION_MODES[0])
        sphere_mode = payload.get("sphere_mode")
        if not isinstance(sphere_mode, str):
            sphere_mode = None  # build_game_data resolves the fallback
        try:
            party_size = int(payload.get("party_size", 6))
        except (TypeError, ValueError):
            party_size = 6
        # Clamp to a real party size. Without this an out-of-range n (e.g. a huge
        # value) drives the generators to allocate/loop far beyond anything
        # sensible — and the Random modes aren't covered by the generation
        # deadline, so a giant n there is a memory/CPU DoS. Mirrors the HTML min/max.
        party_size = max(1, min(6, party_size))

        overrides = payload.get("config")
        if not isinstance(overrides, dict):
            overrides = {}

        # Rebuild config from the pristine preset structure + the user's values,
        # entirely in memory — no working files are written.
        try:
            config_data = apply_overrides(
                load_preset_config(mappings[game]["config"], BASE_PRESET), overrides
            )
        except InvalidOverride:
            return jsonify({"error": "Invalid config values for this game."}), 400

        # Backstop: apply_overrides validates shape/vocabulary, but a residual
        # bad value (e.g. a junk string where core compares numerically) must
        # yield a clean 400, never an unhandled 500 from arbitrary client JSON.
        try:
            all_pools, all_pokemon, meta_data, obtainable_pokemon = build_game_data(
                game, config_data, sphere_mode, mappings
            )

            if generation_mode == "Random (Obtainable)":
                blob = generate_fully_randomized_party(
                    obtainable_pokemon, n=party_size, all_pools=all_pools, all_pokemon=all_pokemon
                )
            elif generation_mode == "Random (National Dex)":
                blob = generate_fully_randomized_party(
                    all_pokemon, n=party_size, all_pools=all_pools, all_pokemon=all_pokemon
                )
            else:  # Progression
                blob = generate_final_party(
                    all_pools, all_pokemon, config_data, meta_data, obtainable_pokemon, n=party_size
                )
        except Exception:
            app.logger.exception("generation failed for a client-supplied config")
            return jsonify({"error": "Invalid config values for this game."}), 400

        # None-handling at the HTTP boundary: turn a failed generation into a
        # clean JSON error instead of serializing null.
        if blob is None:
            return jsonify({
                "error": "Could not generate a valid party. Try adjusting settings."
            }), 200

        return jsonify(_serialize_blob(blob, mappings, game, config_data))

    @app.route("/logo.png")
    def logo():
        """The header logo (black variant, shared with the desktop GUI)."""
        return send_from_directory(resource_path("assets/logo"), "dexelect-logo-black.png")

    @app.route("/og.png")
    def og_image():
        """1200x630 social-preview card (og:image) — the vector logo rendered
        on a solid white background, since scrapers reject SVG and would show
        the transparent header PNG as black-on-dark on dark-themed clients."""
        return send_from_directory(resource_path("assets/logo"), "dexelect-og.png")

    @app.route("/favicon.ico")
    def favicon():
        """Multi-size .ico shared with the desktop app; served at the default
        path browsers probe, plus referenced from the template's <link>."""
        return send_from_directory(resource_path("assets/icons"), "dexelect.ico")

    @app.route("/sprites/<path:subpath>")
    def sprites(subpath):
        """Serve sprite PNGs. In production nginx serves these directly; this
        route exists so sprites also work when running the dev server locally."""
        return send_from_directory(resource_path("assets/sprites"), subpath)

    return app
