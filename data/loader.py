from util import resource_path
from core import *
import yaml

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

    # get global settings
    with open(resource_path('config/global_settings.yaml')) as g:
        global_settings = yaml.safe_load(g)
    game = global_settings['game']

    # get game/config YAML path mappings
    with open(resource_path('data/mappings.yaml')) as m:
        mappings = yaml.safe_load(m)

    # get relevant file paths for selected game in global_settings.yaml
    pokedex_file_path, locations_file_path, meta_file_path, config_file_path = expand_file_paths(mappings[game])

    # get selected game config data
    with open(resource_path(config_file_path)) as f:
        config_data = yaml.safe_load(f)

    # get selected game metadata
    with open(resource_path(meta_file_path)) as m:
        meta_data = yaml.safe_load(m)

    # inject selected sphere mode from game_settings.yaml into meta_data
    with open(resource_path('config/game_settings.yaml')) as gs_f:
        game_settings_data = yaml.safe_load(gs_f) or {}
    sphere_mode = game_settings_data.get(game)
    available_modes = meta_data.get('sphere_generation_modes', {})
    if not sphere_mode or sphere_mode not in available_modes:
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

    return all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon

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