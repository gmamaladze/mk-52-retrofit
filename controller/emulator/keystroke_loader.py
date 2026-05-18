# -*- coding: utf-8 -*-
"""Load МК-52 source programs into the emulator by simulating keystrokes.
Direct M-array writes (via Машина.Ввести_код) don't survive the chip's shift-
register data path. Driving the chip through F+ПРГ → opcodes → F+АВТ does,
because the chip's own microcode places opcodes at the right addresses.

Shared by the desktop web UI (webui/server.py) and the Pi controller
(controller/app.py).
"""

import time

# Key (x, y) by name — mirrors controller/keypad.py.
_KEY = {
    "0": (2, 1),  "1": (3, 1),  "2": (4, 1),  "3": (5, 1),  "4": (6, 1),
    "5": (7, 1),  "6": (8, 1),  "7": (9, 1),  "8": (10, 1), "9": (11, 1),
    "+": (2, 8),  "-": (3, 8),  "*": (4, 8),  "/": (5, 8),
    "↔": (6, 8),  ".": (7, 8),  "/-/": (8, 8), "ВП": (9, 8),
    "Сx": (10, 8), "В↑": (11, 8),
    "С/П": (2, 9), "БП": (3, 9), "В/О": (4, 9), "ПП": (5, 9),
    "X→П": (6, 9), "→ШГ": (7, 9), "П→X": (8, 9), "←ШГ": (9, 9),
    "K": (10, 9),  "F": (11, 9),
}

_SINGLE = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "+", "-", "*", "/", "↔", ".", "/-/", "ВП", "Сx", "В↑",
    "С/П", "БП", "В/О", "ПП",
}

_F_PREFIX = {
    "x^2": "*", "x²": "*", "x2": "*",
    "√": "-", "КвКор": "-", "корень": "-",
    "1/x": "/",
    "x^y": "↔", "xy": "↔",
    "π": "+", "пи": "+",
    "10^x": "0", "10x": "0",
    "e^x": "1", "ex": "1",
    "lg": "2", "ln": "3",
    "sin": "7", "cos": "8", "tg": "9",
    "arcsin": "4", "arccos": "5", "arctg": "6",
    "x=0": "←ШГ",
    "x#0": "С/П", "x≠0": "С/П", "x!=0": "С/П", "x<>0": "С/П",
    "x<0": "→ШГ",
    "x>=0": "В/О", "x≥0": "В/О", "x⩾0": "В/О",
    "L0": "П→X", "L1": "X→П", "L2": "БП", "L3": "ПП",
    "Вx": "В↑", "Bx": "В↑",
}

_K_PREFIX = {
    "[x]": "7",
    "{x}": "8", "(x)": "8",
    "max": "9",
    "|x|": "4",
    "ЗН": "5",
    "СЧ": "В↑",
    "НОП": "ВП", "КНОП": "ВП",
}

# Tokens the loader.py mnemonic table lists as synonyms for a canonical form
# recognized above. Programs in the wild use any of these freely.
_ALIASES = {
    # В↑ push
    "^": "В↑", "↑": "В↑", "В^": "В↑",
    # ↔ swap
    "<->": "↔", "XY": "↔", "X↔Y": "↔",
    # * multiply (note: "х" is Cyrillic, "x" is Latin)
    "x": "*", "х": "*", "×": "*", "⋅": "*",
    # / divide
    ":": "/", "÷": "/",
    # /-/ negate
    "+/-": "/-/",
    # В/О reset
    "В/0": "В/О",
    # decimal point — chip accepts comma or period
    ",": ".",
    # Вx
    "FВx": "Вx", "FBx": "Вx",
    # F-prefix variants (where author wrote "F<name>" explicitly)
    "Fx^2": "x^2", "Fx2": "x^2", "Fx²": "x^2",
    "F√": "√", "FКвКор": "√", "Fквкор": "√", "Fкорень": "√",
    "F10^x": "10^x", "F10x": "10^x",
    "Fe^x": "e^x", "Fex": "e^x",
    "Flg": "lg", "Fln": "ln",
    "Fsin": "sin", "Fcos": "cos", "Ftg": "tg",
    "Farcsin": "arcsin", "Farccos": "arccos", "Farctg": "arctg",
    "Fπ": "π", "Fпи": "π", "пи": "π",
    "F1/x": "1/x", "Fx^y": "x^y", "Fxy": "x^y",
    "FL0": "L0", "FL1": "L1", "FL2": "L2", "FL3": "L3",
    "Fx=0": "x=0", "Fx<0": "x<0",
    "Fx>=0": "x>=0", "Fx≥0": "x>=0", "Fx⩾0": "x>=0",
    "Fx#0": "x#0", "Fx≠0": "x#0", "Fx!=0": "x#0", "Fx<>0": "x#0",
    # К-prefix variants
    "K|x|": "|x|", "К|x|": "|x|",
    "K[x]": "[x]", "К[x]": "[x]",
    "K{x}": "{x}", "К{x}": "{x}", "K(x)": "(x)", "К(x)": "(x)",
    "Kmax": "max", "Кmax": "max",
    "KЗН": "ЗН", "КЗН": "ЗН",
    "KНОП": "НОП",  "КНОП": "НОП",
    "KСЧ": "СЧ", "КСЧ": "СЧ",
}


def token_to_keys(tok):
    """Translate one source token into the key sequence that enters it."""
    tok = _ALIASES.get(tok, tok)
    if tok in _SINGLE:
        return [tok]
    if tok in _F_PREFIX:
        return ["F", _F_PREFIX[tok]]
    if tok in _K_PREFIX:
        return ["K", _K_PREFIX[tok]]
    if len(tok) == 3 and tok[:2] in ("ИП", "ПX", "Пx") and tok[2].isdigit():
        return ["П→X", tok[2]]
    if len(tok) == 2 and tok[0] == "П" and tok[1].isdigit():
        return ["X→П", tok[1]]
    if len(tok) == 2 and tok.isdigit():
        # Two-digit address byte after a jump (chip auto-combines into one byte).
        return [tok[0], tok[1]]
    raise ValueError("unknown program token: {!r}".format(tok))


def _split_source(source):
    tokens = source.split()
    cleaned = []
    for t in tokens:
        if len(t) >= 3 and t[2] == "." and (t[0].isdigit() or t[0] in "A-") and t[1].isdigit():
            t = t[3:]
        if t:
            cleaned.append(t)
    return cleaned


def enter_program(машина, source, key_settle=0.18):
    """Type `source` into program memory via the keypad. Returns step count.

    Sequence: Сx → F+АВТ → В/О → F+ПРГ → tokens → F+АВТ → В/О.
    """
    tokens = _split_source(source)
    sequence = ["Сx", "F", "/-/", "В/О", "F", "ВП"]
    for tok in tokens:
        sequence.extend(token_to_keys(tok))
    sequence.extend(["F", "/-/", "В/О"])

    for k in sequence:
        x, y = _KEY[k]
        машина.press_button(x, y)
        time.sleep(key_settle)
    return len(tokens)
