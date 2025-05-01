# Edge TTS GUI

A simple graphical user interface (GUI) application built with Python and CustomTkinter that allows you to generate Text-to-Speech (TTS) audio using Microsoft Edge's online TTS service (`edge-tts`) and play it back locally using `just_playback`.


## Features

*   **Text Input:** Enter text directly into the textbox or load content from `.txt` or `.srt` (subtitle) files.
*   **Voice Selection:** Fetches and lists available Microsoft Edge TTS voices.
*   **Voice Search:** Filter the voice list using a search bar.
*   **Rate & Pitch Control:** Adjust the speed (rate) and pitch of the generated speech using sliders.
*   **Audio Generation:** Generates MP3 audio from the input text using the selected voice and settings.
*   **Audio Playback:**
    *   Play, Pause, Resume, and Stop the generated audio.
    *   Seek forward/backward using buttons or the progress slider.
    *   Displays current playback time and total duration.
*   **Save Audio:** Save the generated MP3 audio file to your computer.
*   **Theme Toggle:** Supports Light and Dark modes (follows system setting initially, can be overridden with a switch).
*   **Error Handling:** Provides feedback for common issues like missing libraries, network errors, or playback problems.
*   **Temporary File Management:** Automatically creates and cleans up temporary audio files.

## Requirements

*   **Python:** Version 3.8 or higher recommended.
*   **pip:** Python package installer (usually comes with Python).
*   **Network Connection:** Required for `edge-tts` to list voices and generate speech.
*   **Operating System Specific Dependencies:** `just_playback` relies on system audio libraries. See the installation instructions for your specific OS below.

## Installation

Follow the steps for your specific operating system.

### **Linux (Debian/Ubuntu based)**

1.  **Install Python & Pip:** If not already installed.
    ```bash
    sudo apt update
    sudo apt install python3 python3-pip python3-venv git -y
    ```
2.  **Install GStreamer & FFmpeg:** These are crucial for audio playback with `just_playback`.
    ```bash
    sudo apt install libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav ffmpeg -y
    ```
3.  **Clone Repository:** Open a terminal and run:
    ```bash
    git clone https://github.com/Ashfield-dev/edge-tts-gui.git
    cd edge-tts-gui
    ```
4.  **Create & Activate Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
5.  **Install Python Packages:**
    ```bash
    pip install -r requirements.txt
    ```

### **Linux (Fedora based)**

1.  **Install Python & Pip:** If not already installed. (DNF usually installs pip and venv with python3). Consider enabling RPM Fusion repositories first for FFmpeg if not already done.
    ```bash
    sudo dnf install python3 python3-pip git -y
    ```
2.  **Install GStreamer & FFmpeg:**
    ```bash
    sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugins-ugly gstreamer1-plugin-libav ffmpeg -y
    ```
3.  **Clone Repository:** Open a terminal and run:
    ```bash
    git clone https://github.com/Ashfield-dev/edge-tts-gui.git
    cd edge-tts-gui
    ```
4.  **Create & Activate Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
5.  **Install Python Packages:**
    ```bash
    pip install -r requirements.txt
    ```

### **Windows**

