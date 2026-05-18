# -*- coding: utf-8 -*-
# HTTP + keypad helpers for driving the MK-52 web UI from tests.
# Assumes a server is running at BASE.

import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"

# Keypad (x, y) coordinates. See controller/keypad.py ROW_COLUMN_TO_KEY.
KEY = {
    # digits — row y=1
    "0": (2, 1),  "1": (3, 1),  "2": (4, 1),  "3": (5, 1),  "4": (6, 1),
    "5": (7, 1),  "6": (8, 1),  "7": (9, 1),  "8": (10, 1), "9": (11, 1),
    # row y=8
    "+":   (2, 8),  "-":  (3, 8),  "*":  (4, 8),  "/":  (5, 8),
    "↔":   (6, 8),  ".":  (7, 8),  "/-/":(8, 8),  "ВП": (9, 8),
    "Сx":  (10, 8), "В↑": (11, 8),
    # row y=9
    "С/П": (2, 9), "БП": (3, 9), "В/О": (4, 9), "ПП":  (5, 9),
    "X→П": (6, 9), "→ШГ":(7, 9), "П→X": (8, 9), "←ШГ": (9, 9),
    "K":   (10, 9),"F":  (11, 9),
}


def http(path, body=None, timeout=10):
    if body is not None:
        req = urllib.request.Request(
            BASE + path, method="POST",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", "")
        if "json" in ct:
            return json.loads(r.read())
        return r.read()


def wait_server(timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            http("/display")
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"server at {BASE} did not respond within {timeout}s")


def press(key, settle=0.2):
    """Press a key by name (see KEY dict) or by (x, y) tuple."""
    if isinstance(key, tuple):
        x, y = key
    else:
        x, y = KEY[key]
    http("/press", {"x": x, "y": y})
    time.sleep(settle)


def press_seq(keys, settle=0.2):
    for k in keys:
        press(k, settle=settle)


def display():
    return http("/display")


def display_digits():
    return display()["digits"]


def reset_calc():
    """Bring the chip into a clean calculator-mode state: Сx, F+АВТ, В/О."""
    press("Сx")
    press("F"); press("/-/")    # F + АВТ — leave program mode if in it
    press("В/О")


# --------------------------------------------------------------------------
# Display parser
# --------------------------------------------------------------------------
# The МК-52 display has 12 positions:
#   pos 0      mantissa sign (' ' or '-')
#   pos 1-8    mantissa digits (8 digits)
#   pos 9      exponent sign (' ' or '-')
#   pos 10-11  exponent digits
# The `points` string carries the decimal-point indicator: a ',' at position i
# means the decimal point is rendered just after digit position i in the mantissa.

ERROR_CHARS = set("ЕLСГ")


def parse_display(d=None):
    """Parse the current display into a float. Returns None on error/blank."""
    if d is None:
        d = display()
    digits = d["digits"]
    points = d["points"]
    if len(digits) != 12:
        return None
    if any(c in ERROR_CHARS for c in digits[1:9]):
        return None

    sign = -1 if digits[0] == "-" else 1
    mant = ""
    saw_digit = False
    for i in range(1, 9):
        ch = digits[i]
        if ch.isdigit():
            mant += ch
            saw_digit = True
        if points[i] == ",":
            mant += "."
    if not saw_digit:
        return None
    try:
        value = float(mant)
    except ValueError:
        return None

    exp_sign = -1 if digits[9] == "-" else 1
    exp_str = "".join(c for c in digits[10:12] if c.isdigit())
    if exp_str:
        value *= 10 ** (exp_sign * int(exp_str))
    return sign * value


# --------------------------------------------------------------------------
# Program-mode keystroke loader
# --------------------------------------------------------------------------
# Translate each source token into the keypad sequence that produces the
# right opcode in program mode. The chip auto-combines two digit keys after
# a jump opcode into a single BCD address byte.

# Single-press tokens.
_SINGLE = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "+", "-", "*", "/", "↔", ".", "/-/", "ВП", "Сx", "В↑",
    "С/П", "БП", "В/О", "ПП",
}

