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

    return all_pools, all_pokemon, config_data, meta_data, mappings, global_settings