1.  **Install Python:** Download and install Python from [python.org](https://www.python.org/). **Make sure to check the box "Add Python X.X to PATH" during installation.** This usually includes `pip` and `venv`.
2.  **Install Git (Optional but recommended):** Download and install Git from [git-scm.com](https://git-scm.com/). This allows you to use the `git clone` command. Alternatively, download the project ZIP file from the repository page (`https://github.com/Ashfield-dev/edge-tts-gui`) and extract it.
3.  **Clone or Download Repository:**
    *   Using Git (Open Command Prompt or PowerShell):
        ```bash
        git clone https://github.com/Ashfield-dev/edge-tts-gui.git
        cd edge-tts-gui
        ```
    *   Or download and extract the ZIP, then navigate to the `edge-tts-gui` folder using `cd` in Command Prompt/PowerShell.
4.  **Create & Activate Virtual Environment:** Open Command Prompt or PowerShell in the project directory:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
5.  **Install Python Packages:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: `just_playback` usually works out-of-the-box on Windows, but having FFmpeg installed and in your PATH can sometimes help if you encounter specific audio format issues, though it's often not needed initially.)*

### **macOS**

1.  **Install Homebrew (if not installed):** Open Terminal and run:
    ```bash
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    ```
    Follow the on-screen instructions (you might need Xcode Command Line Tools).
2.  **Install Python & Git:**
    ```bash
    brew install python git
    ```
3.  **Install FFmpeg:** Recommended for broader audio compatibility with `just_playback`.
    ```bash
    brew install ffmpeg
    ```
4.  **Clone Repository:** Open Terminal and run:
    ```bash
    git clone https://github.com/Ashfield-dev/edge-tts-gui.git
    cd edge-tts-gui
    ```
5.  **Create & Activate Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
6.  **Install Python Packages:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  Make sure you are in the `edge-tts-gui` directory in your Terminal or Command Prompt.
2.  Ensure your virtual environment (`venv`) is activated (you should see `(venv)` at the start of your prompt).
3.  Run the script:
    ```bash
    python final.py
    ```

## Usage

1.  **Enter Text:** Type or paste text into the main textbox, or click "Load File..." to load from a `.txt` or `.srt` file.
2.  **Select Voice:** Choose a voice from the dropdown list. You can use the search bar above it to filter voices.
3.  **Adjust Settings (Optional):** Move the Rate and Pitch sliders to modify the speech output. Use the "Reset" buttons to return them to default.
4.  **Generate Speech:** Click the "Generate Speech" button. The application will contact the Edge TTS service and create a temporary audio file. The status bar will show progress.
5.  **Playback:** Once generated ("✅ Audio generated! Press Play."), use the player controls:
    *   **▶ Play / ⏸ Pause / ▶ Resume:** Toggles playback.
    *   **⏹ Stop:** Stops playback and resets the position to the beginning.
    *   **<< / >> Buttons:** Seek backward/forward by a few seconds.
    *   **Progress Slider:** Drag to seek to a specific position in the audio.
6.  **Save Audio:** If audio has been generated and playback is stopped, click "Save Audio as MP3" to save the file permanently.
7.  **Theme:** Use the "Dark Mode" switch to toggle between light and dark themes.

## Troubleshooting

*   **"Error: Required library 'just_playback' not found..."**: Ensure `just_playback` is installed (`pip install just_playback` *inside the activated virtual environment*). If it's installed but still fails, double-check that the OS dependencies (GStreamer/FFmpeg) were installed correctly for your system during the setup.
*   **"Error loading voices..." / "Error generating audio..."**: Check your internet connection, as `edge-tts` requires online access. Sometimes the Edge TTS service might be temporarily unavailable.
*   **Audio Playback Issues (No sound, errors on Linux/macOS):** Verify that the GStreamer/FFmpeg libraries were installed correctly as per your OS installation steps. Use system tools to confirm audio output is working generally.
*   **Audio Playback Issues (Windows):** Usually works directly. If issues occur, ensure your system audio drivers are up to date. Installing FFmpeg and adding it to your system PATH *might* help in rare cases, but isn't typically required for `just_playback`.
*   **PermissionError Deleting Temp File:** This can occasionally happen if the audio player hasn't released the file lock quickly enough. The script tries multiple times, but if it persists, restarting the app usually resolves it.
*   **`git` command not found:** Ensure Git is installed correctly for your OS and that its location is included in your system's PATH environment variable.
*   **`python` or `pip` command not found:** Ensure Python is installed correctly and added to your system's PATH (especially important during Windows installation). On Linux/macOS, you might need to use `python3` and `pip3` explicitly if `python` defaults to Python 2.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
