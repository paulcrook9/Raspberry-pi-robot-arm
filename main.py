import sounddevice as sd
import numpy as np
import webrtcvad
import collections
import wave
import sys
import os
import time
import re
import json
import robotArm as ra
import servo

# --- Audio Prompt Library ---
import soundfile as sf

# --- Vosk Imports ---
from vosk import Model, KaldiRecognizer
# set_log_level(-1) # You can try 'import vosk' and then vosk.set_log_level(-1) in main if logs are too verbose

# --- Configuration (General) ---
SAMPLE_RATE = 16000  # VAD and Vosk often work best at 16kHz
FRAME_MS = 30        # Frame size in milliseconds (WebRTC VAD supports 10, 20, or 30ms)
CHANNELS = 1         # Mono for VAD and Vosk
BUFFER_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000) # Number of samples per frame

# --- VAD Configuration ---
# *** IMPORTANT: Adjust VAD_MODE if needed. 0 is least aggressive, 3 is most. ***
# Since your previous VAD code worked, VAD_MODE 0 might be okay, but 1 or 2 can be more robust.
VAD_MODE = 0         # WebRTC VAD aggressiveness (0-3, 0 is often a good balance for general use)

# --- Command Recognition Logic ---
# Max total duration to listen for a command after the prompt.
COMMAND_MAX_DURATION_SECONDS = 5
# Number of consecutive silent frames AFTER detected speech to consider the command ended.
# 0.5 seconds of silence is 500ms / 30ms_per_frame = ~17 frames.
SILENCE_END_COMMAND_FRAMES = int(0.5 * 1000 / FRAME_MS)
# Number of consecutive voiced frames to CONFIRM the start of speech within the command window.
# This helps prevent false positives from brief noises. E.g., 3 * 30ms = 90ms of confirmed speech.
SPEECH_START_THRESHOLD_FRAMES = 3 

# --- Vosk Model Path ---
# VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "vosk-model-small-en-us-0.15")
VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model")
# --- List of valid commands ---
VALID_COMMANDS = ['up', 'down', 'left', 'right', 'forward', 'back', 'open', 'close']

# --- Audio Prompt Configuration ---
PROMPT_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "prompts","beep.wav")
WELCOME_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "prompts","helloBilly.wav")
INSTRUCTIONS_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "prompts","instructions2.wav")
STRETCH_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "prompts","stretch.wav")

# Output directory for recordings (for debugging/review)
output_dir = "vad_recordings"
os.makedirs(output_dir, exist_ok=True)

# --- Global States ---
vad_instance = webrtcvad.Vad(VAD_MODE)

# Vosk instances (initialized in main)
vosk_model = None
vosk_recognizer = None

# States for the command loop
STATE_IDLE = 0
STATE_PLAYING_PROMPT = 1
STATE_LISTENING_FOR_COMMAND = 2
current_state = STATE_IDLE

# Command listening specific buffers and flags
command_buffer = [] # Buffer for audio to send to Vosk
command_start_time = None # Timestamp when we entered STATE_LISTENING_FOR_COMMAND

# Flags/Counters *within* STATE_LISTENING_FOR_COMMAND for speech segmentation
is_currently_speaking_command = False # True if speech has started for the current command
voiced_frames_count_in_command = 0 # Counts consecutive voiced frames at the start of speech
silence_frames_count_after_speech = 0 # Counts consecutive silent frames *after* speech has started

# Cordinates for movement of robot arm
x = 0.0
y = 100.0
z = 200.0

def move_arm(x, y, z):
    """
    Placeholder function to move the robot arm to specified coordinates.
    Replace this with your actual robot arm control logic.
    """
    print(f"Moving arm to coordinates: x={x}, y={y}, z={z}")
    arm.moveStepMotorToTargetAxis([x, y, z])
    arm.setArmEnable(1)
    arm.setArmEnable(0)


