# Copyright 2026 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/

from models.pokemon import Pokemon
from models.location import Location
from models.sphere import Sphere
import random

#DEBUG = True
DEBUG = False

GEN_RANGES = {1: (1, 151), 2: (152, 251), 3: (252, 386), 4: (387, 493)}

def generate_final_party(all_pools: dict, all_pokemon: dict, config_data: dict, meta_data: dict,
                         obtainable_pokemon: dict, n: int = 6,
                         retry: int = 0, max_retries: int = 300, max_iterations: int = 2000):
    """
    Generates a final party of Pokemon.

    args:
        all_pools (dict of pools)
        all_pokemon (dict of Pokemon objects)
        config_data (dict): the config options from the config YAML
        meta_data (dict): the config options from the config YAML
        obtainable_pokemon (dict of Pokemon objects): subset of all_pokemon obtainable in this game
        n (int): optional party size
        retry (int): optional
        max_retries (int): optional
        max_iterations (int): optional

    returns:
        final party blob (party, acquisition data, distribution, balance stats)
        OR None if it fails after max_retries
    """

    if retry > max_retries:
        if DEBUG:
            print("Could not generate valid party with current settings!")
        return None

    if DEBUG:
        print(f"[Attempt {retry} start]")

    iterations = 0
    tentative_party = []

    # include a random starter if force_starter is selected in config
    if config_data["force_starter"]:
        rand_starter_species = random.choice(meta_data["starter_species"])
        #TODO matching_pokemon could still be e.g. Stage 2 (less than max_evo_stage = 3) even though
        # allow_not_fully_evolved = False, which will result in 10000 iterations because the Stage 2 mon
        # will be included in every check of is_party_valid... fix this
        matching_pokemon = [
            all_pokemon[mon] for mon in all_pokemon
            if (all_pokemon[mon].species_line == rand_starter_species) and (all_pokemon[mon].evo_stage <= config_data['max_evo_stage'])
        ]
        if matching_pokemon:
            chosen_starter = random.choice(matching_pokemon)
        else:
            chosen_starter = None
        tentative_party.append(chosen_starter)

    # ---- MAIN GENERATION LOOP WITH FAILSAFE ----
    # iteratively build a party that is valid according to the config options
    while len(tentative_party) < n:
        if iterations > max_iterations:
            # abort this attempt, retry whole function
            return generate_final_party(all_pools, all_pokemon,
                                        config_data, meta_data,
                                        obtainable_pokemon, n, retry + 1,
                                        max_retries, max_iterations)

        rand_mon = generate_random_mon(obtainable_pokemon)

        if is_party_valid(
                tentative_party + [rand_mon],
                bool(len(tentative_party) + 1 == n),
                config_data, meta_data
        ):
            tentative_party.append(rand_mon)

        iterations += 1

    if DEBUG:
        print(f"Tentative party of size {n} generated for Attempt {retry} after {iterations} iterations.")
        print("Checking if party is progression viable...")

    party_with_acquisition_data = is_party_progression_viable(tentative_party, all_pools, all_pokemon, config_data, meta_data)

    # this will be False if party generated is not obtainable from pools
    if party_with_acquisition_data:
        if config_data["force_starter"]:
            if DEBUG:
                print("'force_starter = True' in config. Ensuring 'starter' acquisition method exists in party...")
            if not any(
                member["random_pool_entry_instance"]["acquisition_method"] == "starter"
                for member in party_with_acquisition_data
            ):
                if DEBUG:
                    print("Party doesn't contain 'starter' acquisition method. Retrying final party generation...")
                return generate_final_party(all_pools, all_pokemon,
                                            config_data, meta_data,
                                            obtainable_pokemon, n, retry + 1,
                                            max_retries, max_iterations)
        if DEBUG:
            print("Generating balance stats...")

        balance_stats = assign_balance_grade(party_with_acquisition_data, meta_data, config_data)

        if not validate_balance_grade(balance_stats, config_data):
            if DEBUG:
                print("Party doesn't pass balancing requirements in config. Retrying final party generation...")
            return generate_final_party(all_pools, all_pokemon,
                                        config_data, meta_data,
                                        obtainable_pokemon, n, retry + 1,
                                        max_retries, max_iterations)

        final_party_blob = {
            "party_with_acquisition_data": party_with_acquisition_data,
            'party_distribution': balance_stats['party_distribution'],
            'score_median': balance_stats['score_median'],
            'lean': balance_stats['lean'],
            'spread': balance_stats['spread'],
            'pattern': balance_stats['pattern'],
            'contains_at_least_one_sphere_one': balance_stats['contains_at_least_one_sphere_one']
        }
        return final_party_blob
    else:
        if DEBUG:
            print("Party not progression viable. Retrying final party generation...")

        # try again if party wasn't viable / obtainable from pools
        return generate_final_party(all_pools, all_pokemon,
                                    config_data, meta_data,
                                    obtainable_pokemon, n, retry + 1,
                                    max_retries, max_iterations)

