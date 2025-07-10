import json
import os

import customtkinter as ctk

from config.consts import CONFIG_PATH


class StoredUiState:
    def __init__(self, rate: int = 0, pitch: int = 0, voice: str = None, dark: bool = None):
        if dark is None:
            dark = ctk.get_appearance_mode() == "Dark"
        self.rate = rate
        self.pitch = pitch
        self.voice = voice
        self.dark = dark


def load_ui_state() -> StoredUiState:
    """Loads audio settings from a JSON configuration file or returns defaults."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                defaults = StoredUiState()
                data = json.load(f)
                rate = int(data.get("rate", defaults.rate))
                pitch = int(data.get("pitch", defaults.pitch))
                voice = data.get("voice", defaults.voice)
                dark = data.get("dark", defaults.dark)
                return StoredUiState(rate=rate, pitch=pitch, voice=voice, dark=dark)
    except Exception as e:
        print(f"WARN: Failed to load audio settings from JSON: {e}")
    return StoredUiState()  # Default settings if file missing or error


def store_ui_state(voice:str, rate:int, pitch:int):
    """Saves the current audio settings to a file."""
    if (not voice
            or voice == "Select Voice"
            or "Loading" in voice
            or "No match" in voice
            or voice == "No voices found"):
        voice = None

    settings = StoredUiState(rate, pitch, voice)
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings.__dict__, f)
        print(f"INFO: Audio settings saved to {CONFIG_PATH}")
    except Exception as e:
        print(f"ERROR: Failed to save audio settings: {e}")