# app.py
# ----------------------------------------------------------------------------------
# Python script to convert a single-track MIDI file into C arrays (pitch and duration)
# for use with the Arduino tone() function or ESP32 LEDC on microcontrollers.
# ----------------------------------------------------------------------------------

import mido
import sys
import os
import shutil
from pathlib import Path

# --- Configuration Section ---
#
# !! USER ACTION REQUIRED !!
# 1. Place your MIDI file in the same directory as this script (app.py).
# 2. Update the variable below with the EXACT name of your MIDI file.
# ---------------------------------------------------------------------
MIDI_FILENAME = "raise_up_your_bat.mid" # <--- EDIT THIS LINE (e.g., "MySong.mid")

# The target folder where the converted C array file will be placed.
OUTPUT_DIR = Path("MIDI_Tune_Player")
OUTPUT_H_FILENAME = OUTPUT_DIR / "melody_data.h"

# Directory where previous versions of melody_data.h will be moved for backup
BACKUP_DIR = OUTPUT_DIR / "Backups"

# Standard MIDI Note Number to Macro Name mapping (where 60 is C4).
# This provides the link from MIDI data (note number) to the Arduino header file (pitches.h)
MIDI_PITCH_TO_MACRO = {
    # Octave 0 (C0 = 12)
    12: "NOTE_C0", 13: "NOTE_CS0", 14: "NOTE_D0", 15: "NOTE_DS0", 16: "NOTE_E0", 17: "NOTE_F0", 18: "NOTE_FS0", 19: "NOTE_G0", 20: "NOTE_GS0", 21: "NOTE_A0", 22: "NOTE_AS0", 23: "NOTE_B0",
    # Octave 1 (C1 = 24)
    24: "NOTE_C1", 25: "NOTE_CS1", 26: "NOTE_D1", 27: "NOTE_DS1", 28: "NOTE_E1", 29: "NOTE_F1", 30: "NOTE_FS1", 31: "NOTE_G1", 32: "NOTE_GS1", 33: "NOTE_A1", 34: "NOTE_AS1", 35: "NOTE_B1",
    # Octave 2 (C2 = 36)
    36: "NOTE_C2", 37: "NOTE_CS2", 38: "NOTE_D2", 39: "NOTE_DS2", 40: "NOTE_E2", 41: "NOTE_F2", 42: "NOTE_FS2", 43: "NOTE_G2", 44: "NOTE_GS2", 45: "NOTE_A2", 46: "NOTE_AS2", 47: "NOTE_B2",
    # Octave 3 (C3 = 48)
    48: "NOTE_C3", 49: "NOTE_CS3", 50: "NOTE_D3", 51: "NOTE_DS3", 52: "NOTE_E3", 53: "NOTE_F3", 54: "NOTE_FS3", 55: "NOTE_G3", 56: "NOTE_GS3", 57: "NOTE_A3", 58: "NOTE_AS3", 59: "NOTE_B3",
    # Octave 4 (C4 = 60)
    60: "NOTE_C4", 61: "NOTE_CS4", 62: "NOTE_D4", 63: "NOTE_DS4", 64: "NOTE_E4", 65: "NOTE_F4", 66: "NOTE_FS4", 67: "NOTE_G4", 68: "NOTE_GS4", 69: "NOTE_A4", 70: "NOTE_AS4", 71: "NOTE_B4",
    # Octave 5 (C5 = 72)
    72: "NOTE_C5", 73: "NOTE_CS5", 74: "NOTE_D5", 75: "NOTE_DS5", 76: "NOTE_E5", 77: "NOTE_F5", 78: "NOTE_FS5", 79: "NOTE_G5", 80: "NOTE_GS5", 81: "NOTE_A5", 82: "NOTE_AS5", 83: "NOTE_B5",
    # Octave 6 (C6 = 84)
    84: "NOTE_C6", 85: "NOTE_CS6", 86: "NOTE_D6", 87: "NOTE_DS6", 88: "NOTE_E6", 89: "NOTE_F6", 90: "NOTE_FS6", 91: "NOTE_G6", 92: "NOTE_GS6", 93: "NOTE_A6", 94: "NOTE_AS6", 95: "NOTE_B6",
    # Octave 7 (C7 = 96)
    96: "NOTE_C7", 97: "NOTE_CS7", 98: "NOTE_D7", 99: "NOTE_DS7", 100: "NOTE_E7", 101: "NOTE_F7", 102: "NOTE_FS7", 103: "NOTE_G7", 104: "NOTE_GS7", 105: "NOTE_A7", 106: "NOTE_AS7", 107: "NOTE_B7",
    # Octave 8 (C8 = 108)
    108: "NOTE_C8", 109: "NOTE_CS8", 110: "NOTE_D8", 111: "NOTE_DS8", 112: "NOTE_E8", 113: "NOTE_F8", 114: "NOTE_FS8", 115: "NOTE_G8", 116: "NOTE_GS8", 117: "NOTE_A8", 118: "NOTE_AS8", 119: "NOTE_B8"
}

