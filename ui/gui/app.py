# Copyright 2026 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/

# app.py — the Dexelect GUI (plain Tk/ttk)
# Rendered with the platform's native default theme: system fonts (named Tk
# fonts only), default colors, relief borders instead of color blocking.
# It reads/writes the same config files as the CLI, so both UIs stay in sync.
#
# Run:
#   python main.py            (gui is the default UI)
#
# Structure:
#   - Config file helpers
#   - Tooltip + glyph icons
#   - DexelectApp class
#       - __init__          : root window, fonts, layout, content-driven sizing
#       - _build_sidebar    : left panel (game, mode, party size, toggles, export)
#       - _build_main       : ttk.Notebook (Generate, Spheres, Config) + help
#       - _build_gen_tab    : generate button, cards, HM strip, stats
#       - _build_config_tab : all config_genX.yaml options with autosave
#       - Logic methods     : load_state, autosave, run_generation, export, etc.

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog
import yaml
import threading
import time
import os
import sys
import webbrowser
from PIL import Image, ImageTk
from core import generate_final_party, generate_fully_randomized_party, count_new_species_per_sphere
from data.loader import build_all_data_structures, seed_working_config, list_config_presets
from ui.export import build_export_text, default_export_filename
from util import resource_path, format_duration
from version import __version__


# =============================================================================
# CONFIG FILE HELPERS
# =============================================================================

GLOBAL_SETTINGS_PATH = "config/global_settings.yaml"
GAME_SETTINGS_PATH   = "config/game_settings.yaml"
TOOLTIPS_PATH        = "ui/gui/tooltips.yaml"