def take_action(command):
    """
    Placeholder function to execute actions based on detected command.
    Replace this with your actual robot arm control logic.
    """

    global x, y, z
    print(f"\n*** ROBOT ARM ACTION: Executing '{command.upper()}' command! ***")
    # Example:
    if command == 'up':
        print("Moving arm UP...")
        z = z + 10.0 # Example increment, adjust as needed
        move_arm(x, y, z) # Call to move arm with updated coordinates
    elif command == 'down':
        print("Moving arm DOWN...")
        z = z - 10.0 # Example increment, adjust as needed
        move_arm(x, y, z) # Call to move arm with updated coordinates
    elif command == 'left':
        print("Moving arm LEFT...")
        x = x - 10.0 # Example increment, adjust as needed
        move_arm(x, y, z) # Call to move arm with updated coordinates
    elif command == 'right':
        print("Moving arm RIGHT...")
        x = x + 10.0 # Example increment, adjust as needed
        move_arm(x, y, z) # Call to move arm with updated coordinates
    elif command == 'forward':
        print("Moving arm FORWARD...")
        y = y + 10.0 # Example increment, adjust as needed
        move_arm(x, y, z)
    elif command == 'back':
        print("Moving arm BACK...")
        y = y - 10.0 # Example increment, adjust as needed
        move_arm(x, y, z)
    elif command == 'open':
        print("Opening gripper...")
        # Your robot arm control here
        # Initialize servo
        gripper.setServoAngle(0, 90)
        time.sleep(0.1)
    elif command == 'close':
        print("Closing gripper...")
        # Your robot arm control here
        # Initialize servo
        gripper.setServoAngle(0, 10) # Adjust angle as needed for your servo
        time.sleep(0.1)
    else:
        print(f"Unknown command: {command}")
    print("---------------------------------------------")

def process_and_reset_command_audio():
    """Processes the buffered audio using Vosk to identify commands and resets the state."""
    global current_state, command_buffer, command_start_time, \
           is_currently_speaking_command, voiced_frames_count_in_command, \
           silence_frames_count_after_speech

    if not command_buffer:
        print("No audio captured for command.")
        current_state = STATE_IDLE # Go back to idle, wait for next cycle
        return

    # Concatenate the audio from the buffer
    audio_for_vosk = np.concatenate(command_buffer)

    # Save the captured audio for debugging
    output_filename = os.path.join(output_dir, f"command_{int(time.time())}.wav")
    with wave.open(output_filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2) # 2 bytes for 16-bit audio
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_for_vosk.tobytes())
    print(f"Captured command audio saved to: {output_filename}")


    vosk_recognizer.AcceptWaveform(audio_for_vosk.tobytes())
    result_json = vosk_recognizer.Result() # Get final result for buffered audio

    try:
        result = json.loads(result_json)
        recognized_text = result.get('text', '').strip() # .strip() to remove leading/trailing whitespace
        print(f"Vosk transcribed: '{recognized_text}'")

        # --- Command Parsing ---
        detected_command = None
        # Make sure the recognized text is not empty before searching
        if recognized_text:
            for cmd in VALID_COMMANDS:
                # Use regex with word boundaries to ensure whole word match
                # Convert both to lowercase for case-insensitive matching
                if re.search(r'\b' + re.escape(cmd.lower()) + r'\b', recognized_text.lower()):
                    detected_command = cmd # Keep original casing for action
                    break # Found a command

        if detected_command:
            take_action(detected_command)
        else:
            print("No valid command recognized from transcription.")

    except json.JSONDecodeError:
        print(f"Vosk returned invalid JSON: {result_json}")
    except Exception as e:
        print(f"Error processing Vosk result: {e}")

    # Reset command listening state and internal flags
    command_buffer = [] # Clear buffer
    command_start_time = None
    is_currently_speaking_command = False
    voiced_frames_count_in_command = 0
    silence_frames_count_after_speech = 0
    current_state = STATE_IDLE # Go back to idle to wait for the next cycle
    print("\n--- Ready for next command. ---")


