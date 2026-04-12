# _TeamGen_ – Universal Party Generator

A tool for generating a random, progression-viable party of Pokémon for use in a playthrough. 
Pokémon availability and game progression are respected in the final output, and customization options are 
available to curate the output further.

<p align="center" style="margin-left: 10%; margin-right: 10%">
  <img src="screenshots/sample-output.png">
</p>

## Table of contents
1. [Introduction](#introduction)
2. [Currently supported games](#currently-supported-games)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Contributing](#contributing)
6. [License](#license)

## Introduction
_TeamGen_ generates (prescribes) a party for use in a playthrough — either to introduce an element of 
challenge or simply for team inspiration. 
The tool is **universal** in the sense that it maintains compatibility with _most_ generations of Pokémon, 
but also with romhacks that might contain the following (as long as the relevant game data files are added):
- New Pokémon
- New locations 
- Changes to existing game data (location data, evolution methods, etc.)

## Currently supported games
- **Vanilla**
  - Pokémon Red & Blue
  - Pokémon Gold & Silver
  - Pokémon Ruby & Sapphire
- **Romhacks**
  - [Pokémon Solus RGB](https://github.com/Dechrissen/poke-solus-rgb)

## Installation
### Option 1: Linux / macOS (CLI)

Prerequisites:
- Python 3.10+
- `pip`
- (Optional) `venv`

Steps:
1. Clone this repository (or download the [latest release](https://github.com/Dechrissen/teamgen/releases/latest) 
   source code and extract it)
2. `cd teamgen`
3. (Optional) Create a virtual environment first for less headache
    - `python -m venv .venv`
    - `source .venv/bin/activate`
4. Install dependencies (`pip install -r requirements.txt`)
5. Run with `python main.py`

### Option 2: Windows (Prebuilt executable)

1. Download `teamgen-<version>.zip` from the [latest release](https://github.com/Dechrissen/teamgen/releases/latest) 
  assets
2. Extract
3. Run `teamgen.exe`

## Usage

### Using the app
- `ENTER` – Generate a party with the current settings
- `M` – Toggle the generation mode between 'Progression' and 'Random'
  - Progression: Considers game data, locations, progression, config settings
  - Random: Completely random generation using current game's National Dex
- `G` – Open the 'Supported Games' menu to switch current game
- `R` – Reload the config file (after making any config changes while the app is running)
- `H` – Display help menu
- `Q` – Quit the app

### Changing config settings
Open `/config/config_gen1.yaml` (for example, for Generation 1 games). Modify values according to your preferences. 
Save the file and then use the `R` option in the app to reload.

> [!NOTE]
> If you are running the Windows executable, the config files are in `/_internal/config`.

## Contributing

If you'd like to add support for a missing game or romhack, see [`CONTRIBUTING.md`](/CONTRIBUTING.md).

## License
_TeamGen_ is licensed under the MIT License. See [`LICENSE`](/LICENSE) for full details.
