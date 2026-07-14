from util import resource_path
from core import *
import yaml
import os
import shutil

# Directory holding the pristine, committed config presets. `default` is the
# baseline preset seeded on first run; future themed presets (e.g. `hard`,
# `easy`) are sibling folders, each a full set of per-game config files.
CONFIG_PRESETS_DIR = 'config/presets'

# Default values seeded into global_settings.yaml when the file is absent or a
# key is missing (e.g. a fresh install). The settings files are gitignored, so
# these code-level defaults are the single source of truth for a new user.
GLOBAL_SETTINGS_DEFAULTS = {
    'game': 'Red',
    'generation_mode': 'Progression',
    'party_size': 6,
    'show_acquisition_details': True,
    'show_balance_stats': True,
    'show_hm_coverage': True,
}

def _load_yaml_or_empty(path):
    """Load a YAML file, returning {} if it is missing or empty."""
    try:
        with open(resource_path(path)) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}

def load_or_seed_global_settings():
    """
    Load global_settings.yaml, filling any missing keys from
    GLOBAL_SETTINGS_DEFAULTS. If the file was absent or incomplete, the merged
    result is written back so a complete, real file exists on disk for the
    read-modify-write settings handlers in the CLI/GUI to operate on.
    """
    loaded = _load_yaml_or_empty('config/global_settings.yaml')
    merged = {**GLOBAL_SETTINGS_DEFAULTS, **loaded}
    if merged != loaded:
        with open(resource_path('config/global_settings.yaml'), 'w') as g:
            yaml.safe_dump(merged, g, sort_keys=False)
    return merged

def seed_all_working_configs(mappings):
    """
    Ensure every game's working config exists, seeding any missing one from its
    default preset. seed_working_config is if-missing, so games that share a
    config file (e.g. Red/Blue) only trigger a single copy and later launches
    are no-ops. Called on startup so a full set of config_gen*.yaml exists after
    the first run of `python main.py` (CLI and GUI alike).
    """
    for paths in mappings.values():
        seed_working_config(paths['config'])

def load_or_seed_game_settings(mappings):
    """
    Ensure config/game_settings.yaml has a sphere-mode entry for every game,
    defaulting each missing entry to that game's `suggested_sphere_mode` (from
    its meta file). Writes the file back if anything was added, so a complete
    game_settings.yaml exists on disk after first run. Once complete, later
    launches read no meta files and perform no write.
    """
    settings = _load_yaml_or_empty('config/game_settings.yaml')
    changed = False
    for game, paths in mappings.items():
        if game in settings:
            continue
        meta = _load_yaml_or_empty(paths['meta'])
        modes = meta.get('sphere_generation_modes', {})
        suggested = meta.get('suggested_sphere_mode')
        settings[game] = suggested if suggested in modes else next(iter(modes), None)
        changed = True
    if changed:
        with open(resource_path('config/game_settings.yaml'), 'w') as f:
            yaml.safe_dump(settings, f, sort_keys=False)
    return settings

def seed_working_config(config_file_path, preset="default", force=False):
    """
    Ensure the working config at `config_file_path` (a repo-relative path from
    mappings.yaml, e.g. 'config/config_gen1.yaml') exists on disk, seeding it
    from config/presets/<preset>/<basename> when absent — or unconditionally
    when force=True.

    The working copies are gitignored/per-user; the presets are the pristine,
    committed sources. This single primitive powers three callers:
      - the loader, at startup / on game switch  (force=False, preset='default')
      - a future GUI "Load defaults" button       (force=True,  preset='default')
      - a future theme selector                   (force=True,  preset=<name>)
    Returns the absolute working path.
    """
    working = resource_path(config_file_path)
    if force or not os.path.exists(working):
        basename = os.path.basename(config_file_path)
        source = resource_path(os.path.join(CONFIG_PRESETS_DIR, preset, basename))
        shutil.copyfile(source, working)
    return working

