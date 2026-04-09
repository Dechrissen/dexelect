import pytest
from conftest import load_yaml

def filter_yaml(yaml_files, category):
    return [(p, c) for (p, c) in yaml_files if c == category]

# ================= POKEDEX YAML TESTS =================
# these tests iterate over all `pokedex_` YAMLs in data/
def test_pokedex_required_fields(yaml_files):
    """Tests whether all required fields are present for each Pokemon."""
    REQUIRED = {
        "name",
        "species_line",
        "evo_stage",
        "is_fully_evolved",
        "is_legendary",
        "types",
        "base_stat_total",
        "hm_learnset",
        "evolution_method_required"
    }
    for path, category in filter_yaml(yaml_files, "pokedex"):
        pokedex = load_yaml(path)
        for mon in pokedex:
            assert "name" in mon, "Pokemon must have a 'name' field" # check this first so we don't get a KeyError for name
            missing = REQUIRED - mon.keys()
            assert not missing, f"{path}: missing {missing} for {mon['name']}"

def test_pokedex_data_types(yaml_files):
    """Tests whether all data types are valid for each Pokemon."""
    valid_hms = {'CUT', 'FLASH', 'SURF', 'STRENGTH', 'FLY', 'DIG', 'TELEPORT', 'SOFTBOILED',
                 'WATERFALL', 'WHIRLPOOL', 'ROCK_SMASH', 'DIVE', 'HEADBUTT'}
    valid_types = {'normal', 'fire', 'water', 'grass', 'electric', 'flying', 'fighting',
                   'ice', 'psychic', 'ground', 'rock', 'poison', 'bug', 'dragon', 'ghost',
                   'steel', 'dark'}
    valid_evo_methods = {'none', 'level-up', 'moon_stone', 'fire_stone', 'water_stone',
                         'thunder_stone', 'leaf_stone', 'trade',
                         'happiness', 'trade_metal_coat', 'trade_kings_rock', 'trade_dragon_scale', 'trade_upgrade',
                         'level-up_atk_equal_def', 'level-up_atk_greater_def', 'level-up_def_greater_atk', 'sun_stone',
                         'trade_deepseatooth', 'trade_deepseascale', 'level-up_beauty', 'level-up_empty_slot_extra_ball',
                         'level-up_personality'}

    for path, category in filter_yaml(yaml_files, "pokedex"):
        pokedex = load_yaml(path)
        for mon in pokedex:
            # test name
            assert isinstance(mon["name"], str), f"{path}:{mon['name']}: 'name' must be a string"
            assert mon["name"].isupper(), f"{path}:{mon['name']}: 'name' must be uppercase"

            # test species_line
            assert isinstance(mon["species_line"], str), f"{path}:{mon['name']}: 'species_line' must be a string"

            # test evo_stage
            assert isinstance(mon["evo_stage"], int), f"{path}:{mon['name']}: 'evo_stage' must be an integer"

            # test is_fully_evolved
            assert isinstance(mon["is_fully_evolved"], bool), f"{path}:{mon['name']}: 'is_fully_evolved' must be a boolean"

            # test is_legendary
            assert isinstance(mon["is_legendary"], bool), f"{path}:{mon['name']}: 'is_legendary' must be a boolean"

            # test types
            assert isinstance(mon["types"], list), f"{path}:{mon['name']}: 'types' must be a list"
            assert all(isinstance(t, str) for t in mon["types"]), f"{path}:{mon['name']}: 'types' list must contain only strings"
            for t in mon["types"]:
                assert t in valid_types, f"{path}: Invalid type '{t}' for Pokemon '{mon['name']}'"

            # test base_stat_total
            assert isinstance(mon["base_stat_total"], int), f"{path}:{mon['name']}: 'base_stat_total' must be an integer"
            assert mon["base_stat_total"] > 0, f"{path}:{mon['name']}: 'base_stat_total' must be positive"

            # test hm_learnset
            assert isinstance(mon["hm_learnset"], list), f"{path}:{mon['name']}: 'hm_learnset' must be a list"
            assert all(isinstance(t, str) for t in mon["hm_learnset"]), f"{path}:{mon['name']}: 'hm_learnset' list must contain only strings"
            assert all(hm in valid_hms for hm in mon["hm_learnset"]), f"{path}:{mon['name']}: 'hm_learnset' list must contain only valid HMs"

            # test evolution_method_required
            assert isinstance(mon["evolution_method_required"], str), f"{path}:{mon['name']}: 'evolution_method_required' must be a string"
            assert mon["evolution_method_required"] in valid_evo_methods, f"{path}:Invalid evolution_method_required '{mon['evolution_method_required']}' for Pokemon '{mon['name']}'"


# ================= LOCATIONS YAML TESTS =================
# these tests iterate over all `locations_` YAMLs in data/
def test_location_fields(yaml_files):
    """Tests whether all fields in each location entry are valid."""
    valid_acquisition_methods = {'starter','walk','surf','old_rod','good_rod','super_rod','poke_flute',
                                 'static_encounter','trade','gift','purchase','fossil_restore','prize_window',
                                 'bug_catching_contest', 'rock_smash', 'squirt_bottle', 'headbutt', 'roaming',
                                 'rainbow_wing', 'silver_wing', 'dive', 'go_goggles', 'devon_scope',
                                 'sealed_chamber_puzzle', 'mirage_island'}
    for path, category in filter_yaml(yaml_files, "locations"):
        locations = load_yaml(path)
        for location in locations:
            assert "map_name" in location
            assert isinstance(location["map_name"], str)
            assert all(field in valid_acquisition_methods for field in location if field != "map_name")
            for acquisition_method in location:
                if acquisition_method != 'map_name':
                    assert isinstance(location[acquisition_method], list)
                    assert all(isinstance(pokemon, str) for pokemon in location[acquisition_method])