def read_yaml(path: str) -> dict:
    try:
        with open(resource_path(path), "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

class _InlineListDumper(yaml.Dumper):
    """
    Custom YAML dumper that keeps plain lists on a single line (flow style),
    e.g. [balanced, early_game_heavy] instead of the default multi-line "- item" format.
    Dicts and all other types are still written in block style as normal.
    """
    def represent_sequence(self, tag, sequence, flow_style=None):
        return super().represent_sequence(tag, sequence, flow_style=True)

def write_yaml(path: str, data: dict):
    with open(resource_path(path), "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=_InlineListDumper, default_flow_style=False, allow_unicode=True, sort_keys=False)


# =============================================================================
# SEMANTIC COLORS (states/data only — no theme styling)
# =============================================================================

C_MUTED   = "gray40"      # secondary text
C_DIM     = "gray60"      # disabled/inactive text
C_SUCCESS = "#006400"     # status: success
C_WARNING = "#a40000"     # status: error / warning
C_NOTICE  = "#a05a00"     # warning strip
C_LINK    = "#0645ad"     # clickable text
C_COVERED = "#006400"     # HM covered by party

# Pokémon type -> color (semantic data)
TYPE_COLORS = {
    "normal":   "#9a9a78",
    "fire":     "#f08030",
    "water":    "#6890f0",
    "grass":    "#78c850",
    "electric": "#f8d030",
    "flying":   "#a890f0",
    "fighting": "#c03028",
    "ice":      "#98d8d8",
    "psychic":  "#f85888",
    "ground":   "#e0c068",
    "rock":     "#b8a038",
    "poison":   "#a040a0",
    "bug":      "#a8b820",
    "dragon":   "#7038f8",
    "ghost":    "#705898",
    "steel":    "#b8b8d0",
    "dark":     "#705848",
}

# TYPE_COLORS was tuned for the dark CTk theme; the lightest types (electric,
# ground, steel, ice, ...) wash out on the native light-grey background.
# Colors above a perceptual-luminance threshold are scaled toward black,
# preserving hue, so every badge stays legible.
_BADGE_LUM_LIMIT = 0.55
# Electric is distinguished from the other yellow hues (rock, ground) mainly
# by brightness, which the global limit erases — it keeps a higher ceiling.
_BADGE_LUM_EXCEPTIONS = {"electric": 0.64}
_badge_color_cache = {}

def _badge_color(color: str, limit: float = _BADGE_LUM_LIMIT) -> str:
    if not (color.startswith("#") and len(color) == 7):
        return color  # non-hex fallbacks (e.g. named colors) pass through
    cached = _badge_color_cache.get((color, limit))
    if cached:
        return cached
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    out = color
    if lum > limit:
        k = limit / lum
        out = f"#{int(r * k):02x}{int(g * k):02x}{int(b * k):02x}"
    _badge_color_cache[(color, limit)] = out
    return out


# =============================================================================
# TOOLTIP
# =============================================================================

class _Tooltip:
    """Lightweight hover tooltip rendered as an in-window frame.

    Uses a tk.Frame placed inside the root window via place() rather than a
    Toplevel. This avoids two Wayland/tiling-WM problems with Toplevel:
      1. Absolute screen coordinates are unreliable (winfo_rootx/y returns 0,0
         for XWayland apps). Relative coords (widget - root) cancel that out.
      2. A Toplevel is a separate OS window that steals focus, causes synthetic
         Leave events, and can get orphaned if the reference is lost mid-hide.
    """

    def __init__(self, widget, text: str):
        self._widget  = widget
        self._text    = text
        self._tip     = None
        self._show_id = None
        self._hide_id = None
        widget.bind("<Enter>",   self._on_enter,  add="+")
        widget.bind("<Leave>",   self._on_leave,  add="+")
        widget.bind("<Destroy>", lambda e: self._cancel_all(), add="+")

    def _on_enter(self, event=None):
        self._cancel_hide()
        if not self._tip:
            self._show_id = self._widget.after(300, self._show)

    def _on_leave(self, event=None):
        self._cancel_show()
        self._hide_id = self._widget.after(50, self._check_and_hide)

    def _check_and_hide(self):
        self._hide_id = None
        try:
            px = self._widget.winfo_pointerx()
            py = self._widget.winfo_pointery()
            wx = self._widget.winfo_rootx()
            wy = self._widget.winfo_rooty()
            ww = self._widget.winfo_width()
            wh = self._widget.winfo_height()
            if wx <= px <= wx + ww and wy <= py <= wy + wh:
                if self._tip is None and self._show_id is None:
                    self._show_id = self._widget.after(300, self._show)
                return
        except tk.TclError:
            pass
        self._do_hide()

    def _show(self):
        self._show_id = None
        if self._tip:
            return
        root = self._widget.winfo_toplevel()
        # Classic native tooltip look: pale yellow, thin border.
        tip = tk.Frame(root, bg="#ffffe0", highlightthickness=1,
                       highlightbackground="gray50")
        tk.Label(
            tip, text=self._text, justify="left",
            bg="#ffffe0",
            padx=10, pady=6, wraplength=300,
        ).pack()
        self._tip = tip
        root.update_idletasks()
        tip_w = tip.winfo_reqwidth()
        tip_h = tip.winfo_reqheight()
        # Subtracting root's own winfo_rootx/y converts to root-relative coords,
        # which cancels out any wrong absolute offset Wayland reports.
        rx = self._widget.winfo_rootx() - root.winfo_rootx()
        ry = self._widget.winfo_rooty() - root.winfo_rooty()
        wh = self._widget.winfo_height()
        rw = root.winfo_width()
        rh = root.winfo_height()
        # Horizontal: prefer right of icon, flip left if it would clip.
        tx = rx + 12
        if tx + tip_w > rw - 4:
            tx = rx - tip_w - 4
        tx = max(4, tx)
        # Vertical: prefer above icon, fall back to below.
        ty = ry - tip_h - 4 if ry > tip_h + 4 else ry + wh + 4
        ty = max(4, min(ty, rh - tip_h - 4))
        tip.place(x=tx, y=ty)
        tip.lift()

    def _do_hide(self):
        if self._tip:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None

    def _cancel_show(self):
        if self._show_id:
            self._widget.after_cancel(self._show_id)
            self._show_id = None

    def _cancel_hide(self):
        if self._hide_id:
            self._widget.after_cancel(self._hide_id)
            self._hide_id = None

    def _cancel_all(self):
        self._cancel_show()
        self._cancel_hide()
        self._do_hide()


# =============================================================================
# GLYPH ICONS (system-font text glyphs — no custom drawing)
# =============================================================================

def _icon_canvas(parent):
    """Return a small info-glyph label used as a tooltip hover target."""
    return tk.Label(parent, text="\u24d8", fg="gray35", cursor="question_arrow", bd=0)


# =============================================================================
# MAIN APP CLASS
# =============================================================================

SPRITE_MAX = 112  # sprite size (px) — pixel art, fixed integer size

class DexelectApp(tk.Tk):

    def __init__(self, all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon):
        # className='dexelect' sets WM_CLASS so it matches StartupWMClass in the .desktop launcher files
        super().__init__(className='dexelect')

        # ---- Window setup ----
        # Hidden while the UI is built and measured (_apply_initial_geometry
        # stages placeholder card content to size the window and would flash
        # otherwise); shown once the final geometry is set.
        self.withdraw()
        self.title(f"Dexelect v{__version__}")

        # ---- Named system fonts (the only font styling: derivatives of Tk's
        #      own named fonts — no hardcoded families or point sizes) ----
        base = tkfont.nametofont("TkDefaultFont")
        base_size = base.cget("size")
        step = 1 if base_size > 0 else -1  # size may be negative (pixels)
        self.font_bold = base.copy()
        self.font_bold.configure(weight="bold")
        self.font_h1 = base.copy()
        self.font_h1.configure(weight="bold", size=base_size + 4 * step)
        self.font_h2 = base.copy()
        self.font_h2.configure(weight="bold", size=base_size + 2 * step)
        self.font_small = base.copy()
        self.font_small.configure(size=base_size - step)
        self.font_fixed = tkfont.nametofont("TkFixedFont")

        # ---- App icon ----
        _icon_sizes = [16, 32, 38, 64, 128, 256]
        _icon_imgs = []
        for _s in _icon_sizes:
            _p = resource_path(f"assets/icons/{_s}.png")
            if os.path.exists(_p):
                _icon_imgs.append(ImageTk.PhotoImage(Image.open(_p)))
        if _icon_imgs:
            self.wm_iconphoto(True, *_icon_imgs)
            self._icon_imgs = _icon_imgs  # prevent GC
        if sys.platform == "win32":
            _ico = resource_path("assets/icons/dexelect.ico")
            if os.path.exists(_ico):
                self.iconbitmap(_ico)

        # ---- App state ----
        self.all_pools           = all_pools
        self.all_pokemon         = all_pokemon
        self.config_data         = config_data
        self.meta_data           = meta_data
        self.mappings            = mappings
        self.global_settings     = global_settings
        self.obtainable_pokemon  = obtainable_pokemon

        # Tkinter variables for sidebar controls (bound to widgets)
        self.var_game         = tk.StringVar()
        self.var_gen_mode     = tk.StringVar()
        self.var_show_acq     = tk.BooleanVar()
        self.var_show_balance = tk.BooleanVar()
        self.var_show_hm      = tk.BooleanVar()
        self.var_party_size   = tk.StringVar()
        self.var_sphere_mode  = tk.StringVar()

        # Config tab variables — populated dynamically in _populate_config_controls
        self.config_vars    = {}
        self._config_loading = False
        self._config_built   = False

        # Generation state
        self.is_generating   = False
        self.last_party_blob = None

        # Sprite image refs (prevent GC of PhotoImage objects while displayed)
        self._sprite_images = [None] * 6

        self._config_note_label = None
        self.hm_labels = {}
        self._hm_strip_inner = None
        self._hm_list_frame  = None
        self._hm_dash_label  = None

        # Debounce job IDs for <Configure> handlers (see _debounce)
        self._gen_canvas_resize_job = None
        self._stats_resize_job = None
        self._hm_resize_job = None
        self._config_note_resize_job = None

        # Gen-tab scrollbar auto-hide state (see _yscroll_set in _build_gen_tab)
        self._gen_scrollbar_hidden = False

        # Tooltip text keyed by config field name
        try:
            self.tooltips = read_yaml(TOOLTIPS_PATH) or {}
        except Exception:
            self.tooltips = {}

        # ---- Build UI ----
        self._build_layout()
        self._build_sidebar()
        self._build_main()

        # ---- Populate UI from loaded data ----
        self._populate_ui_from_state()

        # ---- Content-driven window sizing (no %-of-screen formula) ----
        self._apply_initial_geometry()

        self.bind("<Return>", lambda e: self._run_generation()
                  if self.generate_btn.instate(["!disabled"])
                  and self.notebook.select() == str(self._tab_frames["Generate"])
                  and not (self._help_overlay and self._help_overlay.winfo_exists())
                  else None)



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
         self.global_settings,
         self.obtainable_pokemon) = build_all_data_structures()
        self._populate_ui_from_state()
        self._set_status("Config reloaded.", color=C_SUCCESS)

    def _on_load_defaults(self):
        """Overwrite the current game's working config with the default preset,
        then reload so the new values populate the Config tab and all derived
        data structures (obtainable pool, etc.)."""
        game = self.var_game.get()
        config_path = self.mappings[game]["config"]
        seed_working_config(config_path, preset="default", force=True)
        self._reload_data()
        self._set_config_status("Loaded 'Default' preset values.", color=C_SUCCESS)

    def _on_load_preset(self, preset_id, label):
        """Overwrite the current game's working config with the chosen preset
        (folder config/presets/<preset_id>/), then reload — same effect as
        _on_load_defaults but for any non-default preset. `label` is the display
        name, used only for the status message."""
        game = self.var_game.get()
        config_path = self.mappings[game]["config"]
        seed_working_config(config_path, preset=preset_id, force=True)
        self._reload_data()
        self._set_config_status(f"Loaded '{label}' preset values.", color=C_SUCCESS)

    def _rebuild_preset_menu(self):
        """Repopulate the Load Preset menu from the presets on disk each time it
        opens, so newly-added preset folders show up without a restart. Menu
        entries show each preset's display name; 'default' is excluded (the
        dedicated Restore Defaults button covers it)."""
        menu = self._preset_menu
        menu.delete(0, "end")
        game = self.var_game.get()
        config_path = self.mappings[game]["config"]
        presets = [(pid, label) for pid, label in list_config_presets(config_path)
                   if pid != "default"]
        if not presets:
            menu.add_command(label="(no other presets)", state="disabled")
            return
        for pid, label in presets:
            menu.add_command(label=label,
                             command=lambda p=pid, l=label: self._on_load_preset(p, l))


    # =========================================================================
    # LAYOUT SKELETON / SIZING
    # =========================================================================

    def _debounce(self, job_attr: str, delay_ms: int, func):
        """Cancel any pending call scheduled under job_attr and reschedule func.

        Live window resizing fires many <Configure> events per second; routing
        the handlers that do real relayout work through this collapses
        rapid-fire events into a single call once resizing activity settles.
        """
        job = getattr(self, job_attr, None)
        if job is not None:
            self.after_cancel(job)
        setattr(self, job_attr, self.after(delay_ms, func))

    def _apply_initial_geometry(self):
        """Size the window from its content, center it, clamp to the screen.

        No screen-fraction formula: widgets size from system fonts, containers
        size from widgets, and the window takes its natural requested size —
        so it looks the same on 1080p, 1440p, or anything else. If the screen
        is too small, the window is clamped and the gen tab's scroll takes over.

        Measured with placeholder party content staged into the cards so the
        default window is tall enough for a *generated* party — nothing gets
        cut off when Generate fills the cards. The window is withdrawn during
        construction, so the staging is never visible; a manual resize by the
        user is respected as usual (scrolling takes over).
        """
        blank = tk.PhotoImage(width=SPRITE_MAX, height=SPRITE_MAX)
        for card in self.party_cards:
            card["sprite"].configure(image=blank)
            card["name"].configure(text="Placeholder")
            self._render_type_badges(card["types_frame"], ["normal"])
            card["bst"].configure(text="Base stat total: 000")
            card["sep"].grid()
            card["acq"].configure(
                text="Acquire as: X\nMethod: x\nLocation: x\nSphere: 1")
        # Stage a worst-case distribution string as well: the natural width must
        # be wide enough that the stats strip never wraps to a second row at
        # the default size (the wrap costs a full row of height).
        n_spheres = len(self.meta_data.get("spheres", [])) or 10
        self.stat_labels["distribution"].configure(
            text="  ".join(f"S{i}: 6" for i in range(1, n_spheres + 1)))
        self.update_idletasks()
        # The gen canvas has no natural size of its own; request exactly what
        # its content frame wants (+ a small margin for the HM list swapping
        # in for its dash) so the window's natural size fits populated cards.
        self._gen_canvas.configure(width=self._gen_inner.winfo_reqwidth(),
                                   height=self._gen_inner.winfo_reqheight() + 16)
        self._clear_cards()
        self.update_idletasks()
        req_w, req_h = self.winfo_reqwidth(), self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(req_w, sw - 20)
        h = min(req_h, sh - 80)   # leave room for taskbar/decorations
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        min_h = min(self.sidebar_frame.winfo_reqheight() + 8, sh - 80)
        min_w = min(self.sidebar_frame.winfo_reqwidth() + 360, sw - 20)
        self.minsize(min_w, min_h)
        self.deiconify()

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = tk.Frame(self)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        ttk.Separator(self, orient="vertical").grid(row=0, column=1, sticky="ns")

        self.main_frame = tk.Frame(self)
        self.main_frame.grid(row=0, column=2, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=0)  # header (Help button)
        self.main_frame.grid_rowconfigure(1, weight=1)  # notebook
        self.main_frame.grid_columnconfigure(0, weight=1)


    # =========================================================================
    # SIDEBAR
    # =========================================================================

    def _build_sidebar(self):
        """
        Left panel:
          - Logo / version
          - Game selector (dropdown)
          - Generation mode (radio buttons)
          - Party size selector
          - Display toggles
          - Export button
          - Footer links
        """
        sf = self.sidebar_frame
        sf.grid_columnconfigure(0, weight=1)

        # ---- Title ----
        _logo_path = resource_path("assets/logo/dexelect-logo-black.png")
        if os.path.exists(_logo_path):
            _logo_src = Image.open(_logo_path)
            _logo_display_w = 190
            _logo_display_h = round(_logo_display_w * _logo_src.height / _logo_src.width)
            _logo_resized = _logo_src.resize((_logo_display_w, _logo_display_h), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(_logo_resized)
            tk.Label(sf, image=self._logo_img, bd=0).grid(
                row=0, column=0, padx=20, pady=(24, 2), sticky="w")
        else:
            tk.Label(sf, text="Dexelect", font=self.font_h1).grid(
                row=0, column=0, padx=20, pady=(24, 2), sticky="w")
        tk.Label(sf, text=f"v{__version__}", font=self.font_fixed, fg=C_MUTED).grid(
            row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        ttk.Separator(sf, orient="horizontal").grid(row=2, column=0, padx=12, sticky="ew")

        # ---- Game selector ----
        tk.Label(sf, text="GAME", font=self.font_bold).grid(
            row=3, column=0, padx=20, pady=(16, 4), sticky="w")

        self.game_dropdown = tk.OptionMenu(sf, self.var_game, "")
        self.game_dropdown.configure(anchor="w")
        self.game_dropdown.grid(row=4, column=0, padx=20, pady=(0, 14), sticky="ew")

        ttk.Separator(sf, orient="horizontal").grid(row=5, column=0, padx=12, sticky="ew")

        # ---- Generation mode ----
        tk.Label(sf, text="MODE", font=self.font_bold).grid(
            row=6, column=0, padx=20, pady=(16, 4), sticky="w")

        for i, mode in enumerate(["Progression", "Random (Obtainable)", "Random (National Dex)"]):
            tk.Radiobutton(
                sf,
                text=mode,
                variable=self.var_gen_mode,
                value=mode,
                command=self._on_mode_changed,
                anchor="w",
            ).grid(row=7 + i, column=0, padx=20, pady=1, sticky="w")

        ttk.Separator(sf, orient="horizontal").grid(row=10, column=0, padx=12, pady=(14, 0), sticky="ew")

        # ---- Party size ----
        tk.Label(sf, text="PARTY SIZE", font=self.font_bold).grid(
            row=11, column=0, padx=20, pady=(14, 4), sticky="w")

        size_row = tk.Frame(sf)
        size_row.grid(row=12, column=0, padx=20, pady=(0, 4), sticky="w")
        for i in range(1, 7):
            tk.Radiobutton(
                size_row,
                text=str(i),
                variable=self.var_party_size,
                value=str(i),
                indicatoron=0,   # button-style radios read as a segmented strip
                width=2,
                command=lambda: self._on_party_size_changed(self.var_party_size.get()),
            ).pack(side="left")

        ttk.Separator(sf, orient="horizontal").grid(row=13, column=0, padx=12, pady=(14, 0), sticky="ew")

        # ---- Display toggles (global_settings.yaml) ----
        tk.Label(sf, text="DISPLAY", font=self.font_bold).grid(
            row=14, column=0, padx=20, pady=(14, 4), sticky="w")

        tk.Checkbutton(
            sf, text="Acquisition Details",
            variable=self.var_show_acq,
            command=self._on_show_acq_changed,
            anchor="w",
        ).grid(row=15, column=0, padx=20, pady=1, sticky="w")

        tk.Checkbutton(
            sf, text="HM Coverage",
            variable=self.var_show_hm,
            command=self._on_show_hm_changed,
            anchor="w",
        ).grid(row=16, column=0, padx=20, pady=1, sticky="w")

        tk.Checkbutton(
            sf, text="Balance Stats",
            variable=self.var_show_balance,
            command=self._on_show_balance_changed,
            anchor="w",
        ).grid(row=17, column=0, padx=20, pady=1, sticky="w")

        # ---- Export ----
        ttk.Separator(sf, orient="horizontal").grid(row=18, column=0, padx=12, pady=(14, 0), sticky="ew")

        self.export_btn = ttk.Button(
            sf,
            text="Export Party",
            command=self._export_party,
            state="disabled",
        )
        self.export_btn.grid(row=19, column=0, padx=20, pady=(12, 0), sticky="ew")

        # ---- Copyright (pinned to bottom) ----
        self._sidebar_footer = tk.Frame(sf)
        footer = self._sidebar_footer
        footer.grid(row=99, column=0, padx=20, pady=16, sticky="sw")
        sf.grid_rowconfigure(99, weight=1)

        tk.Label(footer, text="© 2026 Derek Andersen", fg=C_MUTED,
                 justify="left").grid(row=0, column=0, columnspan=3, sticky="w")

        links = tk.Frame(footer)
        links.grid(row=1, column=0, sticky="w")

        def link_label(parent, text, url):
            lbl = tk.Label(parent, text=text, fg=C_LINK, cursor="hand2")
            lbl.bind("<Button-1>", lambda e: webbrowser.open(url))
            lbl.bind("<Enter>", lambda e: lbl.configure(fg="#8b008b"))
            lbl.bind("<Leave>", lambda e: lbl.configure(fg=C_LINK))
            return lbl

        link_label(links, "Ko-fi", "https://ko-fi.com/dechrissen").pack(side="left")
        tk.Label(links, text="·", fg=C_MUTED).pack(side="left", padx=(4, 4))
        link_label(links, "GitHub", "https://github.com/Dechrissen/dexelect").pack(side="left")
        tk.Label(links, text="·", fg=C_MUTED).pack(side="left", padx=(4, 4))
        link_label(links, "Report a Bug",
                   "https://github.com/Dechrissen/dexelect/issues/new?template=bug_gui.yml").pack(side="left")

        # Shortest form of the sprite/IP disclaimer; the full text lives in the
        # Legal section of help.md, so clicking this line opens Help scrolled
        # there. Stays muted (not C_LINK) to keep it visually quieter than the
        # Ko-fi/GitHub links; the hand cursor + hover color signal it's clickable.
        legal = tk.Label(footer, text="Dexelect is an unofficial fan project",
                         fg=C_MUTED, font=self.font_small, cursor="hand2",
                         justify="left")
        legal.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        legal.bind("<Button-1>", lambda e: self._show_help(scroll_to="Legal"))
        legal.bind("<Enter>", lambda e: legal.configure(fg=C_LINK))
        legal.bind("<Leave>", lambda e: legal.configure(fg=C_MUTED))


    # =========================================================================
    # MAIN AREA (tabbed)
    # =========================================================================

    def _build_main(self):
        """
        Right panel: a ttk.Notebook with three tabs:
          - Generate : generate button, status, party results
          - Spheres  : sphere mode selector + inline sphere map
          - Config   : all options from the active config YAML
        """
        # ---- Header row: Help button in its own top-right corner ----
        header = tk.Frame(self.main_frame)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Button(header, text="Help", command=self._toggle_help).pack(
            side="right", padx=(0, 10), pady=(8, 6))
        self._help_overlay = None

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self._tab_frames = {}
        for name in ("Generate", "Spheres", "Config"):
            frame = tk.Frame(self.notebook)
            self.notebook.add(frame, text=name)
            self._tab_frames[name] = frame

        self._build_gen_tab(self._tab_frames["Generate"])
        self._build_spheres_tab(self._tab_frames["Spheres"])
        self._build_config_tab(self._tab_frames["Config"])

        # Config controls exist only while their tab is selected (see
        # _sync_config_tab); react to tab switches.
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._sync_config_tab())

    def _switch_tab(self, name: str):
        self.notebook.select(self._tab_frames[name])


    # =========================================================================
    # HELP OVERLAY
    # =========================================================================

    def _toggle_help(self):
        if self._help_overlay and self._help_overlay.winfo_exists():
            self._close_help()
        else:
            self._show_help()

    def _show_help(self, scroll_to=None):
        """Open help as a native transient dialog: real titlebar, real OS close
        button, and tk.Text's built-in mousewheel scrolling — no overlay, no
        custom title bar or close glyph.

        scroll_to: optional heading text (e.g. "Legal"); the dialog opens
        scrolled so that section sits at the top."""
        self._close_help()
        win = tk.Toplevel(self)
        win.title("Dexelect Help")
        win.transient(self)
        w = max(480, int(self.winfo_width() * 0.7))
        h = max(400, int(self.winfo_height() * 0.8))
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self._help_overlay = win

        text = tk.Text(
            win, wrap="word",
            padx=20, pady=14,
            relief="flat", highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        self._render_help_text(text)
        text.configure(state="disabled")

        if scroll_to:
            # Headings render as their own line, so anchor on a whole-line match
            # to avoid hitting the same word inside body text.
            idx = text.search(rf"^{scroll_to}$", "1.0", stopindex="end", regexp=True)
            if idx:
                text.yview(idx)

        win.bind("<Escape>", lambda e: self._close_help())
        win.focus_set()

    def _close_help(self):
        if self._help_overlay:
            try:
                self._help_overlay.destroy()
            except tk.TclError:
                pass
            self._help_overlay = None

    def _render_help_text(self, text_widget):
        text_widget.tag_configure("h1",  font=self.font_h1, spacing1=2,  spacing3=8)
        text_widget.tag_configure("h2",  font=self.font_h2, spacing1=12, spacing3=2)
        text_widget.tag_configure("h3",  font=self.font_bold, spacing1=8, spacing3=1)
        text_widget.tag_configure("body", foreground="gray25")

        try:
            path = resource_path("ui/gui/help.md")
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            text_widget.insert("end", "Help file not found.", "body")
            return

        for line in lines:
            line = line.rstrip("\n")
            if line.startswith("### "):
                text_widget.insert("end", line[4:] + "\n", "h3")
            elif line.startswith("## "):
                text_widget.insert("end", line[3:] + "\n", "h2")
            elif line.startswith("# "):
                text_widget.insert("end", line[2:] + "\n", "h1")
            elif line == "":
                text_widget.insert("end", "\n", "body")
            else:
                text_widget.insert("end", line + "\n", "body")


    # =========================================================================
    # SPHERES TAB
    # =========================================================================

    def _render_sphere_map(self, text_widget):
        text_widget.tag_configure("s_on",     font=self.font_bold, spacing1=8, spacing3=3)
        text_widget.tag_configure("s_off",    font=self.font_bold, foreground=C_DIM, spacing1=8, spacing3=3)
        text_widget.tag_configure("map_on")
        text_widget.tag_configure("map_off",  foreground=C_DIM)
        text_widget.tag_configure("item_on")
        text_widget.tag_configure("item_off", foreground=C_DIM)

        spheres     = self.meta_data.get("spheres", [])
        modes       = self.meta_data.get("sphere_generation_modes", {})
        sel_mode    = self.meta_data.get("selected_sphere_mode", "")
        active_nums = set(modes.get(sel_mode, []))
        new_species_counts = count_new_species_per_sphere(
            self.all_pools, self.obtainable_pokemon, self.all_pokemon)

        for sphere in spheres:
            num    = sphere["sphereNum"]
            active = num in active_nums
            sh = "s_on"    if active else "s_off"
            mh = "map_on"  if active else "map_off"
            ih = "item_on" if active else "item_off"
            status = "Enabled" if active else "Disabled"
            new_count = new_species_counts.get(num, 0)
            text_widget.insert("end", f"Sphere {num} (new species: {new_count}) – {status}\n", sh)
            for entry in sphere.get("contents", []):
                name  = entry["name"]
                etype = entry["type"]
                if etype == "map":
                    text_widget.insert("end", f"      · {name}\n", mh)
                else:
                    label = "item" if etype == "item" else "unlock"
                    text_widget.insert("end", f"      · {name}  [{label}]\n", ih)

    def _build_spheres_tab(self, parent):
        """
        Spheres tab: sphere mode selector (auto-saves on change) + inline sphere map.
        """
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        top = tk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))

        game_row = tk.Frame(top)
        game_row.pack(side="top", anchor="w", pady=(0, 8))
        tk.Label(game_row, text="Current game:").pack(side="left")
        self._spheres_game_label = tk.Label(game_row, text="")
        self._spheres_game_label.pack(side="left", padx=(6, 0))

        mode_row = tk.Frame(top)
        mode_row.pack(side="top", anchor="w")
        tk.Label(mode_row, text="Sphere mode").pack(side="left")
        tip = self.tooltips.get("sphere_mode", "")
        if tip:
            icon = _icon_canvas(mode_row)
            icon.pack(side="left", padx=(5, 12), anchor="center")
            _Tooltip(icon, tip)
        self._spheres_mode_menu = tk.OptionMenu(mode_row, self.var_sphere_mode, "")
        self._spheres_mode_menu.configure(anchor="w")
        self._spheres_mode_menu.pack(side="left")

        ttk.Separator(parent, orient="horizontal").grid(row=1, column=0, sticky="ew")

        map_frame = tk.Frame(parent)
        map_frame.grid(row=2, column=0, sticky="nsew")

        self._spheres_text = tk.Text(
            map_frame, wrap="word", width=80, height=20,
            padx=20, pady=14,
            relief="flat", highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(map_frame, command=self._spheres_text.yview)
        self._spheres_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._spheres_text.pack(side="left", fill="both", expand=True)

        SCROLL_LINES = 3

        def _on_spheres_scroll(event):
            t = self._spheres_text
            if event.num == 4:
                t.yview_scroll(-SCROLL_LINES, "units")
            elif event.num == 5:
                t.yview_scroll(SCROLL_LINES, "units")
            else:
                t.yview_scroll(int(-event.delta / 120) * SCROLL_LINES, "units")
            return "break"

        def _enable_spheres_scroll(e=None):
            self.bind_all("<MouseWheel>", _on_spheres_scroll)
            self.bind_all("<Button-4>",   _on_spheres_scroll)
            self.bind_all("<Button-5>",   _on_spheres_scroll)

        def _disable_spheres_scroll(e=None):
            mx, my = map_frame.winfo_rootx(), map_frame.winfo_rooty()
            if (mx <= self.winfo_pointerx() < mx + map_frame.winfo_width() and
                    my <= self.winfo_pointery() < my + map_frame.winfo_height()):
                return
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")

        # Widget-level bindings prevent native double-scroll on Windows.
        self._spheres_text.bind("<MouseWheel>", _on_spheres_scroll)
        self._spheres_text.bind("<Button-4>",   _on_spheres_scroll)
        self._spheres_text.bind("<Button-5>",   _on_spheres_scroll)
        # Container Enter/Leave activates bind_all so scrollbar hover also scrolls.
        self._spheres_text.bind("<Enter>", _enable_spheres_scroll)
        self._spheres_text.bind("<Leave>", _disable_spheres_scroll)
        scrollbar.bind("<Enter>",          _enable_spheres_scroll)
        scrollbar.bind("<Leave>",          _disable_spheres_scroll)

    def _refresh_spheres_tab(self):
        """Update the game label, sphere mode dropdown options, and re-render the sphere map."""
        self._spheres_game_label.configure(text=self.var_game.get())
        modes = list(self.meta_data.get("sphere_generation_modes", {}).keys())
        current = self.meta_data.get("selected_sphere_mode", modes[0] if modes else "")
        self.var_sphere_mode.set(current)
        suggested = self.meta_data.get("suggested_sphere_mode", "")
        menu = self._spheres_mode_menu["menu"]
        menu.delete(0, "end")
        for m in (modes if modes else [current]):
            label = f"{m}  (suggested)" if m == suggested else m
            menu.add_command(label=label, command=lambda v=m: self._on_sphere_mode_selected(v))
        self._rerender_sphere_map()

    def _rerender_sphere_map(self):
        text = self._spheres_text
        top, _ = text.yview()
        text.configure(state="normal")
        text.delete("1.0", "end")
        self._render_sphere_map(text)
        text.configure(state="disabled")
        text.after_idle(lambda: text.yview_moveto(top))

    def _on_sphere_mode_selected(self, mode: str):
        self.var_sphere_mode.set(mode)
        self._on_sphere_mode_changed(mode)

    def _on_sphere_mode_changed(self, mode: str):
        """Auto-save sphere mode to game_settings.yaml and refresh the sphere map."""
        self._patch_game_setting(self.var_game.get(), mode)
        self.meta_data["selected_sphere_mode"] = mode
        self._rerender_sphere_map()


    # =========================================================================
    # GENERATE TAB
    # =========================================================================

    def _build_gen_tab(self, parent):
        """
        Generate tab layout:
          - Top bar: Generate button + status label
          - 3 × 2 grid of party-member cards
          - HM coverage strip
          - Stats strip below the grid
        All content lives in a canvas-backed inner frame so the stats and HM
        strips are always reachable via scroll when the window is too short.
        """
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=0)
        parent.grid_rowconfigure(0, weight=1)

        # ---- Canvas + scrollbar ----
        canvas = tk.Canvas(parent, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas.configure(yscrollincrement=1)

        scrollbar = tk.Scrollbar(parent, command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Auto-hide: only show scrollbar when content exceeds canvas height.
        # Touch grid state only on actual changes (grid()/grid_remove() trigger
        # a relayout pass even when redundant, and yscrollcommand fires a lot).
        def _yscroll_set(first, last):
            hidden = float(first) <= 0.0 and float(last) >= 1.0
            if hidden != self._gen_scrollbar_hidden:
                self._gen_scrollbar_hidden = hidden
                if hidden:
                    scrollbar.grid_remove()
                else:
                    scrollbar.grid()
            scrollbar.set(first, last)
        canvas.configure(yscrollcommand=_yscroll_set)

        gen_inner = tk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=gen_inner, anchor="nw")
        gen_inner.grid_columnconfigure(0, weight=1)
        gen_inner.grid_rowconfigure(2, weight=1)
        self._gen_inner  = gen_inner
        self._gen_canvas = canvas

        # Cross-platform scroll — identical pattern to config tab
        SCROLL_PX = 60

        def _on_gen_scroll(event):
            if event.num == 4:
                canvas.yview_scroll(-SCROLL_PX, "units")
            elif event.num == 5:
                canvas.yview_scroll(SCROLL_PX, "units")
            else:
                canvas.yview_scroll(int(-event.delta / 120) * SCROLL_PX, "units")

        def _enable_gen_scroll(e=None):
            self.bind_all("<MouseWheel>", _on_gen_scroll)
            self.bind_all("<Button-4>",   _on_gen_scroll)
            self.bind_all("<Button-5>",   _on_gen_scroll)

        def _disable_gen_scroll(e=None):
            # Only truly disable when cursor has left the tab area (canvas + scrollbar).
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            if (px <= self.winfo_pointerx() < px + parent.winfo_width() and
                    py <= self.winfo_pointery() < py + parent.winfo_height()):
                return
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")

        canvas.bind("<Enter>",    _enable_gen_scroll)
        canvas.bind("<Leave>",    _disable_gen_scroll)
        scrollbar.bind("<Enter>", _enable_gen_scroll)
        scrollbar.bind("<Leave>", _disable_gen_scroll)

        def _refit_gen_height():
            """Re-evaluate gen_inner height when content or canvas size changes."""
            gen_inner.update_idletasks()
            content_h = gen_inner.winfo_reqheight()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            new_h = max(ch, content_h)
            canvas.itemconfig(inner_id, height=new_h)
            canvas.configure(scrollregion=(0, 0, cw, new_h))
        self._refit_gen_height = _refit_gen_height

        def _sync_gen_canvas():
            canvas.itemconfig(inner_id, width=canvas.winfo_width())
            _refit_gen_height()

        def _on_gen_canvas_configure(event):
            # Track width immediately (cheap, keeps content visually in sync
            # while dragging); defer the reqheight/scrollregion recompute until
            # resizing activity settles.
            canvas.itemconfig(inner_id, width=event.width)
            self._debounce("_gen_canvas_resize_job", 80, _sync_gen_canvas)

        canvas.bind("<Configure>", _on_gen_canvas_configure)

        # ---- Top bar ----
        top_bar = tk.Frame(gen_inner)
        top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        top_bar.grid_columnconfigure(1, weight=1)

        self.generate_btn = ttk.Button(
            top_bar,
            text="Generate Party",
            command=self._run_generation,
        )
        self.generate_btn.grid(row=0, column=0, padx=(2, 16))

        self.status_label = tk.Label(
            top_bar,
            text="Press Generate Party or Enter to begin.",
            fg=C_MUTED,
            anchor="w",
        )
        self.status_label.grid(row=0, column=1, sticky="w")

        # ---- Warning strip ----
        self.warning_strip = tk.Frame(gen_inner)
        self.warning_strip.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        tk.Label(
            self.warning_strip,
            text="Party sizes under 6 may affect the likelihood of satisfying HM coverage and balancing requirements.",
            fg=C_NOTICE,
            anchor="w",
        ).pack(side="left")
        self.warning_strip.grid_remove()

        # ---- 3 × 2 card grid ----
        cards_outer = tk.Frame(gen_inner)
        cards_outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 4))
        cards_outer.grid_columnconfigure(0, weight=1, uniform="cards")
        cards_outer.grid_columnconfigure(1, weight=1, uniform="cards")
        for r in range(3):
            cards_outer.grid_rowconfigure(r, weight=1)

        self._cards_outer = cards_outer
        self.party_cards = []
        for r in range(3):
            for c in range(2):
                card = self._make_card(cards_outer)
                card["frame"].grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
                self.party_cards.append(card)

        # ---- HM coverage strip ----
        self.hm_strip_frame = tk.Frame(gen_inner)
        self.hm_strip_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 4))

        # ---- Stats strip ----
        stats_frame = tk.Frame(gen_inner)
        stats_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.stat_labels = {}
        self._stat_blocks = []
        stats = [("lean", "Lean"), ("spread", "Spread"),
                 ("pattern", "Pattern"), ("distribution", "Distribution")]
        # Blocks sit in even columns; the odd columns between them are
        # equal-width spacers, so the blocks spread evenly with window size
        # while Lean/Distribution stay flush with the HM strip's 16 px
        # content padding above. The strip's natural width (edge padding +
        # 12 px minimum gaps) doubles as the no-wrap threshold in
        # _update_stats_layout, so the staged default window never wraps.
        for i, (key, label) in enumerate(stats):
            if i:
                stats_frame.grid_columnconfigure(2 * i - 1, weight=1, uniform="statgap", minsize=12)
            block = tk.Frame(stats_frame)
            if i == 0:
                block.grid(row=0, column=0, padx=(16, 0), pady=8)
            elif i == len(stats) - 1:
                block.grid(row=0, column=2 * i, padx=(0, 16), pady=8)
            else:
                block.grid(row=0, column=2 * i, pady=8)
            hdr = tk.Frame(block)
            hdr.grid(row=0, column=0, sticky="w")
            tk.Label(hdr, text=label, font=self.font_bold, anchor="w").pack(side="left")
            tip = self.tooltips.get(key, "")
            if tip:
                icon = _icon_canvas(hdr)
                icon.pack(side="left", padx=(5, 0), anchor="center")
                _Tooltip(icon, tip)
            if key == "distribution":
                smap_btn = tk.Label(hdr, text="\N{TRIGRAM FOR HEAVEN}", fg="gray35", cursor="hand2", bd=0)
                smap_btn.pack(side="left", padx=(5, 0), anchor="center")
                smap_btn.bind("<Button-1>", lambda e: self._switch_tab("Spheres"))
                smap_btn.bind("<Enter>", lambda e: smap_btn.configure(fg="black"))
                smap_btn.bind("<Leave>", lambda e: smap_btn.configure(fg="gray35"))
                val = tk.Label(block, text="—", font=self.font_fixed, fg=C_MUTED, anchor="w")
            else:
                val = tk.Label(block, text="—", font=self.font_fixed, fg=C_MUTED, anchor="w", width=16)
            val.grid(row=1, column=0, sticky="w")
            self.stat_labels[key] = val
            self._stat_blocks.append(block)

        self._stats_frame   = stats_frame
        self._stats_wrapped = False
        stats_frame.bind("<Configure>", lambda e: self._debounce("_stats_resize_job", 80, self._update_stats_layout))


    # =========================================================================
    # CARD HELPERS
    # =========================================================================

    def _make_card(self, parent) -> dict:
        """Build one empty party-member card; return updateable widget refs."""
        frame = tk.Frame(parent, relief="groove", bd=2)
        frame.grid_columnconfigure(0, weight=0, minsize=SPRITE_MAX + 16)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=0)   # name
        frame.grid_rowconfigure(1, weight=0)   # types
        frame.grid_rowconfigure(2, weight=0)   # bst
        frame.grid_rowconfigure(3, weight=1, minsize=30)  # spacer — keeps acq row below sprite bottom
        frame.grid_rowconfigure(4, weight=0)   # separator
        frame.grid_rowconfigure(5, weight=0)   # acq (full width)

        sprite = tk.Label(frame, bd=0)
        sprite.grid(row=0, column=0, rowspan=4, padx=(8, 8), pady=(10, 0), sticky="nw")

        name_lbl = tk.Label(frame, text="", font=self.font_bold, anchor="w")
        name_lbl.grid(row=0, column=1, padx=(0, 10), pady=(6, 2), sticky="nw")
        default_fg = name_lbl.cget("fg")

        empty_lbl = tk.Label(frame, text="Empty", fg=C_DIM)
        empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        empty_lbl.lift()

        types_frame = tk.Frame(frame)
        types_frame.grid(row=1, column=1, padx=(0, 10), pady=(0, 2), sticky="nw")

        bst_lbl = tk.Label(frame, text="", fg=C_MUTED, anchor="nw")
        bst_lbl.grid(row=2, column=1, padx=(0, 10), pady=(0, 0), sticky="nw")

        sep = ttk.Separator(frame, orient="horizontal")
        sep.grid(row=4, column=0, columnspan=2, padx=10, pady=(6, 0), sticky="ew")
        sep.grid_remove()

        acq_lbl = tk.Label(frame, text="", anchor="nw", justify="left")
        acq_lbl.grid(row=5, column=0, columnspan=2, padx=(14, 10), pady=(4, 8), sticky="nw")

        return {"frame": frame, "name": name_lbl, "acq": acq_lbl, "sep": sep, "sprite": sprite,
                "types_frame": types_frame, "bst": bst_lbl, "empty_lbl": empty_lbl,
                "default_fg": default_fg}

    def _build_hm_labels(self):
        """Rebuild HM coverage labels for the current game. Called on startup and game change."""
        if self._hm_strip_inner:
            self._hm_strip_inner.destroy()
        inner = tk.Frame(self.hm_strip_frame)
        inner.pack(fill="x", padx=16, pady=8)
        self._hm_strip_inner = inner
        self.hm_labels = {}
        hdr = tk.Frame(inner)
        hdr.pack(side="top", anchor="w", pady=(0, 4))
        tk.Label(hdr, text="HM Coverage", font=self.font_bold).pack(side="left")
        tip = self.tooltips.get("hm_coverage", "")
        if tip:
            icon = _icon_canvas(hdr)
            icon.pack(side="left", padx=(5, 0), anchor="center")
            _Tooltip(icon, tip)

        # Individual HM labels (shown when toggle on); labels are positioned via
        # place() in _reflow_hm_list so they wrap to a new row when space is tight.
        hm_list = tk.Frame(inner)
        hm_list.pack_propagate(False)
        self._hm_list_frame = hm_list
        for hm_name in self.config_data.get("ensure_hm_coverage", {}):
            lbl = tk.Label(hm_list, text=hm_name, font=self.font_fixed, fg=C_DIM)
            self.hm_labels[hm_name] = lbl
        hm_list.bind("<Configure>", lambda e: self._debounce("_hm_resize_job", 80, self._reflow_hm_list))

        # Single dash (shown when toggle off or no party generated yet)
        self._hm_dash_label = tk.Label(inner, text="—", font=self.font_fixed, fg=C_MUTED)
        self._refresh_hm_labels(party_coverage=None)

    def _reflow_hm_list(self):
        """Position HM labels in a wrapping flow; adjusts frame height to fit all rows."""
        frame = self._hm_list_frame
        if not frame or not self.hm_labels:
            return
        frame.update_idletasks()
        available = frame.winfo_width()
        if available <= 1:
            return
        PAD_X, PAD_Y = 12, 2
        x = y = row_h = 0
        for lbl in self.hm_labels.values():
            lbl.update_idletasks()
            w, h = lbl.winfo_reqwidth(), lbl.winfo_reqheight()
            if x + w > available and x > 0:
                x = 0
                y += row_h + PAD_Y
                row_h = 0
            lbl.place(x=x, y=y)
            x += w + PAD_X
            row_h = max(row_h, h)
        new_h = max(1, y + row_h)
        if frame.winfo_height() != new_h:
            frame.configure(height=new_h)
            self.after_idle(self._refit_gen_height)

    def _refresh_hm_labels(self, party_coverage):
        """Update HM strip based on toggle state and optional coverage set.

        party_coverage: set of covered HM names, or None (no party generated yet).
        """
        if not self.var_show_hm.get() or party_coverage is None:
            if self._hm_list_frame:
                self._hm_list_frame.pack_forget()
            if self._hm_dash_label:
                self._hm_dash_label.pack(side="top", anchor="w")
            return
        if self._hm_dash_label:
            self._hm_dash_label.pack_forget()
        if self._hm_list_frame:
            self._hm_list_frame.pack(side="top", fill="x")
            self._reflow_hm_list()
        for hm_name, lbl in self.hm_labels.items():
            lbl.configure(fg=C_COVERED if hm_name in party_coverage else C_DIM)

    def _clear_cards(self):
        """Reset all party cards to their empty placeholder state."""
        for i, card in enumerate(self.party_cards):
            card["name"].configure(text="", fg=card["default_fg"], cursor="")
            card["name"].unbind("<Button-1>")
            card["name"].unbind("<Enter>")
            card["name"].unbind("<Leave>")
            card["empty_lbl"].place(relx=0.5, rely=0.5, anchor="center")
            card["empty_lbl"].lift()
            card["acq"].configure(text="")
            card["sep"].grid_remove()
            card["bst"].configure(text="")
            card["sprite"].configure(image="", cursor="")
            self._sprite_images[i] = None
            card["sprite"].unbind("<Button-1>")
            for w in card["types_frame"].winfo_children():
                w.destroy()
        for lbl in self.stat_labels.values():
            lbl.configure(text="—", fg=C_MUTED)
        self._refresh_hm_labels(party_coverage=None)
        self.last_party_blob = None
        self.export_btn.configure(state="disabled")
        self.after_idle(self._refit_gen_height)

    def _update_stats_layout(self):
        """Wrap the Distribution block to a second row when there isn't enough horizontal room."""
        sf = self._stats_frame
        sf.update_idletasks()
        available = sf.winfo_width()
        if available <= 1:
            return
        blocks = self._stat_blocks
        # 16 px edge padding each side + 12 px minimum gap between blocks:
        # exactly the strip's natural (staged) width, so the default window
        # size never wraps.
        need = sum(b.winfo_reqwidth() for b in blocks) + 32 + 12 * (len(blocks) - 1)
        dist = blocks[-1]
        last_gap_col = 2 * len(blocks) - 3  # spacer between Pattern and Distribution
        if available < need and not self._stats_wrapped:
            self._stats_wrapped = True
            sf.grid_columnconfigure(last_gap_col, weight=0, uniform="")
            dist.grid(row=1, column=0, columnspan=2 * len(blocks) - 1, padx=0, pady=(0, 8))
            self.after_idle(self._refit_gen_height)
        elif available >= need and self._stats_wrapped:
            self._stats_wrapped = False
            sf.grid_columnconfigure(last_gap_col, weight=1, uniform="statgap")
            dist.grid(row=0, column=2 * len(blocks) - 2, columnspan=1, padx=(0, 16), pady=8)
            self.after_idle(self._refit_gen_height)

    def _render_type_badges(self, types_frame, types: list[str]):
        """Render colored type badges (swatch glyph + name) into the given frame.

        One label per type: the swatch is a text glyph in the same color as the
        name, which halves the party's badge widget count vs a frame+swatch+label
        trio (widget count measurably affects Windows window-move smoothness).
        """
        for w in types_frame.winfo_children():
            w.destroy()
        for col, type_name in enumerate(types):
            key = type_name.lower()
            limit = _BADGE_LUM_EXCEPTIONS.get(key, _BADGE_LUM_LIMIT)
            color = _badge_color(TYPE_COLORS.get(key, C_MUTED), limit)
            tk.Label(types_frame, text=f"\u25a0 {type_name.capitalize()}",
                     fg=color, anchor="w").grid(row=0, column=col, padx=(0, 6))


    # =========================================================================
    # CONFIG TAB
    # =========================================================================

    def _build_config_tab(self, parent):
        """
        Config tab: all options from the active config YAML, auto-saved on change.
        Content lives in a canvas-backed scrollable frame (the standard Tk
        pattern for scrolling a frame).
        """
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        canvas = tk.Canvas(parent, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0, sticky="nsew", pady=(8, 0))
        canvas.configure(yscrollincrement=1)
        scrollbar = tk.Scrollbar(parent, command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        self._config_canvas = canvas
        self._config_inner  = inner

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_config_canvas_configure(event):
            canvas.itemconfig(inner_id, width=event.width)
            self._on_config_note_resize(event)
        canvas.bind("<Configure>", _on_config_canvas_configure)

        # Mouse-wheel scrolling: activate globally while cursor is inside the tab.
        SCROLL_PX = 60

        def _on_config_scroll(event):
            if event.num == 4:                        # Linux scroll-up
                canvas.yview_scroll(-SCROLL_PX, "units")
            elif event.num == 5:                      # Linux scroll-down
                canvas.yview_scroll(SCROLL_PX, "units")
            else:                                     # Windows <MouseWheel> (delta=±120/notch)
                canvas.yview_scroll(int(-event.delta / 120) * SCROLL_PX, "units")

        def _on_config_scroll_enter(e):
            self.bind_all("<MouseWheel>", _on_config_scroll)
            self.bind_all("<Button-4>",   _on_config_scroll)
            self.bind_all("<Button-5>",   _on_config_scroll)

        def _on_config_scroll_leave(e):
            sx, sy = parent.winfo_rootx(), parent.winfo_rooty()
            if (sx <= self.winfo_pointerx() < sx + parent.winfo_width() and
                    sy <= self.winfo_pointery() < sy + parent.winfo_height()):
                return
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")

        canvas.bind("<Enter>",    _on_config_scroll_enter)
        canvas.bind("<Leave>",    _on_config_scroll_leave)
        scrollbar.bind("<Enter>", _on_config_scroll_enter)
        scrollbar.bind("<Leave>", _on_config_scroll_leave)

        ttk.Separator(parent, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew")

        # ---- Bottom bar ----
        save_bar = tk.Frame(parent)
        save_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 10))
        save_bar.grid_columnconfigure(0, weight=1)

        self.config_status_label = tk.Label(save_bar, text="", fg=C_MUTED, anchor="w")
        self.config_status_label.grid(row=0, column=0, sticky="w")

        preset_btn = ttk.Menubutton(save_bar, text="Load Preset", direction="above")
        self._preset_menu = tk.Menu(preset_btn, tearoff=0,
                                    postcommand=self._rebuild_preset_menu)
        preset_btn["menu"] = self._preset_menu
        preset_btn.grid(row=0, column=1, padx=(0, 8))

        ttk.Button(
            save_bar,
            text="Restore Defaults",
            command=self._on_load_defaults,
        ).grid(row=0, column=2, padx=(0, 12))

        self.config_file_label = tk.Label(save_bar, text="", font=self.font_fixed,
                                          fg=C_MUTED, anchor="e")
        self.config_file_label.grid(row=0, column=3, sticky="e", padx=(0, 4))

    def _sync_config_tab(self):
        """Build the Config controls only while the Config tab is selected; tear
        them down when leaving it.

        Bisected on Windows (2026-07-08): the pane's ~150 form widgets measurably
        drag window moves even while unmapped in the notebook — the trail
        disappears when they don't exist. Building on tab entry costs a few
        tens of ms once; dragging stays smooth everywhere else.
        """
        selected = self.notebook.select() == str(self._tab_frames["Config"])
        if selected and not self._config_built:
            self._populate_config_controls()
            self._config_built = True
        elif not selected and self._config_built:
            self._teardown_config_tab()

    def _teardown_config_tab(self):
        for w in self._config_inner.winfo_children():
            w.destroy()
        self.config_vars.clear()
        self._config_note_label = None
        self._config_built = False

    def _populate_config_controls(self):
        """
        Build (or rebuild) all config widgets inside the scrollable config frame.
        Called by _sync_config_tab when the Config tab is entered.
        """
        self._config_loading = True
        inner = self._config_inner

        game = self.var_game.get()
        config_path = self.mappings[game]["config"]
        self.config_file_label.configure(text=os.path.basename(config_path))

        for widget in inner.winfo_children():
            widget.destroy()
        self.config_vars.clear()

        cd = self.config_data
        row = 0

        def label_with_tip(key, text, font=None, fg=None):
            """Return a frame with the label text and a circle-i icon tacked on if a tooltip exists."""
            f = tk.Frame(inner)
            kwargs = {}
            if font is not None:
                kwargs["font"] = font
            if fg is not None:
                kwargs["fg"] = fg
            tk.Label(f, text=text, anchor="w", **kwargs).pack(side="left")
            tip = self.tooltips.get(key, "")
            if tip:
                icon = _icon_canvas(f)
                icon.pack(side="left", padx=(5, 0), anchor="center")
                _Tooltip(icon, tip)
            return f

        def section_label(text):
            nonlocal row
            tk.Label(inner, text=text, font=self.font_h2, anchor="w").grid(
                row=row, column=0, columnspan=2, padx=20, pady=(20, 4), sticky="w")
            row += 1
            ttk.Separator(inner, orient="horizontal").grid(
                row=row, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="ew")
            row += 1

        def bool_row(key, label):
            nonlocal row
            var = tk.BooleanVar(value=bool(cd.get(key, False)))
            var.trace_add("write", lambda *_: self._autosave_config())
            self.config_vars[key] = var
            f = tk.Frame(inner)
            tk.Checkbutton(f, text=label, variable=var).pack(side="left")
            tip = self.tooltips.get(key, "")
            if tip:
                icon = _icon_canvas(f)
                icon.pack(side="left", padx=(5, 0), anchor="center")
                _Tooltip(icon, tip)
            f.grid(row=row, column=0, columnspan=2, padx=28, pady=2, sticky="w")
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
            label_with_tip(key, label).grid(row=row, column=0, padx=28, pady=4, sticky="w")
            entry = tk.Entry(inner, textvariable=var, width=10, font=self.font_fixed)
            entry.grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            entry.bind("<FocusOut>", lambda e: self._autosave_config())
            entry.bind("<Return>",   lambda e: self._autosave_config())
            row += 1

        def multi_check_row(key, label, label_map=None):
            """
            List config key. Config format:
              key:
                value: [balanced, late_game_heavy]
                options: [balanced, early_game_heavy, late_game_heavy]
            label_map: optional dict mapping option values to display strings.
            """
            nonlocal row
            field = cd.get(key, {}) or {}
            current_values = field.get("value", []) or []
            options = field.get("options", []) or []
            label_with_tip(key, label).grid(row=row, column=0, columnspan=2, padx=28, pady=(6, 2), sticky="w")
            row += 1
            var_dict = {"__list__": True}  # sentinel: _autosave_config writes value as a plain list
            for option in options:
                var = tk.BooleanVar(value=(option in current_values))
                var.trace_add("write", lambda *_: self._autosave_config())
                var_dict[option] = var
                display = label_map.get(option, str(option)) if label_map else str(option)
                tk.Checkbutton(inner, text=display, variable=var, font=self.font_fixed).grid(
                    row=row, column=0, columnspan=2, padx=44, pady=1, sticky="w")
                row += 1
            self.config_vars[key] = var_dict

        def nested_bool_row(parent_key, label, options):
            """
            Dict-of-booleans config key.
            e.g. allowed_evo_methods: {level-up: true, trade: false, ...}
            """
            nonlocal row
            current_dict = cd.get(parent_key, {}) or {}
            label_with_tip(parent_key, label).grid(row=row, column=0, columnspan=2, padx=28, pady=(6, 2), sticky="w")
            row += 1
            var_dict = {}
            for option in options:
                var = tk.BooleanVar(value=bool(current_dict.get(option, False)))
                var.trace_add("write", lambda *_: self._autosave_config())
                var_dict[option] = var
                tk.Checkbutton(inner, text=option, variable=var, font=self.font_fixed).grid(
                    row=row, column=0, columnspan=2, padx=44, pady=1, sticky="w")
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
            var.trace_add("write", lambda *_: self._autosave_config())
            self.config_vars[key] = var
            lbl = label_with_tip(key, label)
            lbl.grid(row=row, column=0, padx=28, pady=4, sticky="w")
            menu = tk.OptionMenu(inner, var, *(options if options else [current_val]))
            menu.configure(anchor="w")
            menu.grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            row += 1
            return lbl, menu

        def text_row(key, label, placeholder=""):
            nonlocal row
            current_val = cd.get(key, []) or []
            display_val = ", ".join(current_val) if isinstance(current_val, list) else str(current_val)
            label_with_tip(key, label).grid(row=row, column=0, padx=28, pady=4, sticky="w")
            entry = tk.Entry(inner, width=40, font=self.font_fixed)
            if display_val:
                entry.insert(0, display_val)
            entry.grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            entry.bind("<FocusOut>", lambda e: self._autosave_config())
            entry.bind("<Return>",   lambda e: self._autosave_config())
            self.config_vars[key] = entry
            row += 1

        self._config_note_label = tk.Label(
            inner,
            text="Note: Overly restrictive configuration settings may affect the likelihood of successfully generating a party. Some combinations of settings will not result in a valid party.",
            fg=C_MUTED,
            anchor="w",
            wraplength=self._config_canvas.winfo_width() or 600,
            justify="left",
        )
        self._config_note_label.grid(row=row, column=0, columnspan=2, padx=20, pady=(16, 4), sticky="w")
        row += 1

        section_label("Party Balancing")
        bool_row("require_one_sphere_one", "Require at least one Pokémon in Sphere 1")
        multi_check_row("allowed_balancing", "Allowed balancing")
        multi_check_row("allowed_spreads", "Allowed spreads")
        multi_check_row("allowed_patterns", "Allowed patterns")

        section_label("Pokémon Details")
        bool_row("force_starter",           "Force a random starter")
        bool_row("allow_not_fully_evolved", "Allow not-fully-evolved Pokémon")
        bool_row("allow_legendaries",       "Allow legendary Pokémon")
        bool_row("allow_duplicate_species", "Allow duplicate species")
        int_row("max_evo_stage", "Max evolution stage")
        int_row("bst_max", "BST maximum", nullable=True)
        int_row("bst_min", "BST minimum", nullable=True)
        text_row("species_blacklist", "Species blacklist (comma-separated Stage 1s)", placeholder="e.g. EEVEE, MR.MIME, NIDORAN_M")
        multi_check_row("generation_filter", "Generation filter (empty = no filter)",
                        label_map={1: "Gen 1 (National Dex #1–151)",
                                   2: "Gen 2 (National Dex #152–251)",
                                   3: "Gen 3 (National Dex #252–386)",
                                   4: "Gen 4 (National Dex #387–493)"})
        evo_methods = list(cd.get("allowed_evo_methods", {}).keys())
        nested_bool_row("allowed_evo_methods", "Allowed evolution methods", evo_methods)

        section_label("Type Restrictions")
        bool_row("allow_dual_type", "Allow dual-type Pokémon")
        dropdown_row("type_distribution", "Type distribution")
        pt_lbl, pt_menu = dropdown_row("prescribed_type", "Prescribed type")

        def _sync_prescribed_type(*_):
            enabled = self.config_vars["type_distribution"].get() == "all_share_one_type"
            pt_menu.configure(state="normal" if enabled else "disabled")
            pt_lbl.winfo_children()[0].configure(fg="black" if enabled else C_DIM)

        self.config_vars["type_distribution"].trace_add("write", _sync_prescribed_type)
        _sync_prescribed_type()
        multi_check_row("type_blacklist", "Type blacklist")

        section_label("Learnsets")
        hm_options = list(cd.get("ensure_hm_coverage", {}).keys())
        nested_bool_row("ensure_hm_coverage", "Required learnable HMs (in party move pool)", hm_options)

        section_label("Acquisition Methods")
        acq_options = list(cd.get("allowed_acquisition_methods", {}).keys())
        nested_bool_row("allowed_acquisition_methods", "Allowed acquisition methods", acq_options)

        self._config_loading = False


    # =========================================================================
    # POPULATE UI FROM LOADED STATE
    # =========================================================================

    def _populate_ui_from_state(self):
        """Push current loaded values into all UI controls. Called on startup and after reload."""
        gs = self.global_settings

        game_names = list(self.mappings.keys())
        self.var_game.set(gs.get("game", game_names[0]))
        self._rebuild_game_dropdown_menu(game_names)
        self.var_gen_mode.set(gs.get("generation_mode", "Progression"))
        self.var_show_acq.set(bool(gs.get("show_acquisition_details", True)))
        self.var_show_balance.set(bool(gs.get("show_balance_stats", True)))
        self.var_show_hm.set(bool(gs.get("show_hm_coverage", True)))
        self.var_party_size.set(str(gs.get("party_size", 6)))
        self._update_warning_strip()
        self._build_hm_labels()
        self._refresh_spheres_tab()

        # Rebuild the Config pane for the (possibly new) game — but only if its
        # tab is currently selected; otherwise it stays torn down until visited.
        self._teardown_config_tab()
        self._sync_config_tab()

    def _rebuild_game_dropdown_menu(self, game_names):
        """
        Rebuild the game dropdown's menu so romhack entries display a
        "(romhack)" suffix while the selected value (var_game, _on_game_changed)
        still receives the plain game name. tk.OptionMenu exposes its menu via
        the documented "menu" option, so this is plain supported API.
        """
        menu = self.game_dropdown["menu"]
        menu.delete(0, "end")

        def is_romhack(name):
            return self.mappings[name].get("romhack", False)

        for name in game_names:
            display = name + " (romhack)" if is_romhack(name) else name
            menu.add_command(label=display,
                             command=lambda v=name: self._on_game_selected(v))

    def _on_game_selected(self, name: str):
        self.var_game.set(name)
        self._on_game_changed(name)


    # =========================================================================
    # SIDEBAR EVENT HANDLERS
    # =========================================================================

    def _patch_global_setting(self, key: str, value):
        """Read global_settings.yaml, update one key, and write it back."""
        gs = read_yaml(GLOBAL_SETTINGS_PATH)
        gs[key] = value
        write_yaml(GLOBAL_SETTINGS_PATH, gs)

    def _patch_game_setting(self, game: str, sphere_mode: str):
        """Read game_settings.yaml, update the sphere mode for the given game, and write it back."""
        gs = read_yaml(GAME_SETTINGS_PATH) or {}
        gs[game] = sphere_mode
        write_yaml(GAME_SETTINGS_PATH, gs)

    def _on_game_changed(self, selected_game: str):
        self._patch_global_setting("game", selected_game)
        self._reload_data()
        self._set_status(f"Game set to {selected_game}.", color=C_SUCCESS)
        self._set_config_status(f"Config loaded for {selected_game}.")

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
        else:
            is_random = self.var_gen_mode.get() in ("Random (National Dex)", "Random (Obtainable)")
            placeholder = "N/A" if (is_random and self.var_show_balance.get()) else "—"
            for lbl in self.stat_labels.values():
                lbl.configure(text=placeholder, fg=C_MUTED)

    def _on_show_hm_changed(self):
        self._patch_global_setting("show_hm_coverage", self.var_show_hm.get())
        if self.last_party_blob is not None:
            self._populate_cards(self.last_party_blob)
        else:
            self._refresh_hm_labels(party_coverage=None)

    def _on_party_size_changed(self, value: str):
        self._patch_global_setting("party_size", int(value))
        self._update_warning_strip()

    def _update_warning_strip(self):
        if int(self.var_party_size.get()) < 6:
            self.warning_strip.grid()
        else:
            self.warning_strip.grid_remove()

    def _on_config_note_resize(self, event):
        self._debounce("_config_note_resize_job", 80, self._apply_config_note_wrap)

    def _apply_config_note_wrap(self):
        if not self._config_note_label:
            return
        try:
            width = self._config_canvas.winfo_width()
            self._config_note_label.configure(wraplength=max(200, width - 40))
        except tk.TclError:
            pass  # label was destroyed by a config-tab rebuild mid-debounce


    # =========================================================================
    # CONFIG AUTO-SAVE
    # =========================================================================

    def _autosave_config(self):
        """Write all current config_vars to disk and refresh self.config_data in memory."""
        if self._config_loading:
            return
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

                elif isinstance(var, (tk.StringVar, tk.Entry)):
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
            self._set_config_status(f"Invalid value: {e}", color=C_WARNING)
            return

        write_yaml(config_path, data)
        self.config_data = read_yaml(config_path)
        self._set_config_status("Saved.", color=C_SUCCESS)


    # =========================================================================
    # PARTY GENERATION
    # =========================================================================

    def _run_generation(self):
        """Kick off party generation in a background thread so the GUI stays responsive."""
        if self.is_generating:
            return

        self.is_generating = True
        self.generate_btn.configure(state="disabled")
        self._clear_cards()
        thread = threading.Thread(target=self._generation_worker, daemon=True)
        thread.start()
        self._animate_status(2)

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

            if gen_mode == "Random (National Dex)":
                party_blob = generate_fully_randomized_party(self.all_pokemon, n=int(self.var_party_size.get()), all_pools=self.all_pools, all_pokemon=self.all_pokemon)
            elif gen_mode == "Random (Obtainable)":
                party_blob = generate_fully_randomized_party(self.obtainable_pokemon, n=int(self.var_party_size.get()), all_pools=self.all_pools, all_pokemon=self.all_pokemon)
            else:
                party_blob = generate_final_party(
                    self.all_pools, self.all_pokemon,
                    self.config_data, self.meta_data, self.obtainable_pokemon,
                    n=int(self.var_party_size.get())
                )

            duration = time.time() - start

        except Exception as e:
            self.after(0, self._on_generation_done, None, 0, str(e))
            return

        self.after(0, self._on_generation_done, party_blob, duration, None)

    def _on_generation_done(self, party_blob, duration: float, error: str | None):
        """Called on the main thread once generation finishes."""
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="Generate Party")

        if error:
            self._set_status(f"Error: {error}", color=C_WARNING)
            return

        if party_blob is None:
            self._set_status("Could not generate a valid party. Try adjusting settings.", color=C_WARNING)
            return

        self._set_status(f"Party generated in {format_duration(duration)}.", color=C_SUCCESS)
        self.last_party_blob = party_blob
        self.export_btn.configure(state="normal")
        self._populate_cards(party_blob)
        self.after_idle(self._refit_gen_height)


    # =========================================================================
    # RESULTS RENDERING
    # =========================================================================

    def _populate_cards(self, party_blob: dict):
        """Fill the 6 party-member cards and stats strip from party_blob."""
        show_acq     = self.var_show_acq.get()
        show_balance = self.var_show_balance.get()
        is_random    = self.var_gen_mode.get() in ("Random (National Dex)", "Random (Obtainable)")

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
            card["name"].configure(text=mon_obj.name, fg=card["default_fg"])
            card["empty_lbl"].place_forget()
            url = f"https://pokemondb.net/pokedex/{int(mon_obj.nat_dex_number)}"
            card["name"].configure(cursor="hand2")
            card["name"].bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            card["name"].bind("<Enter>", lambda e, c=card: c["name"].configure(fg=C_LINK))
            card["name"].bind("<Leave>", lambda e, c=card: c["name"].configure(fg=c["default_fg"]))
            self._render_type_badges(card["types_frame"], mon_obj.types)
            card["bst"].configure(text=f"Base stat total: {mon_obj.base_stat_total}")

            sprite_path = os.path.join(sprite_dir, f"{mon_obj.nat_dex_number}.png")
            try:
                pil_img = Image.open(sprite_path)
                resized = pil_img.resize((SPRITE_MAX, SPRITE_MAX), Image.NEAREST)
                photo = ImageTk.PhotoImage(resized)
                card["sprite"].configure(image=photo, cursor="hand2")
                self._sprite_images[i] = photo
                card["sprite"].bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            except (FileNotFoundError, OSError):
                card["sprite"].configure(image="", cursor="")
                self._sprite_images[i] = None
                card["sprite"].unbind("<Button-1>")

            if show_acq and pokemon["random_pool_entry_instance"] is not None:
                prescribed    = pokemon["random_pool_entry_instance"]
                method        = prescribed["acquisition_method"]
                location      = prescribed["acquiring_location"]
                earliest_form = pokemon["earliest_form"]
                earliest_pool = pokemon["earliest_pool"]
                card["acq"].configure(
                    text=(
                        f"Acquire as: {earliest_form.name}\n"
                        f"Method: {method}\n"
                        f"Location: {location}\n"
                        f"Sphere: {earliest_pool}"
                    )
                )
                card["sep"].grid()
            elif is_random and show_acq:
                card["acq"].configure(text="N/A")
                card["sep"].grid_remove()
            else:
                card["acq"].configure(text="")
                card["sep"].grid_remove()

        party_hm_coverage = set(
            hm for m in party_blob["party_with_acquisition_data"]
            for hm in m["party_member_obj"].hm_learnset
        )
        self._refresh_hm_labels(party_coverage=party_hm_coverage)

        if not is_random and show_balance and party_blob.get("lean") is not None:
            self.stat_labels["lean"].configure(text=str(party_blob.get("lean", "—")), fg="black")
            self.stat_labels["spread"].configure(text=str(party_blob.get("spread", "—")), fg="black")
            pattern = party_blob.get("pattern")
            self.stat_labels["pattern"].configure(text=str(pattern) if pattern else "—", fg="black")
            dist = party_blob.get("party_distribution")
            if dist:
                dist_str = "  ".join(f"S{s}: {dist[s]}" for s in dist)
                self.stat_labels["distribution"].configure(text=dist_str, fg="black")
            else:
                self.stat_labels["distribution"].configure(text="—", fg=C_MUTED)
        else:
            placeholder = "N/A" if (is_random and show_balance) else "—"
            for lbl in self.stat_labels.values():
                lbl.configure(text=placeholder, fg=C_MUTED)
        self.after_idle(self._update_stats_layout)


    # =========================================================================
    # EXPORT
    # =========================================================================

    def _export_party(self):
        if self.last_party_blob is None:
            return

        game   = self.var_game.get()
        output = build_export_text(
            self.last_party_blob, game, self.var_gen_mode.get(), self.config_data, "desktop"
        )

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_export_filename(game),
            title="Export Party",
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(output)

        self._set_status(f"Party exported to {os.path.basename(path)}", color=C_SUCCESS)


    # =========================================================================
    # STATUS LABEL HELPERS
    # =========================================================================

    def _set_status(self, message: str, color: str = C_MUTED):
        """Update the status label next to the Generate button."""
        self.status_label.configure(text=message, fg=color)

    def _set_config_status(self, message: str, color: str = C_MUTED):
        """Update the status label in the Config tab."""
        self.config_status_label.configure(text=message, fg=color)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    _pools, _pokemon, _config, _meta, _mappings, _settings, _obtainable = build_all_data_structures()
    app = DexelectApp(_pools, _pokemon, _config, _meta, _mappings, _settings, _obtainable)
    app.mainloop()
