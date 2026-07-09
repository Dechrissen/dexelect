import sys, os

def resource_path(relative_path):
    """Works for both dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def format_duration(seconds):
    """Formats as 'XXXms' (zero-padded) under 1s, else 'X.XXs'."""
    if seconds < 1:
        return f"{seconds * 1000:03.0f}ms"
    return f"{seconds:.2f}s"