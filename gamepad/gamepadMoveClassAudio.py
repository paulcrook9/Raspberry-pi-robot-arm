import sounddevice as sd
import sys
import os
import time
import evdev
from evdev import InputDevice, categorize, ecodes
from select import select

# --- Audio Prompt Library ---
import soundfile as sf

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import robotArm as ra
import servo

# --- Audio Prompt Configuration ---
WELCOME_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "../prompts","helloBilly.wav")
STRETCH_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "../prompts","stretch.wav")
KEYS_AUDIO_FILE = os.path.join(os.path.dirname(__file__), "../prompts","keys.wav")

class RobotArmController:
    # Define movement limits for the arm
    X_LIMITS = (-110, 110)
    Y_LIMITS = (60, 250)
    Z_LIMITS = (20, 320)

    def __init__(self):
        # Initialize robot arm state
        self.ex = 0.0
        self.y = 100.0
        self.z = 200.0
        self.arm = ra.Arm()
        self.gripper = servo.Servo()

        # The following variables will be used to track the last movement command
        self.last_x_command = None
        self.last_y_command = None
        self.last_z_command = None

        # Play welcome audio
        self.play_audio(WELCOME_AUDIO_FILE)
        time.sleep(1)
        self.play_audio(STRETCH_AUDIO_FILE) # Prompt to stretch arm


    def play_audio(self, file_path):
        """Plays an audio file."""
        data, fs = sf.read(file_path, dtype='float32')
        sd.play(data, fs)
        sd.wait()
    
    
    def calibrate(self):
        """Calibrates the robot arm to a known position."""
        print("\n*** Calibrating robot arm... ***")
        self.arm.setArmEnable(0)
        self.arm.setFrequency(1000)
        self.arm.setArmToSensorPoint()
        self.arm.setArmEnable(1)
        self.arm.setArmEnable(0)

        self.move_to_coords(self.ex, self.y, self.z)
        print("Calibration complete.")

    def move_to_coords(self, x, y, z):
        """Moves the arm to the specified coordinates."""
        print(f"Moving arm to coordinates: x={x}, y={y}, z={z}")
        self.arm.moveStepMotorToTargetAxis([x, y, z])
        self.arm.setArmEnable(1)
        self.arm.setArmEnable(0)

    def stop_arm_movement(self):
        """Stops the robot arm's movement."""
        print("Stopping arm movement...")
        self.arm.setArmEnable(0)
        
    def handle_command(self, command):
        """Handles movement and gripper commands, including range checks."""
        new_ex, new_y, new_z = self.ex, self.y, self.z
        
        # Determine the new coordinates based on the command
        if command == 'up':
            new_z += 10.0
        elif command == 'down':
            new_z -= 10.0
        elif command == 'left':
            new_ex -= 10.0
        elif command == 'right':
            new_ex += 10.0
        elif command == 'forward':
            new_y += 10.0
        elif command == 'back':
            new_y -= 10.0
        elif command == 'open':
            print("Opening gripper...")
            self.gripper.setServoAngle(0, 90)
            time.sleep(0.1)
            return  # Exit function after a non-movement command
        elif command == 'close':
            print("Closing gripper...")
            self.gripper.setServoAngle(0, 10)
            time.sleep(0.1)
            return  # Exit function after a non-movement command
        
        # Perform range checks on the new coordinates
        if (self.X_LIMITS[0] <= new_ex <= self.X_LIMITS[1] and
                self.Y_LIMITS[0] <= new_y <= self.Y_LIMITS[1] and
                self.Z_LIMITS[0] <= new_z <= self.Z_LIMITS[1]):
            
            print(f"\n*** ROBOT ARM ACTION: Executing '{command.upper()}' command! ***")
            # Update instance variables and move the arm
            self.ex, self.y, self.z = new_ex, new_y, new_z
            self.move_to_coords(self.ex, self.y, self.z)
        else:
            print(f"Warning: Command '{command.upper()}' would exceed arm limits. Movement cancelled.")
        print("---------------------------------------------")

def main():
    # Find the device by its name (recommended)
    devices = [InputDevice(path) for path in evdev.list_devices()]
    dev = None
    for device in devices:
        if "USB gamepad           " in device.name:
            dev = device
            break
    
    if not dev:
        print("Joystick not found.")
        sys.exit(1)

    controller = RobotArmController()
    controller.calibrate()
    controller.play_audio(KEYS_AUDIO_FILE) # Prompt to show keys

    # Wait for a read event
    print("\nReading joystick input...")
    try:
        while True:
            r, w, x = select([dev.fd], [], [], 0.01) # Set a small timeout
            for fd in r:
                for event in dev.read():
                    if event.type == ecodes.EV_KEY:
                        if event.value == 1:  # Button press
                            if event.code == 288:
                                controller.handle_command("forward")
                            elif event.code == 289:
                                controller.handle_command("back")
                            elif event.code == ecodes.BTN_TOP2:
                                controller.handle_command("open")
                            elif event.code == ecodes.BTN_PINKIE:
                                controller.handle_command("close")
                    
                    elif event.type == ecodes.EV_ABS:
                        # Horizontal movement (X-axis)
                        if event.code == ecodes.ABS_X:
                            if event.value == 0:
                                controller.handle_command("left")
                            elif event.value == 255:
                                controller.handle_command("right")
                            elif event.value == 127:
                                controller.stop_arm_movement()

                        # Vertical movement (Y-axis)
                        elif event.code == ecodes.ABS_Y:
                            if event.value == 0:
                                controller.handle_command("up")
                            elif event.value == 255:
                                controller.handle_command("down")
                            elif event.value == 127:
                                controller.stop_arm_movement()
    except KeyboardInterrupt:
        print("\nExited.")
    finally:
        controller.stop_arm_movement()


if __name__ == "__main__":
    main()