# Dexelect – Progression-aware Party Generator

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Q5Q311GBFF)

> "Dex" (Pokédex) + "elect" / "select" — a tool that elects Pokémon to be used in the player's party

A tool for generating (prescribing) a random, progression-aware party of Pokémon for use in a challenge playthrough. 
Pokémon availability and game progression are respected in the final output, and customization options are 
available to curate the output further.

<p align="center">
  <img src="screenshots/sample-gui-output.png">
</p>


## Table of contents
1. [Introduction](#introduction)
2. [Currently supported games](#currently-supported-games)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Contributing](#contributing)
6. [Support the app](#support-dexelect)
7. [License](#license)


## Introduction
Dexelect generates (prescribes) a **progressively-sound** party for use in a playthrough — either to introduce an element of 
challenge or simply for team inspiration. See the [suggested rulesets](/docs/RULESETS.md) for some ideas about how to use Dexelect.

The app is **universal** in the sense that it maintains compatibility with most generations of Pokémon games, 
_and_ with romhacks that might contain the following (as long as the relevant game data files are added):
- New Pokémon
- New locations 
- Changes to existing game data (location data, evolution methods, etc.)

See [`CONTRIBUTING.md`](/CONTRIBUTING.md) if you'd like to add support for a romhack.


## Currently supported games

### Vanilla

| Gen | Game       | Supported |
|-----|------------|-----------|
| 1   | Red        | ✔         |
| 1   | Blue       | ✔         |
| 1   | Yellow     | Planned   |
| 2   | Gold       | ✔         |
| 2   | Silver     | ✔         |
| 2   | Crystal    | Planned   |
| 3   | Ruby       | ✔         |
| 3   | Sapphire   | ✔         |
| 3   | Emerald    | Planned   |
| 4   | Diamond    | Planned   |
| 4   | Pearl      | Planned   |
| 4   | Platinum   | Planned   |

### Romhacks

| Gen | Game | Supported |
|-----|-----------------------------------------------------------|----|
| 1   | [Solus RGB](https://github.com/Dechrissen/poke-solus-rgb) | ✔  |


## Installation

### Option 1: Download the pre-built GUI executable (Windows/Linux)

1. Download `dexelect-<version>-<platform>.zip` from the [latest release](https://github.com/Dechrissen/dexelect/releases/latest) 
2. Extract it
3. Run `dexelect.exe` on Windows, or `dexelect` on Linux

### Option 2: Command-line installation

Prerequisites:
- Python 3.10+
- `pip`
- (Optional) `venv`

Steps:
1. Clone this repository (or download the [latest release](https://github.com/Dechrissen/dexelect/releases/latest) 
   source code and extract it)
2. `cd dexelect`
3. (Optional) Create a virtual environment (`python -m venv .venv`)
4. (Optional) Activate the virtual environment  (`source .venv/bin/activate`)
5. Install dependencies (`pip install -r requirements.txt`)
6. (Optional) If you want sprites to display in the GUI, run `python main.py --fetch_sprites`
7. Run `python main.py` for the GUI (for the CLI UI, run `python main.py --ui=cli`)


## Usage

### Using the GUI (`python main.py --ui=gui`)
- The app is split into sidebar (left) and main window (right)
- Left sidebar:
  - The mode can be toggled between 'Progression' and 'Random'
  - 'Acquisition details' and 'Balance stats' display can each be disabled
  - 'Reload config' button will reload the config files into the app if they were modified on disk while the app is running
- Main window:
  - "Generate" and "Config" tabs at the top can be switched between
  - Click "Generate party" to generate a party
  - Modify settings in the 'Config' tab if 
  
> [!NOTE]
> If you are running the standalone binary, the config files are in `/_internal/config` and they can still be modified in a text editor (but the 'Config' tab in the GUI is preferred).

### Using the CLI app (`python main.py --ui=cli`)
- `ENTER` – Generate a party with the current settings
- `M` – Toggle the generation mode between 'Progression' and 'Random'
  - Progression: Considers game data, locations, progression, config settings
  - Random: Completely random generation using current game's National Dex
- `G` – Open the 'Supported Games' menu to switch current game
- `R` – Reload the config file (after making any config changes while the app is running)
- `H` – Display help menu
- `Q` – Quit the app

#### Modifying config settings for the CLI app
Open `/config/config_gen1.yaml` (for example, for Generation 1 games). Modify values according to your preferences. 
Save the file and then, if the app was running, use the `R` option in the app to reload.


## Contributing

If you'd like to add support for a missing game or romhack, see [`CONTRIBUTING.md`](/CONTRIBUTING.md).


## Support Dexelect

Please support Dexelect development! The app is free and open-source, but you can support it in these ways:
- [Donate on Ko-fi](https://ko-fi.com/Q5Q311GBFF)
- Give this repository a Star :star:
- [Join the Solus Discord](https://discord.gg/YTxu5uM7r6)
- Share the app with someone who might be interested


## License

Dexelect is licensed under the MIT License. See [`LICENSE`](/LICENSE) for full details.
