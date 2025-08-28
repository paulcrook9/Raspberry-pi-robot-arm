import evdev
from evdev import InputDevice, categorize, ecodes
from select import select

# This is a placeholder for your robot arm control functions
def move_arm(direction):
    print(f"Moving arm {direction}...")
def open_gripper():
    print("Opening gripper...")
def close_gripper():
    print("Closing gripper...")
def stop_arm_movement():
    print("Stopping arm movement...")


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

print(f"Reading events from {dev.name}...")

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
                            move_arm("forward")
                        elif event.code == ecodes.BTN_THUMB:
                            move_arm("back")
                        elif event.code == ecodes.BTN_TOP2:
                            open_gripper()
                        elif event.code == ecodes.BTN_PINKIE:
                            close_gripper()
                    elif event.value == 0:  # Button release
                        if event.code in [ecodes.BTN_JOYSTICK, ecodes.BTN_THUMB, ecodes.BTN_TOP2, ecodes.BTN_PINKIE]:
                            stop_arm_movement()

                elif event.type == ecodes.EV_ABS:
                    # Horizontal movement (X-axis)
                    if event.code == ecodes.ABS_X:
                        if event.value == 0:
                            move_arm("left")
                        elif event.value == 255:
                            move_arm("right")
                        elif event.value == 127:
                            stop_arm_movement()

                    # Vertical movement (Y-axis)
                    elif event.code == ecodes.ABS_Y:
                        if event.value == 0:
                            move_arm("up")
                        elif event.value == 255:
                            move_arm("down")
                        elif event.value == 127:
                            stop_arm_movement()

    except KeyboardInterrupt:
        break

print("\nExited.")