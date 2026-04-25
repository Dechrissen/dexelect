# Contribute to _Dexelect_ development

Contributions to _Dexelect_ are appreciated.

If you think support for...
- a missing game within an already-supported generation, or
- a romhack based on an already-supported generation

should be added, then please follow these guidelines to kickstart their inclusion. Reach out in a [GitHub issue](https://github.com/Dechrissen/dexelect/issues) or in the [Solus Discord server](https://discord.gg/YTxu5uM7r6) if you have any questions about the structure of this project.

## Order of operations for the contributor
1. [Fork this repository](#fork-this-repository)
2. [Add support for new game (in the form of data files)](#adding-support-for-a-new-game)
3. [Test (and run unit tests) to make sure nothing broke](#test-plan)
4. [Commit, push, and open a pull request for your fork (which I'll review and merge if it looks good)](#open-a-pull-request)

## Fork this repository
1. Fork on GitHub
2. Clone your fork to your machine
3. Make changes on your fork

## Adding support for a new game

### Quick background / how the tool works
This project is separated into two parts: A) the logic handling code (where new _features_ are added), and B) the game data files. A relies on B to work, and without B, this software doesn't do anything. Each supported Pokémon generation (or sometimes single game/romhack) is backed by a set of data files — these files contain Pokémon data, location data, progression data, and configuration options for that game.

### What's needed to support a new game?
1. Possibly a new `pokedex_` YAML for the whole generation/set of games, assuming one of the existing ones in the codebase won't work
2. A new `locations_` YAML for each individual game in that generation/set
3. A new `meta_` YAML to encode the progression order and some other metadata about that game/set of games
   - If any new acquisition methods are added, such as `squirt_bottle` for Gen 2 (Sudowoodo), be sure to add them to 
     `location.py`,
     `construct_full_location_set()` in `core.py`, and `test_data_yaml_schema.py`
4. Possibly a new `config_` YAML for the entire generation, assuming one of the existing ones won't work
5. Update `data/mappings.yaml` to ensure all your new files are correctly mapped to your new game

### Breakdown of each needed component

#### Pokédex file

Refer to the `pokedex_` YAMLs in `data/` for examples.

If your game is part of a vanilla generation that is already supported, and for instance, no changes were made to 
the HM learnsets 
of any Pokémon in your new game (e.g. Yellow has slightly different HM learnsets compares to R/B), then you can 
simply use the existing `pokedex_` file and skip this step.

The `hm_learnset` field should consist of moves usable in the field, including things like Dig, Teleport, and 
Softboiled, and only if they're learned in the game in question via machine or level-up (_not_ via trading from an 
older generation).

If you need a new file, it should be structured as a YAML list. Here's a snippet with 2 entries for BULBASAUR and 
IVYSAUR. Follow this format.
```yaml
- name: BULBASAUR
  is_fully_evolved: false
  evo_stage: 1
  species_line: BULBASAUR
  types:
  - grass
  - poison
  is_legendary: false
  base_stat_total: 253
  hm_learnset:
  - CUT
  evolution_method_required: none
- name: IVYSAUR
  is_fully_evolved: false
  evo_stage: 2
  species_line: BULBASAUR
  types:
  - grass
  - poison
  is_legendary: false
  base_stat_total: 325
  hm_learnset:
  - CUT
  evolution_method_required: level-up
```

Add your new file in the relevant directory in `data`. For example, for a Gen 1 romhack called "Pokémon Purple", 
you'd add this new file: `data/gen1/romhacks/pokedex_purple.yaml`.

#### Locations file

Refer to the `locations_` YAMLs in `data/` for examples.

If your game has new locations and/or encounter locations are different from other already-supported games, you'll 
need a new `locations_` YAML. Otherwise, you can reuse an old one if the data is the same in your new game.

If you need a new file, it should be structured as a YAML list. Each entry should have a sub-entry for the 
acquisition methods on that map. Here's a snippet 
with one entry from 
R/B, 
Cerulean 
Cave B1F.

```yaml
- map_name: CeruleanCaveB1F
  walk:
  - ARBOK
  - CHANSEY
  - DITTO
  - ELECTRODE
  - MAROWAK
  - PARASECT
  - RAICHU
  - RHYDON
  - SANDSLASH
  old_rod:
  - MAGIKARP
  good_rod:
  - GOLDEEN
  - POLIWAG
  super_rod:
  - KINGLER
  - SEADRA
  - SEAKING
  - SLOWBRO
  static_encounter:
  - MEWTWO
```

#### Meta file

Refer to the `meta_` YAMLs in `data/` for examples.

The meta file accounts for the bulk of the work that needs to be done for adding support for a new game. 

Since 
progression needs to be encoded in order for the sphere system to work (so that generation is progressively sound), 
the game's general linear progression needs to be manually written out. This means stepping through the game, route by 
route, town 
by town, and creating an ordered list (refer to the example I did for Gen 1 in `notes/gen1_progression.txt.` — it's 
just a blueprint that ultimately helped as a reference when I made the `meta_rb.yaml` file).

The `spheres` list in the `meta_` YAML consists of a list of spheres, each an object with a `sphereNum` and 
`contents` containing a list of maps (and acquisition unlocks, like Old Rod and Poké Flute) in that sphere.

In addition to the `spheres` list, the `meta_` YAMLs contain a few other pieces of metadata important for the 
game:

- `starter_species` to define which Pokémon are starters
- `modal_species` to define sets of Pokémon from which only one is obtainable
- `limited_acquisition_methods` to define acquisition methods that only work once per location per Pokémon
- `acquisition_methods` to define all acquisition methods and which ones are default (start with at beginning of game)
- `sphere_generation_modes` to define some named sets of spheres that can be toggled between in `selected_sphere_mode`
- `selected_sphere_mode` to set the active (default/recommended) sphere generation mode

#### Config file

Refer to the `config_` YAMLs in `config/` for examples.

The config file contains all the customization options for team generation.

The only reason to add a new dedicated config file would be in the case of a not-yet-supported generation. Otherwise,
the config file to be used for your game should match its generation, e.g. `config/config_gen2.yaml` for Gen 2 games.

#### Mappings

Refer to `data/mappings.yaml`. This file needs to be updated when a new game is added.

Simply follow the existing schema and point each of the main data structure names to their corresponding file paths. Indentation matters. The name of the game (Solus RGB in the below example) is how it will appear in the 'Game setting' menu in the app; spaces are OK.

```yaml
Solus RGB:
  meta: 'data/gen1/romhacks/meta_solusrgb.yaml'
  pokedex: 'data/gen1/romhacks/pokedex_solusrgb.yaml'
  locations: 'data/gen1/romhacks/locations_solusrgb.yaml'
  config: 'config/config_gen1.yaml'
```

## Test plan
After all new files have been added and existing files have been updated:
1. `cd dexelect`
2. install dependencies with `pip install -r requirements.txt`
3. run tests with `pytest tests`

All tests should pass.

It would also be wise to run a few test team generations, and make sure all the config settings are working.

## Open a pull request
1. Open a [pull request](https://github.com/Dechrissen/dexelect/pulls) (from your fork to _Dexelect_) on GitHub
2. Assign it to me ([Dechrissen](https://github.com/Dechrissen)) for review