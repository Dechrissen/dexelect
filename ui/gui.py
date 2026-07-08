# Copyright 2026 Derek Andersen
# https://derekandersen.net
# https://github.com/Dechrissen/

# gui.py — CustomTkinter GUI for Dexelect
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
#   - DexelectApp class
#       - __init__          : root window, layout skeleton
#       - _build_sidebar    : left panel (game, mode, global settings)
#       - _build_main       : right panel with tabs (Generate, Config)
#       - _build_gen_tab    : Generate tab (generate button, results)
#       - _build_config_tab : Config tab (all config_genX.yaml options)
#       - Logic methods     : load_state, save_config, run_generation, etc.

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import yaml
import threading
import time
import os
import re
import sys
import webbrowser
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageTk
from core import generate_final_party, generate_fully_randomized_party, count_new_species_per_sphere
from data.loader import build_all_data_structures
from util import resource_path
from version import __version__


# =============================================================================
# THEME & APPEARANCE
# =============================================================================

from ui.gui_theme import (
    C_BG, C_PANEL, C_SIDEBAR, C_ACCENT, C_ACCENT2, C_ACCENT_DIM, C_ACCENT2_DIM,
    C_TEXT, C_MUTED, C_BTN_TEXT, C_SUCCESS, C_WARNING, C_CARD, C_CARD_BORDER, C_ENTRY_BG, C_TITLE, C_SELECT_BG, C_SELECT_FG, C_DIM,
    FONT_TITLE, FONT_APP_TITLE, FONT_HEADER, FONT_SECTION_HEADER, FONT_BTN, FONT_BODY, FONT_SMALL, FONT_MONO, FONT_MONO_HEADER,
    TYPE_COLORS,
)


# =============================================================================
# CONFIG FILE HELPERS
# =============================================================================

GLOBAL_SETTINGS_PATH = "config/global_settings.yaml"
GAME_SETTINGS_PATH   = "config/game_settings.yaml"

def read_yaml(path: str) -> dict:
    with open(resource_path(path), "r", encoding="utf-8") as f:
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
    with open(resource_path(path), "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=_InlineListDumper, default_flow_style=False, allow_unicode=True, sort_keys=False)



# =============================================================================
# TOOLTIP
# =============================================================================

TOOLTIPS_PATH = "ui/tooltips.yaml"

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
        tip = tk.Frame(root, bg=C_ACCENT2, highlightthickness=1,
                       highlightbackground=C_ACCENT)
        tk.Label(
            tip, text=self._text, justify="left",
            bg=C_ACCENT2, fg=C_TEXT,
            font=("Roboto", 11),
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


def _circle_glyph_image(glyph: str, color_hex: str, bg_hex: str,
                        size: int, font_size: int) -> ImageTk.PhotoImage:
    """Render a circle with a centered glyph via PIL — font-metric-independent."""
    def h(s):
        s = s.lstrip("#")
        return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))
    img  = Image.new("RGB", (size, size), h(bg_hex))
    draw = ImageDraw.Draw(img)
    draw.ellipse([1, 1, size - 2, size - 2], outline=h(color_hex), width=1)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), glyph, font=font)
    x = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), glyph, fill=h(color_hex), font=font)
    return ImageTk.PhotoImage(img)


def _icon_canvas(parent, bg=C_PANEL):
    """Return a tk.Label with a PIL-rendered circle-i icon."""
    img = _circle_glyph_image("i", C_MUTED, bg, size=15, font_size=9)
    lbl = tk.Label(parent, image=img, bg=bg, cursor="question_arrow", bd=0)
    lbl._img = img  # prevent GC
    return lbl


def _circle_q_image(color_hex: str, bg_hex: str, size: int = 20) -> ImageTk.PhotoImage:
    return _circle_glyph_image("?", color_hex, bg_hex, size=size, font_size=11)


def _sphere_icon_image(color_hex: str, bg_hex: str, size: int = 15) -> ImageTk.PhotoImage:
    """Render a circle with three horizontal lines (list icon) via PIL."""
    def h(s):
        s = s.lstrip("#")
        return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))
    img  = Image.new("RGB", (size, size), h(bg_hex))
    draw = ImageDraw.Draw(img)
    draw.ellipse([1, 1, size - 2, size - 2], outline=h(color_hex), width=1)
    cx    = size // 2
    half  = size // 4
    for dy in (-3, 0, 3):
        y = cx + dy
        draw.line([(cx - half, y), (cx + half, y)], fill=h(color_hex), width=1)
    return ImageTk.PhotoImage(img)


# =============================================================================
# MAIN APP CLASS
# =============================================================================

SPRITE_MAX = 112  # sprite size (px) — matches original sprite dimensions