def is_party_valid(party, is_party_full, config_data, meta_data) -> bool:
    """
    Checks whether a party is valid per the config options in the config YAML.

    args:
        party (list of Pokemon objects)
        is_party_full (bool): whether the len(party) is equal to the desired party size
        config_data (dict): the config options from the config YAML
        meta_data (dict): the metadata from the meta YAML

    returns:
        bool: whether the party is valid
    """

    # get metadata
    #starter_species = meta_data["starter_species"]
    modal_species = meta_data["modal_species"]

    # get config options
    #force_starter = config_data["force_starter"]
    allow_not_fully_evolved = config_data["allow_not_fully_evolved"]
    allow_legendaries = config_data["allow_legendaries"]
    allow_duplicate_species = config_data["allow_duplicate_species"]
    allow_dual_type = config_data["allow_dual_type"]
    prescribed_type = config_data["prescribed_type"]["value"]
    type_distribution = config_data["type_distribution"]["value"]
    type_blacklist = config_data["type_blacklist"]["value"]
    species_blacklist = config_data["species_blacklist"]
    allowed_evo_methods = [em for em in config_data["allowed_evo_methods"] if config_data["allowed_evo_methods"][em] == True]
    max_evo_stage = config_data["max_evo_stage"]
    bst_max = config_data["bst_max"]
    bst_min = config_data["bst_min"]
    ensure_hm_coverage = set([hm for hm in config_data["ensure_hm_coverage"] if config_data["ensure_hm_coverage"][hm] == True])
    generation_filter = config_data["generation_filter"]["value"]

    # ---------------------------------------
    # immediate False if these checks fail
    if not allow_duplicate_species:
        species_lines = [m.species_line for m in party]
        if len(species_lines) != len(set(species_lines)):
            if DEBUG:
                print("party",[mon.name for mon in party],"contains duplicate species lines")
            return False

    if species_blacklist:
        # check if any party Pokemon species are in the blacklist
        if any(mon.species_line in species_blacklist for mon in party):
            if DEBUG:
                print("party", [mon.name for mon in party], "violates species blacklist", species_blacklist)
            return False

    if type_distribution != 'anything_goes':
        if prescribed_type != 'none':
            for mon in party:
                if prescribed_type not in mon.types:
                    if DEBUG:
                        print("party",[mon.name for mon in party], "contains", mon.name, "which violates config option prescribed_type =", prescribed_type)
                    return False
        # this bool(...) expression evaluates to True if all Pokemon in party share at least one common type, False otherwise
        if (type_distribution == 'all_share_one_type') and not (bool(set.intersection(*(set(mon.types) for mon in party)))):
            if DEBUG:
                print("party",[mon.name for mon in party], "violates type distribution", type_distribution)
            return False
        # this expression evaluates to True if no Pokemon in party share any types, False otherwise
        if (type_distribution == 'no_overlap') and not (len({t for mon in party for t in mon.types}) == sum(len(mon.types) for mon in party)):
            if DEBUG:
                print("party",[mon.name for mon in party], "violates type distribution", type_distribution)
            return False

    if type_blacklist:
        # check if any party Pokemon species have types which are present in the type blacklist
        if any(any(t in type_blacklist for t in mon.types) for mon in party):
            if DEBUG:
                print("party", [mon.name for mon in party], "violates type blacklist", type_blacklist)
            return False

    if is_party_full:
        party_hm_coverage = set({hm for mon in party for hm in mon.hm_learnset})
        if not (ensure_hm_coverage.issubset(party_hm_coverage)):
            if DEBUG:
                print("party",[mon.name for mon in party],"lacks HM coverage", ensure_hm_coverage)
            return False

    for modal_group in modal_species:
        if any(mon.species_line in modal_group for mon in party):
            modals_in_party = [mon.species_line for mon in party if mon.species_line in modal_group]
            if len(modals_in_party) > 1:
                if DEBUG:
                    print("party", [mon.name for mon in party], "violates modal group", modal_group)
                return False
    # ---------------------------------------

    # now check each mon against some more config options
    for mon in party:
        if mon.evo_stage > max_evo_stage:
            if DEBUG:
                print("party",[mon.name for mon in party], "contains", mon.name, "which violates config option max_evo_stage =",max_evo_stage)
            return False
        if (allow_not_fully_evolved == False) and (mon.is_fully_evolved == False):
            if DEBUG:
                print("party",[mon.name for mon in party], "contains", mon.name, "which violates config option allow_not_fully_evolved =",allow_not_fully_evolved)
            return False
        if (allow_legendaries == False) and (mon.is_legendary):
            if DEBUG:
                print("party",[mon.name for mon in party], "contains", mon.name, "which violates config option allow_legendaries =",allow_legendaries)
            return False
        if (allow_dual_type == False) and (len(mon.types) > 1):
            if DEBUG:
                print("party",[mon.name for mon in party], "contains", mon.name, "which violates config option allow_dual_type =", allow_dual_type)
            return False
        if mon.evolution_method_required not in allowed_evo_methods:
            if DEBUG:
                print("party",[mon.name for mon in party], "contains", mon.name, "which violates config option allowed_evo_methods =", allowed_evo_methods)
            return False
        if bst_max != 'none':
            if mon.base_stat_total > bst_max:
                if DEBUG:
                    print("party", [mon.name for mon in party], "contains", mon.name,"which violates config option bst_max =", bst_max)
                return False
        if bst_min != 'none':
            if mon.base_stat_total < bst_min:
                if DEBUG:
                    print("party", [mon.name for mon in party], "contains", mon.name,"which violates config option bst_min =", bst_min)
                return False
        if generation_filter:
            dex_num = int(mon.nat_dex_number)
            if not any(GEN_RANGES[g][0] <= dex_num <= GEN_RANGES[g][1] for g in generation_filter):
                if DEBUG:
                    print("party", [mon.name for mon in party], "contains", mon.name, "which violates config option generation_filter =", generation_filter)
                return False

    return True

