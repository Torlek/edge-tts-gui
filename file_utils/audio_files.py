import os
from tkinter import filedialog
import subprocess
import tempfile

# --- File Operations (Save audio) ---
class AudioSaver:
    def __init__(self, audio_file_path, ui, just_playback_initialized)-> None:
        """Initializes the AudioSaver with the path to the audio file and UI instance."""
        self.audio_file_path = audio_file_path
        self.ui = ui
        self.just_playback_initialized = just_playback_initialized

    def save_audio(self):
        """Opens a dialog to save the temporary audio file to a user-chosen location."""
        if not self.audio_file_path:
             self.ui.update_status("❌ No generated audio file to save."); return
        for path in self.audio_file_path:
            if not os.path.exists(path):
                self.ui.update_status(f"❌ Audio file {path} does not exist."); return

        try: # Create default filename from the beginning of the text
            # Use get_input_text to avoid using placeholder as filename basis
            initial_text = self.ui.get_input_text()[:40].strip().replace("\n", " ") # Limit length
            # Sanitize filename: allow alphanumeric, space, underscore, hyphen
            sanitized_text = "".join(c for c in initial_text if c.isalnum() or c in (' ', '_', '-')).rstrip()
            # Replace spaces with underscores for better compatibility
            sanitized_text = sanitized_text.replace(' ', '_')
            # Limit length again after sanitization
            initial_filename = f"{sanitized_text[:30] if sanitized_text else 'speech'}.mp3"
        except Exception as e:
            print(f"WARN: Error generating initial filename: {e}")
            initial_filename = "speech.mp3" # Fallback name

        # Open 'Save As' dialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 audio file", "*.mp3"), ("All files", "*.*")], # File type options
            title="Save Audio As...", # Dialog title
            initialfile=initial_filename # Default filename suggestion
        )

        if file_path: # If the user selected a path and name
            try:
                print(f"INFO: Copying temp file {self.audio_file_path} to {file_path}")
                # Use subprocess to copy the file to the selected location
                if os.path.exists(file_path):
                    os.remove(file_path)  # Remove existing file if it exists

                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
                    for path in self.audio_file_path:
                        temp_file.write("file '" + path + "'\n")


                result = subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", temp_file.name, "-c", "copy", file_path], capture_output=True, text=True)
                print(result.stdout)  # Output of the command
                os.remove(temp_file.name)  # Clean up temp file
                self.ui.update_status(f"✅ Audio saved successfully to {os.path.basename(file_path)}")
            except IOError as e:
                print(f"ERROR: IOError during file save: {e}")
                self.ui.update_status(f"❌ Error saving file: {e}")
            except Exception as e:
                print(f"ERROR: Unexpected exception during file save: {e}")
                self.ui.update_status(f"❌ An unexpected error occurred during saving: {e}")
        else:
            # User cancelled the save dialog
            self.ui.update_status("Save operation cancelled.")