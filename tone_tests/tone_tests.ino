// Uno_Melody_Player.ino
// ----------------------------------------------------------------------
// Plays the melody data using the standard Arduino tone() function.
// Designed for Arduino Uno R3, which requires careful memory management.
// ----------------------------------------------------------------------

// *** IMPORTANT WARNING FOR ARDUINO UNO R3 ***
// The Uno has limited Flash (32KB) and RAM (2KB). If your MIDI file 
// is very long or complex, the generated C array may exceed the Uno's 
// storage capacity, resulting in compilation errors or unexpected behavior.
// If this happens, try a shorter MIDI file or switch to an ESP32 or Mega board.
// ***

// Required for the PROGMEM functions (accessing data from Flash memory)
#include <avr/pgmspace.h> 

// Includes the generated data files
#include "pitches.h"
#include "raise_up_your_bat.h" 

// --- Configuration ---
// Define the digital pin connected to the passive buzzer or speaker
const int BUZZZER_PIN = 8; 

// --- Setup ---
void setup() {
  // Initialize serial communication for debugging output
  Serial.begin(9600);
  Serial.println("\n--- Arduino Uno Melody Player ---");
  
  // Set the buzzer pin as an output.
  pinMode(BUZZZER_PIN, OUTPUT);
}

// --- Main Loop ---
void loop() {
  playMelody();
  
  // Halt the loop after the song finishes to prevent continuous playback.
  while(true) {
    delay(1000); 
  }
}

// --- Melody Play Function ---
void playMelody() {
  // Iterate through the notes in the melody_data array.
  for (int thisNote = 0; thisNote < melody_length; thisNote++) {
    
    // Read pitch and duration from Flash memory (PROGMEM).
    // This is crucial for the Uno to save valuable RAM.
    int pitch = pgm_read_word_near(melody + thisNote);
    int noteDuration = pgm_read_word_near(durations + thisNote);
    
    // Check if the pitch is a rest (REST is defined as 0 in pitches.h).
    if (pitch != REST) {
      // Plays a tone at the specified pitch for the noteDuration time.
      tone(BUZZZER_PIN, pitch, noteDuration);
      
      Serial.print("Playing Note: ");
      Serial.print(pitch);
      Serial.print(" Hz for ");
      Serial.print(noteDuration);
      Serial.println(" ms");
    } else {
      // Stop the tone for a REST.
      noTone(BUZZZER_PIN); 
      Serial.print("Rest for ");
      Serial.print(noteDuration);
      Serial.println(" ms");
    }

    // Pause for the exact duration of the note/rest.
    delay(noteDuration);

    // Stop the tone explicitly to ensure a clean break before the next note/pause.
    noTone(BUZZZER_PIN); 

    // Pause for a small interval before the next note starts.
    // This pause provides a necessary staccato effect.
    #ifdef PAUSE_BETWEEN_NOTES_MS
      delay(PAUSE_BETWEEN_NOTES_MS);
    #else
      delay(20); // Default pause if macro not found (20ms)
    #endif
  }
  
  Serial.println("Melody finished.");
}