

import customtkinter as ctk
import os

import pyglet
import file_utils.text_files
from config.settings import StoredUiState
from config.consts import SEEK_INTERVAL_SECONDS, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT, TEXTBOX_PLACEHOLDER_TEXT, \
    TEXTBOX_PLACEHOLDER_COLOR
from tkinter import filedialog


class EdgeTTSUi(ctk.CTk):

    def __init__(self, app: 'EdgeTTSApp', ui_state: StoredUiState = StoredUiState()):
        super().__init__()
        self.app = app
        self.playback_end_watcher = False
        self.has_played =False

        # Placeholder state
        self.textbox_placeholder_active = False
        self.default_textbox_color = None # Will be fetched after widget creation

        # --- Theme is now initially System ---
        print(f"INFO: Initial appearance mode requested: 'System'")

        self.title("Edge TTS Text-to-Speech")
        self.resizable(True, True)
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        self._build_ui(app, ui_state)# Build the UI

        # Initial Actions
        self.after(10, self._fetch_default_textbox_color)  # Schedule fetching color early
        self.after(20, self._set_initial_textbox_placeholder)

        # Set initial state of the theme switch based on the *actual* mode determined by "System"
        # Needs a slight delay for the system mode to be resolved and applied
        self.after(50, self._update_theme_switch_state)
        print(f"INFO: Actual initial mode (after System resolution): '{ctk.get_appearance_mode()}'")

    def _build_ui(self, app: 'EdgeTTSApp', ui_state: StoredUiState = StoredUiState()):
        """Creates all user interface elements (widgets)."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Textbox row expands
        self.grid_rowconfigure(3, weight=0)  # Controls row fixed
        self.grid_rowconfigure(5, weight=0)  # Player row fixed

        # --- Input Area ---
        input_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_header_frame.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="ew")
        input_header_frame.grid_columnconfigure(0, weight=1)  # Label expands
        ctk.CTkLabel(input_header_frame, text="Input Text", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0,
                                                                                                           column=0,
                                                                                                           sticky="w")

        # Theme Toggle Switch
        self.theme_switch = ctk.CTkSwitch(
            input_header_frame,
            text="Dark Mode",
            command=self._toggle_theme_override,  # Changed command name
            onvalue=1,  # Represents "Dark" mode ON
            offvalue=0  # Represents "Dark" mode OFF (i.e., Light mode)
        )
        self.theme_switch.grid(row=0, column=1, padx=(10, 5), sticky="e")

        if ui_state.dark:
            self.theme_switch.select()
            ctk.set_appearance_mode("dark")
        else:
            self.theme_switch.deselect()
            ctk.set_appearance_mode("light")

        self.load_file_btn = ctk.CTkButton(input_header_frame, text="Load File...", width=100,
                                           command=self.load_text_from_file)
        self.load_file_btn.grid(row=0, column=2, padx=(0, 5), sticky="e")

        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        input_frame.grid_rowconfigure(0, weight=1)
        input_frame.grid_columnconfigure(0, weight=1)

        # --- Textbox Setup ---
        self.textbox = ctk.CTkTextbox(input_frame, wrap="word")
        self.textbox.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Bind focus events for placeholder simulation
        self.textbox.bind("<FocusIn>", self._on_textbox_focus_in)
        self.textbox.bind("<FocusOut>", self._on_textbox_focus_out)

        # Detect text changes
        self.textbox.bind("<KeyRelease>", self._on_textbox_change)

        # --- Controls Area (Voice & Adjustments) ---
        # [Rest of the controls setup remains the same as before]
        ctk.CTkLabel(self, text="Voice & Adjustments", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0,
                                                                                                      padx=20,
                                                                                                      pady=(10, 0),
                                                                                                      sticky="w")
        controls_frame = ctk.CTkFrame(self)
        controls_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        controls_frame.grid_columnconfigure(0, weight=1, uniform="group1")
        controls_frame.grid_columnconfigure(1, weight=2, uniform="group1")
        voice_select_frame = ctk.CTkFrame(controls_frame)
        voice_select_frame.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="nsew")
        voice_select_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(voice_select_frame, text="Select Voice", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=5,
                                                                                              pady=(5, 2), sticky="w")
        self.voice_search_entry = ctk.CTkEntry(voice_select_frame, placeholder_text="Search voice...")
        self.voice_search_entry.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="ew")
        self.voice_search_entry.bind("<KeyRelease>", self._on_voice_search)
        self.voice_dropdown = ctk.CTkComboBox(voice_select_frame, values=["Loading voices..."], state="disabled",
                                              command=self.voice_selected)
        self.voice_dropdown.grid(row=2, column=0, padx=5, pady=(0, 5), sticky="ew")
        adj_frame = ctk.CTkFrame(controls_frame)
        adj_frame.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="nsew")
        adj_frame.grid_columnconfigure(0, weight=1)
        rate_adj_frame = ctk.CTkFrame(adj_frame)
        rate_adj_frame.grid(row=0, column=0, padx=5, pady=(5, 2), sticky="ew")
        rate_adj_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rate_adj_frame, text="Rate:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(5, 0), pady=5,
                                                                                   sticky="w")
        self.rate_slider = ctk.CTkSlider(rate_adj_frame, from_=-100, to=100, number_of_steps=40,
                                         command=self.update_rate_label)
        self.rate_slider.set(ui_state.rate)
        self.rate_slider.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.rate_value_label = ctk.CTkLabel(rate_adj_frame, text=f"{ui_state.rate}%", width=40, anchor="e")
        self.rate_value_label.grid(row=0, column=2, padx=(0, 5), pady=5, sticky="e")
        self.rate_reset_btn = ctk.CTkButton(rate_adj_frame, text="Reset", width=50,
                                            command=lambda: self.reset_slider("rate"))
        self.rate_reset_btn.grid(row=0, column=3, padx=(0, 5), pady=5)
        pitch_adj_frame = ctk.CTkFrame(adj_frame)
        pitch_adj_frame.grid(row=1, column=0, padx=5, pady=(2, 5), sticky="ew")
        pitch_adj_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(pitch_adj_frame, text="Pitch:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(5, 0),
                                                                                     pady=5, sticky="w")
        self.pitch_slider = ctk.CTkSlider(pitch_adj_frame, from_=-50, to=50, number_of_steps=20,
                                          command=self.update_pitch_label)
        self.pitch_slider.set(ui_state.pitch)
        self.pitch_slider.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.pitch_value_label = ctk.CTkLabel(pitch_adj_frame, text=f"{ui_state.pitch}Hz", width=40, anchor="e")
        self.pitch_value_label.grid(row=0, column=2, padx=(0, 5), pady=5, sticky="e")
        self.pitch_reset_btn = ctk.CTkButton(pitch_adj_frame, text="Reset", width=50,
                                             command=lambda: self.reset_slider("pitch"))
        self.pitch_reset_btn.grid(row=0, column=3, padx=(0, 5), pady=5)

        # --- Generate Button ---
        self.generate_btn = ctk.CTkButton(self, text="Generate Speech", command=app.start_generate_speech_thread,
                                          height=40, font=ctk.CTkFont(size=14, weight="bold"), state="disabled")
        self.generate_btn.grid(row=4, column=0, padx=20, pady=5, sticky="ew")




        # --- Player Controls ---
        # [Player controls setup remains the same as before]
        self.player_frame = ctk.CTkFrame(self)
        self.player_frame.grid(row=5, column=0, padx=20, pady=5, sticky="ew")
        self.player_frame.grid_columnconfigure(4, weight=1)  # Progress slider column expands
        self.rewind_btn = ctk.CTkButton(self.player_frame, text=f"<< {SEEK_INTERVAL_SECONDS}s", width=60,
                                        command=lambda: app.seek_relative(-SEEK_INTERVAL_SECONDS), state="disabled")
        self.rewind_btn.grid(row=0, column=0, padx=(10, 5), pady=10)
        self.play_pause_btn = ctk.CTkButton(self.player_frame, text="▶ Play", width=80, command=self.toggle_play_pause,
                                            state="disabled")
        self.play_pause_btn.grid(row=0, column=1, padx=5, pady=10)
        self.stop_btn = ctk.CTkButton(self.player_frame, text="⏹ Stop", width=80, command=self.stop_audio,
                                      state="disabled")
        self.stop_btn.grid(row=0, column=2, padx=5, pady=10)
        self.forward_btn = ctk.CTkButton(self.player_frame, text=f">> {SEEK_INTERVAL_SECONDS}s", width=60,
                                         command=lambda: app.seek_relative(
                                             SEEK_INTERVAL_SECONDS), state="disabled")
        self.forward_btn.grid(row=0, column=3, padx=5, pady=10)

        self.next_btn = ctk.CTkButton(self.player_frame, text="⏭ Next", width=60,
                                        command=lambda: app.player.next_source(), state="disabled")
        self.next_btn.grid(row=0, column=4, padx=(5, 10), pady=10)

        self.auto_play = ctk.CTkCheckBox(
            self.player_frame,
            text="Auto play after generation",
        )
        if ui_state.auto_play:
            self.auto_play.select()
        else:
            self.auto_play.deselect()
        self.auto_play.grid(row=0, column=5, padx=(10, 0), sticky="w")

        # --- Save Button ---
        self.save_btn = ctk.CTkButton(self, text="Save Audio as MP3", command=app.save_audio, height=40,
                                      font=ctk.CTkFont(size=14), state="disabled")
        self.save_btn.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        # --- Status Label ---
        self.status_label = ctk.CTkLabel(self, text="Status: Initializing...", height=25, anchor="w")
        self.status_label.grid(row=7, column=0, padx=20, pady=(5, 10), sticky="ew")

    def toggle_play_pause(self):
        self.app.toggle_play_pause()  # Use app method to handle play/pause logic
        if not self.playback_end_watcher:
            self.playback_end_watcher = True
            self.after(50, self._trigger_pyglet_eventloop)

    def _trigger_pyglet_eventloop(self):
        if self.playback_end_watcher:
            pyglet.app.platform_event_loop.dispatch_posted_events()
            pyglet.clock.tick()
            if self.app.player.source:
                self.after(50, self._trigger_pyglet_eventloop)
            else:
                self.stop_audio()

    def stop_audio(self):
        """Stops the audio playback and resets the player state."""
        self.has_played = False  # Reset playback state
        self.app.stop_audio()
        self.playback_end_watcher = False  # unblock future watchers

    def load_text_from_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Text or Subtitle File",  # Dialog title
            filetypes=[("Text files", "*.txt"), ("SubRip Subtitles", "*.srt"), ("All files", "*.*")]
            # File type filters
        )
        content = file_utils.text_files.load_text_from_file(self, file_path)
        if content is None:
            return

        # Insert content into the textbox
        if hasattr(self, 'textbox') and self.textbox.winfo_exists():
             self.textbox_placeholder_active = False # Ensure placeholder is off
             self.textbox.delete("1.0", ctk.END) # Clear old text
             if self.default_textbox_color: # Ensure we have a valid color
                 self.textbox.configure(text_color=self.default_textbox_color) # Set normal color
             if content:
                 self.textbox.insert("1.0", content) # Insert new text
             # Check immediately if the loaded content was empty, and reset placeholder if so
             self.check_and_set_placeholder()
        self.set_ui_state('idle') # Update button states based on new text content


    # --- Textbox Placeholder Logic ---
    def _fetch_default_textbox_color(self):
        """Fetches and stores the default text color of the textbox."""
        if hasattr(self, 'textbox') and self.textbox.winfo_exists():
            try:
                # Ensure the widget is fully ready
                self.textbox.update_idletasks()
                self.default_textbox_color = self.textbox.cget("text_color")
                print(f"INFO: Default textbox color fetched: {self.default_textbox_color}")
                # If placeholder is currently active, ensure its color is correct
                # This can happen if fetch was delayed past initial set
                if self.textbox_placeholder_active:
                    self.textbox.configure(text_color=TEXTBOX_PLACEHOLDER_COLOR)

            except Exception as e:
                print(f"WARN: Could not fetch default textbox color: {e}")
                # Fallback (might not match theme perfectly)
                current_mode = ctk.get_appearance_mode()
                self.default_textbox_color = "#DCE4EE" if current_mode == "Dark" else "#111111"  # Near-white for Dark, Near-black for Light
                print(f"INFO: Using fallback textbox color for {current_mode} mode: {self.default_textbox_color}")
        else:
            # Reschedule if textbox doesn't exist or color isn't ready yet
            self.after(50, self._fetch_default_textbox_color)

    def _set_initial_textbox_placeholder(self):
        """Sets the placeholder text and color if the textbox is empty."""
        if not hasattr(self, 'textbox') or not self.textbox.winfo_exists():
            self.after(50, self._set_initial_textbox_placeholder)  # Retry if widget not ready
            return
        # Ensure default color is fetched before proceeding
        if self.default_textbox_color is None:
            print("INFO: Waiting for default text color fetch before setting placeholder...")
            self.after(50, self._set_initial_textbox_placeholder)  # Retry shortly
            return

        current_text = self.textbox.get("1.0", "end-1c").strip()
        if not current_text:
            self.textbox_placeholder_active = True
            self.textbox.insert("1.0", TEXTBOX_PLACEHOLDER_TEXT)
            self.textbox.configure(text_color=TEXTBOX_PLACEHOLDER_COLOR)
            print("INFO: Initial textbox placeholder set.")

    def _on_textbox_focus_in(self, event=None):
        """Handles the textbox gaining focus."""
        if not hasattr(self, 'textbox') or not self.default_textbox_color: return
        if self.textbox_placeholder_active:
            self.textbox_placeholder_active = False
            self.textbox.delete("1.0", ctk.END)
            self.textbox.configure(text_color=self.default_textbox_color)

    def _on_textbox_focus_out(self, event=None):
        """Handles the textbox losing focus."""
        if not hasattr(self, 'textbox') or not self.default_textbox_color: return
        # Use after_idle to allow potential other focus-out events to process first
        self.after_idle(self.check_and_set_placeholder)

    def check_and_set_placeholder(self):
        """Checks if textbox is empty after focus-out and sets placeholder."""
        if not hasattr(self, 'textbox') or not self.default_textbox_color: return
        # Verify focus is actually lost from textbox (important!)
        if self.focus_get() != self.textbox:
            current_text = self.textbox.get("1.0", "end-1c").strip()
            if not current_text:
                self.textbox_placeholder_active = True
                self.textbox.insert("1.0", TEXTBOX_PLACEHOLDER_TEXT)
                self.textbox.configure(text_color=TEXTBOX_PLACEHOLDER_COLOR)

    def get_input_text(self) -> str:
        """Gets the text from the textbox, excluding the placeholder."""
        if not hasattr(self, 'textbox'):
            return ""
        if self.textbox_placeholder_active:
            return ""
        else:
            return self.textbox.get("1.0", "end-1c").strip()

    # --- Theme Toggle ---
    def _toggle_theme_override(self):
        """
        Switches the appearance mode explicitly to Light or Dark,
        overriding the initial "System" setting.
        """
        if hasattr(self, 'theme_switch'):
            switch_state = self.theme_switch.get() # 1 for ON (Dark), 0 for OFF (Light)
            new_mode = "Dark" if switch_state == 1 else "Light"
            # Explicitly set the mode, stopping system following
            ctk.set_appearance_mode(new_mode)
            print(f"INFO: Appearance mode explicitly set to '{new_mode}' (overriding System).")

            # Update default color after theme change (needs a slight delay)
            if hasattr(self, 'textbox'):
                 self.after(50, self._update_textbox_colors_after_theme_change)
        else:
            print("WARN: Theme switch not available.")

    def _update_textbox_colors_after_theme_change(self):
        """Updates textbox color refs and re-applies placeholder if needed."""
        print("INFO: Updating textbox colors after theme change...")
        self._fetch_default_textbox_color() # Re-fetch the potentially new default color
        # The fetch function now handles applying placeholder color if active

    def _update_theme_switch_state(self):
        """Sets the theme switch state based on the *current effective* appearance mode."""
        if hasattr(self, 'theme_switch') and self.theme_switch.winfo_exists():
            try:
                # Use get_appearance_mode() which returns the resolved mode ("Light" or "Dark")
                current_mode = ctk.get_appearance_mode()
                print(f"INFO: Updating theme switch state for effective mode: '{current_mode}'")
                if current_mode == "Dark":
                    self.theme_switch.select() # Turn switch ON
                else:
                    self.theme_switch.deselect() # Turn switch OFF
            except Exception as e:
                 print(f"WARN: Error updating theme switch state: {e}")
        else:
            # Reschedule if switch doesn't exist yet
            self.after(100, self._update_theme_switch_state)
            print("WARN: Theme switch not available for state update yet, rescheduling.")

   # --- UI & State Update Methods ---
    def update_status(self, message: str):
        """Updates the text in the bottom status bar."""
        if hasattr(self, 'status_label'):
            self.status_label.configure(text=f"Status: {message}")

    def _on_textbox_change(self, event=None):
        """Called when text is typed in the textbox to update UI state."""
        # Use after_idle to ensure the text change is processed first
        self.after_idle(self._update_ui_after_text_change)

    def _update_ui_after_text_change(self):
        """Updates UI state after text changes, maintaining current state context."""
        if not hasattr(self, 'textbox'):
            return

        current_state = self.app.check_current_audio_state()

        # Update UI state which will check text and enable/disable generate button
        self.set_ui_state(current_state)


    def set_ui_state(self, state: str):
        """Sets the enabled/disabled state of UI widgets based on application state."""
        is_player_ready = bool(self.app.pyglet_initialized and self.app.player)
        is_audio_loaded = bool(is_player_ready and self.app.audio_file_path and os.path.exists(self.app.audio_file_path))


        is_idle = not self.app.player.playing # Idle/stopped condition

        # Determine capabilities based on state
        can_press_play_pause = is_audio_loaded and state not in ['generating', 'loading']
        can_skip_next = False # Todo: Implement skip next logic when chunks work
        can_stop = is_audio_loaded
        can_seek = is_audio_loaded
        can_save = is_audio_loaded and is_idle # Can save only when idle/stopped

        voices_loaded = bool(self.app.voices_dict)
        has_input_text = bool(self.get_input_text())

        # Add proper voice selection validation
        selected_voice = self.voice_dropdown.get() if hasattr(self, 'voice_dropdown') else ""
        has_valid_voice = (voices_loaded and
                           selected_voice and
                           selected_voice in self.app.voices_dict and
                           "Loading" not in selected_voice and
                           "No match" not in selected_voice)

        can_generate = has_valid_voice and has_input_text and state not in ['loading', 'generating', 'playing', 'error_no_audio']
        can_load_text = state not in ['loading', 'generating', 'playing', 'error_no_audio']
        controls_active = state not in ['loading', 'generating', 'error_no_audio']
        # Theme switch should always be active
        theme_switch_state = ctk.NORMAL

        # Determine widget states (ON/OFF)
        play_pause_btn_state = ctk.NORMAL if can_press_play_pause else ctk.DISABLED
        next_btn_state = ctk.NORMAL if can_skip_next else ctk.DISABLED
        stop_btn_state = ctk.NORMAL if can_stop else ctk.DISABLED
        seek_btns_state = ctk.NORMAL if can_seek else ctk.DISABLED
        progress_slider_state = ctk.NORMAL if can_seek else ctk.DISABLED
        save_btn_state = ctk.NORMAL if can_save else ctk.DISABLED
        generate_btn_state = ctk.NORMAL if can_generate else ctk.DISABLED
        load_file_btn_state = ctk.NORMAL if can_load_text else ctk.DISABLED
        voice_ctrl_state = ctk.NORMAL if voices_loaded and controls_active else ctk.DISABLED
        adj_ctrl_state = ctk.NORMAL if controls_active else ctk.DISABLED
        # Textbox state should generally be normal unless globally disabled
        textbox_state = ctk.NORMAL if controls_active else ctk.DISABLED

        # Determine dynamic button texts
        generate_btn_text = "Generate Speech"
        if state == 'loading': generate_btn_text = "Loading Voices..."
        elif state == 'generating': generate_btn_text = "Generating..."
        elif state == 'error_no_audio': generate_btn_text = "Audio Error"


        play_pause_text = "▶ Play"
        if self.app.player.playing:
            play_pause_text = "⏸ Pause"
            self.has_played = True  # Mark that playback has started
        elif self.has_played and self.app.player.source: play_pause_text= "▶ Resume"

        # Apply states to widgets (use try-except for safety during init)
        try:
            # Use 'winfo_exists' for safety, especially during init/close
            if hasattr(self, 'theme_switch') and self.theme_switch.winfo_exists(): self.theme_switch.configure(state=theme_switch_state)
            if hasattr(self, 'voice_dropdown') and self.voice_dropdown.winfo_exists(): self.voice_dropdown.configure(state=voice_ctrl_state)
            if hasattr(self, 'voice_search_entry') and self.voice_search_entry.winfo_exists(): self.voice_search_entry.configure(state=voice_ctrl_state)
            if hasattr(self, 'rate_slider') and self.rate_slider.winfo_exists(): self.rate_slider.configure(state=adj_ctrl_state)
            if hasattr(self, 'pitch_slider') and self.pitch_slider.winfo_exists(): self.pitch_slider.configure(state=adj_ctrl_state)
            if hasattr(self, 'rate_reset_btn') and self.rate_reset_btn.winfo_exists(): self.rate_reset_btn.configure(state=adj_ctrl_state)
            if hasattr(self, 'pitch_reset_btn') and self.pitch_reset_btn.winfo_exists(): self.pitch_reset_btn.configure(state=adj_ctrl_state)
            if hasattr(self, 'textbox') and self.textbox.winfo_exists(): self.textbox.configure(state=textbox_state)
            if hasattr(self, 'load_file_btn') and self.load_file_btn.winfo_exists(): self.load_file_btn.configure(state=load_file_btn_state)
            if hasattr(self, 'generate_btn') and self.generate_btn.winfo_exists(): self.generate_btn.configure(state=generate_btn_state, text=generate_btn_text)
            if hasattr(self, 'save_btn') and self.save_btn.winfo_exists(): self.save_btn.configure(state=save_btn_state)

            if hasattr(self, 'play_pause_btn') and self.play_pause_btn.winfo_exists(): self.play_pause_btn.configure(state=play_pause_btn_state, text=play_pause_text)
            if hasattr(self, 'next_btn') and self.next_btn.winfo_exists(): self.next_btn.configure(state=next_btn_state)
            if hasattr(self, 'stop_btn') and self.stop_btn.winfo_exists(): self.stop_btn.configure(state=stop_btn_state)
            if hasattr(self, 'rewind_btn') and self.rewind_btn.winfo_exists(): self.rewind_btn.configure(state=seek_btns_state)
            if hasattr(self, 'forward_btn') and self.forward_btn.winfo_exists(): self.forward_btn.configure(state=seek_btns_state)
        except Exception as e:
            # This might happen during shutdown if widgets are destroyed
            if "application has been destroyed" not in str(e):
                 print(f"WARN: Error applying UI state '{state}': {e}")


    def reset_slider(self, slider_type: str):
        """Resets the Rate or Pitch slider to 0."""
        if slider_type == "rate":
            if hasattr(self, 'rate_slider'): self.rate_slider.set(0)
            self.update_rate_label(0)
        elif slider_type == "pitch":
            if hasattr(self, 'pitch_slider'): self.pitch_slider.set(0)
            self.update_pitch_label(0)

    def update_rate_label(self, value: float):
        """Updates the Rate percentage label."""
        if hasattr(self, 'rate_value_label'):
             self.rate_value_label.configure(text=f"{int(value):+d}%")

    def update_pitch_label(self, value: float):
        """Updates the Pitch Hertz label."""
        if hasattr(self, 'pitch_value_label'):
             self.pitch_value_label.configure(text=f"{int(value):+d}Hz")

    def voice_selected(self, choice: str):
        """Callback when a voice is selected from the dropdown. Updates the UI state."""
        current_state = self.app.check_current_audio_state()
        self.set_ui_state(current_state)


    def _on_voice_search(self, event=None):
        """Updates the voice dropdown list as the user types in the search box."""
        if not hasattr(self, 'voice_dropdown'): return
        filtered_voices = self.app.filter_voices()
        current_selection = self.voice_dropdown.get()

        if not filtered_voices:
            # If no results, display message and disable dropdown
            self.voice_dropdown.configure(values=["No match found"], state=ctk.DISABLED)
            self.voice_dropdown.set("No match found")
            # Trigger UI update after setting invalid selection
            current_state = self.app.check_current_audio_state()
            self.set_ui_state(current_state)
        else:
            # If results found, update list and enable dropdown
            self.voice_dropdown.configure(values=filtered_voices, state=ctk.NORMAL)
            # Try to keep the current selection if it's still in the filtered list
            if current_selection in filtered_voices:
                self.voice_dropdown.set(current_selection)
            else: # Otherwise, select the first result
                self.voice_dropdown.set(filtered_voices[0])

            # Trigger UI update after setting new selection
            current_state = self.app.check_current_audio_state()
            self.set_ui_state(current_state)

    def update_voice_dropdown_ui(self, voice_list: list[str], start_voice: str = None):
        """Updates the voice ComboBox on the main thread."""
        if not hasattr(self, 'voice_dropdown') or not self.voice_dropdown.winfo_exists(): return

        if voice_list:
            self.voice_dropdown.configure(values=voice_list)
            if hasattr(self, 'voice_search_entry') and self.voice_search_entry.winfo_exists():
                 self.voice_search_entry.configure(state=ctk.NORMAL)
            self.update_status("Ready.")
            # Determine final state based on whether audio is already loaded
            current_state = 'generated' if self.app.audio_file_path else 'idle'
            self.set_ui_state(current_state)
            if start_voice and start_voice in voice_list:
                self.voice_dropdown.set(start_voice)
            else:
                self.voice_dropdown.set(voice_list[0]) # Select the first voice by default
        else:
            # If the list is empty (error during load)
            self.voice_dropdown.configure(values=["No voices found"], state=ctk.DISABLED)
            if hasattr(self, 'voice_search_entry') and self.voice_search_entry.winfo_exists():
                self.voice_search_entry.configure(state=ctk.DISABLED)
            self.update_status("❌ Error: No voices could be loaded.")
            self.set_ui_state('error_no_voices') # Specific error state

    def update_time_label(self, current_seconds: float, total_seconds: float):
        """Updates the 'MM:SS / MM:SS' time label."""
        # Ensure non-negative inputs
        current_seconds = max(0, current_seconds if isinstance(current_seconds, (int, float)) else 0)
        total_seconds = max(0, total_seconds if isinstance(total_seconds, (int, float)) else 0)
        # Format times
        current_time_str = self.format_time(current_seconds)
        total_time_str = self.format_time(total_seconds)



    @staticmethod
    def format_time(seconds: float) -> str:
        """Formats seconds into an MM:SS string."""
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
