# from mutagen.mp3 import MP3 # Option: Remove if no duration fallback planned
# from mutagen import MutagenError # Option: Remove if no duration fallback planned


try:
    from just_playback import Playback
    JUST_PLAYBACK_AVAILABLE = True
except ImportError:
    print("ERROR: Required library 'just_playback' not found. Please install it: pip install just_playback")
    JUST_PLAYBACK_AVAILABLE = False
except Exception as e:
    # Catch other potential errors during just_playback import/initialization
    print(f"ERROR: Failed to import or initialize just_playback: {e}")
    JUST_PLAYBACK_AVAILABLE = False

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
