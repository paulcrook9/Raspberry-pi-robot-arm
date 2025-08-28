from evdev import ecodes

button1_code = 288
button2_code = 289

# Iterate through the ecodes module's contents to find a match
# This method works even if the 'by_value' attribute is missing
def find_name_from_value(value):
    for name, code in ecodes.__dict__.items():
        if isinstance(code, int) and code == value:
            return name
    return None

name1 = find_name_from_value(button1_code)
name2 = find_name_from_value(button2_code)

if name1:
    print(f"Code {button1_code} maps to: {name1}")
else:
    print(f"Code {button1_code} is not mapped.")

if name2:
    print(f"Code {button2_code} maps to: {name2}")
else:
    print(f"Code {button2_code} is not mapped.")