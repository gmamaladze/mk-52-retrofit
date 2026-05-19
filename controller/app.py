import glob
import os
import queue
import sys
import threading
import time

import RPi.GPIO as GPIO
import yaml

import emulator
import display_b
import keypad
from emulator.keystroke_loader import enter_program

# webui/ is a sibling of controller/ in the repo root.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webui"))
import server as webui_server  # noqa: E402

GPIO.setmode(GPIO.BOARD)

PROGRAMS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "programs")

WEBUI_HOST = os.environ.get("MK52_WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.environ.get("MK52_WEBUI_PORT", "8080"))


def find_program(number):
    for path in sorted(glob.glob(os.path.join(PROGRAMS_DIR, f"{number:02d}-*.yaml"))):
        with open(path, encoding="utf-8") as f:
            return path, yaml.safe_load(f)
    return None


def load_from_rom(em, dsp, digits):
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
    saved = em.on_display
    em.on_display = None
    try:
        steps = enter_program(em, prog["code"])
    finally:
        em.on_display = saved
    dsp.log(f"OK {steps:02d} STEPS".ljust(16))
    time.sleep(1.2)


def main():
    dsp = display_b.Display()
    dsp.log("George's MK 52")

    # The I²C LCD write takes ~85 ms on a Pi Zero — far too slow to do
    # synchronously in the chip thread. Push frames to a single-slot queue
    # and let a worker drain it at its own pace, always with the latest frame.
    lcd_queue = queue.Queue(maxsize=1)

    def lcd_worker():
        while True:
            frame = lcd_queue.get()
            if frame is None:
                return
            try:
                dsp.show(*frame)
            except Exception:
                pass  # I²C glitch — drop frame, keep running
    threading.Thread(target=lcd_worker, daemon=True, name="lcd").start()

    # Fan the chip's display refresh out to both surfaces. Browser path is
    # just a queue.put_nowait (fast). LCD path drops any stale pending frame
    # before queuing the new one so we never queue-grow under back-pressure.
    def on_display(digits, points, is_dimmed):
        frame = (digits, points, is_dimmed)
        try:
            lcd_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            lcd_queue.put_nowait(frame)
        except queue.Full:
            pass
        webui_server._broadcast(*frame)

    em = emulator.Машина(on_display=on_display, on_log=dsp.log)

    # Hand the same chip to the web UI module so /press, /load, /display
    # all drive (and observe) this instance.
    webui_server.машина = em

    kbd = keypad.Keypad(24, 23, 22, 21, 19, 18, 16, 15, 13, 12, 11, 10, 8, 7)

    with em:
        web_thread = threading.Thread(
            target=webui_server.serve,
            kwargs={"host": WEBUI_HOST, "port": WEBUI_PORT},
            daemon=True, name="webui")
        web_thread.start()

        digit_buffer = ""
        for x, y, txt in kbd.get_key_presses():
            # A↑ — load from ROM. keypad.py maps it to row 0 col 1 = (3, 0).
            if (x, y) == (3, 0):
                load_from_rom(em, dsp, digit_buffer)
                digit_buffer = ""
                continue
            if y == 1 and 2 <= x <= 11:
                digit_buffer = (digit_buffer + str(x - 2))[-2:]
            else:
                digit_buffer = ""
            em.press_button(x, y)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
