import argparse
from data.loader import build_all_data_structures
from ui.cli import ui_loop

def main():
    parser = argparse.ArgumentParser(description="Dexelect")
    parser.add_argument("--ui", choices=["cli", "gui", "web"], default="gui", help="Launch app with specified UI mode")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the web UI to (--ui web)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind the web UI to (--ui web)")
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

    # The web UI is stateless and multi-game: it builds per-game data on demand
    # and never seeds the per-user working files, so it deliberately does NOT go
    # through build_all_data_structures(). Return early before that call.
    if args.ui == "web":
        from ui.web.app import create_app
        app = create_app()
        print(f"Dexelect web UI running at http://{args.host}:{args.port}")
        # debug=False: the Werkzeug debugger is a remote-code-execution console
        # on any unhandled exception, so it must never run on a reachable bind.
        # This dev server is for local use; production runs via gunicorn against
        # create_app() and never reaches this line.
        app.run(host=args.host, port=args.port, debug=False)
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
