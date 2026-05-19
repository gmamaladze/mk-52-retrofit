import glob
import os
import time

import RPi.GPIO as GPIO
import yaml

import emulator
import display_b
import keypad
from emulator.keystroke_loader import enter_program

GPIO.setmode(GPIO.BOARD)

# Repo-root/programs/ — controller/app.py is one level deep.
PROGRAMS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "programs")


def find_program(number):
    """Find programs/NN-*.yaml for the given number. Returns (path, dict) or None."""
    for path in sorted(glob.glob(os.path.join(PROGRAMS_DIR, f"{number:02d}-*.yaml"))):
        with open(path, encoding="utf-8") as f:
            return path, yaml.safe_load(f)
    return None


def load_from_rom(em, dsp, digits):
    """Mirror the original МК-52 A↑ behavior: load program by number from
    the on-disk "ROM" (programs/NN-*.yaml). `digits` is whatever the user
    typed before pressing A↑.
    """
    if not digits:
        dsp.log("ENTER NUMBER")
        time.sleep(1.0)
        return
    try:
        n = int(digits)
    except ValueError:
        dsp.log(f"BAD: {digits}".ljust(16))
        time.sleep(1.0)
        return
    found = find_program(n)
    if not found:
        dsp.log(f"NO PROG {n:02d}".ljust(16))
        time.sleep(1.5)
        return
    _, prog = found
    title = prog.get("title", prog.get("id", ""))[:9]
    dsp.log(f"LOAD {n:02d} {title}".ljust(16))
    time.sleep(0.4)
    # Suppress chip-driven display flicker during the keystroke entry so
    # the load message stays visible.
    saved = em.on_display
    em.on_display = None
    try:
        steps = enter_program(em, prog["code"])
    finally:
        em.on_display = saved
    dsp.log(f"OK {steps:02d} STEPS".ljust(16))
    time.sleep(1.2)
    # Chip resumes driving the display from here.


def main():
    dsp = display_b.Display()
    dsp.log("George's MK 52")

    kbd = keypad.Keypad(24, 23, 22, 21, 19, 18, 16, 15, 13, 12, 11, 10, 8, 7)

    with emulator.Машина(on_display=dsp.show, on_log=dsp.log) as em:
        digit_buffer = ""
        for x, y, txt in kbd.get_key_presses():
            # A↑ — load from ROM. keypad.py maps it to row 0 col 1 = (3, 0).
            if (x, y) == (3, 0):
                load_from_rom(em, dsp, digit_buffer)
                digit_buffer = ""
                continue
            # Track digits as they're pressed so A↑ knows which program to load.
            if y == 1 and 2 <= x <= 11:
                digit_buffer = (digit_buffer + str(x - 2))[-2:]
            else:
                digit_buffer = ""
            em.press_button(x, y)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
