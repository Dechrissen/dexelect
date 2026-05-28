# Copyright 2026 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/

from util import resource_path
from core import *
from data.loader import build_all_data_structures
from version import __version__
import os
import yaml
import time
from util import resource_path

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_help():
    print_header()

    with open(resource_path('ui/cli-help.txt')) as f:
        help_text = f.read()
        print(help_text)

    print_copyright()

    print("")

    user = input("Press ENTER to go back.")
    return

def set_game(mappings):
    selected_game = None
    valid_options = {}

    print_header()

    print("Supported Games")
    print("---------------")
    for i, game_title in enumerate(mappings.keys(), start=1):
        valid_options[str(i)] = game_title
        print(f"{i}. {game_title}")

    print("")
    print("Enter game number.\n")

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

def set_party_size():
    print_header()

    print("Set Party Size")
    print("--------------")

    print("\n")
    print("Enter a number (1–6).\n")

    user = input("> ").strip().lower()

    if user not in ['1', '2', '3', '4', '5', '6']:
        return False
    else:
        selected_party_size = int(user)
        with open(resource_path("config/global_settings.yaml"), "r") as f:
            data = yaml.safe_load(f)
        data["party_size"] = selected_party_size
        with open(resource_path("config/global_settings.yaml"), "w") as f:
            yaml.safe_dump(data, f)
        return True


def toggle_generation_mode(generation_mode):
    if generation_mode == 'Progression':
        new_generation_mode = 'Random'
    elif generation_mode == 'Random':
        new_generation_mode = 'Progression'
    else:
        # probably don't need this case but w/e
        new_generation_mode = 'Progression'

    with open(resource_path("config/global_settings.yaml"), "r") as f:
        data = yaml.safe_load(f)
    data["generation_mode"] = new_generation_mode
    with open(resource_path("config/global_settings.yaml"), "w") as f:
        yaml.safe_dump(data, f)

    return new_generation_mode

def print_header():
    TITLE = "\033[1;100;96m"
    RESET = "\033[0m"
    print(f"{TITLE}======== Dexelect v{__version__} ========{RESET}\n")

def print_copyright():
    BRIGHT_BLACK = "\033[90m"
    RESET = "\033[0m"
    print(
            f"{BRIGHT_BLACK}"
            "Copyright 2026 Derek Andersen (derekandersen.net). Licensed under the MIT License.\n"
            "Support this software: https://ko-fi.com/dechrissen"
            f"{RESET}"
        )

