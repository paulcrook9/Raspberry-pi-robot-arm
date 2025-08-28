import evdev
from evdev import InputDevice, categorize, ecodes
from select import select

# Find the device by its name (recommended)
# ... (your existing device-finding code) ...

print(f"Reading ALL events from {dev.name}...")

while True:
    try:
        r, w, x = select([dev.fd], [], [])
        for fd in r:
            for event in dev.read():
                print(event) # This prints the raw event object
    except KeyboardInterrupt:
        break

print("\nExited.")