def is_party_progression_viable(party, all_pools, all_pokemon, config_data, meta_data) -> list | bool:
    """
    Returns the party (list) with added acquisition data if it is obtainable from the pools
    OR False if the party is not obtainable from the pools

    args:
        party (list of Pokemon objects)
        all_pools (dict of pools)
        all_pokemon (dict of Pokemon objects)
        config_data (dict): the config options from the config YAML
        meta_data (dict): the metadata from the meta YAML

    returns:
        final_party_with_acquisition_data OR False

    final_party_with_acquisition_data is a list of these objects:
        {
            "party_member_obj": Pokemon object,
            "earliest_form": earliest form found for that Pokemon in the pools,
            "earliest_pool": pool the earliest form is found in,
            "random_pool_entry_instance": a random pool entry from the instances (in the earliest pool) of the earliest form
        }
    """

    final_party_with_acquisition_data = []

    for mon in party:
        form_found = False
        # keep track of all the previous evos we need to search for in the pools first (order matters)
        cur_mon = mon
        forms_to_search_in_order = [cur_mon]
        # while the current mon has a previous evo, add it to the list to search for
        while cur_mon.get_immediate_child(all_pokemon):
            cur_mon = cur_mon.get_immediate_child(all_pokemon)
            forms_to_search_in_order.append(cur_mon)

        # the latest mon added to forms_to_search_in_order is the lowest stage, so we want to reverse it
        forms_to_search_in_order.reverse() #TODO should we actually do this in descending order? (i.e. should it check for highest evo first?)

        allowed_acquisition_methods = [method for method in config_data["allowed_acquisition_methods"] if
                                       config_data["allowed_acquisition_methods"][method] == True]

        # get 'active' (enabled) spheres from config preset selected_sphere_mode
        sphere_mode = meta_data["selected_sphere_mode"]
        enabled_spheres = [sphere for sphere in meta_data['sphere_generation_modes'][sphere_mode]]

        earliest_form_found, earliest_pool_available = None, None
        # add instances of the earliest available form of this mon (its pool_entry) to a list
        instances_found = []

        for pool_num in all_pools.keys():
            if pool_num not in enabled_spheres:
                # skip pool if it's not for one of the enabled spheres
                continue

            cur_pool = all_pools[pool_num]
            cur_pool_entries = cur_pool['pool_entries'] # list of pool entries for this pool
            #cur_pool_inventory = cur_pool['inventory'] # list of items for this pool #TODO are we tracking items ever?

            # iteratively check for the earliest form --> latest form of an evolution line
            # and exit loop when a form is found
            for form in forms_to_search_in_order:
                for pool_entry in cur_pool_entries:
                    if (
                        (form.name == pool_entry['pokemon_obj'].name) and
                        (pool_entry['acquisition_method'] in allowed_acquisition_methods)
                    ):
                        instances_found.append(pool_entry)
                        form_found = True
                        earliest_pool_available = pool_num
                        earliest_form_found = form
                if form_found:
                    break
            if form_found:
                break

        if not form_found:
            if DEBUG:
                print("FAIL. No obtainable forms found for", mon.name, "in enabled spheres", enabled_spheres)
            return False

        # --- TEST ---
        #print("earliest mon for", mon.name, "is", earliest_form_found.name, "in pool", earliest_pool_available, ":", instances_found)
        # ------------

        final_party_with_acquisition_data.append(
            {
                "party_member_obj": mon,
                "earliest_form": earliest_form_found,
                "earliest_pool": earliest_pool_available,
                "random_pool_entry_instance": random.choice(instances_found) if instances_found else None,
            }
        )

    # now that we have the party with acquisition data (pool entires with acquisition methods, etc.)
    # define some functions to do the final validations for the whole party and make sure it's
    # viable per the pools
    limited_methods_from_metadata = [method for method in meta_data['limited_acquisition_methods']]

    def validate_limited_methods(party_with_acquisition_data, limited_methods) -> bool:
        """
        Checks whether there are > 1 Pokemon in a party that share both the same limited
        acquisition_method and acquiring_location.
        """
        seen_triplets = set()

        for entry in party_with_acquisition_data:
            inst = entry["random_pool_entry_instance"]
            pkmn = entry["earliest_form"]
            if inst["acquisition_method"] in limited_methods:
                triplet = (pkmn.name, inst["acquisition_method"], inst["acquiring_location"])
                if triplet in seen_triplets:
                    if DEBUG:
                        print("FAIL. Multiple instances of limited acquisition method/location with same Pokémon:", triplet)
                    return False
                seen_triplets.add(triplet)

        return True

    def validate_only_one_starter(party_with_acquisition_data) -> bool:
        """
        Checks whether there is > 1 starter in a party.
        """
        seen_starters = set()

        for entry in party_with_acquisition_data:
            inst = entry["random_pool_entry_instance"]
            pkmn = entry["earliest_form"]
            if inst["acquisition_method"] == 'starter':
                seen_starters.add((pkmn.name, inst["acquisition_method"], inst["acquiring_location"]))
                if len(seen_starters) > 1:
                    if DEBUG:
                        print("FAIL. Multiple starters from same location:", seen_starters)
                    return False

        return True

    def validate_evo_item_conditions(party_with_acquisition_data) -> bool:
        """
        Validates whether the party is viable per the evo_items available in the meta YAML.
        For each party member, if any of the Pokemon in the species line and below need a stone evo method,
        this function checks whether that stone is available in the game per the meta YAML evo_items_available list.
        """
        #TODO add this function (it's already in the final validation checks below)
        # might need to consider trade+evo_item cases like metal coat. Do we make a new 'item' called trade_metal_coat?
        # or maybe just rename evo_items_available to something more semantic in the meta yaml.

        # for mon in party_with_acquisition_data:
        #   check here if it needs stone evo...
        #   while mon['party_member_obj'].get_immediate_child(all_pokemon):
        #       check if its child needs stone evo...
        #           if yes, check if that stone is in meta_data['evo_items_available']

        return True # for now, always return True

    # Final validations for party, return False if any don't pass
    if (
        (not validate_limited_methods(final_party_with_acquisition_data, limited_methods_from_metadata)) or
        (not validate_only_one_starter(final_party_with_acquisition_data)) or
        (not validate_evo_item_conditions(final_party_with_acquisition_data))
    ):
        return False
    else:
        if DEBUG:
            print("Party is progression viable!")
        return final_party_with_acquisition_data

