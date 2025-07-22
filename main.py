# --- START OF FILE final.py ---

# --- Imports ---
import customtkinter as ctk

from app import EdgeTTSApp
from config.consts import PYGLET_AVAILABLE
# --- Execution Entry Point ---
if __name__ == "__main__":
    # Check if just_playback is available before starting the main GUI
    if not PYGLET_AVAILABLE:
        # Display a simple error window if the library is missing
        error_root = ctk.CTk()
        # Set mode for the error window too
        ctk.set_appearance_mode("System")
        error_root.title("Dependency Error")
        error_root.geometry("450x120")
        error_label = ctk.CTkLabel(
            error_root,
            text="Required library 'just_playback' is missing or failed to load.\n"
                 "Please install it using:\n"
                 "pip install just_playback",
            font=ctk.CTkFont(size=13)
        )
        error_label.pack(pady=20, padx=20)
        # Automatically close the error window after a few seconds
        error_root.after(7000, error_root.destroy)
        error_root.mainloop()
    else:
        # --- Configuration ---
        # Set initial mode to follow the system setting
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

        # If the library is available, run the main application
        app = EdgeTTSApp()
        # Set the close window action to call our on_closing method
        app.ui.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.ui.mainloop()

# --- END OF FILE ---