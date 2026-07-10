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



- add event support generally (gen 2/3/4)
  - might just be eon_ticket acquisition method toggle
  - add setting to meta file for G/S that is a boolean to enable or disable whether player has access to CELEBI event. 
  celebi event data (gs ball acquisition method? will just be in the data files but only work if this setting is 
  turned on.)
  - shaymin darkrai



- add to AUR somehow
  
- add Claude skill file which acts as instructions for Claude to help guide users when adding a new romhack from the command line (Claude code). e.g. it knows the structure of the pokedex and locations files, it knows the data it needs and where to get it (Serebii or something), and it knows how to add all that to the repo, but it asks user questions along the way, like "does this romhack have custom pokemon or can I use an existing pokedex file?". It needs context about whole project structure.

- an "update" button in the standalone binary GUI, so users can update in-app
  

- for the CLI, add a flag that lets you generate X number of teams and then save to a file
  - i guess this could also be used for coverage testing to make sure certain distributions are being met
  - also have e.g. `dexelect --generate` to print a generated team to the command line instantly and `dexelect --random`
  
- wacky idea: "prescribed poke ball" option that displays the type of ball u should catch something in, like a ball png for the specific ball in the top right of the card. can be in the "Display" toggles. Would require some additional progression/config data because certain balls are not available till later in game.

- honey tree calcs - https://www.dragonflycave.com/sinnoh/honey-trees/

- add a web ui option that can be selected via command line and open locally in browser, but also be the entry point for "standalone hosting" of the web app served on my site. something that runs a webserver on a port or something so we can use the python backend.

- add mac binary to github workflow, and mac build instructions to readme 

- DEBUG stuff:
  - have debug details be output to a file
  - have party be output regularly even if it doesnt fail so we can see the party in debug
  - improve debug logging

- might not make sense to have postgame spheres at all (e.g., in D/P Cresselia can only be obtained post-national dex which contradicts our exclusion of other post-national dex stuff like poke radar and swarms etc. So maybe postgame doesn't need to be included in any of the games.)
  - alternatively, add all postgame stuff in all games (post-national dex stuff)


- add documentation about how to add new config presets (CONTRIBUTING?)

- figure out if we need to handle stone availability in the config/meta files. If Flareon gets generated in party in 
  gen 2, it will assume a fire stone is available. is it? maybe back to the original idea of adding it to the 
  spheres list when it becomes available, then checking if stones are acquired by the time the pokemon is generated.
    - same with other evo items
    - or simply "is X evo item available in Y game at all?" boolean

- add some popular romhacks maybe