import argparse
from data.loader import build_all_data_structures
from ui.cli import ui_loop

def main():
    parser = argparse.ArgumentParser(description="Dexelect")
    parser.add_argument("--ui", choices=["cli", "gui"], default="gui", help="Launch app with specified UI mode")
    parser.add_argument("--fetch-sprites", action="store_true", help="Download sprites then exit")
    parser.add_argument("--gens", nargs="+", type=int, choices=[1, 2, 3, 4], default=[1, 2, 3, 4],
                        metavar="N", help="Generations to fetch when using --fetch-sprites")
    args = parser.parse_args()

    if args.fetch_sprites:
        from scripts.fetch_sprites import fetch_sprites
        from pathlib import Path
        out_root = Path(__file__).parent / "assets/sprites"
        print(f"Output directory : {out_root.resolve()}")
        print(f"Generations      : {args.gens}")
        fetch_sprites(sorted(set(args.gens)), out_root)
        print("\nAll done!")
        return

    all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon = build_all_data_structures()

    if args.ui == "gui":
        from ui.gui import DexelectApp
        app = DexelectApp(all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon)
        app.mainloop()
    else:
        ui_loop(all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon)

if __name__ == "__main__":
    main()
