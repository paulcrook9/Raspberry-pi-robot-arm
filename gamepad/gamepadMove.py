import os
import time
import sys
# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import robotArm as ra
import servo
import evdev
from evdev import InputDevice, categorize, ecodes
from select import select

#global variables
# Cordinates for movement of robot arm
ex = 0.0
y = 100.0
z = 200.0

# This is a placeholder for your robot arm control functions
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

    global ex, y, z
    print(f"\n*** ROBOT ARM ACTION: Executing '{command.upper()}' command! ***")
    # Example:
    if command == 'up':
        print("Moving arm UP...")
        z = z + 10.0 # Example increment, adjust as needed
        move_arm(ex, y, z) # Call to move arm with updated coordinates
    elif command == 'down':
        print("Moving arm DOWN...")
        z = z - 10.0 # Example increment, adjust as needed
        move_arm(ex, y, z) # Call to move arm with updated coordinates
    elif command == 'left':
        print("Moving arm LEFT...")
        ex = ex - 10.0 # Example increment, adjust as needed
        move_arm(ex, y, z) # Call to move arm with updated coordinates
    elif command == 'right':
        print("Moving arm RIGHT...")
        ex = ex + 10.0 # Example increment, adjust as needed
        move_arm(ex, y, z) # Call to move arm with updated coordinates
    elif command == 'forward':
        print("Moving arm FORWARD...")
        y = y + 10.0 # Example increment, adjust as needed
        move_arm(ex, y, z)
    elif command == 'back':
        print("Moving arm BACK...")
        y = y - 10.0 # Example increment, adjust as needed
        move_arm(ex, y, z)
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

def calibrate_arm():
    """
    Placeholder function to calibrate the robot arm.
    Replace this with your actual calibration logic.
    """
    print("Calibrating robot arm...")
    arm.setArmEnable(0)

    arm.setFrequency(1000)
    arm.setArmToSensorPoint()
    arm.setArmEnable(1)
    arm.setArmEnable(0)

    arm.moveStepMotorToTargetAxis([ex, y, z])
    arm.setArmEnable(1)
    arm.setArmEnable(0)
    print("Calibration complete.")
    time.sleep(1)


if __name__ == "__main__":

    # Find the device by its name (recommended)
    devices = [InputDevice(path) for path in evdev.list_devices()]
    dev = None
    for device in devices:
        if "USB gamepad           " in device.name: # Check for the name of your joystick
            dev = device
            break

    if not dev:
        print("Joystick not found.")
        exit()

    arm = ra.Arm() #instantiate robot arm object
    gripper = servo.Servo() # instantiate servo object

    # Calibrate the arm at the start
    calibrate_arm()

    # Wait for a read event
    while True:
        try:
            r, w, x = select([dev.fd], [], [])
            for fd in r:
                for event in dev.read():
                    # Filter for key and absolute axis events
                    if event.type == ecodes.EV_KEY:
                        if event.value == 1:  # Button press
                        # Check for the correct button codes
                            if event.code == ecodes.BTN_JOYSTICK:
                                take_action("forward")
                            elif event.code == ecodes.BTN_THUMB:
                                take_action("back")
                            elif event.code == ecodes.BTN_TOP2:
                                take_action("open")
                            elif event.code == ecodes.BTN_PINKIE:
                                take_action("close")


                    elif event.type == ecodes.EV_ABS:
                    # Horizontal movement (X-axis)
                        if event.code == ecodes.ABS_X:
                            if event.value == 0:
                                take_action("left")
                            elif event.value == 255:
                                take_action("right")

                        # Vertical movement (Y-axis)
                        elif event.code == ecodes.ABS_Y:
                            if event.value == 0:
                                take_action("up")
                            elif event.value == 255:
                                take_action("down")
    
        except KeyboardInterrupt:
            break

print("\nExited.")