def load_preset_config(config_file_path, preset="default"):
    """
    Web counterpart to seed_working_config: read a preset's config for a game
    into a dict WITHOUT copying it to a working file (no disk writes). The web UI
    starts from this pristine structure and overlays the user's in-memory
    overrides before generating, so no per-user working files are ever created.

    `config_file_path` is a game's mappings 'config' entry (e.g.
    'config/config_gen1.yaml'); only its basename is used to locate the file
    inside config/presets/<preset>/.
    """
    basename = os.path.basename(config_file_path)
    source = resource_path(os.path.join(CONFIG_PRESETS_DIR, preset, basename))
    with open(source) as f:
        return yaml.safe_load(f)

def _preset_display_name(preset_dir, slug):
    """Human-facing label for a preset: the `name:` field of its optional
    config/presets/<slug>/preset.yaml (any string — spaces and punctuation are
    fine), falling back to the folder slug when that file/field is absent."""
    data = _load_yaml_or_empty(os.path.join(preset_dir, 'preset.yaml'))
    name = data.get('name')
    return name.strip() if isinstance(name, str) and name.strip() else slug

def list_config_presets(config_file_path):
    """
    Return the presets that provide a config for the given game as a list of
    (id, label) pairs, where `id` is the preset's folder name under
    config/presets/ — a filesystem-safe slug, and the exact value to pass as
    `seed_working_config(..., preset=id)` — and `label` is the display name
    (see _preset_display_name). A folder qualifies only if it contains a file
    matching `config_file_path`'s basename (e.g. 'config_gen1.yaml'), so a
    preset lacking a given gen's config simply won't be offered for it.
    'default' sorts first; the rest follow alphabetically by label.
    """
    basename = os.path.basename(config_file_path)
    presets_root = resource_path(CONFIG_PRESETS_DIR)
    pairs = [
        (slug, _preset_display_name(os.path.join(presets_root, slug), slug))
        for slug in os.listdir(presets_root)
        if os.path.isfile(os.path.join(presets_root, slug, basename))
    ]
    return sorted(pairs, key=lambda p: (p[0] != 'default', p[1].lower()))

def expand_file_paths(game_mappings):

    pokedex_file_path = game_mappings['pokedex']
    locations_file_path = game_mappings['locations']
    meta_file_path = game_mappings['meta']
    config_file_path = game_mappings['config']

    return pokedex_file_path, locations_file_path, meta_file_path, config_file_path

def build_all_data_structures():
    """
    Build all data structures based on `game` from global_settings.yaml and file path mappings from mappings.yaml

    Returns:
        all_pools (dict): all pools for a given game
        all_pokemon (dict): all Pokemon objects for a given game
        config_data (dict): config options for a given game
        meta_data (dict): metadata for a given game
        mappings (dict): game:set_of_file_paths pairs for all supported games
        global_settings (dict): global settings from global_settings.yaml
        obtainable_pokemon (dict): subset of all_pokemon theoretically obtainable for a given game
    """

    if DEBUG:
        print("===== DEBUG MODE =====")

    # get global settings (seeding defaults + materializing the file if absent)
    global_settings = load_or_seed_global_settings()
    game = global_settings['game']

    # get game/config YAML path mappings
    with open(resource_path('data/mappings.yaml')) as m:
        mappings = yaml.safe_load(m)

    # materialize the full set of per-user files on first run so a complete
    # clone exists after `python main.py` (both CLI and GUI): every game's
    # working config plus game_settings.yaml. Idempotent on later launches.
    seed_all_working_configs(mappings)
    load_or_seed_game_settings(mappings)

    # get the working config file path for the selected game
    _, _, _, config_file_path = expand_file_paths(mappings[game])

    # get selected game config data (the seeded, per-user working file)
    with open(resource_path(config_file_path)) as f:
        config_data = yaml.safe_load(f)

    # selected sphere mode from game_settings.yaml; build_game_data resolves the
    # fallback (suggested, then first available) if it's missing or invalid
    game_settings_data = _load_yaml_or_empty('config/game_settings.yaml')
    sphere_mode = game_settings_data.get(game)

    # delegate the pure, disk-write-free build to build_game_data
    all_pools, all_pokemon, meta_data, obtainable_pokemon = build_game_data(
        game, config_data, sphere_mode, mappings
    )

    return all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon


