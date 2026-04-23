# Copyright 2025 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/

# gui.py — CustomTkinter GUI for TeamGen
# This file is a self-contained GUI alternative to cli.py.
# It reads/writes the same config files as cli.py, so both UIs stay in sync.
#
# Dependencies:
#   pip install customtkinter
#
# Run:
#   python gui.py
#
# Structure:
#   - Constants / theme setup
#   - Helper functions (config I/O, generation worker)
#   - TeamGenApp class
#       - __init__          : root window, layout skeleton
#       - _build_sidebar    : left panel (game, mode, global settings)
#       - _build_main       : right panel with tabs (Generate, Config)
#       - _build_gen_tab    : Generate tab (generate button, results)
#       - _build_config_tab : Config tab (all config_genX.yaml options)
#       - Logic methods     : load_state, save_config, run_generation, etc.

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import yaml
import threading
import time
import os
import webbrowser
from PIL import Image
from core import generate_final_party, generate_fully_randomized_party
from data.loader import build_all_data_structures
from util import resource_path
from version import __version__


# =============================================================================
# THEME & APPEARANCE
# =============================================================================

from ui.theme import (
    C_BG, C_PANEL, C_SIDEBAR, C_ACCENT, C_ACCENT2,
    C_TEXT, C_MUTED, C_BTN_TEXT, C_SUCCESS, C_WARNING, C_ENTRY_BG,
    FONT_TITLE, FONT_HEADER, FONT_BODY, FONT_SMALL, FONT_MONO,
    TYPE_COLORS,
)


# =============================================================================
# CONFIG FILE HELPERS
# =============================================================================

GLOBAL_SETTINGS_PATH = "config/global_settings.yaml"

def read_yaml(path: str) -> dict:
    with open(resource_path(path), "r") as f:
        return yaml.safe_load(f)

class _InlineListDumper(yaml.Dumper):
    """
    Custom YAML dumper that keeps plain lists on a single line (flow style),
    e.g. [balanced, early_game_heavy] instead of the default multi-line "- item" format.
    Dicts and all other types are still written in block style as normal.
    """
    def represent_sequence(self, tag, sequence, flow_style=None):
        return super().represent_sequence(tag, sequence, flow_style=True)

def write_yaml(path: str, data: dict):
    with open(resource_path(path), "w") as f:
        yaml.dump(data, f, Dumper=_InlineListDumper, default_flow_style=False, allow_unicode=True, sort_keys=False)



# =============================================================================
# MAIN APP CLASS
# =============================================================================

