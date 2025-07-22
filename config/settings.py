import json
import os

import re
import customtkinter as ctk

from config.consts import CONFIG_PATH


class StoredUiState:
    def __init__(self, 
                 rate: int = 0,
                 pitch: int = 0, 
                 voice: str = None,
                 dark: bool = None,
                 auto_play: bool = False,
                 split: bool = False,
                 words_in_chunk: int = 300,
                 chunk_regex: str = r".*(\.|\?|!|:).*") :
        if dark is None:
            dark = ctk.get_appearance_mode() == "Dark"
        self.rate = rate
        self.pitch = pitch
        self.voice = voice
        self.dark = dark
        self.auto_play = auto_play
        self.split = split
        self.words_in_chunk = words_in_chunk
        self.chunk_regex = chunk_regex


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
                auto_play = data.get("auto_play", defaults.auto_play)
                split = data.get("split", defaults.split)
                words_in_chunk = int(data.get("words_in_chunk", defaults.words_in_chunk))
                chunk_regex = data.get("chunk_regex", defaults.chunk_regex)
                return StoredUiState(rate=rate,
                                     pitch=pitch,
                                     voice=voice,
                                     dark=dark,
                                     auto_play=auto_play,
                                     split=split,
                                     words_in_chunk=words_in_chunk,
                                     chunk_regex=chunk_regex)
    except Exception as e:
        print(f"WARN: Failed to load audio settings from JSON: {e}")
    return StoredUiState()  # Default settings if file missing or error


def store_ui_state(voice:str, rate:int, pitch:int, auto_play:bool, split:bool, words_in_chunk:int, chunk_regex:str):
    """Saves the current audio settings to a file."""
    if (not voice
            or voice == "Select Voice"
            or "Loading" in voice
            or "No match" in voice
            or voice == "No voices found"):
        voice = None

    # Test if chunk_regex is a valid regular expression
    try:
        re.compile(chunk_regex)
    except re.error as e:
        print(f"ERROR: Invalid chunk_regex: {e}")
        chunk_regex = r".*(\.|\?|!|:).*"  # fallback to default

    settings = StoredUiState(rate=rate,
                             pitch=pitch,
                             voice=voice,
                             auto_play=auto_play,
                             split=split,
                             words_in_chunk=words_in_chunk,
                             chunk_regex=chunk_regex)
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings.__dict__, f)
        print(f"INFO: Audio settings saved to {CONFIG_PATH}")
    except Exception as e:
        print(f"ERROR: Failed to save audio settings: {e}")