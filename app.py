import asyncio
import os
import tempfile
import threading
import time

import edge_tts
from just_playback import Playback

import file_utils.audio_files
from config.consts import AUDIO_UPDATE_INTERVAL_MS, JUST_PLAYBACK_AVAILABLE
from config.settings import load_ui_state, StoredUiState, store_ui_state
from ui.base import EdgeTTSUi


# --- Main Application ---
class EdgeTTSApp():
    """
    GUI application to generate Text-to-Speech using Microsoft Edge TTS
    and play it back using the just_playback library.
    Follows system theme initially, with a toggle override.
    Includes Textbox placeholder simulation.
    """
    def __init__(self):
        # Initialize Audio Player

        self.player: Playback | None = None
        self.just_playback_initialized: bool = False
        if JUST_PLAYBACK_AVAILABLE:
            try:
                self.player = Playback()
                self.just_playback_initialized = True
                print("INFO: just_playback initialized successfully.")
            except Exception as e:
                print(f"ERROR: Failed to initialize just_playback: {e}")
                self.just_playback_initialized = False

        # Application State
        self.voices_dict: dict[str, str] = {} # {Display Name: ShortName}
        self._all_voice_display_names: list[str] = []
        self.audio_file_path: str | None = None # Path to the temporary audio file
        self.audio_duration: float = 0.0 # Audio duration in seconds
        self._after_id_update_progress: str | None = None # ID for the 'after' job updating progress
        self._slider_being_dragged: bool = False # Flag if user is dragging the progress slider

        ui_state = load_ui_state()
        self.ui = EdgeTTSUi(self, ui_state)

        # Set initial placeholder state after color fetch attempt
        if self.just_playback_initialized:
            self.ui.update_status("Loading voices...")
            self.load_voices_async(ui_state)
        else:
            self.ui.update_status("❌ Error: Audio library init failed. Audio disabled.")
            self.ui.set_ui_state('error_no_audio')




    def check_current_audio_state(self):
        """ Determine current state based on existing conditions."""
        current_state = 'idle'  # Default
        # Check if we have generated audio
        if self.audio_file_path and os.path.exists(self.audio_file_path):
            if self.just_playback_initialized and self.player:
                if self.player.playing:
                    current_state = 'playing'
                elif self.player.paused:
                    current_state = 'paused'
                else:
                    current_state = 'generated'
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
        if self.just_playback_initialized and self.player and (self.player.playing or self.player.paused):
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
        self.ui.update_status("Generating audio...")
        thread = threading.Thread(target=self._run_async_task,
                                  args=(self._generate_audio_task, text, voice_short_name, rate_str, pitch_str),
                                  daemon=True)
        thread.start()

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


    async def _generate_audio_task(self, text: str, voice_short_name: str, rate_str: str, pitch_str: str):
        """Coroutine to generate audio and save it to a temporary file."""
        tmp_path = None
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice_short_name, rate=rate_str, pitch=pitch_str)
            # Create a temporary file (it won't be deleted automatically with delete=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", prefix="edge_tts_") as tmp_file:
                tmp_path = tmp_file.name

            # Save the audio stream from edge-tts to the created temp file
            await communicate.save(tmp_path)

            # Verify that the file was created and is not empty
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                self.audio_file_path = tmp_path # Store the path if valid
                print(f"INFO: Audio saved to temp file: {self.audio_file_path}")
                # Schedule the _on_audio_generated call on the main thread
                self.ui.after(0, self._on_audio_generated)
            else:
                 # File is missing or empty
                 print(f"ERROR: Temp audio file missing or empty after generation: {tmp_path}")
                 if tmp_path and os.path.exists(tmp_path): # Attempt to remove if it exists
                     try: os.remove(tmp_path)
                     except OSError as rm_err: print(f"WARN: Could not remove invalid temp file {tmp_path}: {rm_err}")
                 self.audio_file_path = None
                 self.ui.after(0, lambda: self.ui.update_status("❌ Error: Failed to generate valid audio file."))
                 self.ui.after(0, lambda: self.ui.set_ui_state('idle'))

        except edge_tts.exceptions.NoAudioGeneratedError as e:
             # Specific error from edge-tts if no audio is produced (e.g., empty text)
             print(f"ERROR: Edge TTS reported no audio generated: {e}")
             if tmp_path and os.path.exists(tmp_path): # Clean up temp file if created
                 try: os.remove(tmp_path)
                 except OSError as rm_err: print(f"WARN: Could not remove temp file {tmp_path}: {rm_err}")
             self.audio_file_path = None
             # Use get_input_text for the message check
             self.ui.after(0, lambda: self.ui.update_status("❌ Error: No audio generated (is input text empty?)."))
             self.ui.after(0, lambda: self.ui.set_ui_state('idle'))
        except Exception as e:
            # Catch any other exceptions during generation
            print(f"ERROR: Exception during audio generation: {e}")
            if tmp_path and os.path.exists(tmp_path): # Attempt cleanup
                 try: os.remove(tmp_path)
                 except OSError as rm_err: print(f"WARN: Could not remove temp file {tmp_path}: {rm_err}")
            self.audio_file_path = None
            self.ui.after(0, lambda: self.ui.update_status(f"❌ Error generating audio: {e}"))
            self.ui.after(0, lambda: self.ui.set_ui_state('idle'))

    def _on_audio_generated(self):
        """Callback on the main thread after the temporary audio file is created."""
        print(f"INFO: Loading generated audio file: {self.audio_file_path}")
        if not self.just_playback_initialized or not self.player:
            self.ui.update_status("❌ Error: Audio generated, but player is not ready."); self.ui.set_ui_state('error_no_audio'); return
        if not self.audio_file_path or not os.path.exists(self.audio_file_path):
             self.ui.update_status("❌ Error: Generated audio file path is invalid or missing."); self.ui.set_ui_state('idle'); return

        try:
            # Stop the player if it's playing something else before loading the new file
            if self.player.playing or self.player.paused:
                self.player.stop()

            # Load the audio file into just_playback
            self.player.load_file(self.audio_file_path)
            # Add a small delay before getting duration, sometimes needed after load
            self.ui.after(50, self._finish_audio_load)

        except Exception as e:
            # Catch errors during file loading *initiation* into just_playback
            print(f"ERROR: Failed to initiate loading audio file into player: {e}")
            self.ui.update_status(f"❌ Error loading audio: {e}")
            self.audio_duration = 0
            self.ui.set_ui_state('error_audio_format')
            self._delete_temp_audio_file() # Delete the problematic file


    def _finish_audio_load(self):
        """Gets duration and updates UI after just_playback has loaded the file."""
        if not self.just_playback_initialized or not self.player: return
        try:
            self.audio_duration = self.player.duration # Get duration from the player
            print(f"INFO: Audio file loaded. Duration: {self.audio_duration:.2f}s")

            # Check if the duration is valid
            if self.audio_duration > 0:
                self.ui.update_status("✅ Audio generated! Press Play.")
                self.ui.set_ui_state('generated') # State: ready to be played
                if hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                    self.ui.progress_slider.set(0) # Reset slider
                self.ui.update_time_label(0, self.audio_duration) # Update time label
                if self.ui.auto_play.get():
                    self.ui.toggle_play_pause()
            else:
                # Invalid duration (0 or negative)
                print(f"WARN: Audio file loaded but reports invalid duration ({self.audio_duration:.2f}s). File might be corrupted.")
                self.ui.update_status("❌ Error: Audio file seems invalid (0 duration).")
                self.ui.set_ui_state('error_audio_format') # Specific error state
                self._delete_temp_audio_file() # Delete the invalid file

        except Exception as e:
             # Catch errors getting duration or updating UI
             print(f"ERROR: Failed to finalize audio load (get duration/update UI): {e}")
             self.ui.update_status(f"❌ Error finalizing audio load: {e}")
             self.audio_duration = 0
             self.ui.set_ui_state('error_audio_format')
             self._delete_temp_audio_file()


    # --- Audio Playback Controls ---
    def toggle_play_pause(self):
        """Starts, pauses, or resumes audio playback."""
        if not self.just_playback_initialized or not self.player:
            self.ui.update_status("❌ Error: Audio player not ready."); return
        # Need a valid audio file and duration > 0 to play/pause
        if not self.audio_file_path or not os.path.exists(self.audio_file_path) or self.audio_duration <= 0:
            # Attempt reload if file exists but duration is invalid (maybe previous load failed)
            if self.audio_file_path and os.path.exists(self.audio_file_path):
                 print("WARN: Audio has invalid duration, attempting reload...")
                 self._on_audio_generated() # Try the loading process again
                 # Note: _on_audio_generated is async in effect due to _finish_audio_load,
                 # so we can't immediately check duration here. Assume it will work or fail later.
                 return # Exit, let the reload process handle the state
            else:
                 self.ui.update_status("❌ Error: No valid audio loaded."); return

        try:
            if self.player.playing:
                self.player.pause()
                self._stop_progress_updater() # Stop updates when paused
                self.ui.set_ui_state('paused'); self.ui.update_status("⏸ Audio paused.")
            elif self.player.paused:
                self.player.resume()
                self.ui.set_ui_state('playing'); self.ui.update_status("▶ Resuming audio...")
                self._start_progress_updater() # Resume updates
            else: # If not playing/paused (i.e., stopped or initial state)
                # Ensure seeked to start if stopped previously? just_playback usually resumes
                # self.player.seek(0) # Optional: uncomment to always start from beginning after stop
                self.player.play() # Start from last position (or beginning if stopped/newly loaded)
                self.ui.set_ui_state('playing'); self.ui.update_status("▶ Playing audio...")
                self._start_progress_updater() # Start progress updates
        except Exception as e:
            print(f"ERROR: Exception during toggle_play_pause: {e}")
            self.ui.update_status(f"❌ Playback Error: {e}")
            self.ui.set_ui_state('generated') # Revert to generated state on error

    def stop_audio(self):
        """Stops audio playback and resets position to the beginning."""
        if not self.just_playback_initialized or not self.player: return

        # Only stop if currently playing or paused
        if self.player.playing or self.player.paused:
            try:
                self.player.stop()
                self._stop_progress_updater()
                # Reset UI to initial position
                if hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                    self.ui.progress_slider.set(0)
                self.ui.update_time_label(0, self.audio_duration)
                self.ui.set_ui_state('generated') # State returns to 'ready to play'
                self.ui.update_status("⏹ Audio stopped.")
            except Exception as e:
                print(f"ERROR: Exception during stop_audio: {e}")
                self.ui.update_status(f"❌ Error stopping audio: {e}")
                self.ui.set_ui_state('generated') # Still try to reset state
        else:
            # If already stopped, ensure UI is consistent
            self._stop_progress_updater()
            if hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                 self.ui.progress_slider.set(0)
            self.ui.update_time_label(0, self.audio_duration)
            self.ui.set_ui_state('generated')

    # --- Progress Update & Seeking Logic ---
    def _start_progress_updater(self):
        """Starts the loop for updating the progress bar and time label."""
        self._stop_progress_updater() # Ensure any previous updater is stopped
        # Only start if player is ready and duration is valid
        if self.player and self.audio_duration > 0:
             # Schedule the first call to _update_progress after a short delay
             self._after_id_update_progress = self.ui.after(AUDIO_UPDATE_INTERVAL_MS, self._update_progress)

    def _stop_progress_updater(self):
        """Stops the progress update loop."""
        if self._after_id_update_progress:
            try:
                 self.ui.after_cancel(self._after_id_update_progress)
            except ValueError: # Can happen if ID is invalid (e.g., already cancelled)
                 pass
            except Exception as e:
                 # Catch TclError if app is closing
                 if "application has been destroyed" not in str(e):
                      print(f"WARN: Error cancelling progress updater: {e}")
            self._after_id_update_progress = None


    def pause_updates_on_drag(self, event=None):
        """Called when the user presses the progress slider."""
        if self._can_seek(): # Only set flag if seeking is possible
            self._slider_being_dragged = True
            # Optional: Could also stop the updater here if needed
            # self._stop_progress_updater()

    def _update_progress(self):
        """Method called periodically to update the progress UI."""
        # Safety check: Stop if player is not ready or window closing
        if not self.just_playback_initialized or not self.player or not self.ui.winfo_exists():
            self._stop_progress_updater(); return

        # Update only if playing AND the user is not dragging the slider
        if self.player.playing and not self._slider_being_dragged:
            try:
                current_pos_sec = self.player.curr_pos
                total_duration = self.audio_duration

                # Ensure duration is valid before calculating percentage
                if total_duration > 0:
                    # Calculate progress percentage (0-100)
                    progress_percent = min(100, max(0, (current_pos_sec / total_duration) * 100))

                    # Check if slider exists before updating
                    slider_exists = hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists()

                    # Update slider UI only if the value changed significantly (reduces flicker)
                    if slider_exists:
                        # Use try-except for slider access as it might be destroyed during close
                        try:
                             current_slider_val = self.ui.progress_slider.get()
                             if abs(current_slider_val - progress_percent) > 0.5: # 0.5% tolerance
                                self.ui.progress_slider.set(progress_percent)
                        except Exception as slider_e:
                              print(f"WARN: Error accessing slider during progress update: {slider_e}")
                              slider_exists = False # Assume slider is gone

                    # Update time label
                    self.ui.update_time_label(current_pos_sec, total_duration)
                else:
                    # Abnormal condition if duration is 0 while playing, stop the updater
                    print("WARN: Invalid duration detected during progress update.")
                    self._stop_progress_updater()
                    if hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                         try: self.ui.progress_slider.set(0)
                         except: pass # Ignore errors if closing
                    self.ui.update_time_label(0, 0)
                    return # Do not reschedule

                # Reschedule the next update call ONLY if still playing
                # Check player state *again* as it might have finished between checks
                if self.player.playing:
                   # Check window exists before scheduling next 'after'
                   if self.ui.winfo_exists():
                        self._after_id_update_progress = self.ui.after(AUDIO_UPDATE_INTERVAL_MS, self._update_progress)
                   else:
                        self._after_id_update_progress = None # Window closed
                else:
                    # Playback finished naturally (detected by state check)
                    print("INFO: Playback finished naturally.")
                    self._stop_progress_updater()
                    # Call stop_audio after a short delay to reset UI/state if window still exists
                    if self.ui.winfo_exists():
                         self.ui.after(50, self.stop_audio) # Increased delay slightly

            except Exception as e:
                # Catch errors during the update process
                # Check if error is due to closing window
                if "application has been destroyed" not in str(e) and "invalid command name" not in str(e):
                     print(f"ERROR: Exception in progress update loop: {e}")
                self._stop_progress_updater() # Stop updater on error

        # If not playing or being dragged, ensure updater is stopped
        elif (not self.player.playing or self._slider_being_dragged) and self._after_id_update_progress:
             self._stop_progress_updater()






    def _can_seek(self) -> bool:
        """Checks if the current conditions allow seeking."""
        # Check player state too
        player_ready = self.just_playback_initialized and self.player and (self.player.playing or self.player.paused)
        return (player_ready
                and self.audio_file_path and os.path.exists(self.audio_file_path) # Check file path
                and self.audio_duration > 0.001)


    def _perform_seek(self, target_seek_time_sec: float):
        """Core logic for seeking: stop updater, seek, update UI, schedule updater restart."""
        if not self._can_seek(): return # Do nothing if seeking isn't possible

        try:
            was_playing = self.player.playing # Remember if it was playing before seek
            self._stop_progress_updater() # Stop updater first

            # Clamp target time to valid duration range (allow seeking very close to end)
            target_seek_time_sec = max(0, min(target_seek_time_sec, self.audio_duration - 0.01)) # Subtract tiny amount

            # Perform seek using just_playback
            self.player.seek(target_seek_time_sec)

            # Schedule immediate UI update after a short delay (allows seek to register)
            # Ensure window exists before scheduling 'after' calls
            if self.ui.winfo_exists():
                 self.ui.after(30, self._update_ui_after_seek_internal)
                 # Schedule the updater restart check only if it was playing before
                 if was_playing:
                     self.ui.after(80, self._maybe_restart_updater) # Slightly longer delay
            else:
                 print("WARN: Window closed during seek operation, skipping UI updates.")

        except Exception as e:
             # Catch errors during the seek operation
             print(f"ERROR: Exception during seek operation: {e}")
             self.ui.update_status(f"❌ Error seeking: {e}")
             # Still try to schedule updater restart check if it was playing
             if self.ui.winfo_exists() and was_playing:
                 self.ui.after(80, self._maybe_restart_updater)


    def seek_relative(self, seconds_to_add: int):
        """Jumps forward or backward by a specified number of seconds."""
        if not self._can_seek(): return
        current_pos_sec = self.player.curr_pos
        target_seek_time_sec = current_pos_sec + seconds_to_add
        self._perform_seek(target_seek_time_sec) # Use the helper

    def seek_audio_on_release(self, event=None):
        """Called when the user releases the click on the progress slider."""
        if not self._can_seek(): # Check if seeking is possible *before* clearing the flag
             self._slider_being_dragged = False # Always clear flag on release
             return
        if not hasattr(self.ui, 'progress_slider'):
             self._slider_being_dragged = False
             return

        seek_percent = self.ui.progress_slider.get()
        # Clear the flag *before* performing the seek
        self._slider_being_dragged = False
        # Calculate target time based on slider percentage
        target_seek_time_sec = (seek_percent / 100.0) * self.audio_duration
        self._perform_seek(target_seek_time_sec) # Use the helper

    def _update_ui_after_seek_internal(self):
        """Updates the slider position and time label immediately after a seek."""
        if not self.just_playback_initialized or not self.player or not self.ui.winfo_exists(): return
        # Update only if player is in a valid state (playing/paused)
        if self.player.playing or self.player.paused:
            try:
                 current_pos = self.player.curr_pos
                 duration = self.audio_duration
                 self.ui.update_time_label(current_pos, duration) # Update time label
                 if duration > 0 and hasattr(self.ui, 'progress_slider') and self.ui.progress_slider.winfo_exists():
                      # Update slider position
                      percent = min(100, max(0, (current_pos / duration) * 100))
                      self.ui.progress_slider.set(percent)
            except Exception as e:
                 # Catch errors during post-seek UI update
                 if "application has been destroyed" not in str(e):
                      print(f"ERROR: Exception updating UI after seek: {e}")

    def _maybe_restart_updater(self):
        """Checks conditions and restarts the progress updater if necessary."""
        if not self.just_playback_initialized or not self.player or not self.ui.winfo_exists(): return
        # Restart only if: playing, NOT dragging, AND updater is not already running
        if self.player.playing and not self._slider_being_dragged and not self._after_id_update_progress:
             self._start_progress_updater()

    # --- Cleanup ---
    def _delete_temp_audio_file(self):
        """Deletes the temporary audio file if it exists, with retries."""
        path_to_delete = self.audio_file_path
        if path_to_delete and os.path.exists(path_to_delete):
            print(f"INFO: Preparing to delete temp file: {path_to_delete}")
            # Clear internal references *before* attempting deletion
            self.audio_file_path = None
            self.audio_duration = 0

            # Stop the player if it's active and loaded this file
            if self.just_playback_initialized and self.player and (self.player.playing or self.player.paused):
                 # Check if the player's source matches the file to delete
                 # Note: just_playback doesn't directly expose the loaded file path easily.
                 # We assume if a file exists, the player *might* be using it.
                 print(f"INFO: Stopping player before attempting to delete potential source file.")
                 try:
                     self.player.stop()
                     time.sleep(0.15) # Give OS time to release handle
                 except Exception as e:
                     # Ignore errors if player is already stopped or invalid
                     if "Playback has not been initialized" not in str(e):
                          print(f"WARN: Exception while stopping player before delete: {e}")

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
        else:
            # Path was already None or file didn't exist
            if self.audio_file_path: # Clear internal refs just in case
                self.audio_file_path = None
                self.audio_duration = 0

    def on_closing(self):
        store_ui_state(self.ui.voice_dropdown.get(), int(self.ui.rate_slider.get()), int(self.ui.pitch_slider.get()))

        """Called when the application window is closed."""
        print("INFO: Closing application...")
        self._stop_progress_updater() # Stop the UI update loop

        # Stop the player if active
        if self.just_playback_initialized and self.player:
             try:
                  if self.player.playing or self.player.paused:
                       print("INFO: Stopping audio playback...")
                       self.player.stop()
                       time.sleep(0.1) # Short pause after stopping
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
        file_utils.audio_files.AudioSaver(self.audio_file_path, self.ui, self.just_playback_initialized, self.player).save_audio()