def build_game_data(game, config_data, sphere_mode, mappings):
    """
    Pure core extracted from build_all_data_structures: build every generation
    data structure for `game` from an explicit `config_data` dict and
    `sphere_mode`, reading ONLY the committed, read-only data files
    (pokedex/locations/meta). Performs no seeding and writes nothing to disk, so
    it is safe to call per-request from the web UI under multiple workers.

    `sphere_mode` may be None or invalid; it is resolved against the game's
    available modes (falling back to suggested_sphere_mode, then the first mode)
    and injected into meta_data as 'selected_sphere_mode', exactly as the desktop
    path did.

    args:
        game (str): a key in mappings
        config_data (dict): config options — from a seeded working file on
            desktop, or preset + user overrides in memory on web
        sphere_mode (str | None): selected sphere mode, resolved if missing/invalid
        mappings (dict): game -> file-path mappings

    returns:
        all_pools (dict), all_pokemon (dict), meta_data (dict), obtainable_pokemon (dict)
    """
    pokedex_file_path, locations_file_path, meta_file_path, _ = expand_file_paths(mappings[game])

    # get selected game metadata
    with open(resource_path(meta_file_path)) as m:
        meta_data = yaml.safe_load(m)

    # resolve + inject the selected sphere mode into meta_data
    available_modes = meta_data.get('sphere_generation_modes', {})
    if not sphere_mode or sphere_mode not in available_modes:
        suggested = meta_data.get('suggested_sphere_mode')
        if suggested in available_modes:
            sphere_mode = suggested
        else:
            sphere_mode = next(iter(available_modes), None)
    meta_data['selected_sphere_mode'] = sphere_mode

    # construct list of starting acquisition methods
    starting_acquisition_methods = []
    for method in meta_data['acquisition_methods']:
        # add each acquisition method to the list of starting methods if it's both default (in metadata) and True (in allowed list in config data)
        if method['is_default'] == True and config_data['allowed_acquisition_methods'][method['name']] == True:
            starting_acquisition_methods.append(method['name'])

    # construct all_pokemon
    with open(resource_path(pokedex_file_path)) as f:
        pokedex_data = yaml.safe_load(f)
    all_pokemon = construct_full_pokemon_set(pokedex_data)

    # construct all_locations
    with open(resource_path(locations_file_path)) as l:
        location_data = yaml.safe_load(l)
    all_locations = construct_full_location_set(location_data)

    # construct all_spheres
    all_spheres = construct_spheres(meta_data, all_locations)

    # build pools from all previously constructed data
    all_pools = build_pools(all_spheres, all_pokemon, starting_acquisition_methods)

    # build the set of all species theoretically obtainable in this game (any sphere, any acquisition
    # method, regardless of current config restrictions), used to narrow candidate draws during
    # progression-mode generation so it doesn't waste attempts on species that can never appear
    # in this game's pools at all.
    obtainable_pokemon = build_obtainable_pokemon(all_pools, all_pokemon)

    return all_pools, all_pokemon, meta_data, obtainable_pokemon

def build_obtainable_pokemon(all_pools, all_pokemon) -> dict[str, 'Pokemon']:
    """
    Builds the subset of all_pokemon theoretically obtainable in this game: every species
    that appears directly in any pool (any sphere, any acquisition method, regardless of current
    config restrictions), plus every species reachable by evolving up from one of those.

    This is deliberately config-agnostic (ignores allowed_acquisition_methods and sphere mode);
    it only prunes species that can never appear in this game's pools. The precise,
    config-aware acquisition checks still happen later in is_party_progression_viable.

    args:
        all_pools (dict of pools)
        all_pokemon (dict of Pokemon objects)

    returns:
        obtainable_pokemon (dict of Pokemon objects, a subset of all_pokemon)
    """

    directly_pooled = {
        pool_entry["pokemon_obj"].name
        for pool in all_pools.values()
        for pool_entry in pool["pool_entries"]
    }

    obtainable_names = set()
    for name, mon in all_pokemon.items():
        cur_mon = mon
        while cur_mon is not None:
            if cur_mon.name in directly_pooled:
                obtainable_names.add(name)
                break
            cur_mon = cur_mon.get_immediate_child(all_pokemon)

    if not obtainable_names:
        raise RuntimeError("No obtainable Pokemon found for this game! Check pool/location data.")

    return {name: all_pokemon[name] for name in obtainable_names}