# --- Core Logic ---

def ticks_to_ms(ticks, tempo_us, ticks_per_beat):
    """Converts MIDI ticks into milliseconds (ms)."""
    # Formula: (ticks * microseconds_per_beat) / (ticks_per_beat * 1000)
    return (ticks * tempo_us) / (ticks_per_beat * 1000.0)

def convert_midi_to_arrays(filename):
    """Converts a MIDI file to two C++ arrays (melody and duration)."""
    try:
        mid = mido.MidiFile(filename)
    except FileNotFoundError:
        print(f"ERROR: MIDI file '{filename}' not found. Check the name and location.")
        return None, None
    except Exception as e:
        print(f"ERROR loading MIDI file: {e}")
        return None, None

    tpb = mid.ticks_per_beat
    tempo_us = mido.bpm2tempo(120)  # Default to 120 BPM (500,000 us/beat)

    melody_macros = []
    duration_ms = []
    held_notes = {}
    current_time_ticks = 0

    # Find the first track containing notes
    track = next((t for t in mid.tracks if any(msg.type == 'note_on' for msg in t)), mid.tracks[0])

    # Pre-scan for initial tempo
    for msg in track:
        if msg.type == 'set_tempo':
            tempo_us = msg.tempo
            break

    # Process events to extract a monophonic melody
    for msg in track:
        current_time_ticks += msg.time
        
        # Tempo change updates the tempo for subsequent time conversions
        if msg.type == 'set_tempo':
            tempo_us = msg.tempo
            continue # No note event, so skip to next message

        is_note_on = msg.type == 'note_on' and msg.velocity > 0
        is_note_off = msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)

        # --- Handle Monophonic Melody Extraction ---
        if is_note_on:
            note = msg.note

            # If a note is already held (monophonic rule: close the previous one)
            if held_notes:
                for held_note, start_ticks in list(held_notes.items()):
                    # Calculate duration of the *previous* note up to this point
                    duration_ticks = current_time_ticks - start_ticks
                    
                    if duration_ticks > 0:
                        macro_name = MIDI_PITCH_TO_MACRO.get(held_note, "REST")
                        duration = round(ticks_to_ms(duration_ticks, tempo_us, tpb))
                        
                        melody_macros.append(macro_name)
                        duration_ms.append(duration)
                    
                    del held_notes[held_note] # Release the previous note
            
            # Start tracking the new note
            held_notes[note] = current_time_ticks

        elif is_note_off:
            note = msg.note
            if note in held_notes:
                start_ticks = held_notes[note]
                
                # Calculate duration of the note
                duration_ticks = current_time_ticks - start_ticks
                
                if duration_ticks > 0:
                    macro_name = MIDI_PITCH_TO_MACRO.get(note, "REST")
                    duration = round(ticks_to_ms(duration_ticks, tempo_us, tpb))
                    
                    melody_macros.append(macro_name)
                    duration_ms.append(duration)
                
                del held_notes[note] # Release the current note
                
    if not melody_macros:
        print("WARNING: No notes were extracted from the MIDI file.")

    return melody_macros, duration_ms