def audio_callback(indata, frames, time_info, status):
    """This is called (potentially) in a separate thread for each audio block."""
    global current_state, command_buffer, command_start_time, \
           is_currently_speaking_command, voiced_frames_count_in_command, \
           silence_frames_count_after_speech

    if status:
        print(f"SoundDevice Warning: {status}", file=sys.stderr)

    # Ensure data is 16-bit PCM and mono
    indata = indata.flatten().astype(np.int16)

    # Only process audio if we are in the listening for command state
    if current_state == STATE_LISTENING_FOR_COMMAND:
        # Check for global command timeout first
        if (time.time() - command_start_time) > COMMAND_MAX_DURATION_SECONDS:
            print(f"\nCommand listening timed out after {COMMAND_MAX_DURATION_SECONDS} seconds. Processing buffered audio.")
            process_and_reset_command_audio()
            return

        is_speech_vad = vad_instance.is_speech(indata.tobytes(), SAMPLE_RATE)

        if not is_currently_speaking_command: # We are waiting for speech to begin for this command
            if is_speech_vad:
                voiced_frames_count_in_command += 1
                if voiced_frames_count_in_command >= SPEECH_START_THRESHOLD_FRAMES:
                    is_currently_speaking_command = True
                    print(f"\rSpeech detected. Capturing command...            ") # Added spaces to clear line
                    # Start buffering from this confirmed speech point
                    command_buffer.append(indata)
                    silence_frames_count_after_speech = 0 # Reset silence after speech
            else:
                voiced_frames_count_in_command = 0 # Reset if silence breaks initial count
                sys.stdout.write(f"\rListening for command... (awaiting speech) ")
                sys.stdout.flush()

        else: # is_currently_speaking_command is True, we are actively capturing speech for the command
            command_buffer.append(indata) # Keep adding frames

            if is_speech_vad:
                silence_frames_count_after_speech = 0 # Reset silence counter if speech continues
                sys.stdout.write(f"\rListening for command... (speaking) ")
                sys.stdout.flush()
            else:
                silence_frames_count_after_speech += 1
                if silence_frames_count_after_speech >= SILENCE_END_COMMAND_FRAMES:
                    print(f"\nSilence detected after speech ({silence_frames_count_after_speech * FRAME_MS}ms). Processing command.")
                    process_and_reset_command_audio()
                    return # Exit callback, state will be reset for next cycle

                sys.stdout.write(f"\rListening for command... (silence after speech) ")
                sys.stdout.flush()

    # When in STATE_IDLE or STATE_PLAYING_PROMPT, we generally don't buffer
    # for command recognition. We just let VAD process the frames to keep its
    # internal state updated for when we transition to STATE_LISTENING_FOR_COMMAND.
    elif current_state == STATE_IDLE or current_state == STATE_PLAYING_PROMPT:
        try:
            # Process frames with VAD, but ignore the result. This keeps VAD "warmed up."
            _ = vad_instance.is_speech(indata.tobytes(), SAMPLE_RATE)
        except Exception as e:
            print(f"VAD error during idle/prompt processing: {e}", file=sys.stderr)