def display_party(party_blob, config_data, global_settings, duration, game, generation_mode, config_file_path, party_size):
    # ANSI codes
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_YELLOW = "\033[93m"
    RESET = "\033[0m"

    show_acquisition_details = global_settings['show_acquisition_details']
    show_balance_stats = global_settings['show_balance_stats']
    show_hm_coverage = global_settings['show_hm_coverage']

    def print_global_settings():
        # ---------------- PRINT SETTINGS ---------------------------------------------------------------------
        print(f"{BRIGHT_CYAN}---- SETTINGS ------------------{RESET}")
        print(f"Game:\t\t {game}")
        print(f"Mode:\t\t {generation_mode}")
        print(f"Party size:\t {party_size}")
        print(f"Config:\t\t {config_file_path}")
        print("")

    print_header()

    # Case 1: Never generated yet, or set_game invalid option was passed
    if party_blob is None:
        print("Welcome to Dexelect!\n")
        print_global_settings()
        return

    # Case 2: Tried but failed
    if party_blob is False:
        print("No party could be generated. Please adjust settings or try again.\n")
        print_global_settings()
        return

    # Other cases
    if party_blob == 'invalid_input':
        print(f"{BRIGHT_RED}Invalid input! Please try again.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'game_updated':
        print(f"{BRIGHT_GREEN}OK! Game updated.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'party_size_updated':
        print(f"{BRIGHT_GREEN}OK! Party size updated.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'generation_mode_toggled':
        print(f"{BRIGHT_GREEN}OK! Mode updated.{RESET}\n")
        print_global_settings()
        return

    if party_blob == 'config_reloaded':
        print(f"{BRIGHT_GREEN}OK! Config reloaded.{RESET}\n")
        print_global_settings()
        return

    # ---------------- PRINT PARTY --------------------------------------------------------------------------
    print(f"{BRIGHT_YELLOW}---- PARTY ---------------------{RESET}")
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
    for i in range(len(sorted_party) + 1, 7):
        print(f"{i}. —")
    # ---------------------------------------------------------------------------- END PRINT PARTY ----------

    if show_balance_stats or show_hm_coverage:
        print(f"\n{BRIGHT_YELLOW}---- STATS ---------------------{RESET}")

    if show_balance_stats:
        print("Distribution:\t", [("Sphere " + str(sphere) + ": " + str(party_blob["party_distribution"][sphere])) for sphere in party_blob["party_distribution"]] if party_blob["party_distribution"] else None)
        #print("score_median:", party_blob["score_median"])
        print("Lean:\t\t", party_blob["lean"])
        print("Spread:\t\t", party_blob["spread"])
        print("Pattern:\t", party_blob["pattern"])

    if show_hm_coverage:
        hm_config = config_data.get("ensure_hm_coverage", {})
        party_hm_coverage = set(
            hm for m in party_blob["party_with_acquisition_data"]
            for hm in m["party_member_obj"].hm_learnset
        )
        parts = []
        for hm_name in hm_config:
            if hm_name in party_hm_coverage:
                parts.append(f"{BRIGHT_GREEN}✓{hm_name}{RESET}")
            else:
                parts.append(f"{BRIGHT_BLACK}{hm_name}{RESET}")
        print("HM Coverage:\t", " ".join(parts))

    print()

    if duration:
        print(f"[Generation took {duration:.2f}s]\n")

    print_global_settings()


def ui_loop(all_pools, all_pokemon, config_data, meta_data, mappings, global_settings):
    # ANSI codes
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_BLACK = "\033[90m"
    RESET = "\033[0m"

    party_on_screen = None
    duration = None
    generation_mode = global_settings['generation_mode']
    game = global_settings['game']
    party_size = global_settings.get('party_size', 6)
    config_file_path = mappings[game]['config']

    while True:
        if DEBUG:
            # so we don't clear the screen and can see debug output
            pass
        else:
            clear()

        mode = None

        display_party(party_on_screen, config_data, global_settings, duration, game, generation_mode, config_file_path, party_size)

        print(f"Press {BRIGHT_CYAN}ENTER{RESET} to generate a party.")
        print(f"{BRIGHT_CYAN}G{RESET} - Set [G]ame")
        print(f"{BRIGHT_CYAN}M{RESET} - Toggle [M]ode")
        print(f"{BRIGHT_CYAN}P{RESET} - Set [P]arty Size")
        print(f"{BRIGHT_CYAN}R{RESET} - [R]eload config from disk")
        print(f"{BRIGHT_CYAN}H{RESET} - [H]elp")
        print(f"{BRIGHT_CYAN}Q{RESET} - [Q]uit")
        print("")

        print_copyright()

        print("")

        user = input("> ").strip().lower()

        # check if any options pressed
        if user == "q":
            print("Goodbye!")
            return
        if user == "m":
            mode = "toggle_generation_mode"
        if user == "g":
            mode = "set_game"
        if user == "p":
            mode = "set_party_size"
        if user == "r":
            mode = "reload_config"
        if user == "h":
            mode = "help"

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

        elif mode == 'set_party_size':
            if set_party_size():
                with open(resource_path("config/global_settings.yaml"), "r") as f:
                    party_size = yaml.safe_load(f).get('party_size', 6)
                party_on_screen = 'party_size_updated'
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

        elif mode == 'help':
            print_help()
            continue


        # generation
        if generation_mode == 'Random':
            print("Generating party...\n")
            start = time.time()
            party_blob = generate_fully_randomized_party(all_pokemon, n=party_size)
            end = time.time()
            duration = end - start
        elif generation_mode == 'Progression':
            print("Generating party...\n")
            start = time.time()
            party_blob = generate_final_party(
                all_pools, all_pokemon, config_data, meta_data, n=party_size
            )
            end = time.time()
            duration = end - start

        # if generation fails, mark explicitly with False
        if party_blob is None:
            party_on_screen = False
        else:
            party_on_screen = party_blob
