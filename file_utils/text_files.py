import os
import re


# --- File Operations (Load Text) ---
def _parse_srt(file_path: str) -> str:
    """Reads an SRT file and extracts only the dialogue text."""
    dialogue_lines: list[str] = []
    full_content: str = ""
    try:
        # Try reading as UTF-8 with error handling
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            full_content = f.read()
    except Exception as e: # Catch potential errors even opening the file
        print(f"ERROR: Failed to read SRT file {file_path}: {e}")
        return ""

    lines = full_content.splitlines()
    buffer: list[str] = []
    is_dialogue_block: bool = False
    # Regex patterns for line detection (more robust)
    block_number_pattern = re.compile(r'^\d+\s*$') # Matches lines with only numbers
    timestamp_pattern = re.compile(r'^\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{1,2}:\d{2}:\d{2}[,.]\d{3}.*') # Allow comma or period for ms

    for line in lines:
        line = line.strip()
        if not line:
             # Empty line, potential end of block
             if buffer:
                 dialogue_lines.append(" ".join(buffer))
                 buffer = []
             is_dialogue_block = False # Reset state
        elif block_number_pattern.match(line) and not is_dialogue_block:
             # Block number line (ignore if already in dialogue or buffer has text)
             # Reset just in case of malformed SRT
             if buffer:
                 dialogue_lines.append(" ".join(buffer))
                 buffer = []
             is_dialogue_block = False
        elif timestamp_pattern.match(line):
             # Timestamp line, definitely start of a new dialogue block
             if buffer: # Append previous buffer if any
                 dialogue_lines.append(" ".join(buffer))
             buffer = [] # Clear buffer for new dialogue
             is_dialogue_block = True
        elif is_dialogue_block:
             # Dialogue text line, clean simple tags and add to buffer
             cleaned_line = re.sub(r'<[^>]+>', '', line) # Remove simple HTML/XML tags
             cleaned_line = re.sub(r'{[^}]+}', '', cleaned_line) # Remove simple curly brace tags (e.g., {\an8})
             # More aggressive cleaning (optional): remove lines starting with typical non-dialogue chars
             # if not cleaned_line.startswith(('-', '[', '(')):
             if cleaned_line: # Only add if not empty after cleaning
                 buffer.append(cleaned_line)
        # else: Ignore lines that don't fit patterns (comments, etc.)


    # Add the last buffer if file doesn't end with an empty line
    if buffer: dialogue_lines.append(" ".join(buffer))

    # Join all collected dialogue lines into a single string with spaces
    final_text = " ".join(line for line in dialogue_lines if line)
    # Further cleanup: Replace multiple spaces with single space
    final_text = re.sub(r'\s{2,}', ' ', final_text).strip()
    return final_text

def load_text_from_file(ui:'EdgeTTSUi', file_path: str) -> str:
    """Opens a dialog to select a text (.txt or .srt) file and loads its content."""
    if not file_path:
        ui.update_status("File selection cancelled.");
        return None # User cancelled

    try:
        content = ""
        filename = os.path.basename(file_path)
        print(f"INFO: Loading file content from: {file_path}")

        if filename.lower().endswith(".srt"):
            # Parse SRT file
            content = _parse_srt(file_path)
            ui.update_status(f"✅ Loaded dialogue from {filename}" if content else f"⚠️ No dialogue found in SRT: {filename}")
            return content
        else:
            # Read plain text file
            try:
                # Try UTF-8 encoding first (more common)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    ui.update_status(f"✅ Loaded text from {file_path}")
                    return content
            except UnicodeDecodeError:
                # If UTF-8 fails, try default system encoding (less reliable)
                print(f"WARN: UTF-8 decoding failed for {filename}. Trying default system encoding.")
                try:
                    # Python 3: encoding=None uses default locale encoding
                    with open(file_path, 'r', encoding=None) as f:
                        content = f.read()
                        ui.update_status(f"✅ Loaded text from {file_path}")
                        return content
                except UnicodeDecodeError as e_enc:
                    # Handle specific encoding errors on second attempt
                    print(f"ERROR: Failed to read {filename} with default encoding: {e_enc}")
                    ui.update_status(f"❌ Error reading file (encoding issue)"); return
                except Exception as e_read_alt:
                     print(f"ERROR: Failed to read {filename} with default encoding: {e_read_alt}")
                     ui.update_status(f"❌ Error reading file"); return
            except Exception as e_read_main:
                 # Catch other file reading errors (e.g., permission)
                 print(f"ERROR: Failed to read file {filename}: {e_read_main}")
                 ui.update_status(f"❌ Error reading file"); return



    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}")
        ui.update_status("❌ Error: File not found.")
    except Exception as e:
        # Catch other errors during loading/parsing
        print(f"ERROR: Exception loading/processing file {file_path}: {e}")
        ui.update_status(f"❌ Error loading file.")
    return None