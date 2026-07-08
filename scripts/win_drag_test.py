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
#
# Reading the result:
#   A laggy                 -> Tk/system level; no app code involved at all
#   B laggy, A smooth       -> SetProcessDpiAwareness(2) is the culprit
#   C laggy, A+B smooth     -> CustomTkinter machinery is the culprit
#   C laggy, D smooth       -> the mitigations work; wire them into the app
#   C+D laggy, A+B smooth   -> CustomTkinter's widget drawing itself
#
# Each phase runs in its own process because DPI awareness is process-wide and
# can only be set once.

import subprocess
import sys

PHASES = {
    "a": "PHASE A - plain Tk, DPI-unaware",
    "b": "PHASE B - plain Tk, per-monitor DPI aware",
    "c": "PHASE C - CustomTkinter, stock",
    "d": "PHASE D - CustomTkinter, Dexelect mitigations",
}
INSTRUCTIONS = "  |  drag + resize me for a few seconds, then close"


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


def run_ctk(title, mitigated):
    import customtkinter as ctk
    if mitigated:
        ctk.deactivate_automatic_dpi_awareness()
        ctk.set_appearance_mode("dark")
        ctk.ScalingTracker.update_loop_interval = 1000
        ctk.AppearanceModeTracker.update_loop_interval = 1000
    root = ctk.CTk()
    root.title(title + INSTRUCTIONS)
    root.geometry("1000x700")
    frame = ctk.CTkFrame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    for i in range(12):
        row = ctk.CTkFrame(frame)
        row.pack(fill="x", padx=6, pady=2)
        for j in range(3):
            ctk.CTkButton(row, text=f"button {i}-{j}").pack(side="left", padx=4)
        ctk.CTkLabel(row, text="some label text " * 3).pack(side="left", padx=8)
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
            run_ctk(title, mitigated=False)
        elif phase == "d":
            run_ctk(title, mitigated=True)
        return

    print("Four windows will open one at a time. Drag + resize each by the")
    print("title bar/edges for a few seconds, close it, and note whether it")
    print("showed the slow-motion trail. The title names the phase.\n")
    for phase, title in PHASES.items():
        print(f"running {title} ...")
        subprocess.run([sys.executable, __file__, phase])
    print("\nDone. Report which phases were laggy vs smooth (e.g. 'A smooth,")
    print("B smooth, C laggy, D laggy').")


if __name__ == "__main__":
    main()