class TeamGenApp(ctk.CTk):

    def __init__(self, all_pools, all_pokemon, config_data, meta_data, mappings, global_settings):
        super().__init__()

        # ---- Window setup ----
        self.title(f"TeamGen v{__version__}")
        self.geometry("1100x750")
        self.minsize(900, 620)
        self.configure(fg_color=C_BG)

        # ---- App state ----
        self.all_pools       = all_pools
        self.all_pokemon     = all_pokemon
        self.config_data     = config_data
        self.meta_data       = meta_data
        self.mappings        = mappings
        self.global_settings = global_settings

        # Tkinter variables for sidebar controls (bound to widgets)
        self.var_game         = tk.StringVar()
        self.var_gen_mode     = tk.StringVar()
        self.var_show_acq     = tk.BooleanVar()
        self.var_show_balance = tk.BooleanVar()

        # Config tab variables — populated dynamically in _build_config_tab
        self.config_vars = {}

        # Generation state
        self.is_generating   = False
        self.last_party_blob = None

        # Sprite image refs (prevent GC of CTkImage objects while they're displayed)
        self._sprite_images = [None] * 6

        # ---- Build UI ----
        self._build_layout()
        self._build_sidebar()
        self._build_main()

        # ---- Populate UI from loaded data ----
        self._populate_ui_from_state()


    # =========================================================================
    # DATA LOADING
    # =========================================================================

    def _reload_data(self):
        """Reload all data structures and refresh the UI (equivalent to CLI 'R' command)."""
        (self.all_pools,
         self.all_pokemon,
         self.config_data,
         self.meta_data,
         self.mappings,
         self.global_settings) = build_all_data_structures()
        self._populate_ui_from_state()
        self._set_status("Config reloaded.", color=C_SUCCESS)


    # =========================================================================
    # LAYOUT SKELETON
    # =========================================================================

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, fg_color=C_SIDEBAR, corner_radius=0, width=240)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_propagate(False)

        self.main_frame = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)


    # =========================================================================
    # SIDEBAR
    # =========================================================================

    def _build_sidebar(self):
        """
        Left panel:
          - App title / version
          - Game selector (dropdown)
          - Generation mode (radio buttons)
          - Global display toggles (show acquisition details, show balance stats)
          - Reload config button
        """
        sf = self.sidebar_frame
        sf.grid_columnconfigure(0, weight=1)

        # ---- Title ----
        ctk.CTkLabel(sf, text="TeamGen", font=FONT_TITLE, text_color=C_ACCENT).grid(
            row=0, column=0, padx=20, pady=(24, 2), sticky="w")
        ctk.CTkLabel(sf, text=f"v{__version__}", font=FONT_SMALL, text_color=C_MUTED).grid(
            row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        ctk.CTkFrame(sf, height=1, fg_color=C_ACCENT2).grid(
            row=2, column=0, padx=16, sticky="ew")

        # ---- Game selector ----
        ctk.CTkLabel(sf, text="GAME", font=FONT_HEADER, text_color=C_MUTED).grid(
            row=3, column=0, padx=20, pady=(20, 4), sticky="w")

        self.game_dropdown = ctk.CTkOptionMenu(
            sf,
            variable=self.var_game,
            values=[],
            command=self._on_game_changed,
            fg_color=C_ENTRY_BG,
            button_color=C_ACCENT2,
            button_hover_color=C_ACCENT,
            text_color=C_TEXT,
            font=FONT_BODY,
            width=200,
        )
        self.game_dropdown.grid(row=4, column=0, padx=20, pady=(0, 16), sticky="w")

        ctk.CTkFrame(sf, height=1, fg_color=C_ACCENT2).grid(
            row=5, column=0, padx=16, sticky="ew")

        # ---- Generation mode ----
        ctk.CTkLabel(sf, text="MODE", font=FONT_HEADER, text_color=C_MUTED).grid(
            row=6, column=0, padx=20, pady=(20, 6), sticky="w")

        for i, mode in enumerate(["Progression", "Random"]):
            ctk.CTkRadioButton(
                sf,
                text=mode,
                variable=self.var_gen_mode,
                value=mode,
                command=self._on_mode_changed,
                text_color=C_TEXT,
                font=FONT_BODY,
                fg_color=C_ACCENT,
                hover_color=C_ACCENT2,
            ).grid(row=7 + i, column=0, padx=24, pady=3, sticky="w")

        ctk.CTkFrame(sf, height=1, fg_color=C_ACCENT2).grid(
            row=9, column=0, padx=16, pady=(16, 0), sticky="ew")

        # ---- Display toggles (global_settings.yaml) ----
        ctk.CTkLabel(sf, text="DISPLAY", font=FONT_HEADER, text_color=C_MUTED).grid(
            row=10, column=0, padx=20, pady=(16, 6), sticky="w")

        ctk.CTkCheckBox(
            sf,
            text="Acquisition details",
            variable=self.var_show_acq,
            command=self._on_show_acq_changed,
            text_color=C_TEXT,
            font=FONT_BODY,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            checkmark_color=C_TEXT,
        ).grid(row=11, column=0, padx=24, pady=3, sticky="w")

        ctk.CTkCheckBox(
            sf,
            text="Balance stats",
            variable=self.var_show_balance,
            command=self._on_show_balance_changed,
            text_color=C_TEXT,
            font=FONT_BODY,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            checkmark_color=C_TEXT,
        ).grid(row=12, column=0, padx=24, pady=3, sticky="w")

        ctk.CTkFrame(sf, height=1, fg_color=C_ACCENT2).grid(
            row=13, column=0, padx=16, pady=(16, 0), sticky="ew")

        # ---- Reload config button ----
        ctk.CTkButton(
            sf,
            text="↺  Reload Config",
            command=self._reload_data,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            text_color=C_BTN_TEXT,
            font=FONT_BODY,
            height=34,
            width=200,
        ).grid(row=14, column=0, padx=20, pady=(20, 8), sticky="w")

        # ---- Copyright (pinned to bottom) ----
        footer = tk.Frame(sf, bg=C_SIDEBAR)
        footer.grid(row=99, column=0, padx=20, pady=20, sticky="sw")
        sf.grid_rowconfigure(99, weight=1)

        ctk.CTkLabel(
            footer,
            text="© 2025 Derek Andersen\nMIT License",
            font=FONT_SMALL,
            text_color=C_MUTED,
            justify="left",
            fg_color=C_SIDEBAR,
        ).grid(row=0, column=0, sticky="w")

        kofi_lbl = ctk.CTkLabel(
            footer,
            text="☕ Support on Ko-fi",
            font=FONT_SMALL,
            text_color=C_ACCENT,
            justify="left",
            fg_color=C_SIDEBAR,
            cursor="hand2",
        )
        kofi_lbl.grid(row=1, column=0, pady=(2, 0), sticky="w")
        kofi_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://ko-fi.com/dechrissen"))
        kofi_lbl.bind("<Enter>", lambda e: kofi_lbl.configure(text_color=C_TEXT))
        kofi_lbl.bind("<Leave>", lambda e: kofi_lbl.configure(text_color=C_ACCENT))


    # =========================================================================
    # MAIN AREA (tabbed)
    # =========================================================================

    def _build_main(self):
        """
        Right panel with two tabs:
          - Generate : generate button, status, party results
          - Config   : all options from the active config YAML
        """
        self.tabview = ctk.CTkTabview(
            self.main_frame,
            fg_color=C_PANEL,
            segmented_button_fg_color=C_SIDEBAR,
            segmented_button_selected_color=C_ACCENT,
            segmented_button_selected_hover_color=C_ACCENT2,
            segmented_button_unselected_color=C_SIDEBAR,
            segmented_button_unselected_hover_color=C_ACCENT2,
            text_color=C_TEXT,
            text_color_disabled=C_MUTED,
        )
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.tabview.add("Generate")
        self.tabview.add("Config")

        self._build_gen_tab(self.tabview.tab("Generate"))
        self._build_config_tab(self.tabview.tab("Config"))


    # =========================================================================
    # GENERATE TAB
    # =========================================================================

    def _build_gen_tab(self, parent):
        """
        Generate tab layout:
          - Top bar: Generate button + status label
          - 3 × 2 grid of party-member cards
          - Stats strip below the grid
        """
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # ---- Top bar ----
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top_bar.grid_columnconfigure(1, weight=1)

        self.generate_btn = ctk.CTkButton(
            top_bar,
            text="▶  Generate Party",
            command=self._run_generation,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            text_color=C_BTN_TEXT,
            font=("Courier New", 15, "bold"),
            height=42,
            width=180,
            corner_radius=6,
        )
        self.generate_btn.grid(row=0, column=0, padx=(0, 16))

        self.status_label = ctk.CTkLabel(
            top_bar,
            text="Press Generate to begin.",
            font=FONT_BODY,
            text_color=C_MUTED,
            anchor="w",
        )
        self.status_label.grid(row=0, column=1, sticky="w")

        # ---- 3 × 2 card grid ----
        cards_outer = ctk.CTkFrame(parent, fg_color="transparent")
        cards_outer.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        cards_outer.grid_columnconfigure(0, weight=1)
        cards_outer.grid_columnconfigure(1, weight=1)
        for r in range(3):
            cards_outer.grid_rowconfigure(r, weight=1, minsize=105)

        self.party_cards = []
        for r in range(3):
            for c in range(2):
                card = self._make_card(cards_outer)
                card["frame"].grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
                self.party_cards.append(card)

        # ---- Stats strip ----
        stats_frame = ctk.CTkFrame(parent, fg_color=C_PANEL, corner_radius=8)
        stats_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(stats_frame, fg_color=C_PANEL, corner_radius=0)
        left.grid(row=0, column=0, padx=(16, 0), pady=10, sticky="w")

        self.stat_labels = {}
        for col, (key, label) in enumerate([("lean", "Lean"), ("spread", "Spread"), ("pattern", "Pattern")]):
            ctk.CTkLabel(left, text=label, font=FONT_SMALL, text_color=C_MUTED, anchor="w", width=150).grid(
                row=0, column=col, sticky="w")
            val = ctk.CTkLabel(left, text="—", font=FONT_BODY, text_color=C_TEXT, anchor="w", width=150)
            val.grid(row=1, column=col, sticky="w")
            self.stat_labels[key] = val

        right = ctk.CTkFrame(stats_frame, fg_color=C_PANEL, corner_radius=0)
        right.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="e")

        ctk.CTkLabel(right, text="Distribution", font=FONT_SMALL, text_color=C_MUTED, anchor="e").grid(
            row=0, column=0, sticky="e")
        dist_val = ctk.CTkLabel(right, text="—", font=FONT_BODY, text_color=C_TEXT, anchor="e")
        dist_val.grid(row=1, column=0, sticky="e")
        self.stat_labels["distribution"] = dist_val


    # =========================================================================
    # CARD HELPERS
    # =========================================================================

    def _make_card(self, parent) -> dict:
        """Build one empty party-member card; return updateable widget refs."""
        frame = ctk.CTkFrame(
            parent,
            fg_color=C_PANEL,
            corner_radius=8,
            border_width=1,
            border_color=C_ACCENT2,
        )
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)   # top spacer
        frame.grid_rowconfigure(1, weight=0)   # name
        frame.grid_rowconfigure(2, weight=0)   # types
        frame.grid_rowconfigure(3, weight=0)   # bst
        frame.grid_rowconfigure(4, weight=0)   # acq
        frame.grid_rowconfigure(5, weight=1)   # bottom spacer
        frame.grid_propagate(False)

        # Sprite slot — CTkLabel so it can hold a CTkImage; blank bg when empty
        # rowspan=6 + sticky="w" (no n/s) centers it vertically in the card
        sprite = ctk.CTkLabel(
            frame,
            text="",
            image=None,
            fg_color=C_ENTRY_BG,
            corner_radius=4,
            width=96,
            height=96,
        )
        sprite.grid(row=0, column=0, rowspan=6, padx=(10, 8), pady=0, sticky="w")

        name_lbl = ctk.CTkLabel(frame, text="—", font=FONT_HEADER, text_color=C_MUTED, anchor="w")
        name_lbl.grid(row=1, column=1, padx=(0, 10), pady=(0, 1), sticky="sew")

        # plain tk.Frame avoids CTkFrame canvas overpainting the card border
        types_frame = tk.Frame(frame, bg=C_PANEL)
        types_frame.grid(row=2, column=1, padx=(0, 10), pady=(0, 2), sticky="nw")

        bst_lbl = ctk.CTkLabel(frame, text="", font=FONT_SMALL, text_color=C_MUTED, anchor="nw")
        bst_lbl.grid(row=3, column=1, padx=(0, 10), pady=(0, 2), sticky="nw")

        acq_lbl = ctk.CTkLabel(
            frame, text="", font=FONT_SMALL, text_color=C_MUTED,
            anchor="nw", justify="left", wraplength=240,
        )
        acq_lbl.grid(row=4, column=1, padx=(0, 10), pady=(0, 0), sticky="nw")

        return {"frame": frame, "name": name_lbl, "acq": acq_lbl, "sprite": sprite,
                "types_frame": types_frame, "bst": bst_lbl}

    def _clear_cards(self):
        """Reset all party cards to their empty placeholder state."""
        for i, card in enumerate(self.party_cards):
            card["name"].configure(text="—", text_color=C_MUTED)
            card["acq"].configure(text="")
            card["bst"].configure(text="")
            card["frame"].configure(border_color=C_ACCENT2)
            card["sprite"].configure(image=None)
            self._sprite_images[i] = None
            for w in card["types_frame"].winfo_children():
                w.destroy()
        for lbl in self.stat_labels.values():
            lbl.configure(text="—", text_color=C_TEXT)
        self.last_party_blob = None

    def _render_type_badges(self, types_frame, types: list[str]):
        """Render colored type badges (swatch + label) into the given frame."""
        for w in types_frame.winfo_children():
            w.destroy()
        for col, type_name in enumerate(types):
            color = TYPE_COLORS.get(type_name.lower(), C_MUTED)
            badge = tk.Frame(types_frame, bg=C_PANEL)
            badge.grid(row=0, column=col, padx=(0, 6))
            tk.Frame(badge, width=10, height=10, bg=color).grid(row=0, column=0, padx=(0, 4))
            ctk.CTkLabel(badge, text=type_name.capitalize(), font=FONT_SMALL,
                         text_color=color, anchor="w", fg_color=C_PANEL).grid(row=0, column=1)


    # =========================================================================
    # CONFIG TAB
    # =========================================================================

    def _build_config_tab(self, parent):
        """
        Config tab: all options from the active config YAML.
        Changes are staged here and written to disk only when Save Config is clicked.

        Sections mirror the config YAML structure:
          1. Balancing
          2. Pokémon details
          3. Type restrictions
          4. Move coverage (HMs)
          5. Acquisition methods
        """
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(parent, fg_color=C_PANEL, scrollbar_button_color=C_ACCENT2)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)
        self.config_scroll = scroll

        # Mouse-wheel scrolling: activate globally while cursor is inside the frame.
        # Using enter/leave avoids accumulating duplicate bindings on every rebuild.
        canvas = scroll._parent_canvas

        def _on_config_scroll(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(-int(event.delta / 40), "units")

        scroll.bind("<Enter>", lambda e: [
            self.bind_all("<MouseWheel>", _on_config_scroll),
            self.bind_all("<Button-4>",   _on_config_scroll),
            self.bind_all("<Button-5>",   _on_config_scroll),
        ])
        scroll.bind("<Leave>", lambda e: [
            self.unbind_all("<MouseWheel>"),
            self.unbind_all("<Button-4>"),
            self.unbind_all("<Button-5>"),
        ])

        # ---- Save button ----
        save_bar = ctk.CTkFrame(parent, fg_color="transparent", height=50)
        save_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 10))
        save_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            save_bar,
            text="💾  Save Config",
            command=self._save_config,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            text_color=C_BTN_TEXT,
            font=("Courier New", 15, "bold"),
            height=38,
            width=160,
        ).grid(row=0, column=0, padx=(0, 12))

        self.config_status_label = ctk.CTkLabel(
            save_bar, text="", font=FONT_BODY, text_color=C_MUTED, anchor="w")
        self.config_status_label.grid(row=0, column=1, sticky="w")


    def _populate_config_controls(self):
        """
        Build (or rebuild) all config widgets inside the scrollable config frame.
        Called on initial load and whenever the game changes.
        """
        scroll = self.config_scroll

        for widget in scroll.winfo_children():
            widget.destroy()
        self.config_vars.clear()

        cd = self.config_data
        row = 0

        def section_label(text):
            nonlocal row
            ctk.CTkLabel(
                scroll, text=text, font=FONT_HEADER, text_color=C_ACCENT, anchor="w"
            ).grid(row=row, column=0, columnspan=2, padx=20, pady=(20, 4), sticky="w")
            row += 1
            ctk.CTkFrame(scroll, height=1, fg_color=C_ACCENT2).grid(
                row=row, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="ew")
            row += 1

        def bool_row(key, label):
            nonlocal row
            var = tk.BooleanVar(value=bool(cd.get(key, False)))
            self.config_vars[key] = var
            ctk.CTkCheckBox(
                scroll, text=label, variable=var,
                text_color=C_TEXT, font=FONT_BODY,
                fg_color=C_ACCENT, hover_color=C_ACCENT2,
                checkmark_color=C_TEXT,
            ).grid(row=row, column=0, columnspan=2, padx=28, pady=3, sticky="w")
            row += 1

        def int_row(key, label, nullable=False):
            nonlocal row
            current_val = cd.get(key, None)
            if nullable:
                is_none = current_val is None or str(current_val).lower() == "none"
                var = tk.StringVar(value="" if is_none else str(current_val))
            else:
                var = tk.StringVar(value=str(current_val if current_val is not None else ""))
            self.config_vars[key] = var
            ctk.CTkLabel(scroll, text=label, font=FONT_BODY, text_color=C_TEXT, anchor="w").grid(
                row=row, column=0, padx=28, pady=4, sticky="w")
            ctk.CTkEntry(
                scroll, textvariable=var, width=100,
                fg_color=C_ENTRY_BG, text_color=C_TEXT,
                border_color=C_ACCENT2, font=FONT_BODY,
                placeholder_text="none" if nullable else "",
            ).grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            row += 1

        def multi_check_row(key, label):
            """
            List-of-strings config key. Config format:
              key:
                value: [balanced, late_game_heavy]
                options: [balanced, early_game_heavy, late_game_heavy]
            """
            nonlocal row
            field = cd.get(key, {}) or {}
            current_values = field.get("value", []) or []
            options = field.get("options", []) or []
            ctk.CTkLabel(scroll, text=label, font=FONT_BODY, text_color=C_TEXT, anchor="w").grid(
                row=row, column=0, columnspan=2, padx=28, pady=(6, 2), sticky="w")
            row += 1
            var_dict = {"__list__": True}  # sentinel: _save_config writes value as a plain list
            for option in options:
                var = tk.BooleanVar(value=(option in current_values))
                var_dict[option] = var
                ctk.CTkCheckBox(
                    scroll, text=option, variable=var,
                    text_color=C_MUTED, font=FONT_SMALL,
                    fg_color=C_ACCENT2, hover_color=C_ACCENT,
                    checkmark_color=C_TEXT,
                ).grid(row=row, column=0, columnspan=2, padx=44, pady=2, sticky="w")
                row += 1
            self.config_vars[key] = var_dict

        def nested_bool_row(parent_key, label, options):
            """
            Dict-of-booleans config key.
            e.g. allowed_evo_methods: {level-up: true, trade: false, ...}
            """
            nonlocal row
            current_dict = cd.get(parent_key, {}) or {}
            ctk.CTkLabel(scroll, text=label, font=FONT_BODY, text_color=C_TEXT, anchor="w").grid(
                row=row, column=0, columnspan=2, padx=28, pady=(6, 2), sticky="w")
            row += 1
            var_dict = {}
            for option in options:
                var = tk.BooleanVar(value=bool(current_dict.get(option, False)))
                var_dict[option] = var
                ctk.CTkCheckBox(
                    scroll, text=option, variable=var,
                    text_color=C_MUTED, font=FONT_SMALL,
                    fg_color=C_ACCENT2, hover_color=C_ACCENT,
                    checkmark_color=C_TEXT,
                ).grid(row=row, column=0, columnspan=2, padx=44, pady=2, sticky="w")
                row += 1
            self.config_vars[parent_key] = var_dict

        def dropdown_row(key, label):
            """
            String config key with options. Config format:
              key:
                value: anything_goes
                options: [anything_goes, no_overlap, all_share_one_type]
            """
            nonlocal row
            field = cd.get(key, {}) or {}
            options = field.get("options", []) or []
            current_val = str(field.get("value", None) or "none")
            if options and current_val not in options:
                current_val = options[0]
            var = tk.StringVar(value=current_val)
            self.config_vars[key] = var
            ctk.CTkLabel(scroll, text=label, font=FONT_BODY, text_color=C_TEXT, anchor="w").grid(
                row=row, column=0, padx=28, pady=4, sticky="w")
            ctk.CTkOptionMenu(
                scroll, variable=var, values=options if options else [current_val],
                fg_color=C_ENTRY_BG, button_color=C_ACCENT2,
                button_hover_color=C_ACCENT, text_color=C_TEXT, font=FONT_BODY,
                width=200,
            ).grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            row += 1

        def text_row(key, label, placeholder=""):
            nonlocal row
            current_val = cd.get(key, []) or []
            display_val = ", ".join(current_val) if isinstance(current_val, list) else str(current_val)
            var = tk.StringVar(value=display_val)
            self.config_vars[key] = var
            ctk.CTkLabel(scroll, text=label, font=FONT_BODY, text_color=C_TEXT, anchor="w").grid(
                row=row, column=0, padx=28, pady=4, sticky="w")
            ctk.CTkEntry(
                scroll, textvariable=var, width=320,
                fg_color=C_ENTRY_BG, text_color=C_TEXT,
                border_color=C_ACCENT2, font=FONT_BODY,
                placeholder_text=placeholder,
            ).grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            row += 1

        section_label("Balancing")
        multi_check_row("allowed_balancing", "Allowed balancing modes:")
        multi_check_row("allowed_spreads", "Allowed spreads:")
        multi_check_row("allowed_patterns", "Allowed patterns:")

        section_label("Pokémon Details")
        bool_row("force_starter",           "Force a random starter in the party")
        bool_row("allow_not_fully_evolved", "Allow not fully evolved Pokémon")
        bool_row("allow_legendaries",       "Allow legendary Pokémon")
        bool_row("allow_duplicate_species", "Allow duplicate species")
        int_row("max_evo_stage", "Max evolution stage:")
        int_row("bst_max", "BST maximum (none = no limit):", nullable=True)
        int_row("bst_min", "BST minimum (none = no limit):", nullable=True)
        text_row("species_blacklist", "Species blacklist (comma-separated):", placeholder="e.g. RATTATA, PIDGEY")
        evo_methods = list(cd.get("allowed_evo_methods", {}).keys())
        nested_bool_row("allowed_evo_methods", "Allowed evolution methods:", evo_methods)

        section_label("Type Restrictions")
        bool_row("allow_dual_type", "Allow dual-type Pokémon")
        dropdown_row("type_distribution", "Type distribution:")
        dropdown_row("prescribed_type", "Prescribed type (for all_share_one_type):")

        section_label("HM Coverage")
        hm_options = list(cd.get("ensure_hm_coverage", {}).keys())
        nested_bool_row("ensure_hm_coverage", "Require these HMs in party move pool:", hm_options)

        section_label("Acquisition Methods")
        acq_options = list(cd.get("allowed_acquisition_methods", {}).keys())
        nested_bool_row("allowed_acquisition_methods", "Allowed acquisition methods:", acq_options)


    # =========================================================================
    # POPULATE UI FROM LOADED STATE
    # =========================================================================

    def _populate_ui_from_state(self):
        """Push current loaded values into all UI controls. Called on startup and after reload."""
        gs = self.global_settings

        game_names = list(self.mappings.keys())
        self.game_dropdown.configure(values=game_names)
        self.var_game.set(gs.get("game", game_names[0]))
        self.var_gen_mode.set(gs.get("generation_mode", "Progression"))
        self.var_show_acq.set(bool(gs.get("show_acquisition_details", True)))
        self.var_show_balance.set(bool(gs.get("show_balance_stats", True)))

        self._populate_config_controls()


    # =========================================================================
    # SIDEBAR EVENT HANDLERS
    # =========================================================================

    def _patch_global_setting(self, key: str, value):
        """Read global_settings.yaml, update one key, and write it back."""
        gs = read_yaml(GLOBAL_SETTINGS_PATH)
        gs[key] = value
        write_yaml(GLOBAL_SETTINGS_PATH, gs)

    def _on_game_changed(self, selected_game: str):
        self._patch_global_setting("game", selected_game)
        self._reload_data()
        self._set_status(f"Game set to {selected_game}.", color=C_SUCCESS)
        self._set_config_status(f"Loaded config for {selected_game}.")

    def _on_mode_changed(self):
        new_mode = self.var_gen_mode.get()
        self._patch_global_setting("generation_mode", new_mode)
        self._set_status(f"Mode set to {new_mode}.", color=C_SUCCESS)

    def _on_show_acq_changed(self):
        self._patch_global_setting("show_acquisition_details", self.var_show_acq.get())
        if self.last_party_blob is not None:
            self._populate_cards(self.last_party_blob)

    def _on_show_balance_changed(self):
        self._patch_global_setting("show_balance_stats", self.var_show_balance.get())
        if self.last_party_blob is not None:
            self._populate_cards(self.last_party_blob)


    # =========================================================================
    # CONFIG SAVE
    # =========================================================================

    def _save_config(self):
        """
        Read all config_vars, convert back to the correct Python types,
        and write to the config YAML for the currently selected game.
        """
        game = self.var_game.get()
        config_path = self.mappings[game]["config"]
        data = read_yaml(config_path)

        try:
            for key, var in self.config_vars.items():

                # List-of-strings keys (multi_check_row) — identified by "__list__" sentinel
                # Only update the "value" subkey; preserve "options" in the config file
                if isinstance(var, dict) and var.get("__list__"):
                    data[key]["value"] = [opt for opt, v in var.items() if opt != "__list__" and v.get()]

                # Dict-of-booleans keys (nested_bool_row)
                elif isinstance(var, dict):
                    data[key] = {option: v.get() for option, v in var.items()}

                elif isinstance(var, tk.BooleanVar):
                    data[key] = var.get()

                elif isinstance(var, tk.StringVar):
                    raw = var.get().strip()

                    # int-or-none fields
                    # Note: core.py expects the string "none" (not Python None / YAML null)
                    if key in ("bst_max", "bst_min"):
                        data[key] = "none" if (raw == "" or raw.lower() == "none") else int(raw)

                    elif key == "max_evo_stage":
                        data[key] = int(raw) if raw else data[key]

                    elif key == "species_blacklist":
                        data[key] = [s.strip() for s in raw.split(",") if s.strip()] if raw else []

                    # dropdown fields — only update the "value" subkey; preserve "options"
                    else:
                        data[key]["value"] = raw

        except (ValueError, TypeError) as e:
            messagebox.showerror("Save Error", f"Invalid value in config:\n{e}")
            return

        write_yaml(config_path, data)
        self._reload_data()
        self._set_config_status("Config saved.", color=C_SUCCESS)


    # =========================================================================
    # PARTY GENERATION
    # =========================================================================

    def _run_generation(self):
        """Kick off party generation in a background thread so the GUI stays responsive."""
        if self.is_generating:
            return

        self.is_generating = True
        self.generate_btn.configure(state="disabled", text="Generating…")
        self._set_status("Generating party…", color=C_MUTED)
        self._clear_cards()

        thread = threading.Thread(target=self._generation_worker, daemon=True)
        thread.start()
        self._animate_status(0)

    def _animate_status(self, tick: int):
        """Dot-cycling animation on the status label while generation runs."""
        if not self.is_generating:
            return
        dots = "." * ((tick % 3) + 1)
        self._set_status(f"Generating party{dots}", color=C_MUTED)
        self.after(400, self._animate_status, tick + 1)

    def _generation_worker(self):
        """Background thread: calls core generation, then schedules UI update on main thread."""
        try:
            gen_mode = self.var_gen_mode.get()
            start = time.time()

            if gen_mode == "Random":
                party_blob = generate_fully_randomized_party(self.all_pokemon, n=6)
            else:
                party_blob = generate_final_party(
                    self.all_pools, self.all_pokemon,
                    self.config_data, self.meta_data, n=6
                )

            duration = time.time() - start

        except Exception as e:
            self.after(0, self._on_generation_done, None, 0, str(e))
            return

        self.after(0, self._on_generation_done, party_blob, duration, None)

    def _on_generation_done(self, party_blob, duration: float, error: str | None):
        """Called on the main thread once generation finishes."""
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="▶  Generate Party")

        if error:
            self._set_status(f"Error: {error}", color=C_WARNING)
            return

        if party_blob is None:
            self._set_status("Could not generate a party. Try adjusting settings.", color=C_WARNING)
            return

        self._set_status(f"Done! ({duration:.2f}s)", color=C_SUCCESS)
        self.last_party_blob = party_blob
        self._populate_cards(party_blob)


    # =========================================================================
    # RESULTS RENDERING
    # =========================================================================

    def _populate_cards(self, party_blob: dict):
        """Fill the 6 party-member cards and stats strip from party_blob."""
        show_acq     = self.var_show_acq.get()
        show_balance = self.var_show_balance.get()

        game = self.var_game.get()
        sprite_dir = resource_path(self.mappings[game]["sprites"])

        def sort_key(p):
            prescribed = p["random_pool_entry_instance"]
            method = prescribed["acquisition_method"] if prescribed else None
            earliest_pool = p.get("earliest_pool", 9999) or 9999
            return (0 if method == "starter" else 1, earliest_pool)

        sorted_party = sorted(party_blob["party_with_acquisition_data"], key=sort_key)

        for i, pokemon in enumerate(sorted_party):
            card = self.party_cards[i]
            mon_obj = pokemon["party_member_obj"]
            card["name"].configure(text=mon_obj.name, text_color=C_TEXT)
            card["frame"].configure(border_color=C_ACCENT)
            self._render_type_badges(card["types_frame"], mon_obj.types)
            card["bst"].configure(text=f"Base stat total: {mon_obj.base_stat_total}")

            sprite_path = os.path.join(sprite_dir, f"{mon_obj.nat_dex_number}.png")
            try:
                pil_img = Image.open(sprite_path).resize((96, 96), Image.NEAREST)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(96, 96))
                self._sprite_images[i] = ctk_img
                card["sprite"].configure(image=ctk_img)
            except (FileNotFoundError, OSError):
                self._sprite_images[i] = None
                card["sprite"].configure(image=None)

            if show_acq and pokemon["random_pool_entry_instance"] is not None:
                prescribed    = pokemon["random_pool_entry_instance"]
                method        = prescribed["acquisition_method"]
                location      = prescribed["acquiring_location"]
                earliest_form = pokemon["earliest_form"]
                earliest_pool = pokemon["earliest_pool"]
                card["acq"].configure(
                    text=(
                        f"acquire as {earliest_form.name}\n"
                        f"via {method} at {location}\n"
                        f"(Sphere {earliest_pool})"
                    )
                )
            else:
                card["acq"].configure(text="")

        if show_balance and party_blob.get("lean") is not None:
            self.stat_labels["lean"].configure(text=str(party_blob.get("lean", "—")), text_color=C_TEXT)
            self.stat_labels["spread"].configure(text=str(party_blob.get("spread", "—")), text_color=C_TEXT)
            pattern = party_blob.get("pattern")
            self.stat_labels["pattern"].configure(text=str(pattern) if pattern else "—", text_color=C_TEXT)
            dist = party_blob.get("party_distribution")
            if dist:
                dist_str = "  ".join(f"S{s}: {dist[s]}" for s in dist)
                self.stat_labels["distribution"].configure(text=dist_str, text_color=C_TEXT)
            else:
                self.stat_labels["distribution"].configure(text="—", text_color=C_MUTED)
        else:
            for lbl in self.stat_labels.values():
                lbl.configure(text="—", text_color=C_MUTED)


    # =========================================================================
    # STATUS LABEL HELPERS
    # =========================================================================

    def _set_status(self, message: str, color: str = C_MUTED):
        """Update the status label next to the Generate button."""
        self.status_label.configure(text=message, text_color=color)

    def _set_config_status(self, message: str, color: str = C_MUTED):
        """Update the status label in the Config tab."""
        self.config_status_label.configure(text=message, text_color=color)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    _pools, _pokemon, _config, _meta, _mappings, _settings = build_all_data_structures()
    app = TeamGenApp(_pools, _pokemon, _config, _meta, _mappings, _settings)
    app.mainloop()