def test_no_duplicate_location_fields(yaml_files):
    """Tests whether there are no duplicate location entries in a single locations YAML."""
    for path, category in filter_yaml(yaml_files, "locations"):
        unique_locations = []
        locations = load_yaml(path)
        for location in locations:
            assert location["map_name"] not in unique_locations, f"{path}: duplicate location entry {location['map_name']}"
            unique_locations.append(location["map_name"])


# ================= META YAML TESTS =================
# these tests iterate over all `meta_` YAMLs in data/
def test_meta_required_fields(yaml_files):
    """Tests whether all required fields are present in a meta YAML."""
    REQUIRED = {
        "starter_species",
        "modal_species",
        "limited_acquisition_methods",
        "acquisition_methods",
        "spheres",
        "sphere_generation_modes",
        "selected_sphere_mode"
    }
    for path, category in filter_yaml(yaml_files, "meta"):
        meta = load_yaml(path)
        missing = REQUIRED - meta.keys()
        assert not missing, f"{path}: missing required fields {missing}"

def test_meta_data_types(yaml_files):
    """Tests whether all data types are valid for entries in meta YAML."""
    for path, category in filter_yaml(yaml_files, "meta"):
        meta = load_yaml(path)

        #TODO should also check whether each of these have the correct format for the entries within them
        assert isinstance(meta['starter_species'], list), f"{path}: 'starter_species' must be a list"
        assert isinstance(meta['modal_species'], list), f"{path}: 'modal_species' must be a list"
        assert isinstance(meta['limited_acquisition_methods'], list), f"{path}: 'limited_acquisition_methods' must be a list"
        assert isinstance(meta['acquisition_methods'], list), f"{path}: 'acquisition_methods' must be a list"
        assert isinstance(meta['spheres'], list), f"{path}: 'spheres' must be a list"
        assert isinstance(meta['sphere_generation_modes'], dict), f"{path}: 'sphere_generation_modes' must be a dict"
        assert isinstance(meta['selected_sphere_mode'], str), f"{path}: 'selected_sphere_mode' must be a str"


# ================= CONFIG YAML TESTS =================
# these tests iterate over all `pokedex_` YAMLs in config/
def test_config_required_fields(yaml_files):
    """Tests whether all required fields are present in a config YAML."""
    REQUIRED = {
        "allowed_balancing",
        "allowed_spreads",
        "allowed_patterns",
        "force_starter",
        "allow_not_fully_evolved",
        "max_evo_stage",
        "allow_legendaries",
        "allow_duplicate_species",
        "allow_dual_type",
        "type_distribution",
        "prescribed_type",
        "species_blacklist",
        "allowed_evo_methods",
        "bst_max",
        "bst_min",
        "ensure_hm_coverage",
        "allowed_acquisition_methods"
    }
    for path, category in filter_yaml(yaml_files, "config"):
        config = load_yaml(path)
        missing = REQUIRED - config.keys()
        assert not missing, f"{path}: missing required fields {missing}"

def test_config_data_types(yaml_files):
    """Tests whether all data types are valid for entries in config YAML."""
    valid_type_distributions = {"no_overlap", "all_share_one_type", "anything_goes"}
    valid_types = {'normal', 'fire', 'water', 'grass', 'electric', 'flying', 'fighting',
                   'ice', 'psychic', 'ground', 'rock', 'poison', 'bug', 'dragon', 'ghost'}
    for path, category in filter_yaml(yaml_files, "config"):
        config = load_yaml(path)

        assert isinstance(config['allowed_balancing'], list), f"{path}: 'allowed_balancing' must be a list"
        assert isinstance(config['allowed_spreads'], list), f"{path}: 'allowed_spreads' must be a list"
        assert isinstance(config['allowed_patterns'], list), f"{path}: 'allowed_patterns' must be a list"
        assert isinstance(config['force_starter'], bool), f"{path}: 'force_starter' must be a bool"
        assert isinstance(config['allow_not_fully_evolved'], bool), f"{path}: 'allow_not_fully_evolved' must be a bool"
        assert isinstance(config['max_evo_stage'], int), f"{path}: 'max_evo_stage' must be an int"
        assert isinstance(config['allow_legendaries'], bool), f"{path}: 'allow_legendaries' must be a bool"
        assert isinstance(config['allow_duplicate_species'], bool), f"{path}: 'allow_duplicate_species' must be a bool"
        assert isinstance(config['allow_dual_type'], bool), f"{path}: 'allow_dual_type' must be a bool"

        assert isinstance(config['type_distribution'], str), f"{path}: 'type_distribution' must be a str"
        assert config['type_distribution'] in valid_type_distributions, f"{path}: 'type_distribution' must be one of: {valid_type_distributions}"

        assert config['prescribed_type'] in (valid_types | {'none'}), f"{path}: 'prescribed_type' must be one of: {valid_types | {'none'}}"

        assert isinstance(config['species_blacklist'], list), f"{path}: 'species_blacklist' must be a list"
        assert isinstance(config['allowed_evo_methods'], dict), f"{path}: 'allowed_evo_methods' must be a dict"

        assert (isinstance(config['bst_max'], int) or config['bst_max'] == 'none'), f"{path}: 'bst_max' must be an int or 'none'"
        assert (isinstance(config['bst_min'], int) or config['bst_min'] == 'none'), f"{path}: 'bst_min' must be an int or 'none'"

        assert isinstance(config['ensure_hm_coverage'], dict), f"{path}: 'ensure_hm_coverage' must be a dict"
        assert isinstance(config['allowed_acquisition_methods'], dict), f"{path}: 'allowed_acquisition_methods' must be a dict"

