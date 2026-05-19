# -*- coding: utf-8 -*-
# Web UI for poking the MK-52 emulator. Can run alongside controller/app.py
# on the Pi for browser access in addition to the physical keypad.
#
# Usage:
#   python3 webui/server.py                       # http://127.0.0.1:8080/
#   python3 webui/server.py 8888                  # custom port
#   python3 webui/server.py 8080 0.0.0.0          # bind to LAN (Pi mode)
import glob
import http.server
import json
import os
import queue
import sys
import threading

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


from emulator.keystroke_loader import enter_program as _load_via_keystrokes  # noqa: E402

# Tracks the most recent digit keys pressed via /press so A↑ knows which
# program to load from "ROM". Reset by any non-digit key. Server is
# single-user so a module-level buffer is fine.
_digit_buffer = ""


def _find_program_by_number(n):
    for path in sorted(glob.glob(os.path.join(PROGRAMS_DIR, f"{n:02d}-*.yaml"))):
        with open(path, encoding="utf-8") as f:
            return path, yaml.safe_load(f)
    return None


def _load_from_rom():
    """Look up programs/NN-*.yaml using the current digit buffer and load it
    via keystroke entry. Returns a dict the JS shows in the log."""
    global _digit_buffer
    digits, _digit_buffer = _digit_buffer, ""
    if not digits:
        return {"ok": False, "message": "A↑: type a program number first"}
    try:
        n = int(digits)
    except ValueError:
        return {"ok": False, "message": f"A↑: bad number {digits!r}"}
    found = _find_program_by_number(n)
    if not found:
        return {"ok": False, "message": f"A↑: no program #{n:02d}"}
    _, prog = found
    title = prog.get("title", prog.get("id", ""))
    try:
        steps = _load_via_keystrokes(машина, prog["code"])
    except Exception as e:
        return {"ok": False, "message": f"A↑: load failed: {e}"}
    return {"ok": True, "steps": steps,
            "message": f"A↑: loaded #{n:02d} ({title}, {steps} steps) — press В/О then С/П"}


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
        global _digit_buffer
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body)
            x, y = int(data["x"]), int(data["y"])
        except (ValueError, KeyError, json.JSONDecodeError):
            self.send_error(400, "expected JSON {x, y}")
            return

        # A↑ ("load from ROM"): use the buffered digits to find a program in
        # programs/NN-*.yaml and keystroke-enter it. Returns JSON; the JS
        # writes the result to the load log.
        if (x, y) == (3, 0):
            self._serve_json(_load_from_rom())
            return

        if y == 1 and 2 <= x <= 11:
            _digit_buffer = (_digit_buffer + str(x - 2))[-2:]
        else:
            _digit_buffer = ""
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
            steps = _load_via_keystrokes(машина, code)
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
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    with машина:
        srv = ThreadingServer((host, port), Handler)
        print(f"MK-52 web UI: http://{host}:{port}/")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