def get_config_agnostic_party_acquisition_data(party, all_pools, all_pokemon) -> list:
    """
    Returns the party (list) with added acquisition data based on the pools (or None
    for an individual mon if it's not found). Does not validate against config settings
    or meta data like is_party_progression_viable() does.

    args:
        party (list of Pokemon objects)
        all_pools (dict of pools)
        all_pokemon (dict of Pokemon objects)

    returns:
        final_party_with_acquisition_data

    final_party_with_acquisition_data is a list of these objects:
        {
            "party_member_obj": Pokemon object,
            "earliest_form": earliest form found for that Pokemon in the pools,
            "earliest_pool": pool the earliest form is found in,
            "random_pool_entry_instance": a random pool entry from the instances (in the earliest pool) of the earliest form
        }
    """

    final_party_with_acquisition_data = []

    for mon in party:
        form_found = False
        # keep track of all the previous evos we need to search for in the pools first (order matters)
        cur_mon = mon
        forms_to_search_in_order = [cur_mon]
        # while the current mon has a previous evo, add it to the list to search for
        while cur_mon.get_immediate_child(all_pokemon):
            cur_mon = cur_mon.get_immediate_child(all_pokemon)
            forms_to_search_in_order.append(cur_mon)

        # the latest mon added to forms_to_search_in_order is the lowest stage, so we want to reverse it
        forms_to_search_in_order.reverse() #TODO should we actually do this in descending order? (i.e. should it check for highest evo first?)

        earliest_form_found, earliest_pool_available = None, None
        # add instances of the earliest available form of this mon (its pool_entry) to a list
        instances_found = []

        for pool_num in all_pools.keys():

            cur_pool = all_pools[pool_num]
            cur_pool_entries = cur_pool['pool_entries'] # list of pool entries for this pool
            #cur_pool_inventory = cur_pool['inventory'] # list of items for this pool #TODO are we tracking items ever?

            # iteratively check for the earliest form --> latest form of an evolution line
            # and exit loop when a form is found
            for form in forms_to_search_in_order:
                for pool_entry in cur_pool_entries:
                    if (form.name == pool_entry['pokemon_obj'].name):
                        instances_found.append(pool_entry)
                        form_found = True
                        earliest_pool_available = pool_num
                        earliest_form_found = form
                if form_found:
                    break
            if form_found:
                break

        if not form_found:
            # if DEBUG:
            #     print("No obtainable forms found for", mon.name, "in enabled spheres", enabled_spheres, ", so setting values to None for acquisition data for this mon")
            # doing nothing here because `earliest_form_found, earliest_pool_available = None, None` from earlier, which is what we want if a mon isn't found
            pass

        final_party_with_acquisition_data.append(
            {
                "party_member_obj": mon,
                "earliest_form": earliest_form_found,
                "earliest_pool": earliest_pool_available,
                "random_pool_entry_instance": random.choice(instances_found) if instances_found else None,
            }
        )

    return final_party_with_acquisition_data

