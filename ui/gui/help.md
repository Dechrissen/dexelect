# Dexelect — Progression-aware Pokémon Party Generator

## Overview

Dexelect is a progression-aware Pokémon party generator tool which generates parties according to the game's natural progression.

Basic output:

1. A party, along with per-member details such as types and base stat totals
2. The acquisition details for each member (i.e., how and where to obtain them)
3. Party balance stats, which describe the overall feasibility of assembling the party

## Options (Left Sidebar)

- Game: Dropdown of available games
- Mode: Radio list of available generation modes
- Party Size: Radio list of party size limits (1–6)
- Display: Checklist for toggling display of party details
    - Acquisition Details: Per-Pokémon "how to acquire" details (which form, location, method)
    - HM Coverage: Collective list of HMs learnable by the party
    - Balance Stats: Semantic labels which describe the overall feasibility of assembling the party
- Export Party: Save current party to a text file

## Modes

### Progression
Generates a party which adheres to logical game progression and config settings.

### Random (Obtainable)
Generates a completely random party drawn from the set of obtainable Pokémon for the selected game. Game restrictions and config settings are ignored in this mode (e.g., multiple legendary or starter Pokémon could co-occur).

### Random (National Dex)
Generates a completely random party drawn from the National Pokédex for the selected game. Game restrictions and config settings are ignored in this mode (e.g., multiple legendary or starter Pokémon could co-occur).

## Tabs (Right Panel)

### Generate

To generate a party while in the Generate tab, click "Generate Party" or press Enter.

### Spheres

In the Spheres tab, enabled spheres along with the number of new species they introduce are displayed.

Sphere modes can be changed. Each game has its own set of available sphere modes. The 'all' option enables all spheres for a given game, including endgame and postgame (for typical usage, you'd probably want to keep these spheres disabled).

### Config

Use the Config tab to view and edit settings for the currently selected game.

The tool's output can be fine-tuned to your liking by tweaking values such as:

- Party balancing
- Pokémon details (types, stat totals, etc.)
- Allowed acquisition methods (walk, surf, old_rod, etc.)

Hover over the tooltips for an explanation of each config field.

## Terminology

### Sphere
A broad chunk of game progression (e.g. Sphere 1 for Kanto spans Pallet Town to Viridian Forest).

### Lean
The general bias of the party toward early or late game (early_game_heavy / balanced / late_game_heavy).

### Spread
How tightly grouped the party's acquisition spheres are (clustered / mixed_spread / wide_spread).

### Pattern
The qualitative shape of the party across spheres (single_cluster / dual_cluster / early_late_split / middle_only).

### Distribution
A breakdown of how many party members appear in each sphere.

## Tips & Suggestions

Dexelect intended usage is to "prescribe" a party to be used in challenge playthroughs. Depending on the restrictiveness of your configuration settings, the output party could be quite challenging to use in-game.

### Challenge run
Generate a party with difficult configuration settings, and challenge yourself to enter the Hall of Fame using only that party.

### Race with friends
Generate a party and race your friends (using the same party) to finish the game. In-game time (IGT) can be used to determine a victor at the end.

### General party inspiration
To introduce variety to your playthroughs, Dexelect can be used to generate a party which you might not otherwise assemble on your own. For instance, if you only want 1 party member to be randomly chosen for you: set Party Size to 1 and Generation Mode to "Random (Obtainable)", then generate.