class DexelectApp(ctk.CTk):

    def __init__(self, all_pools, all_pokemon, config_data, meta_data, mappings, global_settings, obtainable_pokemon):
        # CustomTkinter polls Windows DPI-per-monitor every 100ms forever (ScalingTracker's
        # internal after() loop) to catch cross-monitor scaling changes. On Windows that polling
        # collides with the OS's modal move loop during window drags and produces visible
        # slow-motion stutter. Slowing the poll to 1s keeps per-monitor DPI awareness working
        # (just detected up to 1s later) while cutting the overhead during drags.
        ctk.ScalingTracker.update_loop_interval = 1000
        # AppearanceModeTracker is worse: it polls the OS light/dark theme every 30ms
        # forever, and on Windows each poll is a registry read via darkdetect.theme()
        # (~33 reads/sec, slower still when antivirus hooks registry access). Those
        # timer callbacks starve the modal move loop and make the window trail behind
        # the cursor during drags. This app is a fixed dark theme, so pin the mode —
        # a "user"-set mode skips the darkdetect call — and slow the now-no-op loop.
        ctk.set_appearance_mode("dark")
        ctk.AppearanceModeTracker.update_loop_interval = 1000
        super().__init__()

        # ---- Window setup ----
        self.title(f"Dexelect v{__version__}")
        self.configure(fg_color=C_BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        win_w = min(max(900,  int(sw * 0.85)), 1280)
        win_h = min(max(620,  int(sh * 0.72)), 1050)
        win_w = min(win_w, sw - 20)   # never wider than screen
        win_h = min(win_h, sh - 60)   # leave room for taskbar/decorations
        x = (sw - win_w) // 2
        y = max(0, (sh - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

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

        # Config tab variables — populated dynamically in _build_config_tab
        self.config_vars    = {}
        self._config_loading = False

        # Generation state
        self.is_generating   = False
        self.last_party_blob = None

        # Sprite image refs (prevent GC of CTkImage objects while they're displayed)
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

        # True while the OS modal move/resize loop is running (Windows only; set by
        # the WM_ENTERSIZEMOVE hook in _install_win_sizemove_hook). Relayout work
        # requested during that window is parked here and flushed once on exit.
        self._in_sizemove = False
        self._sizemove_deferred = {}

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

        self.after(0, self._update_min_size)

        if sys.platform == "win32":
            # Deferred so the window is fully created and GetParent(winfo_id())
            # resolves the real OS frame window.
            self.after(0, self._install_win_sizemove_hook)

        self.bind("<Return>", lambda e: self._run_generation()
                  if self.generate_btn.cget("state") == "normal"
                  and self.tabview.get() == "Generate"
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

    def _on_reload_from_disk(self):
        game = self.var_game.get()
        self._reload_data()
        self._set_config_status("Config reloaded from disk.", color=C_SUCCESS)


    # =========================================================================
    # LAYOUT SKELETON
    # =========================================================================

    def _debounce(self, job_attr: str, delay_ms: int, func):
        """Cancel any pending call scheduled under job_attr and reschedule func.

        Live window resizing on Windows fires many <Configure> events per second;
        handlers that call update_idletasks() on every one of them make dragging the
        window edges visibly laggy. Routing those handlers through this collapses
        rapid-fire events into a single call once resizing activity settles.
        """
        if self._in_sizemove:
            # Inside the OS modal move/resize loop: don't even schedule — after()
            # callbacks fire during the modal loop and each relayout starves it.
            # Only the latest func per job survives; flushed on WM_EXITSIZEMOVE.
            self._sizemove_deferred[job_attr] = func
            return
        job = getattr(self, job_attr, None)
        if job is not None:
            self.after_cancel(job)
        setattr(self, job_attr, self.after(delay_ms, func))

    def _flush_sizemove_deferred(self):
        """Run relayout work parked while the OS modal move/resize loop was active."""
        deferred, self._sizemove_deferred = self._sizemove_deferred, {}
        for job_attr, func in deferred.items():
            self._debounce(job_attr, 10, func)

    def _install_win_sizemove_hook(self):
        """Windows only: subclass the native window proc to catch the OS modal
        move/resize loop (WM_ENTERSIZEMOVE .. WM_EXITSIZEMOVE).

        While that loop runs, all <Configure>-driven relayout is parked in
        _sizemove_deferred (see _debounce and the gen-canvas handler) instead of
        executing, then flushed once on exit. Without this, Windows delivers
        <Configure> on every mouse movement of an edge drag and the per-widget
        CustomTkinter redraws back up the message loop for seconds. Best-effort:
        any failure leaves the app on the debounce-only behavior.
        """
        try:
            import ctypes
            from ctypes import wintypes

            WM_ENTERSIZEMOVE = 0x0231
            WM_EXITSIZEMOVE  = 0x0232
            GWL_WNDPROC      = -4

            user32 = ctypes.windll.user32
            user32.GetParent.restype  = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.CallWindowProcW.restype  = ctypes.c_ssize_t
            user32.CallWindowProcW.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
            ]
            user32.SetWindowLongPtrW.restype  = ctypes.c_void_p
            user32.SetWindowLongPtrW.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
            ]

            # winfo_id() is Tk's client-area window; the OS frame window that
            # receives WM_ENTERSIZEMOVE is its parent.
            hwnd = user32.GetParent(self.winfo_id())
            if not hwnd:
                return

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p,
                                         ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)

            def _wndproc(h, msg, wparam, lparam):
                # Never let an exception escape a ctypes callback: ctypes would
                # swallow it and return 0 ("handled"), skipping the original proc.
                try:
                    if msg == WM_ENTERSIZEMOVE:
                        self._in_sizemove = True
                    elif msg == WM_EXITSIZEMOVE:
                        self._in_sizemove = False
                        self.after(0, self._flush_sizemove_deferred)
                except Exception:
                    self._in_sizemove = False
                return user32.CallWindowProcW(self._orig_wndproc, h, msg, wparam, lparam)

            # Keep a reference on self: if the WNDPROC thunk is garbage-collected
            # while installed, the next window message crashes the process.
            self._sizemove_wndproc = WNDPROC(_wndproc)
            self._orig_wndproc = user32.SetWindowLongPtrW(
                hwnd, GWL_WNDPROC, ctypes.cast(self._sizemove_wndproc, ctypes.c_void_p))
        except Exception:
            self._in_sizemove = False

    def _update_min_size(self):
        self.update_idletasks()
        min_h = (self.export_btn.winfo_y()
                 + self.export_btn.winfo_height()
                 + 20                                       # footer top padding
                 + self._sidebar_footer.winfo_reqheight()
                 + 20)                                      # footer bottom padding
        self.minsize(900, min_h)

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
        _logo_path = resource_path("assets/logo/dexelect-logo-white.png")
        if os.path.exists(_logo_path):
            _logo_src = Image.open(_logo_path)
            _logo_display_w = 190
            _logo_display_h = round(_logo_display_w * _logo_src.height / _logo_src.width)
            self._logo_ctk = ctk.CTkImage(
                light_image=_logo_src, dark_image=_logo_src,
                size=(_logo_display_w, _logo_display_h),
            )
            ctk.CTkLabel(sf, image=self._logo_ctk, text="").grid(
                row=0, column=0, padx=20, pady=(24, 2), sticky="w")
        else:
            ctk.CTkLabel(sf, text="Dexelect", font=FONT_APP_TITLE, text_color=C_TITLE).grid(
                row=0, column=0, padx=20, pady=(24, 2), sticky="w")
        ctk.CTkLabel(sf, text=f"v{__version__}", font=FONT_MONO, text_color=C_TEXT).grid(
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

        for i, mode in enumerate(["Progression", "Random (Obtainable)", "Random (National Dex)"]):
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
            row=10, column=0, padx=16, pady=(16, 0), sticky="ew")

        # ---- Party size ----
        ctk.CTkLabel(sf, text="PARTY SIZE", font=FONT_HEADER, text_color=C_MUTED).grid(
            row=11, column=0, padx=20, pady=(16, 6), sticky="w")

        self.party_size_btn = ctk.CTkSegmentedButton(
            sf,
            values=["1", "2", "3", "4", "5", "6"],
            variable=self.var_party_size,
            command=self._on_party_size_changed,
            corner_radius=0,
            fg_color=C_ACCENT_DIM,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACCENT,
            unselected_color=C_ACCENT_DIM,
            unselected_hover_color=C_ACCENT2,
            text_color=C_TEXT,
            font=FONT_BODY,
        )
        self.party_size_btn.grid(row=12, column=0, padx=20, pady=(0, 4), sticky="w")

        ctk.CTkFrame(sf, height=1, fg_color=C_ACCENT2).grid(
            row=13, column=0, padx=16, pady=(16, 0), sticky="ew")

        # ---- Display toggles (global_settings.yaml) ----
        ctk.CTkLabel(sf, text="DISPLAY", font=FONT_HEADER, text_color=C_MUTED).grid(
            row=14, column=0, padx=20, pady=(16, 6), sticky="w")

        ctk.CTkCheckBox(
            sf,
            text="Acquisition Details",
            variable=self.var_show_acq,
            command=self._on_show_acq_changed,
            text_color=C_TEXT,
            font=FONT_BODY,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            checkmark_color=C_TEXT,
        ).grid(row=15, column=0, padx=24, pady=3, sticky="w")

        ctk.CTkCheckBox(
            sf,
            text="HM Coverage",
            variable=self.var_show_hm,
            command=self._on_show_hm_changed,
            text_color=C_TEXT,
            font=FONT_BODY,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            checkmark_color=C_TEXT,
        ).grid(row=16, column=0, padx=24, pady=3, sticky="w")

        ctk.CTkCheckBox(
            sf,
            text="Balance Stats",
            variable=self.var_show_balance,
            command=self._on_show_balance_changed,
            text_color=C_TEXT,
            font=FONT_BODY,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            checkmark_color=C_TEXT,
        ).grid(row=17, column=0, padx=24, pady=3, sticky="w")

        # ---- Export ----
        ctk.CTkFrame(sf, height=1, fg_color=C_ACCENT2).grid(
            row=18, column=0, padx=16, pady=(16, 0), sticky="ew")

        self.export_btn = ctk.CTkButton(
            sf,
            text="Export Party",
            command=self._export_party,
            fg_color=C_ACCENT_DIM,
            hover_color=C_ACCENT2,
            text_color=C_TEXT,
            font=FONT_BTN,
            height=36,
            corner_radius=5,
            state="disabled",
        )
        self.export_btn.grid(row=19, column=0, padx=20, pady=(12, 0), sticky="ew")

        # ---- Copyright (pinned to bottom) ----
        self._sidebar_footer = tk.Frame(sf, bg=C_SIDEBAR)
        footer = self._sidebar_footer
        footer.grid(row=99, column=0, padx=20, pady=20, sticky="sw")
        sf.grid_rowconfigure(99, weight=1)

        ctk.CTkLabel(
            footer,
            text="© 2026 Derek Andersen",
            font=FONT_BODY,
            text_color=C_MUTED,
            justify="left",
            fg_color=C_SIDEBAR,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        links = tk.Frame(footer, bg=C_SIDEBAR)
        links.grid(row=1, column=0, sticky="w")

        kofi_lbl = ctk.CTkLabel(
            links,
            text="☕ Ko-fi",
            font=FONT_BODY,
            text_color=C_ACCENT,
            fg_color=C_SIDEBAR,
            cursor="hand2",
        )
        kofi_lbl.pack(side="left")
        kofi_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://ko-fi.com/dechrissen"))
        kofi_lbl.bind("<Enter>", lambda e: kofi_lbl.configure(text_color=C_TEXT))
        kofi_lbl.bind("<Leave>", lambda e: kofi_lbl.configure(text_color=C_ACCENT))

        ctk.CTkLabel(links, text="·", font=FONT_BODY, text_color=C_MUTED,
                     fg_color=C_SIDEBAR).pack(side="left", padx=(4, 4))

        gh_lbl = ctk.CTkLabel(
            links,
            text="GitHub",
            font=FONT_BODY,
            text_color=C_ACCENT,
            fg_color=C_SIDEBAR,
            cursor="hand2",
        )
        gh_lbl.pack(side="left")
        gh_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Dechrissen/dexelect"))
        gh_lbl.bind("<Enter>", lambda e: gh_lbl.configure(text_color=C_TEXT))
        gh_lbl.bind("<Leave>", lambda e: gh_lbl.configure(text_color=C_ACCENT))

        ctk.CTkLabel(links, text="·", font=FONT_BODY, text_color=C_MUTED,
                     fg_color=C_SIDEBAR).pack(side="left", padx=(4, 4))

        bug_lbl = ctk.CTkLabel(
            links,
            text="Report a Bug",
            font=FONT_BODY,
            text_color=C_ACCENT,
            fg_color=C_SIDEBAR,
            cursor="hand2",
        )
        bug_lbl.pack(side="left")
        bug_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Dechrissen/dexelect/issues/new?labels=bug"))
        bug_lbl.bind("<Enter>", lambda e: bug_lbl.configure(text_color=C_TEXT))
        bug_lbl.bind("<Leave>", lambda e: bug_lbl.configure(text_color=C_ACCENT))


    # =========================================================================
    # MAIN AREA (tabbed)
    # =========================================================================

    def _build_main(self):
        """
        Right panel with three tabs:
          - Generate : generate button, status, party results
          - Spheres  : sphere mode selector + inline sphere map
          - Config   : all options from the active config YAML
        """
        self.tabview = ctk.CTkTabview(
            self.main_frame,
            fg_color=C_PANEL,
            corner_radius=0,
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
        self.tabview.add("Spheres")
        self.tabview.add("Config")

        # Selected-tab text colour + remove font-glyph corner feathering + no gaps
        _sb = self.tabview._segmented_button
        _sb.configure(corner_radius=0, border_width=0)
        _btns = _sb._buttons_dict
        for _btn in _btns.values():
            _btn._text_label.configure(padx=12)
        _btns["Generate"].configure(text_color=C_BTN_TEXT)
        _btns["Spheres"].configure(text_color=C_TEXT)
        _btns["Config"].configure(text_color=C_TEXT)

        _orig_tab_cmd = self.tabview._segmented_button._command
        def _tab_switch(val, _cmd=_orig_tab_cmd):
            if _cmd:
                _cmd(val)
            for _n, _b in self.tabview._segmented_button._buttons_dict.items():
                _b.configure(text_color=C_BTN_TEXT if _n == val else C_TEXT)
        self.tabview._segmented_button.configure(command=_tab_switch)

        self._build_gen_tab(self.tabview.tab("Generate"))
        self._build_spheres_tab(self.tabview.tab("Spheres"))
        self._build_config_tab(self.tabview.tab("Config"))

        # ---- Help button (top-right corner, anchored inside tab strip) ----
        self._help_img_normal = _circle_q_image(C_MUTED, C_PANEL)
        self._help_img_hover  = _circle_q_image(C_TEXT,  C_PANEL)
        help_btn = tk.Label(
            self.main_frame, image=self._help_img_normal,
            bg=C_PANEL, cursor="hand2", bd=0,
        )
        help_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-40, y=38)
        help_btn.bind("<Button-1>", lambda e: self._toggle_help())
        help_btn.bind("<Enter>", lambda e: help_btn.configure(image=self._help_img_hover))
        help_btn.bind("<Leave>", lambda e: help_btn.configure(image=self._help_img_normal))
        self._help_overlay = None


    def _switch_tab(self, val):
        """Programmatically switch to a tab, keeping button text colours consistent."""
        self.tabview.set(val)
        for _n, _b in self.tabview._segmented_button._buttons_dict.items():
            _b.configure(text_color=C_BTN_TEXT if _n == val else C_TEXT)

    # =========================================================================
    # HELP OVERLAY
    # =========================================================================

    def _toggle_help(self):
        if self._help_overlay and self._help_overlay.winfo_exists():
            self._close_help()
        else:
            self._show_help()

    def _show_help(self):
        overlay = tk.Frame(self, bg=C_BG, highlightthickness=2,
                           highlightbackground=C_CARD_BORDER, highlightcolor=C_CARD_BORDER)
        overlay.place(x=14, y=14, relwidth=1.0, relheight=1.0, width=-28, height=-28)
        overlay.lift()
        self._help_overlay = overlay

        # Title bar
        title_bar = tk.Frame(overlay, bg=C_BG)
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="Help", bg=C_BG, fg=C_TEXT,
                 font=FONT_HEADER, padx=14, pady=8).pack(side="left")
        close = tk.Label(title_bar, text="  ✕  ", bg=C_BG, fg=C_MUTED,
                         font=("Roboto", 16), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self._close_help())
        close.bind("<Enter>", lambda e: close.configure(fg=C_TEXT))
        close.bind("<Leave>", lambda e: close.configure(fg=C_MUTED))

        # Separator
        tk.Frame(overlay, bg=C_CARD_BORDER, height=1).pack(fill="x")

        # Scrollable text area
        text = tk.Text(
            overlay, bg=C_BG, fg=C_MUTED,
            font=FONT_BODY, wrap="word",
            padx=20, pady=14,
            relief="flat", highlightthickness=0,
            selectbackground=C_SELECT_BG, selectforeground=C_SELECT_FG,
            state="normal",
        )
        scrollbar = ctk.CTkScrollbar(overlay, command=text.yview,
                                     fg_color=C_BG, button_color=C_ACCENT2,
                                     button_hover_color=C_ACCENT)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        SCROLL_LINES = 3

        def _on_help_scroll(event):
            if event.num == 4:
                text.yview_scroll(-SCROLL_LINES, "units")
            elif event.num == 5:
                text.yview_scroll(SCROLL_LINES, "units")
            else:
                text.yview_scroll(int(-event.delta / 120) * SCROLL_LINES, "units")
            return "break"

        def _enable_help_scroll(e=None):
            self.bind_all("<MouseWheel>", _on_help_scroll)
            self.bind_all("<Button-4>",   _on_help_scroll)
            self.bind_all("<Button-5>",   _on_help_scroll)

        def _disable_help_scroll(e=None):
            ox, oy = overlay.winfo_rootx(), overlay.winfo_rooty()
            if (ox <= self.winfo_pointerx() < ox + overlay.winfo_width() and
                    oy <= self.winfo_pointery() < oy + overlay.winfo_height()):
                return
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")

        text.bind("<MouseWheel>", _on_help_scroll)
        text.bind("<Button-4>",   _on_help_scroll)
        text.bind("<Button-5>",   _on_help_scroll)
        text.bind("<Enter>",      _enable_help_scroll)
        text.bind("<Leave>",      _disable_help_scroll)
        scrollbar.bind("<Enter>", _enable_help_scroll)
        scrollbar.bind("<Leave>", _disable_help_scroll)

        self._render_help_text(text)
        text.configure(state="disabled")

        self.bind("<Escape>", lambda e: self._close_help())

    def _close_help(self):
        if self._help_overlay:
            try:
                self._help_overlay.destroy()
            except tk.TclError:
                pass
            self._help_overlay = None
        self.unbind("<Escape>")

    def _render_help_text(self, text_widget):
        text_widget.tag_configure("h1",  font=("Roboto", 17, "bold"), foreground=C_ACCENT,
                                         spacing1=2, spacing3=8)
        text_widget.tag_configure("h2",  font=("Roboto", 15, "bold"), foreground=C_TEXT,
                                         spacing1=12, spacing3=2)
        text_widget.tag_configure("h3",  font=("Roboto", 13, "bold"), foreground=C_TEXT,
                                         spacing1=8, spacing3=1)
        text_widget.tag_configure("body", font=FONT_BODY, foreground=C_MUTED)
        text_widget.tag_configure("sel", foreground=C_SELECT_FG, background=C_SELECT_BG)
        text_widget.tag_raise("sel")

        try:
            path = resource_path("ui/gui-help.md")
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


    def _render_sphere_map(self, text_widget):
        text_widget.tag_configure("s_on",     font=("Roboto", 13, "bold"),  foreground=C_TEXT,   spacing1=8, spacing3=3)
        text_widget.tag_configure("s_off",    font=("Roboto", 13, "bold"),  foreground=C_DIM,    spacing1=8, spacing3=3)
        text_widget.tag_configure("map_on",   font=FONT_BODY,               foreground=C_TEXT)
        text_widget.tag_configure("map_off",  font=FONT_BODY,               foreground=C_DIM)
        text_widget.tag_configure("item_on",  font=FONT_BODY,               foreground=C_TEXT)
        text_widget.tag_configure("item_off", font=FONT_BODY,               foreground=C_DIM)
        text_widget.tag_configure("sel", foreground=C_SELECT_FG, background=C_SELECT_BG)
        text_widget.tag_raise("sel")

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


    # =========================================================================
    # SPHERES TAB
    # =========================================================================

    def _build_spheres_tab(self, parent):
        """
        Spheres tab: sphere mode selector (auto-saves on change) + inline sphere map.
        """
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(parent, fg_color=C_PANEL, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))

        game_row = tk.Frame(top, bg=C_PANEL)
        game_row.pack(side="top", anchor="w", padx=(4, 0), pady=(0, 8))
        ctk.CTkLabel(game_row, text="Current game:", font=FONT_BODY, text_color=C_MUTED,
                     fg_color=C_PANEL).pack(side="left")
        self._spheres_game_label = ctk.CTkLabel(game_row, text="", font=FONT_BODY,
                                                text_color=C_TEXT, fg_color=C_PANEL)
        self._spheres_game_label.pack(side="left", padx=(6, 0))

        mode_row = tk.Frame(top, bg=C_PANEL)
        mode_row.pack(side="top", anchor="w", padx=(4, 0))
        ctk.CTkLabel(mode_row, text="Sphere mode", font=FONT_BODY, text_color=C_TEXT,
                     fg_color=C_PANEL).pack(side="left", padx=(0, 0))
        tip = self.tooltips.get("sphere_mode", "")
        if tip:
            icon = _icon_canvas(mode_row)
            icon.pack(side="left", padx=(5, 12), anchor="center")
            _Tooltip(icon, tip)
        self._spheres_mode_menu = ctk.CTkOptionMenu(
            mode_row,
            variable=self.var_sphere_mode,
            values=[],
            command=self._on_sphere_mode_changed,
            fg_color=C_ENTRY_BG, button_color=C_ACCENT2,
            button_hover_color=C_ACCENT, text_color=C_TEXT, font=FONT_MONO,
            width=200,
        )
        self._spheres_mode_menu.pack(side="left")

        tk.Frame(parent, height=1, bg=C_ACCENT2).grid(
            row=1, column=0, sticky="ew")

        map_frame = tk.Frame(parent, bg=C_BG)
        map_frame.grid(row=2, column=0, sticky="nsew")

        self._spheres_text = tk.Text(
            map_frame, bg=C_BG, fg=C_MUTED,
            font=FONT_BODY, wrap="word",
            padx=20, pady=14,
            relief="flat", highlightthickness=0,
            selectbackground=C_SELECT_BG, selectforeground=C_SELECT_FG,
        )
        scrollbar = ctk.CTkScrollbar(map_frame, command=self._spheres_text.yview,
                                     fg_color=C_BG, button_color=C_ACCENT2,
                                     button_hover_color=C_ACCENT)
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
        self._spheres_mode_menu.configure(values=modes if modes else [current])
        self._rerender_sphere_map()

    def _rerender_sphere_map(self):
        text = self._spheres_text
        top, _ = text.yview()
        text.configure(state="normal")
        text.delete("1.0", "end")
        self._render_sphere_map(text)
        text.configure(state="disabled")
        text.after_idle(lambda: text.yview_moveto(top))

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
        # Use C_PANEL to match the tabview's own fg_color — any sub-pixel gap
        # between the canvas edge and the tab frame then shows the same colour.
        canvas = tk.Canvas(parent, bg=C_PANEL, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas.configure(yscrollincrement=1)

        scrollbar = ctk.CTkScrollbar(parent, command=canvas.yview,
                                      button_color=C_ACCENT2, button_hover_color=C_ACCENT)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Auto-hide: only show scrollbar when content exceeds canvas height.
        def _yscroll_set(first, last):
            if float(first) <= 0.0 and float(last) >= 1.0:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()
            scrollbar.set(first, last)
        canvas.configure(yscrollcommand=_yscroll_set)

        # Inner frame: plain tk.Frame avoids CTkFrame rendering artefacts
        # (CTkFrame uses an internal canvas that produces a faint background line).
        gen_inner = tk.Frame(canvas, bg=C_PANEL)
        inner_id = canvas.create_window((0, 0), window=gen_inner, anchor="nw")
        gen_inner.grid_columnconfigure(0, weight=1)
        gen_inner.grid_rowconfigure(2, weight=1)

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

        def _sync_gen_canvas():
            # Reads live canvas dims rather than stale <Configure> event values so
            # a run deferred past the end of an OS resize drag lands on the final
            # size. _refit_gen_height handles the height/scrollregion recompute.
            canvas.itemconfig(inner_id, width=canvas.winfo_width())
            _refit_gen_height()

        def _on_gen_canvas_configure(event):
            if self._in_sizemove:
                # OS modal resize loop (Windows): the width itemconfig below is what
                # propagates each resize step into every themed widget of the card
                # grid (each redraws its own canvas on <Configure>), so skip it
                # entirely — content stays frozen at its old size until the
                # WM_EXITSIZEMOVE flush runs _sync_gen_canvas once.
                self._sizemove_deferred["_gen_canvas_resize_job"] = _sync_gen_canvas
                return
            # Track width immediately (cheap, keeps content visually in sync while
            # dragging on platforms without the sizemove hook); defer the expensive
            # reqheight/scrollregion recompute until resizing activity settles.
            canvas.itemconfig(inner_id, width=event.width)
            self._debounce("_gen_canvas_resize_job", 80, _sync_gen_canvas)

        canvas.bind("<Configure>", _on_gen_canvas_configure)

        def _refit_gen_height():
            """Re-evaluate gen_inner height when HM/stats panels change size."""
            gen_inner.update_idletasks()
            content_h = gen_inner.winfo_reqheight()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            new_h = max(ch, content_h)
            canvas.itemconfig(inner_id, height=new_h)
            canvas.configure(scrollregion=(0, 0, cw, new_h))
        self._refit_gen_height = _refit_gen_height

        def _seed_gen_height():
            gen_inner.update_idletasks()
            h = gen_inner.winfo_reqheight()
            cw, ch = canvas.winfo_width(), canvas.winfo_height()
            if cw > 1 and ch > 1 and h > 1:
                new_h = max(ch, h)
                canvas.itemconfig(inner_id, width=cw, height=new_h)
                canvas.configure(scrollregion=(0, 0, cw, new_h))
        self.after(50, _seed_gen_height)

        # ---- Top bar ----
        top_bar = ctk.CTkFrame(gen_inner, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top_bar.grid_columnconfigure(1, weight=1)

        self.generate_btn = ctk.CTkButton(
            top_bar,
            text="Generate Party",
            command=self._run_generation,
            fg_color=C_ACCENT,
            hover_color=C_ACCENT2,
            text_color=C_BTN_TEXT,
            font=FONT_BTN,
            height=36,
            width=180,
            corner_radius=5,
        )
        self.generate_btn.grid(row=0, column=0, padx=(6, 16))
        self.generate_btn._canvas.configure(bg=C_BG)

        self.status_label = ctk.CTkLabel(
            top_bar,
            text="Press Generate Party or Enter to begin.",
            font=FONT_BODY,
            text_color=C_MUTED,
            anchor="w",
            width=350,
        )
        self.status_label.grid(row=0, column=1, sticky="w")

        # ---- Warning strip ----
        self.warning_strip = ctk.CTkFrame(gen_inner, fg_color="transparent")
        self.warning_strip.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            self.warning_strip,
            text="Party sizes under 6 may affect the likelihood of satisfying HM coverage and balancing requirements.",
            font=FONT_BODY,
            text_color=C_WARNING,
            anchor="w",
        ).pack(side="left")
        self.warning_strip.grid_remove()

        # ---- 3 × 2 card grid ----
        cards_outer = ctk.CTkFrame(gen_inner, fg_color="transparent")
        cards_outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 4))
        cards_outer.grid_columnconfigure(0, weight=1, uniform="cards")
        cards_outer.grid_columnconfigure(1, weight=1, uniform="cards")
        for r in range(3):
            cards_outer.grid_rowconfigure(r, weight=1)

        self._cards_outer = cards_outer
        self._gen_canvas  = canvas
        self.party_cards = []
        for r in range(3):
            for c in range(2):
                card = self._make_card(cards_outer)
                card["frame"].grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
                self.party_cards.append(card)

        # ---- HM coverage strip ----
        self.hm_strip_frame = ctk.CTkFrame(gen_inner, fg_color=C_PANEL, corner_radius=5)
        self.hm_strip_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 4))

        # ---- Stats strip ----
        stats_frame = ctk.CTkFrame(gen_inner, fg_color=C_PANEL, corner_radius=5)
        stats_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 8))
        stats_frame.grid_columnconfigure(0, weight=1)
        stats_frame.grid_columnconfigure(1, weight=0)


        left = ctk.CTkFrame(stats_frame, fg_color=C_PANEL, corner_radius=0)
        left.grid(row=0, column=0, padx=(16, 0), pady=10, sticky="w")

        self.stat_labels = {}
        for col, (key, label) in enumerate([("lean", "Lean"), ("spread", "Spread"), ("pattern", "Pattern")]):
            hdr = tk.Frame(left, bg=C_PANEL)
            hdr.grid(row=0, column=col, sticky="w", padx=(0, 20))
            ctk.CTkLabel(hdr, text=label, font=FONT_BODY, text_color=C_TEXT,
                         fg_color=C_PANEL, anchor="w").pack(side="left")
            tip = self.tooltips.get(key, "")
            if tip:
                icon = _icon_canvas(hdr)
                icon.pack(side="left", padx=(5, 0), anchor="center")
                _Tooltip(icon, tip)
            val = ctk.CTkLabel(left, text="—", font=FONT_MONO, text_color=C_MUTED, anchor="w", width=150)
            val.grid(row=1, column=col, sticky="w")
            self.stat_labels[key] = val

        right = ctk.CTkFrame(stats_frame, fg_color=C_PANEL, corner_radius=0)
        right.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="e")

        hdr = tk.Frame(right, bg=C_PANEL)
        hdr.grid(row=0, column=0, sticky="e")
        ctk.CTkLabel(hdr, text="Distribution", font=FONT_BODY, text_color=C_TEXT,
                     fg_color=C_PANEL, anchor="e").pack(side="left")
        tip = self.tooltips.get("distribution", "")
        if tip:
            icon = _icon_canvas(hdr)
            icon.pack(side="left", padx=(5, 0), anchor="center")
            _Tooltip(icon, tip)
        self._sphere_icon_normal = _sphere_icon_image(C_MUTED, C_PANEL)
        self._sphere_icon_hover  = _sphere_icon_image(C_TEXT,  C_PANEL)
        smap_btn = tk.Label(hdr, image=self._sphere_icon_normal, bg=C_PANEL, cursor="hand2", bd=0)
        smap_btn.pack(side="left", padx=(5, 0), anchor="center")
        smap_btn.bind("<Button-1>", lambda e: self._switch_tab("Spheres"))
        smap_btn.bind("<Enter>", lambda e: smap_btn.configure(image=self._sphere_icon_hover))
        smap_btn.bind("<Leave>", lambda e: smap_btn.configure(image=self._sphere_icon_normal))
        dist_val = ctk.CTkLabel(right, text="—", font=FONT_MONO, text_color=C_MUTED, anchor="e")
        dist_val.grid(row=1, column=0, sticky="e")
        self.stat_labels["distribution"] = dist_val

        self._stats_frame   = stats_frame
        self._stats_left    = left
        self._stats_right   = right
        self._stats_wrapped = False
        stats_frame.bind("<Configure>", lambda e: self._debounce("_stats_resize_job", 80, self._update_stats_layout))


    # =========================================================================
    # CARD HELPERS
    # =========================================================================

    def _make_card(self, parent) -> dict:
        """Build one empty party-member card; return updateable widget refs."""
        frame = ctk.CTkFrame(
            parent,
            fg_color=C_CARD,
            corner_radius=5,
            border_width=1,
            border_color=C_CARD_BORDER,
        )
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=0)   # name
        frame.grid_rowconfigure(1, weight=0)   # types
        frame.grid_rowconfigure(2, weight=0)   # bst
        frame.grid_rowconfigure(3, weight=1, minsize=30)  # spacer — keeps acq row below sprite bottom
        frame.grid_rowconfigure(4, weight=0)   # separator
        frame.grid_rowconfigure(5, weight=0)   # acq (full width)
        # No grid_propagate(False): the card's winfo_reqheight() must reflect
        # its content so the scroll region grows to fit when a party is loaded.

        sprite = ctk.CTkLabel(
            frame,
            text="",
            image=None,
            fg_color="transparent",
            corner_radius=5,
            width=80,
            height=80,
        )
        sprite.grid(row=0, column=0, rowspan=4, padx=(8, 8), pady=(10, 0), sticky="nw")

        name_lbl = ctk.CTkLabel(frame, text="", font=FONT_MONO_HEADER, text_color=C_MUTED, anchor="w")
        name_lbl.grid(row=0, column=1, padx=(0, 10), pady=(4, 2), sticky="nw")

        empty_lbl = ctk.CTkLabel(frame, text="Empty", font=FONT_MONO_HEADER,
                                  text_color=C_MUTED, fg_color="transparent")
        empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        empty_lbl.lift()

        # plain tk.Frame avoids CTkFrame canvas overpainting the card border
        types_frame = tk.Frame(frame, bg=C_CARD)
        types_frame.grid(row=1, column=1, padx=(0, 10), pady=(0, 2), sticky="nw")

        bst_lbl = ctk.CTkLabel(frame, text="", font=FONT_BODY, text_color=C_MUTED, anchor="nw")
        bst_lbl.grid(row=2, column=1, padx=(0, 10), pady=(0, 0), sticky="nw")

        sep = ctk.CTkFrame(frame, height=1, fg_color=C_ACCENT2)
        sep.grid(row=4, column=0, columnspan=2, padx=10, pady=(6, 0), sticky="ew")
        sep.grid_remove()

        acq_lbl = ctk.CTkLabel(
            frame, text="", font=FONT_BODY, text_color=C_MUTED,
            anchor="nw", justify="left", wraplength=0,
        )
        acq_lbl.grid(row=5, column=0, columnspan=2, padx=(14, 10), pady=(4, 8), sticky="nw")

        return {"frame": frame, "name": name_lbl, "acq": acq_lbl, "sep": sep, "sprite": sprite,
                "types_frame": types_frame, "bst": bst_lbl, "empty_lbl": empty_lbl}

    def _build_hm_labels(self):
        """Rebuild HM coverage labels for the current game. Called on startup and game change."""
        if self._hm_strip_inner:
            self._hm_strip_inner.destroy()
        inner = tk.Frame(self.hm_strip_frame, bg=C_PANEL)
        inner.pack(fill="x", padx=16, pady=10)
        self._hm_strip_inner = inner
        self.hm_labels = {}
        hdr = tk.Frame(inner, bg=C_PANEL)
        hdr.pack(side="top", anchor="w", pady=(0, 4))
        ctk.CTkLabel(hdr, text="HM Coverage", font=FONT_BODY, text_color=C_TEXT,
                     fg_color=C_PANEL).pack(side="left")
        tip = self.tooltips.get("hm_coverage", "")
        if tip:
            icon = _icon_canvas(hdr)
            icon.pack(side="left", padx=(5, 0), anchor="center")
            _Tooltip(icon, tip)

        # Individual HM labels (shown when toggle on); labels are positioned via
        # place() in _reflow_hm_list so they wrap to a new row when space is tight.
        hm_list = tk.Frame(inner, bg=C_PANEL)
        hm_list.pack_propagate(False)
        self._hm_list_frame = hm_list
        for hm_name in self.config_data.get("ensure_hm_coverage", {}):
            lbl = ctk.CTkLabel(hm_list, text=hm_name, font=FONT_MONO, text_color=C_MUTED, fg_color=C_PANEL)
            self.hm_labels[hm_name] = lbl
        hm_list.bind("<Configure>", lambda e: self._debounce("_hm_resize_job", 80, self._reflow_hm_list))

        # Single dash (shown when toggle off or no party generated yet)
        self._hm_dash_label = ctk.CTkLabel(inner, text="—", font=FONT_MONO,
                                            text_color=C_MUTED, fg_color=C_PANEL)
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
            lbl.configure(text_color=C_ACCENT if hm_name in party_coverage else C_MUTED)

    def _clear_cards(self):
        """Reset all party cards to their empty placeholder state."""
        for i, card in enumerate(self.party_cards):
            card["name"].configure(text="", text_color=C_MUTED, cursor="")
            for w in (card["name"], card["name"]._label):
                w.unbind("<Button-1>")
                w.unbind("<Enter>")
                w.unbind("<Leave>")
            card["empty_lbl"].place(relx=0.5, rely=0.5, anchor="center")
            card["empty_lbl"].lift()
            card["acq"].configure(text="")
            card["sep"].grid_remove()
            card["bst"].configure(text="")
            try:
                card["sprite"].configure(image=None, cursor="")
            except tk.TclError:
                lbl = card["sprite"]._label
                lbl.tk.call(lbl._w, "configure", "-image", "", "-cursor", "")
            card["sprite"].configure(width=SPRITE_MAX, height=SPRITE_MAX)
            self._sprite_images[i] = None
            for w in (card["sprite"], card["sprite"]._label):
                w.unbind("<Button-1>")
            for w in card["types_frame"].winfo_children():
                w.destroy()
        for lbl in self.stat_labels.values():
            lbl.configure(text="—", text_color=C_MUTED)
        self._refresh_hm_labels(party_coverage=None)
        self.last_party_blob = None
        self.export_btn.configure(state="disabled")
        self.after_idle(self._refit_gen_height)

    def _update_stats_layout(self):
        """Wrap the Distribution panel to a second row when there isn't enough horizontal room."""
        sf = self._stats_frame
        sf.update_idletasks()
        available = sf.winfo_width()
        if available <= 1:
            return
        left  = self._stats_left
        right = self._stats_right
        need  = left.winfo_reqwidth() + right.winfo_reqwidth() + 32  # 16 px padx each side
        if available < need and not self._stats_wrapped:
            self._stats_wrapped = True
            left.grid(row=0, column=0, columnspan=2, padx=(16, 16), pady=(10, 4), sticky="w")
            right.grid(row=1, column=0, columnspan=2, padx=(0, 16), pady=(4, 10), sticky="e")
            self.after_idle(self._refit_gen_height)
        elif available >= need and self._stats_wrapped:
            self._stats_wrapped = False
            left.grid(row=0, column=0, padx=(16, 0), pady=10, sticky="w")
            right.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="e")
            self.after_idle(self._refit_gen_height)

    def _render_type_badges(self, types_frame, types: list[str]):
        """Render colored type badges (swatch + label) into the given frame."""
        for w in types_frame.winfo_children():
            w.destroy()
        for col, type_name in enumerate(types):
            color = TYPE_COLORS.get(type_name.lower(), C_MUTED)
            badge = tk.Frame(types_frame, bg=C_CARD)
            badge.grid(row=0, column=col, padx=(0, 6))
            tk.Frame(badge, width=12, height=12, bg=color).grid(row=0, column=0, padx=(0, 4))
            ctk.CTkLabel(badge, text=type_name.capitalize(), font=FONT_BODY,
                         text_color=color, anchor="w", fg_color=C_CARD).grid(row=0, column=1)


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
        scroll.grid(row=0, column=0, sticky="nsew", pady=(8, 0))
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)
        self.config_scroll = scroll

        # bind() without add="+" replaces CTkScrollableFrame's own internal
        # <Configure> binding (_fit_frame_dimensions_to_canvas — stretches the
        # content frame to the canvas width), so chain it explicitly here. It's
        # routed through the sizemove gate because its width itemconfigure is what
        # would cascade each Windows resize step into every config widget (the
        # same storm as the gen tab's card grid); it ignores its event arg and
        # reads live canvas dims, so a deferred call with None lands correctly.
        def _on_config_canvas_configure(event):
            if self._in_sizemove:
                self._sizemove_deferred["_config_fit_job"] = \
                    lambda: scroll._fit_frame_dimensions_to_canvas(None)
            else:
                scroll._fit_frame_dimensions_to_canvas(event)
            self._on_config_note_resize(event)

        scroll._parent_canvas.bind("<Configure>", _on_config_canvas_configure)

        # Mouse-wheel scrolling: activate globally while cursor is inside the frame.
        # Using enter/leave avoids accumulating duplicate bindings on every rebuild.
        canvas = scroll._parent_canvas
        # CTkScrollableFrame sets yscrollincrement=1 on Windows; set it on Linux too
        # so that 1 unit = 1 pixel on every platform and SCROLL_PX is always exact.
        canvas.configure(yscrollincrement=1)
        SCROLL_PX = 60  # pixels per scroll notch

        def _on_config_scroll(event):
            if event.num == 4:                        # Linux scroll-up
                canvas.yview_scroll(-SCROLL_PX, "units")
            elif event.num == 5:                      # Linux scroll-down
                canvas.yview_scroll(SCROLL_PX, "units")
            else:                                     # Windows <MouseWheel> (delta=±120/notch)
                canvas.yview_scroll(int(-event.delta / 120) * SCROLL_PX, "units")

        # scroll._parent_frame is the outer CTkFrame that contains both the
        # _parent_canvas and the CTkScrollbar — binding here covers the full
        # footprint (content area + scrollbar column).  Binding on `scroll`
        # (the inner tk.Frame inside _parent_canvas) misses the scrollbar.
        _pf = scroll._parent_frame

        def _on_config_scroll_enter(e):
            self.bind_all("<MouseWheel>", _on_config_scroll)
            self.bind_all("<Button-4>",   _on_config_scroll)
            self.bind_all("<Button-5>",   _on_config_scroll)

        def _on_config_scroll_leave(e):
            sx, sy = _pf.winfo_rootx(), _pf.winfo_rooty()
            if (sx <= self.winfo_pointerx() < sx + _pf.winfo_width() and
                    sy <= self.winfo_pointery() < sy + _pf.winfo_height()):
                return
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")

        _pf.bind("<Enter>", _on_config_scroll_enter)
        _pf.bind("<Leave>", _on_config_scroll_leave)

        tk.Frame(parent, height=1, bg=C_CARD_BORDER).grid(
            row=1, column=0, sticky="ew")

        # ---- Bottom bar ----
        save_bar = ctk.CTkFrame(parent, fg_color="transparent", height=50)
        save_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 10))
        save_bar.grid_columnconfigure(0, weight=1)

        self.config_status_label = ctk.CTkLabel(
            save_bar, text="", font=FONT_BODY, text_color=C_MUTED, anchor="w")
        self.config_status_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            save_bar,
            text="Reload from Disk",
            command=self._on_reload_from_disk,
            fg_color=C_ACCENT_DIM,
            hover_color=C_ACCENT2,
            text_color=C_MUTED,
            font=FONT_BTN,
            height=38,
            width=160,
        ).grid(row=0, column=1, padx=(0, 12))

        self.config_file_label = ctk.CTkLabel(
            save_bar, text="", font=FONT_MONO, text_color=C_MUTED, anchor="e")
        self.config_file_label.grid(row=0, column=2, sticky="e", padx=(0, 4))


    def _populate_config_controls(self):
        """
        Build (or rebuild) all config widgets inside the scrollable config frame.
        Called on initial load and whenever the game changes.
        """
        self._config_loading = True
        scroll = self.config_scroll

        game = self.var_game.get()
        config_path = self.mappings[game]["config"]
        self.config_file_label.configure(text=os.path.basename(config_path))

        for widget in scroll.winfo_children():
            widget.destroy()
        self.config_vars.clear()

        cd = self.config_data
        row = 0

        def label_with_tip(key, text, font=FONT_BODY, text_color=C_TEXT):
            """Return a frame with the label text and a circle-i icon tacked on if a tooltip exists."""
            f = tk.Frame(scroll, bg=C_PANEL)
            ctk.CTkLabel(f, text=text, font=font, text_color=text_color,
                         fg_color=C_PANEL, anchor="w").pack(side="left")
            tip = self.tooltips.get(key, "")
            if tip:
                icon = _icon_canvas(f)
                icon.pack(side="left", padx=(5, 0), anchor="center")
                _Tooltip(icon, tip)
            return f

        def section_label(text):
            nonlocal row
            ctk.CTkLabel(
                scroll, text=text, font=FONT_SECTION_HEADER, text_color=C_ACCENT, anchor="w"
            ).grid(row=row, column=0, columnspan=2, padx=20, pady=(20, 4), sticky="w")
            row += 1
            tk.Frame(scroll, height=1, bg=C_ACCENT2).grid(
                row=row, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="ew")
            row += 1

        def bool_row(key, label):
            nonlocal row
            var = tk.BooleanVar(value=bool(cd.get(key, False)))
            var.trace_add("write", lambda *_: self._autosave_config())
            self.config_vars[key] = var
            f = tk.Frame(scroll, bg=C_PANEL)
            ctk.CTkCheckBox(
                f, text=label, variable=var,
                text_color=C_TEXT, font=FONT_BODY,
                fg_color=C_ACCENT, hover_color=C_ACCENT2,
                checkmark_color=C_TEXT,
            ).pack(side="left")
            tip = self.tooltips.get(key, "")
            if tip:
                icon = _icon_canvas(f)
                icon.pack(side="left", padx=(5, 0), anchor="center")
                _Tooltip(icon, tip)
            f.grid(row=row, column=0, columnspan=2, padx=28, pady=3, sticky="w")
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
            entry = ctk.CTkEntry(
                scroll, textvariable=var, width=100,
                fg_color=C_ENTRY_BG, text_color=C_TEXT,
                border_color=C_ACCENT2, font=FONT_MONO,
                placeholder_text="none" if nullable else "",
            )
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
                ctk.CTkCheckBox(
                    scroll, text=display, variable=var,
                    text_color=C_TEXT, font=FONT_MONO,
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
            label_with_tip(parent_key, label).grid(row=row, column=0, columnspan=2, padx=28, pady=(6, 2), sticky="w")
            row += 1
            var_dict = {}
            for option in options:
                var = tk.BooleanVar(value=bool(current_dict.get(option, False)))
                var.trace_add("write", lambda *_: self._autosave_config())
                var_dict[option] = var
                ctk.CTkCheckBox(
                    scroll, text=option, variable=var,
                    text_color=C_TEXT, font=FONT_MONO,
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
            var.trace_add("write", lambda *_: self._autosave_config())
            self.config_vars[key] = var
            lbl = label_with_tip(key, label)
            lbl.grid(row=row, column=0, padx=28, pady=4, sticky="w")
            menu = ctk.CTkOptionMenu(
                scroll, variable=var, values=options if options else [current_val],
                fg_color=C_ENTRY_BG, button_color=C_ACCENT2,
                button_hover_color=C_ACCENT, text_color=C_TEXT, font=FONT_MONO,
                width=200,
            )
            menu.grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            row += 1
            return lbl, menu

        def text_row(key, label, placeholder=""):
            nonlocal row
            current_val = cd.get(key, []) or []
            display_val = ", ".join(current_val) if isinstance(current_val, list) else str(current_val)
            label_with_tip(key, label).grid(row=row, column=0, padx=28, pady=4, sticky="w")
            entry = ctk.CTkEntry(
                scroll, width=320,
                fg_color=C_ENTRY_BG, text_color=C_TEXT,
                border_color=C_ACCENT2, font=FONT_MONO,
                placeholder_text=placeholder,
            )
            if display_val:
                entry.insert(0, display_val)
            entry.grid(row=row, column=1, padx=(0, 28), pady=4, sticky="w")
            entry.bind("<FocusOut>", lambda e: self._autosave_config())
            entry.bind("<Return>",   lambda e: self._autosave_config())
            self.config_vars[key] = entry
            row += 1

        self._config_note_label = ctk.CTkLabel(
            scroll,
            text="Note: Overly restrictive configuration settings may affect the likelihood of successfully generating a party. Some combinations of settings will not result in a valid party.",
            font=FONT_BODY,
            text_color=C_MUTED,
            anchor="w",
            wraplength=scroll._parent_canvas.winfo_width() or 600,
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
            pt_menu.configure(
                state="normal" if enabled else "disabled",
                button_color=C_ACCENT2 if enabled else C_ACCENT2_DIM,
                button_hover_color=C_ACCENT if enabled else C_ACCENT2_DIM,
            )
            pt_lbl.winfo_children()[0].configure(text_color=C_TEXT if enabled else C_DIM)

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
        self.game_dropdown.configure(values=game_names)
        self._rebuild_game_dropdown_menu(game_names)
        self.var_game.set(gs.get("game", game_names[0]))
        self.var_gen_mode.set(gs.get("generation_mode", "Progression"))
        self.var_show_acq.set(bool(gs.get("show_acquisition_details", True)))
        self.var_show_balance.set(bool(gs.get("show_balance_stats", True)))
        self.var_show_hm.set(bool(gs.get("show_hm_coverage", True)))
        self.var_party_size.set(str(gs.get("party_size", 6)))
        self._update_party_size_text_colors()
        self._update_warning_strip()
        self._build_hm_labels()
        self._refresh_spheres_tab()

        self._populate_config_controls()

    def _rebuild_game_dropdown_menu(self, game_names):
        """
        Rebuild the game dropdown's popup menu so romhack entries display a
        "(romhack)" suffix, while the underlying selected value (var_game,
        _on_game_changed, etc.) still receives the plain game name. Reaches into
        CTkOptionMenu/DropdownMenu internals since customtkinter has no public
        support for per-entry display text that differs from the entry's value.
        """
        dropdown = self.game_dropdown
        menu = dropdown._dropdown_menu
        width = menu._min_character_width

        menu.delete(0, "end")

        def format_label(text):
            if sys.platform.startswith("linux"):
                return "  " + text.ljust(width) + "  "
            return text.ljust(width)

        def is_romhack(name):
            return "romhacks" in self.mappings[name]["pokedex"]

        for name in game_names:
            display = name + " (romhack)" if is_romhack(name) else name
            menu.add_command(label=format_label(display),
                             command=lambda v=name: dropdown._dropdown_callback(v))


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
                lbl.configure(text=placeholder, text_color=C_MUTED)

    def _on_show_hm_changed(self):
        self._patch_global_setting("show_hm_coverage", self.var_show_hm.get())
        if self.last_party_blob is not None:
            self._populate_cards(self.last_party_blob)
        else:
            self._refresh_hm_labels(party_coverage=None)

    def _on_party_size_changed(self, value: str):
        self._patch_global_setting("party_size", int(value))
        self._update_party_size_text_colors()
        self._update_warning_strip()

    def _update_warning_strip(self):
        if int(self.var_party_size.get()) < 6:
            self.warning_strip.grid()
        else:
            self.warning_strip.grid_remove()

    def _on_config_note_resize(self, event):
        # Fires on every <Configure> of the config canvas during a live resize, and
        # each wraplength configure forces a label re-measure + redraw — debounce it.
        # The deferred run reads the width live since the event's value goes stale.
        self._debounce("_config_note_resize_job", 80, self._apply_config_note_wrap)

    def _apply_config_note_wrap(self):
        if not self._config_note_label:
            return
        try:
            width = self.config_scroll._parent_canvas.winfo_width()
            self._config_note_label.configure(wraplength=max(200, width - 40))
        except tk.TclError:
            pass  # label was destroyed by a config-tab rebuild mid-debounce

    def _update_party_size_text_colors(self):
        current = self.var_party_size.get()
        for val, btn in self.party_size_btn._buttons_dict.items():
            btn.configure(text_color=C_BTN_TEXT if val == current else C_TEXT)


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

                elif isinstance(var, (tk.StringVar, ctk.CTkEntry)):
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

    def _cover_cards(self):
        """Overlay each card with a blank card-shaped cover to hide the clear/repopulate flash.

        Placed as a sibling inside cards_outer (not inside the card itself) so its
        transparent corners reveal the cards_outer background (C_PANEL) exactly as the
        real card does, avoiding any sharp-corner mismatch.
        """
        self._cards_outer.update_idletasks()
        for card in self.party_cards:
            frame = card["frame"]
            ov = ctk.CTkFrame(
                self._cards_outer,
                fg_color=C_CARD,
                corner_radius=5,
                border_width=1,
                border_color=C_CARD_BORDER,
                width=frame.winfo_width(),
                height=frame.winfo_height(),
            )
            ov.place(x=frame.winfo_x(), y=frame.winfo_y())
            ov.lift()
            card["_overlay"] = ov

    def _uncover_cards(self):
        for card in self.party_cards:
            ov = card.pop("_overlay", None)
            if ov:
                try:
                    ov.destroy()
                except tk.TclError:
                    pass

    def _run_generation(self):
        """Kick off party generation in a background thread so the GUI stays responsive."""
        if self.is_generating:
            return

        self.is_generating = True
        self.generate_btn.configure(state="disabled")
        self._cover_cards()
        # Give tkinter one paint cycle to render the overlay before clearing cards.
        self.after(20, self._begin_generation)

    def _begin_generation(self):
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
                party_blob = generate_fully_randomized_party(self.all_pokemon, n=int(self.var_party_size.get()))
            elif gen_mode == "Random (Obtainable)":
                party_blob = generate_fully_randomized_party(self.obtainable_pokemon, n=int(self.var_party_size.get()))
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
            self.after_idle(self._uncover_cards)
            return

        if party_blob is None:
            self._set_status("Could not generate a party. Try adjusting settings.", color=C_WARNING)
            self.after_idle(self._uncover_cards)
            return

        self._set_status(f"Party generated in {duration:.2f}s.", color=C_SUCCESS)
        self.last_party_blob = party_blob
        self.export_btn.configure(state="normal")
        self._populate_cards(party_blob)
        self.after_idle(self._uncover_cards)
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
            card["name"].configure(text=mon_obj.name, text_color=C_TEXT)
            card["empty_lbl"].place_forget()
            url = f"https://pokemondb.net/pokedex/{int(mon_obj.nat_dex_number)}"
            card["name"].configure(cursor="hand2")
            for w in (card["name"], card["name"]._label):
                w.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
                w.bind("<Enter>", lambda e, c=card: c["name"].configure(text_color=C_ACCENT))
                w.bind("<Leave>", lambda e, c=card: c["name"].configure(text_color=C_TEXT))
            self._render_type_badges(card["types_frame"], mon_obj.types)
            card["bst"].configure(text=f"Base stat total: {mon_obj.base_stat_total}")

            sprite_path = os.path.join(sprite_dir, f"{mon_obj.nat_dex_number}.png")
            try:
                pil_img = Image.open(sprite_path)
                resized = pil_img.resize((SPRITE_MAX, SPRITE_MAX), Image.NEAREST)
                ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(SPRITE_MAX, SPRITE_MAX))
                card["sprite"].configure(image=ctk_img, cursor="hand2", width=SPRITE_MAX, height=SPRITE_MAX)
                self._sprite_images[i] = ctk_img
                for w in (card["sprite"], card["sprite"]._label):
                    w.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            except (FileNotFoundError, OSError):
                try:
                    card["sprite"].configure(image=None, cursor="")
                except tk.TclError:
                    lbl = card["sprite"]._label
                    lbl.tk.call(lbl._w, "configure", "-image", "", "-cursor", "")
                self._sprite_images[i] = None
                for w in (card["sprite"], card["sprite"]._label):
                    w.unbind("<Button-1>")

            if is_random and show_acq:
                card["acq"].configure(text="N/A")
                card["sep"].grid_remove()
            elif show_acq and pokemon["random_pool_entry_instance"] is not None:
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
            else:
                card["acq"].configure(text="")
                card["sep"].grid_remove()

        party_hm_coverage = set(
            hm for m in party_blob["party_with_acquisition_data"]
            for hm in m["party_member_obj"].hm_learnset
        )
        self._refresh_hm_labels(party_coverage=party_hm_coverage)

        if not is_random and show_balance and party_blob.get("lean") is not None:
            self.stat_labels["lean"].configure(text=str(party_blob.get("lean", "—")), text_color=C_MUTED)
            self.stat_labels["spread"].configure(text=str(party_blob.get("spread", "—")), text_color=C_MUTED)
            pattern = party_blob.get("pattern")
            self.stat_labels["pattern"].configure(text=str(pattern) if pattern else "—", text_color=C_MUTED)
            dist = party_blob.get("party_distribution")
            if dist:
                dist_str = "  ".join(f"S{s}: {dist[s]}" for s in dist)
                self.stat_labels["distribution"].configure(text=dist_str, text_color=C_MUTED)
            else:
                self.stat_labels["distribution"].configure(text="—", text_color=C_MUTED)
        else:
            placeholder = "N/A" if (is_random and show_balance) else "—"
            for lbl in self.stat_labels.values():
                lbl.configure(text=placeholder, text_color=C_MUTED)
        self.after_idle(self._update_stats_layout)


    # =========================================================================
    # EXPORT
    # =========================================================================

    def _export_party(self):
        if self.last_party_blob is None:
            return

        game      = self.var_game.get()
        mode      = self.var_gen_mode.get()
        blob      = self.last_party_blob
        is_random = mode in ("Random (National Dex)", "Random (Obtainable)")

        # --- Party list ---
        def sort_key(p):
            prescribed = p["random_pool_entry_instance"]
            method = prescribed["acquisition_method"] if prescribed else None
            earliest_pool = p.get("earliest_pool", 9999) or 9999
            return (0 if method == "starter" else 1, earliest_pool)

        sorted_party = sorted(blob["party_with_acquisition_data"], key=sort_key)
        party_lines = []
        for i, member in enumerate(sorted_party, 1):
            mon   = member["party_member_obj"]
            entry = member["random_pool_entry_instance"]
            if is_random or entry is None:
                party_lines.append(f"{i}. {mon.name}")
            else:
                form     = member["earliest_form"].name
                method   = entry["acquisition_method"]
                location = entry["acquiring_location"]
                pool     = member["earliest_pool"]
                party_lines.append(
                    f"{i}. {mon.name} — Acquire as {form} via {method} at {location} (Sphere {pool})"
                )
        party_str = "\n".join(party_lines)

        # --- HM Coverage ---
        hm_config = self.config_data.get("ensure_hm_coverage", {})
        hm_set = set(
            hm for m in blob["party_with_acquisition_data"]
            for hm in m["party_member_obj"].hm_learnset
        )
        if hm_config:
            hm_parts = [
                f"{hm}(Y)" if hm in hm_set else f"{hm}(N)"
                for hm in hm_config
            ]
            hm_str = "  ".join(hm_parts)
        else:
            hm_str = "—"

        # --- Balance Stats ---
        if not is_random and blob.get("lean") is not None:
            dist     = blob.get("party_distribution") or {}
            dist_str = "  ".join(f"S{s}: {dist[s]}" for s in dist) if dist else "—"
            pattern  = blob.get("pattern") or "—"
            balance_str = (
                f"Lean:         {blob.get('lean', '—')}\n"
                f"Spread:       {blob.get('spread', '—')}\n"
                f"Pattern:      {pattern}\n"
                f"Distribution: {dist_str}"
            )
        else:
            balance_str = "N/A"

        # --- Render template ---
        template_path = resource_path("ui/export_template.txt")
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        ctx = {
            "game":          game,
            "mode":          mode,
            "party":         party_str,
            "hm_coverage":   hm_str,
            "balance_stats": balance_str,
            "version":       __version__,
            "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        def _render(tmpl, context):
            return re.sub(
                r"\{\{\s*(\w+)\s*\}\}",
                lambda m: str(context.get(m.group(1).strip(), m.group(0))),
                tmpl,
            )

        output = _render(template, ctx)

        # --- Save dialog ---
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        game_slug = re.sub(r"[^\w]+", "_", game.lower()).strip("_")
        default_name = f"dexelect_generated_party_{game_slug}_{ts}.txt"

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
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
        self.status_label.configure(text=message, text_color=color)

    def _set_config_status(self, message: str, color: str = C_MUTED):
        """Update the status label in the Config tab."""
        self.config_status_label.configure(text=message, text_color=color)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    _pools, _pokemon, _config, _meta, _mappings, _settings, _obtainable = build_all_data_structures()
    app = DexelectApp(_pools, _pokemon, _config, _meta, _mappings, _settings, _obtainable)
    app.mainloop()