def assign_balance_grade(party_with_acquisition_data, meta_data, config_data) -> dict:
    """
    Assigns a balance grade to a Pokémon party based on the distribution of each member's
    availability in the enabled spheres (game progression pools).

    args:
        party_with_acquisition_data (list): output of is_party_progression_viable
        meta_data (dict): the metadata from the meta YAML

    returns a dict with these keys:
    - party_distribution: dict of sphere_num/pokemon_count key/value pairs
    - lean: qualitative indication of early vs late game (early_game_heavy / balanced / late_game_heavy)
    - spread: span of spheres covered (clustered / mixed_spread / wide_spread)
    - pattern: qualitative shape of party across spheres
               (early_late_split, middle_only, dual_cluster, single_cluster, None)
    - score_median: normalized median sphere (0=start of game, 1=end), for reference
    - contains_at_least_one_sphere_one: boolean value indicating whether at least one Sphere 1 mon is in the party
    """

    lean_cutoffs = (0.30, 0.70)
    spread_cutoffs = (0.35, 0.70)

    # Build party distribution across enabled spheres
    sphere_mode = meta_data["selected_sphere_mode"]
    enabled_spheres = [sphere for sphere in meta_data['sphere_generation_modes'][sphere_mode]]
    total_spheres = len(enabled_spheres)
    party_distribution = {sphere: 0 for sphere in enabled_spheres}

    for member in party_with_acquisition_data:
        party_distribution[member["earliest_pool"]] += 1

    total = sum(party_distribution.values())
    if total == 0 or total_spheres < 2:
        return {'party_distribution': party_distribution,
                'score_median': None, 'lean': None, 'spread': None, 'pattern': None,
                'contains_at_least_one_sphere_one': False}

    # ---------- Lean calculation ----------
    # Expand counts for median calculation
    expanded = []
    for i, count in party_distribution.items():
        expanded.extend([i] * count)
    expanded.sort()

    # Compute median sphere
    m = len(expanded) // 2
    if len(expanded) % 2 == 1:
        median_sphere = expanded[m]
    else:
        median_sphere = (expanded[m - 1] + expanded[m]) / 2

    lean_score = (median_sphere - 1) / (total_spheres - 1)

    # Determine if majority of Pokemon in lower or upper half
    halfway_index = total_spheres // 2
    lower_half_count = sum(
        count for sphere, count in party_distribution.items()
        if sphere <= halfway_index
    )
    upper_half_count = total - lower_half_count

    # Assign qualitative lean
    low, high = lean_cutoffs
    if upper_half_count > (total / 2):
        lean = 'late_game_heavy'
    elif lower_half_count > (total / 2):
        lean = 'early_game_heavy'
    elif lean_score < low:
        lean = 'early_game_heavy'
    elif lean_score > high:
        lean = 'late_game_heavy'
    else:
        lean = 'balanced'

    # ---------- Spread calculation ----------
    active_spheres = [i for i, count in party_distribution.items() if count > 0]
    range_raw = max(active_spheres) - min(active_spheres)
    spread_score = range_raw / (total_spheres - 1)

    sp_low, sp_high = spread_cutoffs
    if spread_score < sp_low:
        spread = 'clustered'       # Pokemon tightly grouped in few spheres
    elif spread_score > sp_high:
        spread = 'wide_spread'     # Pokemon span most/all of the game
    else:
        spread = 'mixed_spread'    # intermediate span

    # Count gaps between active spheres for pattern detection
    gaps = sum(
        1 for i in range(len(active_spheres) - 1)
        if active_spheres[i+1] - active_spheres[i] > 1
    )

    # ---------- Pattern detection ----------
    middle_start = total_spheres // 3 + 1
    middle_end = total_spheres * 2 // 3

    if (1 in active_spheres and total_spheres in active_spheres
            and any(c == 0 for i, c in party_distribution.items() if i not in (1, total_spheres))):
        pattern = 'early_late_split'    # Clusters at the start and end
    elif all(middle_start <= s <= middle_end for s in active_spheres):
        pattern = 'middle_only'         # All Pokemon in middle third
    elif gaps == 1:
        pattern = 'dual_cluster'        # Two separate clusters
    elif len(active_spheres) > 1 and max(active_spheres) - min(active_spheres) + 1 == len(active_spheres):
        pattern = 'single_cluster'      # Single contiguous cluster
    elif len(active_spheres) == 1:      # Check for cases where only 1 sphere is active
        pattern = 'single_cluster'
    else:
        pattern = None                  # No distinct pattern

    # set this boolean value to true if there is at least 1 sphere 1 mon in the party
    contains_at_least_one_sphere_one = False
    if any(member["earliest_pool"] == 1 for member in party_with_acquisition_data):
        contains_at_least_one_sphere_one = True

    return {
        'party_distribution': party_distribution,
        'score_median': lean_score,
        'lean': lean,
        'spread': spread,
        'pattern': pattern,
        'contains_at_least_one_sphere_one': contains_at_least_one_sphere_one
    }

def validate_balance_grade(balance_stats, config_data) -> bool:
    """
    Checks whether a balance grade is valid per the allowed balance modes in a config YAML.

    args:
        balance_stats (dict): output of assign_balance_grade
        config_data (dict): the config options from the config YAML

    returns:
        bool
    """
    # the allowed modes per the config file
    allowed_balancing = [mode for mode in config_data['allowed_balancing']['value']]
    allowed_spreads = [mode for mode in config_data['allowed_spreads']['value']]
    allowed_patterns = [mode for mode in config_data['allowed_patterns']['value']]
    require_one_sphere_one = config_data['require_one_sphere_one']

    # the assigned modes given to the party (from balance_stats) by assign_balance_grade
    assigned_balancing = balance_stats['lean']
    assigned_spread = balance_stats['spread']
    assigned_pattern = balance_stats['pattern']
    contains_at_least_one_sphere_one = balance_stats['contains_at_least_one_sphere_one']

    if assigned_balancing not in allowed_balancing:
        if DEBUG:
            print(f"FAIL (Balancing). Lean '{assigned_balancing}' not in allowed_balancing {allowed_balancing}")
        return False
    if assigned_spread not in allowed_spreads:
        if DEBUG:
            print(f"FAIL (Balancing). Spread '{assigned_spread}' not in allowed_spreads {allowed_spreads}")
        return False
    if assigned_pattern not in allowed_patterns:
        if DEBUG:
            print(f"FAIL (Balancing). Pattern '{assigned_pattern}' not in allowed_patterns {allowed_patterns}")
        return False
    if (require_one_sphere_one == True) and (contains_at_least_one_sphere_one == False):
        if DEBUG:
            print(f"FAIL (Balancing). Party does not contain at least one Sphere 1 Pokemon while require_one_sphere_one = true")
        return False
    return True


