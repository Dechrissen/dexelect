import argparse
from data.loader import build_all_data_structures
from ui.cli import ui_loop

def main():
    parser = argparse.ArgumentParser(description="Dexelect")
    parser.add_argument("--ui", choices=["cli", "gui", "tk"], default="gui",
                        help="Launch app with specified UI mode (gui = CustomTkinter, tk = plain Tk)")
    parser.add_argument("--fetch-sprites", action="store_true", help="Download sprites then exit")
    parser.add_argument("--gens", nargs="+", type=int, choices=[1, 2, 3, 4], default=[1, 2, 3, 4],
                        metavar="N", help="Generations to fetch when using --fetch-sprites")
    args = parser.parse_args()

    if args.fetch_sprites:
        from scripts.fetch_sprites import fetch_gen, GENS
        from pathlib import Path
        out_root = Path(__file__).parent / "assets/sprites"
        print(f"Output directory : {out_root.resolve()}")
        print(f"Generations      : {args.gens}")
        for gen_num in sorted(args.gens):
            fetch_gen(gen_num, GENS[gen_num], out_root)
        print("\nAll done!")
        return

    all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon = build_all_data_structures()

    if args.ui in ("gui", "tk"):
        if args.ui == "tk":
            from ui.gui_tk import DexelectApp
        else:
            from ui.gui import DexelectApp
        app = DexelectApp(all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon)
        app.mainloop()
    else:
        ui_loop(all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon)

if __name__ == "__main__":
    main()
