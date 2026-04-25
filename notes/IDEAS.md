## names
- finalsix
- vanillasix
- teamgen <--
- partygen
- uf6g (universal final six generator) or ufsg
- upg (universal party generator)
- poketeamgen
- pokesix

## names phase 2
- MonGenie
- Monfigurator
- MonSelect
- Monselectrx
- Monselectool
- Monselector
- MonSelRx
- DexSelect
- DeXelect
- Dexelect <--
- Dexelector
- DexSel
- Monscriber
- MonScribe
- MonConfig
- Moncompile
- Parselec
- Parselector
- Partsel
- Genster
- Runtool
- Selectrx
- Partselrx
- ProgTeam
- Proggy
- ProgPal
- Proggymon
- Progerator
- Proggydex
- Progdexter
- Progster

## example "build" (list and order of routes and items in file)
- or "world" ? "structure" ?
```json
"build": {
  "spheres":
    {
      "sphereNum": 1,
      "contents": [
        {"name": "Route1", "type": "map"},
        {"name":"PokeFlute", "type": "item"},
        {"name":"SuperRod", "type": "item"},
        {"name": "Surf", "type": "item"} // or "hm"?
      ]
    },
    {
      "sphereNum": 2,
      "contents": [
        ...
      ]
    }
}
```
- based on the above, the program will iterate over everything in the current sphere, add any items to "inventory", and then when it comes time to iterate over all the current maps in the sphere, it will check for inventory items to see if Super Rod entries for that map are up for grabs, if Snorlax is up for grabs based on whether poke flute is in inventory, etc.
- for each game file, in order to get the list of items to check for without hardcoding it, you can just have a quick run through the file for all the "type": "item"s from above and add all unique instances to a list. then when checking for each route, youll know which item to check for?

## what the pools look like after being generated
```json
"pools" : {
  "poolNum": 1,
  "contents": [
    "ELECTABUZZ",
    "MAGNEMITE",
    "MAGNETON",
    "PIKACHU",
    "VOLTORB"
  ],
  // this list keeps track of evo items that are available at this sphere, so the program can check all the pools to see if
  // the required evo item for the generated mon is available. it probably isnt relevant which sphere its in unless
  // you have a setting like "make sure i can get this pokemon before X point in the game"
  "evo_items": [
    "FIRE_STONE",
    "METAL_COAT"
  ]
}
```

## more ideas

- for trades in the pokemon data file: `"trade": ["ABRA for MR.MIME"]`
- add ALL moon stones separately to the logic file spheres? (in `evo_items` list)


- option to reroll 1 pokemon (e.g. `reroll 2` to reroll the second) (to do this, we can pass an optional party list 
  of Pokemon objects to the generate_final_party function. If it's non-empty, it can be treated as the base party to 
  use/continue generating for)

- add visual graph or w/e to balance grade output
- add a region map (the one from the game) with a heatmap style overlay (or just dots) that shows where your party is 
  acquired :)

- DEBUG stuff:
  - have debug details be output to a file
  - have party be output regularly even if it doesnt fail so we can see the party in debug


## final unit tests/checks
- have a lookup table of all valid pokemon for a given region/gen, make sure all pokemon listed in the files are present in the lookup table
- validate formatting of logic file (instructions for running this should be in docs/MR instructions so contributors of new games can run the unit test first)
- the 'meta' yaml could also be used to keep track of the list of all possible items in the game? (the master list 
  source of truth to check against during unit tests?)
  - yes, via the "evolution_items_available" list
- can have test parties already built to send to the is_party_valid funciton to make sure certain ones fail (2 
  modals, etc.)
output some sort of "incompatibility" message if it detects that the 3 data YAMLs 
  are not compatible with each other (i.e. all the maps and pokemon should match spelling, etc between all 3 files 
  before any logic is run)

## Later ideas
- Provide ChatGPT-powered subtool in the program (CLI) that allows the user or a developer to add a new logic file for a new game by having a ChatGPT token in a config, and then a prompt with placeholders etc where the user can provide links to the prompt for ChatGPT (like links to pokemon data, locations on bulbapedia, etc) to build at least the bulk of a new logic json. Maybe in the case of romhacks, a link to the code idk.
- nickname generator function
  - pokemon universe pack
  - wacky pack
- gym leader themed generation (create pools of valid canonical pokemon from certain characters like leaders, gio, etc.)
  - then you can have a check that selects only from that pool of pokemon, OR there must be X overlap or something
  - for this mode, it might not work with the other options like BALANCED, etc. so i wonder if you just leave it 
    all as-is and let the user see if it works, or if you add in overrides to ignore the balancing for this mode
- wacky "team name assignment" feature. analyzes certain things about the pokemon (types? egg group? etc) and 
  somehow generates a name for the team from a preset pool of nouns and adjectives etc. ("the aquatic defenders"... 
  "the fiery humanoids") :/ ... idk
  - can take into account stats of the pokemon as well, e.g. "defenders" gets high probability of being picked if 
    most pokemon on team have relatively high defense
- add a "Team Defense" and "Team Coverage" analysis to the output, like here: https://richi3f.github.io/pokemon-team-planner
- Learn how to make a Python app work on web app --> `www.dexelect.app`
- Integrate with randomized roms of vanilla games (need a function that reads rom data and outputs pokemon data in 
  my needed format in `locations` yaml)


## Similar things
- https://richi3f.github.io/pokemon-team-planner
- https://randompokemon.com/
- https://mypokemonteam.com/
