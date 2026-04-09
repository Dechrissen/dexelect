from util import resource_path
from core import *
from data.loader import build_all_data_structures
from version import __version__
import os
import yaml
import time

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def set_game(mappings):
    selected_game = None
    valid_options = {}

    for i, game_title in enumerate(mappings.keys(), start=1):
        valid_options[str(i)] = game_title
        print(f"{i}. {game_title}")

    print("")
    print("Select game number.\n")

    user = input("> ").strip().lower()

    if user not in valid_options.keys():
        #print("not a valid selection")
        return False
    else:
        #print("valid selection")
        selected_game = valid_options[user]
        #print(f"selected game is {selected_game} with mappings {mappings[selected_game]}")
        with open(resource_path("config/global_settings.yaml"), "r") as f:
            data = yaml.safe_load(f)
        data["game"] = selected_game
        with open(resource_path("config/global_settings.yaml"), "w") as f:
            yaml.safe_dump(data, f)
        return True

def toggle_generation_mode(generation_mode):
    if generation_mode == 'Progression-viable':
        new_generation_mode = 'Random'
    elif generation_mode == 'Random':
        new_generation_mode = 'Progression-viable'
    else:
        # probably don't need this case but w/e
        new_generation_mode = 'Progression-viable'

    with open(resource_path("config/global_settings.yaml"), "r") as f:
        data = yaml.safe_load(f)
    data["generation_mode"] = new_generation_mode
    with open(resource_path("config/global_settings.yaml"), "w") as f:
        yaml.safe_dump(data, f)

    return new_generation_mode

