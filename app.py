import asyncio
import os
import tempfile
import threading
import time
import re
from typing import List

import edge_tts
from pyglet.media import load
from pyglet.media import Player

import file_utils.audio_files
from config.consts import AUDIO_UPDATE_INTERVAL_MS, PYGLET_AVAILABLE
from config.settings import load_ui_state, StoredUiState, store_ui_state
from ui.base import EdgeTTSUi, UIStatusUpdate


# --- Main Application ---
class EdgeTTSApp():
    """
    GUI application to generate Text-to-Speech using Microsoft Edge TTS
    and play it back using the pyglet library.
    Follows system theme initially, with a toggle override.
    Includes Textbox placeholder simulation.
    """
    def __init__(self):
        # Initialize Audio Player

        self.player: Player | None = None
        self.pyglet_initialized: bool = False
        if PYGLET_AVAILABLE:
            try:
                self.reinitialize_player()
                self.pyglet_initialized = True
                print("INFO: pyglet initialized successfully.")
            except Exception as e:
                print(f"ERROR: Failed to initialize pyglet: {e}")
                self.pyglet_initialized = False


        # Application State
        self.voices_dict: dict[str, str] = {} # {Display Name: ShortName}
        self._all_voice_display_names: list[str] = []
        self.audio_file_path: list[str] = []# Path to the temporary audio file
        self._after_id_update_progress: str | None = None # ID for the 'after' job updating progress
        self._slider_being_dragged: bool = False # Flag if user is dragging the progress slider
        self.currently_playing_file_index = 0 # Index of the currently playing file in audio_file_path
        self.last_index = -1

        ui_state = load_ui_state()
        self.ui = EdgeTTSUi(self, ui_state)

        # Set initial placeholder state after color fetch attempt
        if self.pyglet_initialized:
            self.ui.update_status("Loading voices...")
            self.load_voices_async(ui_state)
        else:
            self.ui.update_status("❌ Error: Audio library init failed. Audio disabled.")
            self.ui.set_ui_state('error_no_audio')



    def reinitialize_player(self):
        self.player = Player()
        self.currently_playing_file_index = 0 # Reset current playing index
        self.last_index = -1
        @self.player.event
        def on_eos():
            self.currently_playing_file_index += 1
            if self.player.playing:
                self.ui.after(0, lambda: self.ui.update_status(f"▶ Playing audio({self.currently_playing_file_index + 1}/{len(self.audio_file_path)})", UIStatusUpdate.PLAYBACK))



    def check_current_audio_state(self):
        """ Determine current state based on existing conditions."""
        current_state = 'idle'  # Default
        # Check if we have generated audio
        if self.audio_file_path:
            if self.pyglet_initialized and self.player:
                if self.player.playing:
                    current_state = 'playing'
                else:
                    current_state = 'paused'
            else:
                current_state = 'generated'
        return current_state

    def filter_voices(self) -> list[str]:
        """Filters the list of voice display names based on search input."""
        if not hasattr(self.ui, 'voice_search_entry'): return []
        search_term = self.ui.voice_search_entry.get().lower()
        if not search_term: return self._all_voice_display_names # Return all if search is empty
        # Return names containing the search term (case-insensitive)
        return [name for name in self._all_voice_display_names if search_term in name.lower()]

    # --- Asynchronous Operations & Threading ---
    def load_voices_async(self, ui_state: StoredUiState = None):
        """Starts a thread to load the voice list asynchronously."""
        self.ui.set_ui_state('loading')
        self.ui.update_status("Loading voice list...")
        if ui_state:
            thread = threading.Thread(target=self._run_async_task, args=(self._load_voices_task, ui_state.voice), daemon=True)
        else:
            thread = threading.Thread(target=self._run_async_task, args=(self._load_voices_task,), daemon=True)
        thread.start()

    def start_generate_speech_thread(self):
        """Starts a thread to generate TTS audio asynchronously."""
        self._delete_temp_audio_file() # Delete old temp file first
        if self.pyglet_initialized and self.player and self.player.playing:
             self.stop_audio() # Stop playback if currently active

        # Use the dedicated function to get input text, ignoring placeholder
        text = self.ui.get_input_text()
        selected_voice_display = self.ui.voice_dropdown.get()

        # Input validation
        if not text: # Check if actual text is empty
            self.ui.update_status("❌ Error: Text input is empty."); self.ui.set_ui_state('idle'); return
        if not selected_voice_display or "Loading" in selected_voice_display or "No match" in selected_voice_display or selected_voice_display not in self.voices_dict:
            self.ui.update_status("❌ Error: Please select a valid voice."); self.ui.set_ui_state('idle'); return

        voice_short_name = self.voices_dict[selected_voice_display]
        rate = int(self.ui.rate_slider.get())
        pitch = int(self.ui.pitch_slider.get())
        rate_str = f"{rate:+d}%"
        pitch_str = f"{pitch:+d}Hz"

        self.ui.set_ui_state('generating')
        self.ui.update_status("Generating audio...", UIStatusUpdate.GENERATOR)
        chunked_text = self._chunk_text(text, int(self.ui.min_words_entry.get()), self.ui.chunk_sep_entry.get()) if self.ui.split_chunks_checkbox.get() else [text]
        thread = threading.Thread(target=self._run_async_task,
                                  args=(self._generate_audio_task, chunked_text, voice_short_name, rate_str, pitch_str),
                                  daemon=True)
        thread.start()

    @staticmethod
    def _chunk_text(text: str, min_words: int, chunk_separator_regex: str) -> List[str]:
        words = re.findall(r'\S+', text)
        chunks = []
        i = 0
        n = len(words)
        sep_pattern = re.compile(chunk_separator_regex) if chunk_separator_regex else None

        while i < n:
            start = i
            end = min(i + min_words, n)
            # If no separator regex, just take min_words at a time
            if not sep_pattern:
                chunks.append(' '.join(words[start:end]))
                i = end
            else:
                # Always take at least min_words, then continue until separator is found or end
                j = end
                while j < n and not sep_pattern.fullmatch(words[j]):
                    j += 1
                # If found, include the separator word
                if j < n:
                    j += 1
                chunks.append(' '.join(words[start:j]))
                i = j
        return [chunk for chunk in chunks if chunk]

    def _run_async_task(self, coro, *args):
        """Runs an asyncio coroutine in a new event loop (suitable for threads)."""
        try:
            asyncio.run(coro(*args))
        except Exception as e:
            print(f"ERROR: Exception in async task thread: {e}")
            # Update status on the main thread
            self.ui.after(0, lambda: self.ui.update_status(f"❌ Error during async operation: {e}"))
            self.ui.after(0, lambda: self.ui.set_ui_state('idle')) # Revert to idle state on error

    async def _load_voices_task(self, start_voice: str = None):
        """Coroutine to fetch the list of voices from edge-tts."""
        try:
            voices = await edge_tts.list_voices()
            # Sort by Locale, then ShortName for a structured display
            voices.sort(key=lambda v: (v['Locale'], v['ShortName']))
            # Create a dictionary for quick lookup {DisplayName: ShortName}
            self.voices_dict = {f"{v['FriendlyName']} ({v['Locale']}, {v['Gender']})": v['ShortName'] for v in voices}
            self._all_voice_display_names = list(self.voices_dict.keys())
            # Update the UI on the main thread when done
            self.ui.after(0, self.ui.update_voice_dropdown_ui, self._all_voice_display_names, start_voice)
        except Exception as e:
            print(f"ERROR: Failed to load voices: {e}")
            self.ui.after(0, lambda: self.ui.update_status(f"❌ Error loading voices: {e}"))
            self.ui.after(0, lambda: self.ui.set_ui_state('idle')) # Set to idle if loading fails


    async def _generate_audio_task(self, chunks: List[str], voice_short_name: str, rate_str: str, pitch_str: str):
        """Coroutine to generate audio and save it to a temporary file."""
        tmp_path = None
        self.audio_file_path = [] # Reset the audio file path list before generation
        count = 1
        for text in chunks:
            print(f"Chunk {count}/{len(chunks)}: Generating audio for text: {text[:50]}...")  # Log first 50 chars
            try:
                communicate = edge_tts.Communicate(text=text, voice=voice_short_name, rate=rate_str, pitch=pitch_str)
                # Create a temporary file (it won't be deleted automatically with delete=False)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", prefix="edge_tts_") as tmp_file:
                    tmp_path = tmp_file.name

                # Save the audio stream from edge-tts to the created temp file
                await communicate.save(tmp_path)


                # Verify that the file was created and is not empty
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                    self.audio_file_path.append(tmp_path) # Store the path if valid
                    print(f"INFO: Audio saved to temp file: {self.audio_file_path}")
                    message = "Chunk " + str(count) + " out of " + str(len(chunks)) + " generated successfully."
                    self.ui.after(0, lambda: self.ui.update_status(message, UIStatusUpdate.GENERATOR))
                    count += 1
                    self._on_audio_generated(tmp_path, count)
                    # Schedule the _on_audio_generated call on the main thread
                else:
                     # File is missing or empty
                     print(f"ERROR: Temp audio file missing or empty after generation: {tmp_path}")
                     if tmp_path and os.path.exists(tmp_path): # Attempt to remove if it exists
                         try: os.remove(tmp_path)
                         except OSError as rm_err: print(f"WARN: Could not remove invalid temp file {tmp_path}: {rm_err}")
                     break

            except Exception as e:
                # Catch any other exceptions during generation
                print(f"ERROR: Exception during audio generation: {e}")
                if tmp_path and os.path.exists(tmp_path): # Attempt cleanup
                     try: os.remove(tmp_path)
                     except OSError as rm_err: print(f"WARN: Could not remove temp file {tmp_path}: {rm_err}")
                self.ui.after(0, lambda: self.ui.update_status(f"❌ Error generating audio: {e}"))
                self.ui.after(0, lambda: self.ui.set_ui_state('idle'))
                self.audio_file_path = [] # Clear the path since no valid audio was generated
                return
        if self.audio_file_path:
            if self.player.playing:
                self.ui.update_status("", UIStatusUpdate.GENERATOR)
            else:
                self.ui.update_status("✅ Audio generated! Press Play.", UIStatusUpdate.GENERATOR)
            print(f"INFO: Successfully generated audio file(s): {self.audio_file_path}")
        else:
            self.ui.after(0, lambda: self.ui.update_status("❌ Error: Failed to generate valid audio file."))
            self.ui.after(0, lambda: self.ui.set_ui_state('idle'))

    def _on_audio_generated(self, path: str, index):
        """Callback on the main thread after the temporary audio file is created."""
        print(f"INFO: Loading generated audio file: {self.audio_file_path}")
        if index < self.last_index:
            raise ValueError(f"Index {index} is less than last index {self.last_index}. This should not happen.")
        else:
            self.last_index = index

        if not self.pyglet_initialized or not self.player:
            self.ui.update_status("❌ Error: Audio generated, but player is not ready."); self.ui.set_ui_state('error_no_audio'); return
        if not self.audio_file_path:
             self.ui.update_status("❌ Error: Generated audio file path is invalid or missing."); self.ui.set_ui_state('idle'); return

        try:
            # Load the audio file into pyglet
            if os.path.exists(path):
                self.player.queue(load(path, streaming=False))
            else:
                raise FileNotFoundError(f"Generated audio file not found: {path}")
            # Add a small delay before getting duration, sometimes needed after load
            if self.player.playing:
                self.ui.after(0, lambda: self.ui.update_status(f"▶ Playing audio({self.currently_playing_file_index + 1}/{len(self.audio_file_path)})", UIStatusUpdate.PLAYBACK))
            self.ui.after(50, self._finish_audio_load)

        except Exception as e:
            # Catch errors during file loading *initiation* into pyglet
                print(f"ERROR: Failed to initiate loading audio file into player: {e}")
                self.ui.update_status(f"❌ Error loading audio: {e}")
                self.ui.set_ui_state('error_audio_format')
                self._delete_temp_audio_file() # Delete the problematic file


    def _finish_audio_load(self):
        """Gets duration and updates UI after pyglet has loaded the file."""
        if not self.pyglet_initialized or not self.player: return
        try:
            print(f"INFO: Audio file loaded.")

            self.ui.set_ui_state('generated') # State: ready to be played
            if self.ui.auto_play.get() and not self.player.playing:
                self.ui.toggle_play_pause()

        except Exception as e:
             # Catch errors getting duration or updating UI
             print(f"ERROR: Failed to finalize audio load (get duration/update UI): {e}")
             self.ui.update_status(f"❌ Error finalizing audio load: {e}")
             self.ui.set_ui_state('error_audio_format')
             self._delete_temp_audio_file()


    # --- Audio Playback Controls ---
    def toggle_play_pause(self):
        """Starts, pauses, or resumes audio playback."""
        if not self.pyglet_initialized or not self.player:
            self.ui.update_status("❌ Error: Audio player not ready."); return
        # Need a valid audio file and duration > 0 to play/pause
        if not self.audio_file_path:
            self.ui.update_status("❌ Error: No valid audio loaded."); return

        try:
            if self.player.playing:
                self.player.pause()
                self.ui.set_ui_state('paused'); self.ui.update_status("⏸ Audio paused.", UIStatusUpdate.PLAYBACK)
            else: # If not playing/paused (i.e., stopped or initial state)
                # Ensure seeked to start if stopped previously? pyglet usually resumes
                # self.player.seek(0) # Optional: uncomment to always start from beginning after stop
                self.player.play() # Start from last position (or beginning if stopped/newly loaded)
                self.ui.set_ui_state('playing')
                self.ui.update_status(f"▶ Playing audio({self.currently_playing_file_index + 1}/{len(self.audio_file_path)})", UIStatusUpdate.PLAYBACK)
        except Exception as e:
            print(f"ERROR: Exception during toggle_play_pause: {e}")
            self.ui.update_status(f"❌ Playback Error: {e}")
            self.ui.set_ui_state('generated') # Revert to generated state on error

    def stop_audio(self):
        """Stops audio playback and resets position to the beginning."""
        if not self.pyglet_initialized or not self.player: return

        self.player.delete()
        self.reinitialize_player()
        if self.audio_file_path:
            for path in self.audio_file_path:
                if os.path.exists(path):
                    self.player.queue(load(path, streaming=False))


        # Only stop if currently playing or paused
        if self.player.playing:
            try:
                # Reset UI to initial position
                if hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                    self.ui.progress_slider.set(0)
                self.ui.set_ui_state('generated') # State returns to 'ready to play'
                self.ui.update_status("⏹ Audio stopped.",  UIStatusUpdate.PLAYBACK)
            except Exception as e:
                print(f"ERROR: Exception during stop_audio: {e}")
                self.ui.update_status(f"❌ Error stopping audio: {e}")
                self.ui.set_ui_state('generated') # Still try to reset state
        else:
            # If already stopped, ensure UI is consistent
            if hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                 self.ui.progress_slider.set(0)
            self.ui.set_ui_state('generated')

    # --- Seeking Logic ---
    def _can_seek(self) -> bool:
        """Checks if the current conditions allow seeking."""
        # Check player state too
        player_ready = self.pyglet_initialized and self.player and self.player.source is not None
        return player_ready and self.audio_file_path# Check file path


    def _perform_seek(self, target_seek_time_sec: float):
        """Core logic for seeking: stop updater, seek, update UI, schedule updater restart."""
        if not self._can_seek(): return # Do nothing if seeking isn't possible

        try:
            # Perform seek using pyglet
            self.player.seek(target_seek_time_sec)

        except Exception as e:
             # Catch errors during the seek operation
             print(f"ERROR: Exception during seek operation: {e}")
             self.ui.update_status(f"❌ Error seeking: {e}")
             # Still try to schedule updater restart check if it was playing


    def seek_relative(self, seconds_to_add: int):
        """Jumps forward or backward by a specified number of seconds."""
        if not self._can_seek(): return
        current_pos_sec = self.player.time
        target_seek_time_sec = current_pos_sec + seconds_to_add
        self._perform_seek(target_seek_time_sec) # Use the helper




    # --- Cleanup ---
    def _delete_temp_audio_file(self):
        """Deletes the temporary audio file if it exists, with retries."""
        paths_to_delete = self.audio_file_path
        if paths_to_delete:
            # Clear internal references *before* attempting deletion
            # Stop the player if it's active and loaded this file
            self.audio_file_path = []
            if self.pyglet_initialized and self.player:
                 # Check if the player's source matches the file to delete
                 # Note: pyglet doesn't directly expose the loaded file path easily.
                 # We assume if a file exists, the player *might* be using it.
                 print(f"INFO: Stopping player before attempting to delete potential source file.")
                 try:
                     self.player.delete() # Stop playback and release resources
                     self.reinitialize_player() # Reinitialize player to reset state
                     time.sleep(0.15) # Give OS time to release handle
                 except Exception as e:
                     # Ignore errors if player is already stopped or invalid
                     if "Playback has not been initialized" not in str(e):
                          print(f"WARN: Exception while stopping player before delete: {e}")
            for path_to_delete in paths_to_delete:
                print(f"INFO: Preparing to delete temp file: {path_to_delete}")
                # Attempt to delete the physical file with retries
                max_retries = 4
                retry_delay = 0.25 # seconds
                for attempt in range(max_retries):
                    try:
                        os.remove(path_to_delete)
                        print(f"INFO: Deleted temp file: {path_to_delete}")
                        path_to_delete = None # Mark as deleted successfully
                        break # Exit loop if successful
                    except PermissionError as e:
                        print(f"WARN: Attempt {attempt + 1}/{max_retries} - PermissionError removing temp file {path_to_delete}: {e}. Retrying...")
                        time.sleep(retry_delay)
                    except OSError as e:
                        print(f"ERROR: Attempt {attempt + 1}/{max_retries} - OSError removing temp file {path_to_delete}: {e}. Retrying...")
                        time.sleep(retry_delay)
                    except Exception as e:
                        print(f"ERROR: Unexpected exception deleting temp file {path_to_delete} (Attempt {attempt + 1}): {e}")
                        break # Don't retry on unexpected errors

                if path_to_delete and os.path.exists(path_to_delete):
                    print(f"ERROR: Failed to delete temp file after {max_retries} retries: {path_to_delete}")
                    # Log the failure, internal path is already None.


    def on_closing(self):
        store_ui_state(self.ui.voice_dropdown.get(), int(self.ui.rate_slider.get()), int(self.ui.pitch_slider.get()), self.ui.auto_play.get(), self.ui.split_chunks_checkbox.get(), int(self.ui.min_words_entry.get()), self.ui.chunk_sep_entry.get())

        """Called when the application window is closed."""
        print("INFO: Closing application...")

        # Stop the player if active
        if self.pyglet_initialized and self.player:
             try:
                  if self.player:
                      self.player.delete() # Stop playback and release resources
             except Exception as e:
                  # Ignore "Playback has not been initialized" error if player failed
                  if "Playback has not been initialized" not in str(e):
                     print(f"WARN: Exception stopping player during close: {e}")

        # Delete the last temporary file
        print("INFO: Cleaning up temporary audio file...")
        self._delete_temp_audio_file()

        # I Removed the problematic after_cancel loop entirely
        # The _stop_progress_updater() call above already handles the main updater
        # Got exceptions during the after_cancel call otherwise.
        if hasattr(self.ui,'destroy'):
            self.ui.destroy() # Close the Tkinter window

    def save_audio(self):
        file_utils.audio_files.AudioSaver(self.audio_file_path, self.ui, self.pyglet_initialized).save_audio()