def generate_random_mon(all_pokemon: dict[str, 'Pokemon']) -> 'Pokemon':
    """
    Generates a random Pokemon.

    args:
        all_pokemon (dict of Pokemon objects)

    returns:
        random Pokemon object
    """
    return random.choice(list(all_pokemon.values()))

def generate_fully_randomized_party(pokemon_dict: dict[str, 'Pokemon'], n: int = 6, all_pools=None, all_pokemon=None) -> dict:
    """
    Generates a fully randomized party of Pokemon with balance stats (always empty) and acquisition data
    (if a Pokemon is not obtainable, acquisition data will be None).

    args:
        pokemon_dict: dict of Pokemon objects to draw the random party from (may be a subset, e.g. obtainable_pokemon)
        n (int): the party size
        (optional) all_pools: dict of pools
        (optional) all_pokemon: full dict of Pokemon objects, used to walk pre-evolutions when looking up
            acquisition data. Falls back to pokemon_dict if not provided. Pass the full set if pokemon_dict
            is a subset like obtainable_pokemon: currently, any pre-evolution missing from such a subset is
            guaranteed to be non-poolable anyway, so omitting it from the walk is harmless.

    returns:
        final_party_blob (dict): the full party blob with balance stats (always empty) and acquisition data
    """
    party_with_acquisition_data = []

    if all_pools:
        # all_pools was passed in, which means we want to get acquisition data for the party regardless of viability
        party = []
        for i in range(n):
            mon = generate_random_mon(pokemon_dict)
            party.append(mon)
        party_with_acquisition_data = get_config_agnostic_party_acquisition_data(
            party, all_pools, all_pokemon if all_pokemon is not None else pokemon_dict
        )
    else:
        # we never get to this branch actually, since i decided to make both 'Random (Obtainable)' and
        # 'Random (National Dex)' pass in all_pools so acquisition data can be shown partially
        # for a fully random National Dex party (only for those that are actually obtainable).
        # TODO we could delete this branch, currently an artifact but maybe we use it for something else
        # where we don't have to pass in all_pools?
        for i in range(n):
            mon = generate_random_mon(pokemon_dict)
            # fill its entry with dummy (empty) acquisition data
            entry = {
                "party_member_obj": mon,
                "earliest_form": None,
                "earliest_pool": None,
                "random_pool_entry_instance": None
            }
            party_with_acquisition_data.append(entry)

    # add dummy (empty) balance stats to the final party blob
    final_party_blob = {
        "party_with_acquisition_data": party_with_acquisition_data,
        'party_distribution': None,
        'score_median': None,
        'lean': None,
        'spread': None,
        'pattern': None,
        'contains_at_least_one_sphere_one': None
    }

    return final_party_blob

def construct_full_pokemon_set(pokedex_data) -> dict[str, 'Pokemon']:
    """
    Creates a dict of all Pokemon from an input Pokedex YAML.

    args:
        pokedex_data (list of dicts, one for each mon)

    returns:
        all_pokemon (dict of Pokemon objects where keys are names of Pokemon)
    """

    if DEBUG:
        print("Constructing full Pokemon set...")

    # create empty dict
    all_pokemon = dict()

    # iterate through each dict in the list pokedex_data
    for cur_mon in pokedex_data:
        # create object of class Pokemon for current mon
        cur_mon_obj = Pokemon(
            name=cur_mon["name"],
            nat_dex_number=cur_mon.get("nat_dex_number", "000"),
            species_line=cur_mon["species_line"],
            evo_stage=cur_mon["evo_stage"],
            is_fully_evolved=cur_mon["is_fully_evolved"],
            is_legendary=cur_mon["is_legendary"],
            types=cur_mon["types"],
            base_stat_total=cur_mon["base_stat_total"],
            hm_learnset=cur_mon["hm_learnset"],
            evolution_method_required=cur_mon["evolution_method_required"]
            )
        
        # add current mon's Pokemon object to dict
        all_pokemon[cur_mon["name"]] = cur_mon_obj

    if DEBUG:
        print("Done.")

    return all_pokemon