# F-prefix tokens: F then the listed key.
_F_PREFIX = {
    # Math
    "x^2": "*",  "x²": "*",  "x2": "*",
    "√": "-",   "КвКор": "-", "корень": "-",
    "1/x": "/",
    "x^y": "↔", "x²y": "↔", "xy": "↔",
    "π": "+",   "пи": "+",
    "10^x": "0", "10x": "0",
    "e^x": "1",  "ex": "1",
    "lg": "2", "ln": "3",
    "sin": "7", "cos": "8", "tg": "9",
    "arcsin": "4", "arccos": "5", "arctg": "6",
    # Conditionals
    "x=0":  "←ШГ",
    "x#0":  "С/П", "x≠0": "С/П", "x!=0": "С/П", "x<>0": "С/П",
    "x<0":  "→ШГ",
    "x>=0": "В/О", "x≥0": "В/О", "x⩾0": "В/О",
    # Loops L0..L3
    "L0": "П→X", "L1": "X→П", "L2": "БП", "L3": "ПП",
    # Vx (Вx)
    "Вx": "В↑", "Bx": "В↑",
    "->": "В/О",  # rotate stack? actually F + В/О is x>=0 — leave unmapped to avoid confusion
}

# К-prefix tokens.
_K_PREFIX = {
    "[x]":  "7",
    "{x}":  "8", "(x)": "8",
    "max":  "9",
    "|x|":  "4",
    "ЗН":   "5",
    "СЧ":   "В↑",
    "НОП":  "ВП",  # K + ВП = НОП
    "КНОП": "ВП",
}


def token_to_keys(tok):
    """Return a list of keys (names or (x,y) tuples) to press in order
    to enter `tok` in program mode."""
    if tok in _SINGLE:
        return [tok]
    if tok in _F_PREFIX:
        return ["F", _F_PREFIX[tok]]
    if tok in _K_PREFIX:
        return ["K", _K_PREFIX[tok]]
    # Register addressing: П<n>, ИП<n>, ПX<n>, XП<n>, KП<n>, KИП<n>
    if len(tok) == 2 and tok[0] in "ПXП" and tok[1].isdigit():
        n = tok[1]
        if tok[0] == "П":
            return ["X→П", n]
    if len(tok) == 3 and tok[:2] in ("ИП", "ПX", "Пx") and tok[2].isdigit():
        return ["П→X", tok[2]]
    if len(tok) == 2 and tok[0] == "П" and tok[1].isdigit():
        return ["X→П", tok[1]]
    # Two-digit address (BCD): each digit is a keystroke; chip combines them.
    if len(tok) == 2 and tok.isdigit():
        return [tok[0], tok[1]]
    raise ValueError(f"don't know how to keystroke-enter token: {tok!r}")


def load_program(source, key_settle=0.18):
    """Enter `source` into program memory by simulating keystrokes.

    Sequence: Сx → F+АВТ → В/О → F+ПРГ → opcodes → F+АВТ → В/О.
    """
    tokens = source.split()
    # Strip optional 'NN.' or 'AN.' line-number prefixes.
    cleaned = []
    for t in tokens:
        if len(t) >= 3 and t[2] == "." and (t[0].isdigit() or t[0] in "A-") and t[1].isdigit():
            t = t[3:]
        if t:
            cleaned.append(t)

    press_seq(["Сx", "F", "/-/", "В/О", "F", "ВП"], settle=key_settle)  # → prog mode at step 0
    for tok in cleaned:
        for k in token_to_keys(tok):
            press(k, settle=key_settle)
    press_seq(["F", "/-/", "В/О"], settle=key_settle)  # exit prog mode, reset PC
    return len(cleaned)


def run_and_wait(timeout=20.0):
    """Press С/П to (re)start, then poll the display until it stabilizes.

    Returns the final display dict.
    """
    press("С/П", settle=0.1)
    t0 = time.time()
    last = None
    stable_since = None
    while time.time() - t0 < timeout:
        d = display()
        cur = (d["digits"], d["is_dimmed"])
        if d["is_dimmed"]:
            if cur != last:
                last = cur
                stable_since = time.time()
            elif time.time() - stable_since > 0.6:
                return d
        time.sleep(0.1)
    return display()
