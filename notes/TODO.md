# TODO

- make a README logo / app icon for Linux and Windows top left window icon
- add to itch.io

- add support for:
  - Yellow
  - Crystal
  - Emerald

- clean up CLI UI code and add some comments

- add comments to unit test functions

- make "gift" into "choice" for HITMONs? this would allow "modal" list to not be used for fossils etc.

- add "user defined modals" to the config, which are extra modals that get added to the modal list when doing the check
  - e.g. "nidoran_m and nidoran_f"
  - jynx and mr.mime

- annotate the progression file so we know where certain things come from, e.g. the moon stone on route 2 can only be gotten in sphere 2, so we should have a comment "from Route2 after Cut"

- Finish unit test suite

- add Pool class
- config should maybe be a Config class. This would make it easier to validate and pass along to functions

- add HM coverage output
  - list of HMs, check marks next to covered ones, or color them green
  
- other similar coverage bar graphs, etc. (type coverage distribution)

- check every location from locations is in meta spheres list (also add unit test for this?)

- add unit tests for party generation functions (define test parties)

- add coverage tests for running generation for a few minutes and making sure certain % of pokemon get generated? gotta figure out what metric makes sense

- add 'export to txt' option for saving teams, or do it automatically (last X teams generated in a file)

- add some script that generates the config files for each game (creates the yaml) or something that resets it to the default (recommended) values before i push a release (or maybe have options in the UI to switch to certain presets, like "recommended", "hard", etc)
  - `config_gen1.default.yaml`
  - `config_gen1.hard.yaml`

- add event support generally (gen 2/3)
  - might just be eon_ticket acquisition method toggle
  - add setting to meta file for G/S that is a boolean to enable or disable whether player has access to CELEBI event. 
  celebi event data (gs ball acquisition method? will just be in the data files but only work if this setting is 
  turned on.)

- figure out if we need to handle stone availability in the config/meta files. If Flareon gets generated in party in 
  gen 2, it will assume a fire stone is available. is it? maybe back to the original idea of adding it to the 
  spheres list when it becomes available, then checking if stones are acquired by the time the pokemon is generated.

- toggle for "gen 2 or gen 1 pokemon only" in gen 2 generation? and onward
  - or not a toggle, but a list of 'allowed generations' e.g. [1,2,3]
  - will need to add a field for every pokemon in every pokedex file "gen_introduced"
  - additional possibile field: "in_regional_dex" (bool)

- add 'Milk Drink' as field moves (HMs) in Gen 2 and 3?
- add 'Secret Power' as field move (HM) in gen 3?
- "Sweet Scent" Gen 3?

- add feature "only generate pokemon in Sphere X" (or should this only be accomplished by the sphere_modes in meta file?)

- add to AUR somehow, or add some instructions in README for "how to install on Linux so it can run from launchers like wofi, etc.".
  - Use a `.desktop` file setup?
  - add to `/bin`?
  - PATH?
  - app icon which can be used by application launchers in Linux but also to replace the top left window icon in Windows
  
- add `--help` to main.py

- add instructions for building local Linux binary and testing to some TEST.md file

- add Claude skill file which acts as instructions for Claude to help guide users when adding a new romhack from the command line (Claude code). e.g. it knows the structure of the pokedex and locations files, it knows the data it needs and where to get it (Serebii or something), and it knows how to add all that to the repo, but it asks user questions along the way, like "does this romhack have custom pokemon or can I use an existing pokedex file?". It needs context about whole project structure.

- move to 1.0.0 after config file schemas / system is finished (so users can keep config files and it can be `.gitignore`ed in the repo)
  - an "update" button in the standalone binary GUI would also be nice so users can update in-app
  
- dynamic color theme matching game? (GUI)

- for the CLI, add a flag that lets you generate X number of teams and then save to a file
  - i guess this could also be used for coverage testing to make sure certain distributions are being met
  - also have e.g. `dexelect --generate` to print a generated team to the command line instantly and `dexelect --random`
  

- add bug report link / template

- "report a bug" button in the GUI

- wacky idea: "prescribed poke ball" option that displays the type of ball u should catch something in, like a ball png for the specific ball in the top right of the card. can be in the "Display" toggles. Would require some additional progression/config data because certain balls are not available till later in game.

- Get the Gen 3 "? in circle" sprite for not-yet-generated party members

- change "selected_sphere_mode"s in meta file to be numbered instead, so they can be selected from config file regardless of name (to allow customizing this setting)

- add 'type_blacklist' to pytests
- add new 'party_size' global config setting to pytests?

