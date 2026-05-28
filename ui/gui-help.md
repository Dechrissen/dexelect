# Dexelect — Progression-aware Pokémon Party Generator

## Overview

Dexelect is a progression-aware Pokémon party generator tool. It can generate a party according to the game's natural progression.

Output contains:

1. The party, along with details such as types and base stat totals for each member
2. The acquisition details for each member (i.e., how and where to obtain them in the game)
3. Party balance stats (Lean, Spread, Pattern, Distribution, HM Coverage) which describe the overall feasibility of assembling that party

## How to Use

To generate a party, click "Generate Party" or press Enter in the Generate tab.

From the left sidebar, you can:

- Change Game
- Change Mode
- Set Party Size (1–6)
- Hide accompanying details for generated teams
- Export party to text file

To modify configuration options, navigate to the Config tab and make changes to your liking.

## Modes

### Progression
Generates a party which adheres to logical game progression and config settings.

### Random
Generates a completely random party drawn from the National Pokédex for the selected game. Config settings are ignored in this mode.

## Balance Stats / Terminology

### Sphere
A broad chunk of game progression (e.g. Sphere 1 for Kanto spans Pallet Town to Cerulean City).

### Lean
The general bias of the party toward early or late game (early_game_heavy / balanced / late_game_heavy).

### Spread
How tightly grouped the party's acquisition spheres are (clustered / mixed_spread / wide_spread).

### Pattern
The qualitative shape of the party across spheres (single_cluster / dual_cluster / early_late_split / middle_only).

### Distribution
A breakdown of how many party members appear in each sphere.

## Spheres

Sphere modes can be changed in the Spheres tab. Enabled spheres are displayed beneath the selector depending on the active Sphere mode. Per-sphere location lists can be referenced here as well.

Each game has its own available Sphere modes. The 'all' option enables all spheres for a given game, including postgame.

## Configuration

Use the Config tab to view and edit settings for the currently selected game.

The tool's output can be fine-tuned to your liking by tweaking values such as:

- Party balancing
- Pokémon details (types, stat totals, etc.)
- Allow acquisition methods (walk, surf, rod, etc.)

Hover over the tooltips in the Config tab for an explanation of each config field.

## Tips & Suggestions

Dexelect can be used to "prescribe" a party to be used in challenge playthroughs. Depending on the restrictiveness of your configuration settings, the output party could be quite challenging to use in-game.

### Challenge run
Generate a party with difficult configuration settings, and challenge yourself to enter the Hall of Fame using only that party.

### Race with friends
Generate a party and race your friends (using the same party) to finish the game. In-game time (IGT) can be used to determine a victor.

### General team inspiration
To introduce variety to your playthroughs, Dexelect can be used to generate a team for you that you might not otherwise assmeble on your own.

