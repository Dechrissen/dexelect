# TODO

- make a logo
- add to itch.io
- add Yellow
- add Crystal

- clean up CLI UI code and add some comments

- add comments to unit test functions

- make "gift" into "choice" for HITMONs?

- add "user defined modals" to the config, which are extra modals that get added to the modal list when doing the check
  - e.g. "nidoran_m and nidoran_f"
  - jynx and mr.mime

- annotate the progression file so we know where certain things come from, e.g. the moon stone on route 2 can only be gotten in sphere 2, so we should have a comment "from Route2 after Cut"

- Finish unit test suite

- add Pool class
- config should maybe be a Config class. This would make it easier to validate and pass along to functions

- add HM coverage output
  - list of HMs, check marks next to covered ones, or color them green

- check every location from locations is in meta spheres list (also add unit test for this?)

- add unit tests for party generation functions (define test parties)

- add toggle options for "Show balance stats" and "Show acquisition details" in UI

- add 'export to txt' option for saving teams, or do it automatically (last X teams generated in a file)

- add some code that generates the config files for each game (creates the yaml) or something that resets it to the default (recommended) values before i push a release (or maybe have options in the UI to switch to certain presets, like "recommended", "hard", etc)

- add "types to exclude" config setting

- add setting to meta file for G/S that is a boolean to enable or disable whether player has access to CELEBI event. 
  celebi event data (gs ball acquisition method? will just be in the data files but only work if this setting is 
  turned on.)

- figure out if we need to handle stone availability in the config/meta files. If Flareon gets generated in party in 
  gen 2, it will assume a fire stone is available. is it? maybe back to the original idea of adding it to the 
  spheres list when it becomes available, then checking if stones are acquired by the time the pokemon is generated.

- toggle for "gen 2 or gen 1 pokemon only" in gen 2 generation? and onward
  - or not a toggle, but a list of 'allowed generations' e.g. [1,2,3]

- add 'Milk Drink' as field moves (HMs) in Gen 2 and 3?
- add 'Secret Power' as field move (HM) in gen 3?

- add party size limit to config file options
