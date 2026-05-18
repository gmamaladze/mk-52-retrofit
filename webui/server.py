# -*- coding: utf-8 -*-
# Desktop-only web UI for poking the MK-52 emulator. Not used on the Pi.
#
# Usage:
#   python3 webui/server.py            # http://127.0.0.1:8080/
#   python3 webui/server.py 8888       # custom port
import glob
import http.server
import json
import os
import queue
import sys
import threading
import time

import yaml

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(THIS_DIR)
sys.path.insert(0, os.path.join(ROOT, "controller"))

from emulator import Машина  # noqa: E402

PROGRAMS_DIR = os.path.join(ROOT, "programs")


def _load_programs():
    items = []
    for path in sorted(glob.glob(os.path.join(PROGRAMS_DIR, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            prog = yaml.safe_load(f)
        items.append({
            "id": prog.get("id") or os.path.splitext(os.path.basename(path))[0],
            "title": prog.get("title", ""),
            "description": prog.get("description", ""),
            "author": prog.get("author", ""),
            "instructions": prog.get("instructions", ""),
            "code": prog.get("code", ""),
        })
    return items

_subscribers_lock = threading.Lock()
_subscribers: list[queue.Queue] = []
_last_frame = {"digits": "            ", "points": "            ", "is_dimmed": False}


def _broadcast(digits, points, is_dimmed):
    frame = {"digits": digits, "points": points, "is_dimmed": is_dimmed}
    _last_frame.update(frame)
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(frame)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


машина = Машина(on_display=_broadcast)


# --------------------------------------------------------------------------
# Keystroke-based program loader.
#
# Direct memory writes via Ввести_код don't survive the chip's shift-register
# data path — the bytes get clobbered within one Шаг. Instead we drive the
# chip through its keyboard interface: F+АВТ → В/О → F+ПРГ → opcodes → F+АВТ
# → В/О. The chip's own microcode places opcodes at the right addresses.
# --------------------------------------------------------------------------

# Key (x, y) by name — mirrors controller/keypad.py.
_KEY = {
    "0": (2, 1), "1": (3, 1), "2": (4, 1), "3": (5, 1), "4": (6, 1),
    "5": (7, 1), "6": (8, 1), "7": (9, 1), "8": (10, 1), "9": (11, 1),
    "+": (2, 8), "-": (3, 8), "*": (4, 8), "/": (5, 8),
    "↔": (6, 8), ".": (7, 8), "/-/": (8, 8), "ВП": (9, 8),
    "Сx": (10, 8), "В↑": (11, 8),
    "С/П": (2, 9), "БП": (3, 9), "В/О": (4, 9), "ПП": (5, 9),
    "X→П": (6, 9), "→ШГ": (7, 9), "П→X": (8, 9), "←ШГ": (9, 9),
    "K": (10, 9), "F": (11, 9),
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


def _token_to_keys(tok):
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
        return [tok[0], tok[1]]
    raise ValueError(f"unknown program token: {tok!r}")


def _load_via_keystrokes(source, key_settle=0.18):
    tokens = source.split()
    cleaned = []
    for t in tokens:
        if len(t) >= 3 and t[2] == "." and (t[0].isdigit() or t[0] in "A-") and t[1].isdigit():
            t = t[3:]
        if t:
            cleaned.append(t)

    sequence = ["Сx", "F", "/-/", "В/О", "F", "ВП"]
    for tok in cleaned:
        sequence.extend(_token_to_keys(tok))
    sequence.extend(["F", "/-/", "В/О"])

    for k in sequence:
        x, y = _KEY[k]
        машина.press_button(x, y)
        time.sleep(key_settle)
    return len(cleaned)


def _dump_state():
    from emulator.loader import Адрес_команды, ПРОГРАММНЫХ_ШАГОВ
    chips = {1: машина.ИР2_1, 2: машина.ИР2_2, 3: машина.ИК1302, 4: машина.ИК1303}
    with машина._lock:
        перестановка = (машина.ИР2_1.микротакт // 84) % 3
        bytes_per_step = []
        for i in range(ПРОГРАММНЫХ_ШАГОВ):
            chip_id, addr = Адрес_команды(i, перестановка)
            chip = chips[chip_id]
            hi = chip.M[addr]
            lo = chip.M[addr - 3]
            bytes_per_step.append((hi << 4) | lo)
        return {
            "perm": перестановка,
            "ир2_1_микротакт": машина.ИР2_1.микротакт,
            "ир2_2_микротакт": машина.ИР2_2.микротакт,
            "program": [f"{b:02X}" for b in bytes_per_step[:20]],
        }


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet the default access log
        pass

    def do_GET(self):
        if self.path == "/":
            self._serve_file("index.html", "text/html; charset=utf-8")
        elif self.path == "/events":
            self._serve_sse()
        elif self.path == "/programs":
            self._serve_json(_load_programs())
        elif self.path == "/display":
            self._serve_json(_last_frame)
        elif self.path == "/dump":
            self._serve_json(_dump_state())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/press":
            self._handle_press()
        elif self.path == "/load":
            self._handle_load()
        else:
            self.send_error(404)

    def _handle_press(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
            x, y = int(data["x"]), int(data["y"])
        except (ValueError, KeyError, json.JSONDecodeError):
            self.send_error(400, "expected JSON {x, y}")
            return
        машина.press_button(x, y)
        self.send_response(204)
        self.end_headers()

    def _handle_load(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
            code = str(data["code"])
        except (ValueError, KeyError, json.JSONDecodeError):
            self.send_error(400, "expected JSON {code}")
            return
        try:
            steps = _load_via_keystrokes(code)
        except Exception as e:
            self.send_error(400, f"load failed: {e}")
            return
        self._serve_json({"steps": steps})

    def _serve_json(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, name, ctype):
        path = os.path.join(THIS_DIR, name)
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q: queue.Queue = queue.Queue(maxsize=64)
        with _subscribers_lock:
            _subscribers.append(q)
        try:
            # send current frame immediately so a fresh page isn't blank
            self._send_sse(_last_frame)
            while True:
                frame = q.get()
                self._send_sse(frame)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _subscribers_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    def _send_sse(self, frame):
        payload = "data: " + json.dumps(frame) + "\n\n"
        self.wfile.write(payload.encode("utf-8"))
        self.wfile.flush()


class ThreadingServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    with машина:
        srv = ThreadingServer(("127.0.0.1", port), Handler)
        print(f"MK-52 web UI: http://127.0.0.1:{port}/")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