def construct_full_location_set(location_data) -> dict[str, Location]:
    """
    Creates a dict of all Locations from an input locations YAML.

    args:
        location_data (list of dicts, one for each location)

    returns:
        all_locations (dict of Location objects where keys are names of locations)
    """

    if DEBUG:
        print("Constructing full location set...")

    # create empty dict
    all_locations = dict()

    # iterate through each dict in the list location_data
    for cur_loc in location_data:
        # create object of class Location for current location
        cur_loc_obj = Location(
            name=cur_loc["map_name"],
            # gen 1 methods ...
            starter=cur_loc["starter"] if "starter" in cur_loc else None,
            walk=cur_loc["walk"] if "walk" in cur_loc else None,
            surf=cur_loc["surf"] if "surf" in cur_loc else None,
            old_rod=cur_loc["old_rod"] if "old_rod" in cur_loc else None,
            good_rod=cur_loc["good_rod"] if "good_rod" in cur_loc else None,
            super_rod=cur_loc["super_rod"] if "super_rod" in cur_loc else None,
            poke_flute=cur_loc["poke_flute"] if "poke_flute" in cur_loc else None,
            static_encounter=cur_loc["static_encounter"] if "static_encounter" in cur_loc else None,
            repeatable_static_encounter=cur_loc["repeatable_static_encounter"] if "repeatable_static_encounter" in cur_loc else None,
            trade=cur_loc["trade"] if "trade" in cur_loc else None,
            gift=cur_loc["gift"] if "gift" in cur_loc else None,
            purchase=cur_loc["purchase"] if "purchase" in cur_loc else None,
            fossil_restore=cur_loc["fossil_restore"] if "fossil_restore" in cur_loc else None,
            prize_window=cur_loc["prize_window"] if "prize_window" in cur_loc else None,
            # gen 2 methods ...
            bug_catching_contest=cur_loc["bug_catching_contest"] if "bug_catching_contest" in cur_loc else None,
            squirt_bottle=cur_loc["squirt_bottle"] if "squirt_bottle" in cur_loc else None,
            headbutt=cur_loc["headbutt"] if "headbutt" in cur_loc else None,
            rock_smash=cur_loc["rock_smash"] if "rock_smash" in cur_loc else None,
            roaming=cur_loc["roaming"] if "roaming" in cur_loc else None,
            rainbow_wing=cur_loc["rainbow_wing"] if "rainbow_wing" in cur_loc else None,
            silver_wing=cur_loc["silver_wing"] if "silver_wing" in cur_loc else None,
            # gen 3 methods ...
            dive=cur_loc["dive"] if "dive" in cur_loc else None,
            go_goggles=cur_loc["go_goggles"] if "go_goggles" in cur_loc else None,
            devon_scope=cur_loc["devon_scope"] if "devon_scope" in cur_loc else None,
            sealed_chamber_puzzle=cur_loc["sealed_chamber_puzzle"] if "sealed_chamber_puzzle" in cur_loc else None,
            mirage_island=cur_loc["mirage_island"] if "mirage_island" in cur_loc else None,
            # gen 4 methods ...
            honey_tree=cur_loc["honey_tree"] if "honey_tree" in cur_loc else None,
            binoculars=cur_loc["binoculars"] if "binoculars" in cur_loc else None,
            odd_keystone=cur_loc["odd_keystone"] if "odd_keystone" in cur_loc else None,
            munchlax_tree=cur_loc["munchlax_tree"] if "munchlax_tree" in cur_loc else None
        )

        # add current loc's Location object to dict
        all_locations[cur_loc["map_name"]] = cur_loc_obj

    if DEBUG:
        print("Done.")

    return all_locations

def construct_spheres(meta_data, all_locations) -> dict[int, Sphere]:
    """
    Creates a set of all Spheres from an input meta YAML.

    args:
        meta_data (from meta YAML)
        all_locations (dict of all Location objects)

    returns:
        all_spheres (dict of Sphere objects, where keys are numbers (int) of spheres)
    """

    if DEBUG:
        print("Constructing spheres...")

    # create empty set
    all_spheres = dict()

    # iterate through each sphere in the meta data 'spheres' list
    for cur_sphere in meta_data['spheres']:
        # get the sphere number and contents (list of maps items, acquisition_unlocks)
        sphere_num = cur_sphere['sphereNum']
        sphere_contents = cur_sphere['contents']
        maps, items, acquisition_unlocks = [], [], []

        # add all the maps and items to lists for each type
        for element in sphere_contents:
            if element['type'] == 'map':
                map_object = all_locations[element['name']]
                maps.append(map_object)
            elif element['type'] == 'item':
                items.append(element['name'])
            elif element['type'] == 'acquisition_unlock':
                acquisition_unlocks.append(element['name'])
            else:
                raise TypeError(f"Type '{element['type']}' for '{element['name']}' not supported in meta YAML (sphere {sphere_num}).")

        # create a Sphere object and add it to the dict of all spheres, where the key is the sphere num (1, 2, 3, etc.)
        all_spheres[sphere_num] = Sphere(maps, items, acquisition_unlocks)

    if DEBUG:
        print("Done.")

    return all_spheres


