# _Dexelect_ Suggested Rulesets & Usage

The purpose of this document is to provide inspiration for how to use _Dexelect_. This is not an exhaustive list — just ideas!

## Regular challenge run
- Generate a party with the default config settings (or your own)
- Defeat the Pokémon League, registering the generated party in the Hall of Fame

## Async race
- Multiple players play the same game
- Everyone uses the same generated party
- Defeat the Pokémon League, registering the generated party in the Hall of Fame
- Reach the win condition with a faster IGT than anyone else

## Ideas for extra "hard mode" restrictions
- Do not acquire _any_ other Pokémon than what was generated (this might require `force_starter: true` and all necessary HMs to be selected in the config)
- All of your Pokémon must be at least the level of the lowest-leveled Pokémon in the Pokémon League before you enter the League
- Defeat the Pokémon League within a certain IGT, e.g. 8 hours for Gen 1
- Set `bst_max` to a value which excludes pseudo-legendaries and other high-stat Pokémon
- Mono-type run (set `type_distribution: all_share_one_type` and `allow_dual_type: false`)
- Set `allow_not_fully_evolved: true` and `max_evo_stage: 2` to restrict all 3-stage Pokémon to their second stage

## Miscellaneous usecases
- Generate a single random Pokémon to obtain by setting Party Size = 1 and Mode = 'Random (Obtainable)'
