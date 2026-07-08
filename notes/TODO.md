# TODO

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

- coverage bar graphs, etc. (type coverage distribution)

- check every location from locations is in meta spheres list (also add unit test for this?)

- add unit tests for party generation functions (define test parties)

- add coverage tests for running generation for a few minutes and making sure certain % of pokemon get generated? gotta figure out what metric makes sense



- add event support generally (gen 2/3)
  - might just be eon_ticket acquisition method toggle
  - add setting to meta file for G/S that is a boolean to enable or disable whether player has access to CELEBI event. 
  celebi event data (gs ball acquisition method? will just be in the data files but only work if this setting is 
  turned on.)

- figure out if we need to handle stone availability in the config/meta files. If Flareon gets generated in party in 
  gen 2, it will assume a fire stone is available. is it? maybe back to the original idea of adding it to the 
  spheres list when it becomes available, then checking if stones are acquired by the time the pokemon is generated.
    - same with other evo items


- add feature "only generate pokemon in Sphere X" (or should this only be accomplished by the sphere_modes in meta file?)

- add to AUR somehow, or add some instructions in README for "how to install on Linux so it can run from launchers like wofi, etc.".
  - Use a `.desktop` file setup?
  - add to `/bin`?
  - PATH?
  - app icon which can be used by application launchers in Linux but also to replace the top left window icon in Windows
  - maybe install an install.sh script to build the binary, create the /bin entry, put the icon in the right spot, and make the .desktop file
  
- add `--help` to main.py

- add Claude skill file which acts as instructions for Claude to help guide users when adding a new romhack from the command line (Claude code). e.g. it knows the structure of the pokedex and locations files, it knows the data it needs and where to get it (Serebii or something), and it knows how to add all that to the repo, but it asks user questions along the way, like "does this romhack have custom pokemon or can I use an existing pokedex file?". It needs context about whole project structure.

- move to 1.0.0 after config file schemas / system is finished (so users can keep config files and it can be `.gitignore`ed in the repo)

- an "update" button in the standalone binary GUI, so users can update in-app
  
- dynamic color theme matching game? (GUI)

- for the CLI, add a flag that lets you generate X number of teams and then save to a file
  - i guess this could also be used for coverage testing to make sure certain distributions are being met
  - also have e.g. `dexelect --generate` to print a generated team to the command line instantly and `dexelect --random`
  
- wacky idea: "prescribed poke ball" option that displays the type of ball u should catch something in, like a ball png for the specific ball in the top right of the card. can be in the "Display" toggles. Would require some additional progression/config data because certain balls are not available till later in game.

- add honey tree calcs - https://www.dragonflycave.com/sinnoh/honey-trees/

- add a web ui option that can be selected via command line and open locally in browser, but also be the entry point for "standalone hosting" of the web app served on my site

- add mac binary

- DEBUG stuff:
  - have debug details be output to a file
  - have party be output regularly even if it doesnt fail so we can see the party in debug

- improve debug logging

- might not make sense to have postgame spheres at all (e.g., in D/P Cresselia can only be obtained post-national dex which contradicts our exclusion of other post-national dex stuff like poke radar and swarms etc. So maybe postgame doesn't need to be included in any of the games.)
  - alternatively, add all postgame stuff in all games (post-national dex stuff)


- add some script that generates the config files for each game (creates the yaml) or something that resets it to the default (recommended) values before i push a release (or maybe have options in the UI to switch to certain presets, like "recommended", "hard", etc)
  - `config_gen1.default.yaml`
  - `config_gen1.hard.yaml`
  - then i can start releasing new rulesets, themed challenges, etc. and distribute the config yamls to people
    - e.g. mono-type runs or 2nd stage only runs

- add acq details and balance stats to 'Random (Obtainable)' parties