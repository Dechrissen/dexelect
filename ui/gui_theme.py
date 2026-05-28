import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colour palette — dark minimal, single soft blue accent (matches app icon gradient)
C_BG        = "#111111"   # near-black main background
C_PANEL     = "#171717"   # slightly lifted panel background
C_SIDEBAR   = "#141414"   # sidebar (subtle distinction from main)
C_ACCENT    = "#40b3d9"   # soft blue — sole accent colour
C_ACCENT2   = "#1c3040"   # dark blue — hover states, dividers, secondary fills
C_ACCENT_DIM = "#152535"  # very subtle blue tint — secondary button faces
C_ACCENT2_DIM = "#101e2a"  # dimmed dark blue — disabled button faces
C_TEXT      = "#e0e0e0"   # primary text (off-white, not harsh)
C_MUTED     = "#b8b8b8"   # secondary / muted text
C_BTN_TEXT  = "#071828"   # dark text for use on blue (accent) buttons
C_SUCCESS   = "#40b3d9"   # same as accent for success messages
C_WARNING   = "#c8a96e"   # muted amber — kept for warnings only
C_TITLE     = "#d4a84b"   # muted gold — app title
C_CARD      = "#222222"   # card face background (lifted above C_PANEL)
C_CARD_BORDER = "#333333" # subtle grey card border (no accent colour)
C_ENTRY_BG  = "#0e0e0e"   # input field background (slightly darker than C_BG)
C_SELECT_BG = "#ffffff"   # text selection background
C_SELECT_FG = "#000000"   # text selection foreground
C_DIM       = "#4a4a4a"   # heavily muted — inactive/disabled text

FONT_TITLE     = ("Roboto", 24, "bold")
FONT_APP_TITLE = ("Roboto", 24, "bold")
FONT_HEADER         = ("Roboto", 15, "bold")
FONT_SECTION_HEADER = ("Roboto", 17, "bold")
FONT_BTN    = ("Roboto", 15)
FONT_BODY   = ("Roboto", 13)
FONT_SMALL  = ("Roboto", 11)
FONT_MONO        = ("Courier New", 13)
FONT_MONO_HEADER = ("Courier New", 15, "bold")

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
