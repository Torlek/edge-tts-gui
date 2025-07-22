# from mutagen.mp3 import MP3 # Option: Remove if no duration fallback planned
# from mutagen import MutagenError # Option: Remove if no duration fallback planned


try:
    from pyglet.media import Player
    PYGLET_AVAILABLE = True
except ImportError:
    print("ERROR: Required library 'pyglet' not found. Please install it: pip install pyglet")
    PYGLET_AVAILABLE = False
except Exception as e:
    # Catch other potential errors during pyglet import/initialization
    print(f"ERROR: Failed to import or initialize pyglet: {e}")
    PYGLET_AVAILABLE = False

# --- Constants ---
# DEFAULT_APPEARANCE_MODE = "Light" # REMOVED - Now starts with "System"
# Choose a placeholder color that works reasonably well in both light/dark modes
AUDIO_UPDATE_INTERVAL_MS = 100 # Progress bar update interval (ms)
MIN_WINDOW_WIDTH = 700
MIN_WINDOW_HEIGHT = 650
SEEK_INTERVAL_SECONDS = 5 # Number of seconds to jump forward/backward
TEXTBOX_PLACEHOLDER_TEXT = "Enter text here or load from a file..."
TEXTBOX_PLACEHOLDER_COLOR = "#888888" # Medium-Gray
CONFIG_PATH = "ui_state.json"