def backup_existing_file(filepath: Path):
    """Backs up the existing melody_data.h file before replacement."""
    if not filepath.exists():
        return

    # Extract the original MIDI filename from the first line of the existing file
    midi_source_name = "previous_melody"
    try:
        with open(filepath, 'r') as f:
            # Skip initial comment lines until we find the GENERATED FROM tag
            for line in f:
                if 'GENERATED FROM:' in line:
                    # Extract the filename and clean it up for the backup
                    midi_source_name = line.split(':')[1].strip().replace('.mid', '').strip()
                    break
    except Exception:
        # Default name if file is unreadable or format is wrong
        pass
    
    # Create the backup directory if it doesn't exist
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Determine the unique backup filename (e.g., IRIS OUT.h)
    backup_filename = BACKUP_DIR / f"{midi_source_name.replace(' ', '_')}.h"
    
    # Check for duplicates and append a counter if necessary
    counter = 1
    original_backup_filename = backup_filename
    while backup_filename.exists():
        # Append a counter to the stem if the file already exists
        backup_filename = original_backup_filename.with_stem(f"{original_backup_filename.stem}_{counter}")
        counter += 1

    # Move/Rename the old file to the backup location
    shutil.move(filepath, backup_filename)
    print(f"INFO: Existing file backed up to: '{backup_filename.name}' in the '{BACKUP_DIR}' folder.")

def generate_header_file(melody, durations, output_filename, midi_source):
    """Writes the C++ arrays to a header file, using C++ best practices."""
    if not melody:
        print("ERROR: No melody data extracted. Cannot generate file.")
        return

    # Use a clean, formatted block for the arrays
    melody_str = ',\n    '.join(melody)
    duration_str = ',\n    '.join(map(str, durations))
    
    # Ensure the output directory exists
    output_filename.parent.mkdir(parents=True, exist_ok=True)

    # Format the output C++ code for Arduino (using PROGMEM for Uno)
    content = f"""
/*************************************************
 * GENERATED FROM: {midi_source}
 * DO NOT EDIT THIS FILE MANUALLY
 *
 * This file contains the C-arrays for the melody pitch and duration.
 * It is designed for use with the Arduino tone() function or ESP32 LEDC.
 * The pitches (e.g., NOTE_C4) are defined in 'pitches.h'.
 *************************************************/
#pragma once
#include "pitches.h"

// The notes array (pitch macro names from pitches.h)
// PROGMEM is used to store the data in Flash memory on Uno/Nano.
const int melody[] PROGMEM = {{
    {melody_str}
}};

// The duration array in milliseconds (ms)
const int durations[] PROGMEM = {{
    {duration_str}
}};

// The total number of notes in the melody (must match the lengths of both arrays)
const int melody_length = sizeof(melody) / sizeof(melody[0]);
"""
    try:
        with open(output_filename, 'w') as f:
            f.write(content.strip())
        
        print(f"\nSUCCESS: Generated C++ header file: '{output_filename}'")
        print(f"Total notes extracted: {len(melody)}")

    except Exception as e:
        print(f"ERROR writing file: {e}")

if __name__ == '__main__':
    print(f"--- MIDI to Arduino Converter ({MIDI_FILENAME}) ---")
    
    # Check for required library
    try:
        import mido
    except ImportError:
        print("ERROR: The 'mido' library is not installed.")
        print("Please run: pip install mido")
        sys.exit(1)
        
    # 1. Backup existing file if it exists
    backup_existing_file(OUTPUT_H_FILENAME)
        
    # 2. Convert the MIDI file
    melody_macros, duration_ms = convert_midi_to_arrays(MIDI_FILENAME)
    
    # 3. Generate the new header file
    if melody_macros and duration_ms:
        generate_header_file(melody_macros, duration_ms, OUTPUT_H_FILENAME, MIDI_FILENAME)