def build_pools(all_spheres, all_pokemon, starting_acquisition_methods) -> dict[int, dict]:
    """
    Expands the Pokemon lists in each Sphere of all_spheres, then creates a dict of pools (each containing a list of available Pokemon for each pool).

    args:
        all_spheres (dict of Sphere objects, where keys are numbers (int) of spheres)
        all_pokemon (dict of Pokemon objects where keys are names of Pokemon)
        starting_acquisition_methods (list of default acquisition methods from config file)

    returns:
        all_pools (dict of pools -> {pool_num: {"pool_entries": [list of pool entries], "inventory": [list of items up to this pool]}})
            example pool entry: {"pokemon_obj": Pokemon object, "acquisition_method": method (str), "acquiring_location": location name (str)}
    """

    if DEBUG:
        print("Building pools...")

    all_pools = dict()

    # to keep track of set of items that enable evolution (stones, etc.)
    inventory = []

    # to keep track of current enabled acquisition methods that unlock Location sublists (old_rod, surf, etc.)
    enabled_acquisition_methods = [method for method in starting_acquisition_methods]

    # to keep track of spheres checked (which acquisition methods have been expanded)
    spheres_checked = {}

    # iterate over all spheres from all_spheres dict (in ascending key order)
    for sphere_num in sorted(all_spheres.keys()):

        locations = all_spheres[sphere_num].maps
        items = all_spheres[sphere_num].items
        acquisition_unlocks = all_spheres[sphere_num].acquisition_unlocks
        for item in items:
            if item not in inventory: #TODO modify this to add dupes if we want to count how many are used
                inventory.append(item)

        for unlock in acquisition_unlocks:
            if unlock not in enabled_acquisition_methods:
                enabled_acquisition_methods.append(unlock)

        # initialize empty list to store pokemon objects for this pool
        current_pool_entries = []

        # build list of Pokemon by iterating over each location in locations and adding all its Pokemon (the object version, from all_pokemon) to current_pool_entries
        for location_obj in locations:
            for method in enabled_acquisition_methods:
                # get list stored in that attribute (like location_obj.walk)
                method_list = getattr(location_obj, method, None)
                if method_list:
                    for pokemon in method_list:
                        pool_entry = {"pokemon_obj": all_pokemon[pokemon],
                                      "acquisition_method": method,
                                      "acquiring_location": location_obj.name}
                        current_pool_entries.append(pool_entry)

        # now also iterate over all locations from previous spheres (the ones kept track of in spheres_checked)
        # and then compare enabled_acquisition_methods at THIS point to the point in time when the previous spheres were iterated over.
        # i.e. expand all currently possible methods not yet expanded for previous spheres, and add those pokemon to this current pool as well
        for prev_sphere_num in sorted(spheres_checked.keys()):
            methods_expanded = spheres_checked[prev_sphere_num]["methods_expanded"]
            new_unlocks_to_check = [method for method in enabled_acquisition_methods if method not in methods_expanded]
            if new_unlocks_to_check:
                prev_sphere_locations = all_spheres[prev_sphere_num].maps
                # build list of Pokemon by iterating over each location in locations and adding all its Pokemon (the object version, from all_pokemon) to a list
                for prev_location_obj in prev_sphere_locations:
                    for method in new_unlocks_to_check:
                        # get list stored in that attribute (like prev_location_obj.walk)
                        method_list = getattr(prev_location_obj, method, None)
                        if method_list:
                            for pokemon in method_list:
                                pool_entry = {"pokemon_obj": all_pokemon[pokemon],
                                              "acquisition_method": method,
                                              "acquiring_location": prev_location_obj.name}
                                current_pool_entries.append(pool_entry)
                # update methods_expanded for this sphere to match current possible methods
                spheres_checked[prev_sphere_num]["methods_expanded"] += new_unlocks_to_check

        # then, current sphere "methods_expanded" list in spheres_checked dict needs to be updated so it matches the current one (so we don't do it again next iteration)
        spheres_checked[sphere_num] = {"methods_expanded": [method for method in enabled_acquisition_methods]}

        all_pools[sphere_num] = {"pool_entries": current_pool_entries, "inventory": [item for item in inventory]}

    if DEBUG:
        print("Done.")

    return all_pools


def count_new_species_per_sphere(all_pools, obtainable_pokemon, all_pokemon) -> dict[int, int]:
    """
    For each sphere, counts how many species are introduced there for the
    first time: the sphere containing the earliest form (walking down through
    pre-evolutions) of that species that appears in any pool entry, regardless of
    acquisition method. This is deliberately config-agnostic (like build_obtainable_pokemon),
    so it reflects the game's theoretically obtainable Pokemon rather than the user's
    current settings.

    args:
        all_pools (dict of pools, as built by build_pools)
        obtainable_pokemon (dict of Pokemon objects theoretically obtainable in this game)
        all_pokemon (dict of all Pokemon objects, needed to walk evolution chains)

    returns:
        dict mapping sphere_num -> count of species first introduced in that sphere
    """

    counts = {sphere_num: 0 for sphere_num in all_pools}

    for mon in obtainable_pokemon.values():
        cur_mon = mon
        forms = [cur_mon]
        while cur_mon.get_immediate_child(all_pokemon):
            cur_mon = cur_mon.get_immediate_child(all_pokemon)
            forms.append(cur_mon)
        forms.reverse()

        for sphere_num in sorted(all_pools.keys()):
            pool_entries = all_pools[sphere_num]["pool_entries"]
            found = any(form.name == entry["pokemon_obj"].name for form in forms for entry in pool_entries)
            if found:
                counts[sphere_num] += 1
                break

    return counts