def display_party(party_blob, config_data, global_settings, duration, game, generation_mode, config_file_path):
    # ANSI codes
    TITLE = "\033[1;100;93m" # bright black background, bold bright yellow text
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_YELLOW = "\033[93m"
    RESET = "\033[0m"

    show_acquisition_details = global_settings['show_acquisition_details']
    show_balance_stats = global_settings['show_balance_stats']

    def print_global_settings():
        print(f"Game setting:\t {game}")
        print(f"Config file:\t {config_file_path}")
        print(f"Generation mode: {generation_mode}\n")

    print(f"{TITLE}===== TeamGen v{__version__} ====={RESET}\n")

    # Case 1: Never generated yet, or set_game invalid option was passed
    if party_blob is None:
        print("Welcome to TeamGen!\n")
        print_global_settings()
        return

    # Case 2: Tried but failed
    if party_blob is False:
        print("No party could be generated with current settings!\n")
        print_global_settings()
        return

    # Other cases
    if party_blob == 'invalid_input':
        print(f"{BRIGHT_RED}Invalid input! Please try again.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'game_updated':
        print(f"{BRIGHT_GREEN}Game setting updated.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'generation_mode_toggled':
        print(f"{BRIGHT_GREEN}Generation mode updated.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'config_reloaded':
        print(f"{BRIGHT_GREEN}Config reloaded.{RESET}\n")
        print_global_settings()
        return

    # ---------------- PRINT PARTY --------------------------------------------------------------------------
    print(f"{BRIGHT_YELLOW}---- PARTY -------------------{RESET}")
    # sort party by Sphere number appearance ascending, with exception for starter in slot 1
    def sort_key(p):
        prescribed = p["random_pool_entry_instance"]
        # acquisition method (None in Random generation_mode)
        method = prescribed["acquisition_method"] if prescribed else None
        is_starter = (method == "starter")

        # put starters first. starter_rank = 0, others = 1
        starter_rank = 0 if is_starter else 1

        # earliest_pool for ordering (safe fallback if None)
        earliest_pool = p.get("earliest_pool", None)
        pool_rank = earliest_pool if earliest_pool is not None else 9999

        return (starter_rank, pool_rank)

    sorted_party = sorted(party_blob["party_with_acquisition_data"], key=sort_key)

    for i, pokemon in enumerate(sorted_party, start=1):
        prescription_details = ""
        if show_acquisition_details:
            prescribed_pool_entry = pokemon["random_pool_entry_instance"]

            # only exists in non-Random generation_mode
            if prescribed_pool_entry is not None:
                prescribed_acquisition_method = prescribed_pool_entry["acquisition_method"]
                prescribed_acquiring_location = prescribed_pool_entry["acquiring_location"]

                earliest_form = pokemon["earliest_form"]
                earliest_pool = pokemon["earliest_pool"]

                prescription_details = (
                    f"  \t acquire as {earliest_form.name} via "
                    f"{prescribed_acquisition_method} at {prescribed_acquiring_location} "
                    f"(Sphere {earliest_pool})"
                )
        print(f"{i}. {pokemon['party_member_obj'].name}" + prescription_details)
    # ---------------------------------------------------------------------------- END PRINT PARTY ----------

    if show_balance_stats:
        print(f"\n{BRIGHT_YELLOW}---- STATS -------------------{RESET}")
        print("Distribution:\t", [("Sphere " + str(sphere) + ": " + str(party_blob["party_distribution"][sphere])) for sphere in party_blob["party_distribution"]] if party_blob["party_distribution"] else None)
        #print("score_median:", party_blob["score_median"])
        print("Lean:\t\t", party_blob["lean"])
        print("Spread:\t\t", party_blob["spread"])
        print("Pattern:\t", party_blob["pattern"])
    print()

    if duration:
        print(f"[Generation took {duration:.2f}s]\n")

    print_global_settings()


def ui_loop(all_pools, all_pokemon, config_data, meta_data, mappings, global_settings):
    # ANSI codes
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_MAGENTA = "\033[95m"
    RESET = "\033[0m"

    party_on_screen = None
    duration = None
    generation_mode = global_settings['generation_mode']
    game = global_settings['game']
    config_file_path = mappings[game]['config']

    while True:
        if DEBUG:
            # so we don't clear the screen and can see debug output
            pass
        else:
            clear()

        mode = None

        display_party(party_on_screen, config_data, global_settings, duration, game, generation_mode, config_file_path)

        print(f"Press {BRIGHT_CYAN}ENTER{RESET} to generate a party.")
        print(f"{BRIGHT_CYAN}G{RESET} - Toggle generation mode")
        print(f"{BRIGHT_CYAN}S{RESET} - Set game")
        print(f"{BRIGHT_CYAN}R{RESET} - Reload config")
        print(f"{BRIGHT_CYAN}Q{RESET} - Quit")
        print("")
        print(f"Support this software: {BRIGHT_MAGENTA}https://ko-fi.com/dechrissen{RESET}")
        print("")

        user = input("> ").strip().lower()

        # check if any options pressed
        if user == "q":
            print("Goodbye!")
            return
        if user == "g":
            mode='toggle_generation_mode'
        if user == "s":
            mode = "set_game"
        if user == "r":
            mode = "reload_config"

        # otherwise, when ENTER pressed ...
        if DEBUG:
            pass
        else:
            clear()

        # check for any set modes
        if mode == 'set_game':
            if set_game(mappings):
                all_pools, all_pokemon, config_data, meta_data, mappings, global_settings = build_all_data_structures()
                # if user sets a new game, then the displayed game and corresponding config file path need to change too
                game = global_settings['game']
                config_file_path = mappings[game]['config']
                party_on_screen = 'game_updated'
                continue
            else:
                party_on_screen = 'invalid_input'
                continue
        elif mode == 'toggle_generation_mode':
            generation_mode = toggle_generation_mode(generation_mode)
            party_on_screen = 'generation_mode_toggled'
            continue
        elif mode == 'reload_config':
            all_pools, all_pokemon, config_data, meta_data, mappings, global_settings = build_all_data_structures()
            party_on_screen = 'config_reloaded'
            continue

        # generation
        if generation_mode == 'Random':
            print("Generating party...\n")
            start = time.time()
            party_blob = generate_fully_randomized_party(all_pokemon, n=6)
            end = time.time()
            duration = end - start
        elif generation_mode == 'Progression-viable':
            print("Generating party...\n")
            start = time.time()
            party_blob = generate_final_party(
                all_pools, all_pokemon, config_data, meta_data, n=6
            )
            end = time.time()
            duration = end - start

        # if generation fails, mark explicitly with False
        if party_blob is None:
            party_on_screen = False
        else:
            party_on_screen = party_blob
