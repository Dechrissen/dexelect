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
#   PHASE G  like B (plain Tk, DPI-aware), but with ~150 widgets - separates
#            "CustomTkinter widgets are slow" from "many Tk windows are slow"
#
# Round 1 results, corrected (2026-07-08, Win10 19045): A smooth, B smooth;
# C, D, E, F all show the move trail AND resize lag, F worst by far. So both
# symptoms are CustomTkinter widgets scaling with count — not DPI, not the
# polls, not Dexelect's window setup. Phase G exists to separate "CTk themed
# widgets are the cost" from "any ~150 Tk child windows are the cost".
#
# Reading the result:
#   A laggy                 -> Tk/system level; no app code involved at all
#   B laggy, A smooth       -> SetProcessDpiAwareness(2) is the culprit
#   C laggy, A+B smooth     -> CustomTkinter machinery is the culprit
#   C laggy, D smooth       -> the mitigations work; wire them into the app
#   C+D laggy, A+B smooth   -> CustomTkinter's widget drawing itself
#   E trails on move        -> Dexelect's window setup (size/icons/minsize)
#   F trails on move        -> widget count is the move-trail ingredient
#   G trails like F         -> raw Tk child-window count; reduce total widgets
#   G smooth, F trails      -> CustomTkinter widgets specifically; swap the
#                              hardcoded-color CTk labels/frames for plain tk
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
    "g": "PHASE G - plain Tk, ~150 widgets",
    "h": "PHASE H - plain Tk + ttk.Notebook",
    "i": "PHASE I - plain Tk + Notebook + canvas-embedded content",
    "j": "PHASE J - plain Tk + Notebook + canvas + images/window icons",
    "k": "PHASE K - plain Tk + window icons only",
    "l": "PHASE L - plain Tk + displayed images only",
    "m": "PHASE M - plain Tk + PIL-loaded images (logo + sprites)",
}
INSTRUCTIONS = "  |  drag + resize me for a few seconds, then close"

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_plain_tk(title, dpi_aware, rows=12):
    if dpi_aware and sys.platform == "win32":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    import tkinter as tk
    root = tk.Tk()
    root.title(title + INSTRUCTIONS)
    root.geometry("1000x700")
    for i in range(rows):
        row = tk.Frame(root)
        row.pack(fill="x", padx=10, pady=2)
        for j in range(3):
            tk.Button(row, text=f"button {i}-{j}").pack(side="left", padx=4)
        tk.Entry(row, width=12).pack(side="left", padx=4)
        tk.Label(row, text="some label text " * 2).pack(side="left", padx=8)
    root.mainloop()


def run_app_like(title, notebook=False, canvas_embed=False, images=False, rows=25,
                 win_icons=False, photo_labels=False, pil_images=False):
    """Phase G plus Dexelect-tk ingredients, stacked one at a time, to find
    which one causes the residual ~0.5s move trail in the tk GUI (round 3)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title(title + INSTRUCTIONS)
    root.geometry("1000x800")

    if images:
        win_icons = True
        photo_labels = True

    if win_icons:
        icon_imgs = []
        for size in (16, 32, 38, 64, 128, 256):
            path = REPO_ROOT / f"assets/icons/{size}.png"
            if path.exists():
                icon_imgs.append(tk.PhotoImage(file=str(path)))
        if icon_imgs:
            root.wm_iconphoto(True, *icon_imgs)
            root._icons = icon_imgs
        ico = REPO_ROOT / "assets/icons/dexelect.ico"
        if sys.platform == "win32" and ico.exists():
            root.iconbitmap(str(ico))

    container = root
    if notebook:
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        tabs = []
        for name in ("Generate", "Spheres", "Config"):
            f = tk.Frame(nb)
            nb.add(f, text=name)
            tabs.append(f)
        tk.Text(tabs[1]).pack(fill="both", expand=True)
        for i in range(40):
            tk.Checkbutton(tabs[2], text=f"option {i}").pack(anchor="w")
        container = tabs[0]

    if canvas_embed:
        canvas = tk.Canvas(container, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(container, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set, yscrollincrement=1)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas)
        iid = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(iid, width=e.width))
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        container = inner

    photos = []
    if pil_images:
        # Load images exactly the way the real tk GUI does: PIL -> ImageTk.
        from PIL import Image, ImageTk
        logo_path = REPO_ROOT / "assets/logo/dexelect-logo-black.png"
        if logo_path.exists():
            src = Image.open(logo_path)
            w = 190
            h = round(w * src.height / src.width)
            photos.append(ImageTk.PhotoImage(src.resize((w, h), Image.LANCZOS)))
            tk.Label(container, image=photos[-1]).pack(anchor="w", padx=10, pady=4)
        sprite_dir = REPO_ROOT / "assets/sprites/gen1"
        sprite_files = sorted(sprite_dir.glob("*.png"))[:6] if sprite_dir.exists() else []
        for f in sprite_files:
            img = Image.open(f).resize((112, 112), Image.NEAREST)
            photos.append(ImageTk.PhotoImage(img))

    pil_sprites = photos[1:] if pil_images else []
    for i in range(rows):
        row = tk.Frame(container)
        row.pack(fill="x", padx=10, pady=2)
        for j in range(3):
            tk.Button(row, text=f"button {i}-{j}").pack(side="left", padx=4)
        tk.Entry(row, width=12).pack(side="left", padx=4)
        tk.Label(row, text="some label text " * 2).pack(side="left", padx=8)
        if photo_labels and i < 6:
            photo = tk.PhotoImage(width=112, height=112)
            photos.append(photo)
            tk.Label(row, image=photo).pack(side="left")
        if pil_sprites and i < len(pil_sprites):
            tk.Label(row, image=pil_sprites[i]).pack(side="left")
    root._photos = photos
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
        elif phase == "g":
            run_plain_tk(title, dpi_aware=True, rows=25)
        elif phase == "h":
            run_app_like(title, notebook=True)
        elif phase == "i":
            run_app_like(title, notebook=True, canvas_embed=True)
        elif phase == "j":
            run_app_like(title, notebook=True, canvas_embed=True, images=True)
        elif phase == "k":
            run_app_like(title, win_icons=True)
        elif phase == "l":
            run_app_like(title, photo_labels=True)
        elif phase == "m":
            run_app_like(title, pil_images=True)
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