def play_prompt_and_listen():
    """Plays the audio prompt and then sets state to listen for command."""
    global current_state, command_start_time, \
           is_currently_speaking_command, voiced_frames_count_in_command, \
           silence_frames_count_after_speech

    if not os.path.exists(PROMPT_AUDIO_FILE):
        print(f"ERROR: Prompt audio file not found at {PROMPT_AUDIO_FILE}")
        current_state = STATE_IDLE # Revert to idle
        return

    time.sleep(3)

    print("Playing prompt...")
    current_state = STATE_PLAYING_PROMPT
    try:
        data, fs = sf.read(PROMPT_AUDIO_FILE, dtype='float32') # Read as float for sd.play
        
        # Resample and convert to mono if necessary. Using librosa or pydub is more robust,
        # but for simplicity, we'll give a warning if it doesn't match and assume it's close enough
        # or that the user converts manually.
        if fs != SAMPLE_RATE or data.ndim > 1:
            print("WARNING: Prompt WAV not 16kHz mono. Attempting basic conversion (may need manual pre-processing).")
            if data.ndim > 1:
                data = data.mean(axis=1) # Mix to mono (average channels)
            if fs != SAMPLE_RATE:
                # Basic check, but real resampling requires more robust libraries like librosa or scipy.signal.resample
                print("WARNING: Prompt samplerate does not match target. Please ensure prompt.wav is 16kHz.")
                # You might add a more sophisticated resampling here if needed.
        
        sd.play(data, samplerate=fs)
        sd.wait() # Wait for the prompt to finish playing
        print("Prompt finished. Now listening for command...")

        # After prompt, immediately transition to listening for command
        current_state = STATE_LISTENING_FOR_COMMAND
        command_start_time = time.time() # Start timer for overall command max duration
        
        # Reset all command-specific speech detection counters for the new command
        is_currently_speaking_command = False
        voiced_frames_count_in_command = 0
        silence_frames_count_after_speech = 0
        command_buffer.clear() # Ensure buffer is empty for the new command

    except Exception as e:
        print(f"Error playing prompt: {e}")
        current_state = STATE_IDLE # Revert to idle
        return

def play_welcome_and_calibrate():
    """Plays the audio welcome prompt and calibrates robot arm."""

    global x, y, z

    if not os.path.exists(WELCOME_AUDIO_FILE):
        print(f"ERROR: Welcome audio file not found at {WELCOME_AUDIO_FILE}")
        current_state = STATE_IDLE # Revert to idle
        return
    
    if not os.path.exists(STRETCH_AUDIO_FILE):
        print(f"ERROR: Calibration audio file not found at {STRETCH_AUDIO_FILE}")
        current_state = STATE_IDLE # Revert to idle
        return
       
    if not os.path.exists(INSTRUCTIONS_AUDIO_FILE):
        print(f"ERROR: Calibration audio file not found at {INSTRUCTIONS_AUDIO_FILE}")
        current_state = STATE_IDLE # Revert to idle
        return


    print("Playing welcome...")
    try:
        data, fs = sf.read(WELCOME_AUDIO_FILE, dtype='float32') # Read as float for sd.play
        
        # Resample and convert to mono if necessary. Using librosa or pydub is more robust,
        # but for simplicity, we'll give a warning if it doesn't match and assume it's close enough
        # or that the user converts manually.
        if fs != SAMPLE_RATE or data.ndim > 1:
            print("WARNING: Welcome WAV not 16kHz mono. Attempting basic conversion (may need manual pre-processing).")
            if data.ndim > 1:
                data = data.mean(axis=1) # Mix to mono (average channels)
            if fs != SAMPLE_RATE:
                # Basic check, but real resampling requires more robust libraries like librosa or scipy.signal.resample
                print("WARNING: Welcome samplerate does not match target. Please ensure helloBilly.wav is 16kHz.")
                # You might add a more sophisticated resampling here if needed.
        
        sd.play(data, samplerate=fs)
        sd.wait() # Wait for the prompt to finish playing
        print("Welcome finished.")

    except Exception as e:
        print(f"Error playing welcome: {e}")
        current_state = STATE_IDLE # Revert to idle
        return

    print("Playing stretch...")
    try:
        data, fs = sf.read(STRETCH_AUDIO_FILE, dtype='float32') # Read as float for sd.play
        
        # Resample and convert to mono if necessary. Using librosa or pydub is more robust,
        # but for simplicity, we'll give a warning if it doesn't match and assume it's close enough
        # or that the user converts manually.
        if fs != SAMPLE_RATE or data.ndim > 1:
            print("WARNING: Stretch WAV not 16kHz mono. Attempting basic conversion (may need manual pre-processing).")
            if data.ndim > 1:
                data = data.mean(axis=1) # Mix to mono (average channels)
            if fs != SAMPLE_RATE:
                # Basic check, but real resampling requires more robust libraries like librosa or scipy.signal.resample
                print("WARNING: Stretch samplerate does not match target. Please ensure stretch.wav is 16kHz.")
                # You might add a more sophisticated resampling here if needed.
        
        sd.play(data, samplerate=fs)
        sd.wait() # Wait for the prompt to finish playing
        print("Stretch finished.")

    

    except Exception as e:
        print(f"Error playing stretch: {e}")
        current_state = STATE_IDLE # Revert to idle
        return
    
    
    
    time.sleep(1)
    
    arm.setArmEnable(0)

    arm.setFrequency(1000)
    arm.setArmToSensorPoint()
    arm.setArmEnable(1)
    arm.setArmEnable(0)

    arm.moveStepMotorToTargetAxis([x, y, z])
    arm.setArmEnable(1)
    arm.setArmEnable(0)

    print("Playing instructions...")
    try:
        data, fs = sf.read(INSTRUCTIONS_AUDIO_FILE, dtype='float32') # Read as float for sd.play
        
        # Resample and convert to mono if necessary. Using librosa or pydub is more robust,
        # but for simplicity, we'll give a warning if it doesn't match and assume it's close enough
        # or that the user converts manually.
        if fs != SAMPLE_RATE or data.ndim > 1:
            print("WARNING: Insructions WAV not 16kHz mono. Attempting basic conversion (may need manual pre-processing).")
            if data.ndim > 1:
                data = data.mean(axis=1) # Mix to mono (average channels)
            if fs != SAMPLE_RATE:
                # Basic check, but real resampling requires more robust libraries like librosa or scipy.signal.resample
                print("WARNING: Instructions samplerate does not match target. Please ensure stretch.wav is 16kHz.")
                # You might add a more sophisticated resampling here if needed.
        
        sd.play(data, samplerate=fs)
        sd.wait() # Wait for the prompt to finish playing
        print("Instructions finished.")

    

    except Exception as e:
        print(f"Error playing instructions: {e}")
        current_state = STATE_IDLE # Revert to idle
        return

