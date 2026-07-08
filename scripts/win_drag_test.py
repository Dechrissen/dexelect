# Windows drag/resize bisection test for the Dexelect performance problem.
#
# Run on the Windows machine (from the repo root, venv active):
#
#   python scripts\win_drag_test.py
#
# Four bare-bones windows open ONE AT A TIME (close each to advance to the
# next). Drag each around by the title bar and resize it by the edges for a few
# seconds, then close it. Note which phases show the slow-motion trail /
# delayed resize. The window title says which phase you're in.
#
#   PHASE A  plain Tk, process left DPI-unaware (Windows stretches the bitmap)
#   PHASE B  plain Tk, per-monitor DPI aware (the process mode CustomTkinter sets)
#   PHASE C  CustomTkinter + widgets, bone stock (incl. its 30ms/100ms polls)
#   PHASE D  CustomTkinter + widgets, with all Dexelect mitigations
#            (DPI awareness deactivated, appearance pinned, polls slowed)
#   PHASE E  like C, but with Dexelect's exact window setup (size formula,
#            wm_iconphoto icon set, iconbitmap, minsize)
#   PHASE F  like C, but with ~150 widgets (Dexelect-scale widget count)
#
# Round 1 results (2026-07-08, Win10 19045): A smooth, B smooth, C laggy resize
# only, D laggy resize only. Conclusions: resize lag = CustomTkinter per-widget
# redraw machinery (not DPI, not the polls); the MOVE trail did not reproduce
# in any phase, so it comes from something Dexelect's window has that these
# didn't — hence phases E (window setup) and F (widget count).
#
# Reading the result:
#   A laggy                 -> Tk/system level; no app code involved at all
#   B laggy, A smooth       -> SetProcessDpiAwareness(2) is the culprit
#   C laggy, A+B smooth     -> CustomTkinter machinery is the culprit
#   C laggy, D smooth       -> the mitigations work; wire them into the app
#   C+D laggy, A+B smooth   -> CustomTkinter's widget drawing itself
#   E trails on move        -> Dexelect's window setup (size/icons/minsize)
#   F trails on move        -> widget count is the move-trail ingredient
#
# Each phase runs in its own process because DPI awareness is process-wide and
# can only be set once.

import subprocess
import sys
from pathlib import Path

PHASES = {
    "a": "PHASE A - plain Tk, DPI-unaware",
    "b": "PHASE B - plain Tk, per-monitor DPI aware",
    "c": "PHASE C - CustomTkinter, stock",
    "d": "PHASE D - CustomTkinter, Dexelect mitigations",
    "e": "PHASE E - CustomTkinter, Dexelect window setup",
    "f": "PHASE F - CustomTkinter, ~150 widgets",
}
INSTRUCTIONS = "  |  drag + resize me for a few seconds, then close"

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_plain_tk(title, dpi_aware):
    if dpi_aware and sys.platform == "win32":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    import tkinter as tk
    root = tk.Tk()
    root.title(title + INSTRUCTIONS)
    root.geometry("1000x700")
    for i in range(12):
        row = tk.Frame(root)
        row.pack(fill="x", padx=10, pady=2)
        for j in range(3):
            tk.Button(row, text=f"button {i}-{j}").pack(side="left", padx=4)
        tk.Label(row, text="some label text " * 3).pack(side="left", padx=8)
    root.mainloop()


def run_ctk(title, mitigated=False, dexelect_window=False, rows=12):
    import customtkinter as ctk
    if mitigated:
        ctk.deactivate_automatic_dpi_awareness()
        ctk.set_appearance_mode("dark")
        ctk.ScalingTracker.update_loop_interval = 1000
        ctk.AppearanceModeTracker.update_loop_interval = 1000
    root = ctk.CTk()
    root.title(title + INSTRUCTIONS)

    if dexelect_window:
        # Mirror DexelectApp.__init__'s window setup exactly: size formula,
        # centering, the multi-size iconphoto set, iconbitmap, minsize.
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        win_w = min(max(900, int(sw * 0.85)), 1280)
        win_h = min(max(620, int(sh * 0.72)), 1050)
        win_w = min(win_w, sw - 20)
        win_h = min(win_h, sh - 60)
        x = (sw - win_w) // 2
        y = max(0, (sh - win_h) // 2)
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        import tkinter as tk
        icon_imgs = []
        for s in (16, 32, 38, 64, 128, 256):
            p = REPO_ROOT / f"assets/icons/{s}.png"
            if p.exists():
                icon_imgs.append(tk.PhotoImage(file=str(p)))  # tk reads png natively
        if icon_imgs:
            root.wm_iconphoto(True, *icon_imgs)
            root._icon_imgs = icon_imgs
        if sys.platform == "win32":
            ico = REPO_ROOT / "assets/icons/dexelect.ico"
            if ico.exists():
                root.iconbitmap(str(ico))
        root.minsize(900, 620)
    else:
        root.geometry("1000x700")

    frame = ctk.CTkFrame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    for i in range(rows):
        row = ctk.CTkFrame(frame)
        row.pack(fill="x", padx=6, pady=2)
        for j in range(3):
            ctk.CTkButton(row, text=f"button {i}-{j}", width=90, height=22).pack(
                side="left", padx=4)
        ctk.CTkEntry(row, width=90, height=22).pack(side="left", padx=4)
        ctk.CTkLabel(row, text="some label text " * 2).pack(side="left", padx=8)
    root.mainloop()


def main():
    if len(sys.argv) > 1:
        phase = sys.argv[1]
        title = PHASES[phase]
        if phase == "a":
            run_plain_tk(title, dpi_aware=False)
        elif phase == "b":
            run_plain_tk(title, dpi_aware=True)
        elif phase == "c":
            run_ctk(title)
        elif phase == "d":
            run_ctk(title, mitigated=True)
        elif phase == "e":
            run_ctk(title, dexelect_window=True)
        elif phase == "f":
            run_ctk(title, rows=25)
        return

    print("Windows will open one at a time. Drag + resize each by the")
    print("title bar/edges for a few seconds, close it, and note whether it")
    print("showed the slow-motion trail. The title names the phase.\n")
    for phase, title in PHASES.items():
        print(f"running {title} ...")
        subprocess.run([sys.executable, __file__, phase])
    print("\nDone. Report which phases were laggy vs smooth (e.g. 'A smooth,")
    print("B smooth, C laggy, D laggy').")


if __name__ == "__main__":
    main()