if __name__ == "__main__":
    arm = ra.Arm() #instantiate robot arm object
    gripper = servo.Servo() # instantiate servo object
    
    

    play_welcome_and_calibrate()  # Play welcome and calibration prompts

    



    print(f"Robot Arm Voice Control - Command Prompt Mode")
    print(f"Listening for commands: {', '.join(VALID_COMMANDS)}")
    print("Press Ctrl+C to stop.")

    if not os.path.exists(VOSK_MODEL_PATH):
        print(f"\nERROR: Vosk model not found at '{VOSK_MODEL_PATH}'.")
        print(f"Please download a small Vosk English model from https://alphacephei.com/vosk/models and extract it to '{os.path.join(os.path.dirname(__file__), 'model', 'vosk-model-small-en-us-0.15')}' (or adjust VOSK_MODEL_PATH).")
        sys.exit(1)

    if not os.path.exists(PROMPT_AUDIO_FILE):
        print(f"\nERROR: Prompt audio file not found at '{PROMPT_AUDIO_FILE}'.")
        print("Please create or place a 'prompt.wav' file (16kHz, mono, 16-bit PCM) in the script directory.")
        sys.exit(1)

    try:
        # Initialize Vosk
        vosk_model = Model(VOSK_MODEL_PATH)
        vosk_recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
        print("Vosk initialized successfully.")

        # Start the audio stream
        with sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BUFFER_SIZE,
                            channels=CHANNELS, dtype='int16', callback=audio_callback):
            while True:
                # Main loop manages the state transitions
                if current_state == STATE_IDLE:
                    play_prompt_and_listen()
                elif current_state == STATE_LISTENING_FOR_COMMAND:
                    # The audio_callback handles the listening and processing in this state
                    time.sleep(0.1) # Keep the main thread alive, yield control
                elif current_state == STATE_PLAYING_PROMPT:
                    time.sleep(0.1) # Waiting for prompt to finish playing (sd.wait() handles blocking)

    except KeyboardInterrupt:
        print("\nStopping audio capture.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Exited.") 