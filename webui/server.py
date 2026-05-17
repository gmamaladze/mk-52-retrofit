# -*- coding: utf-8 -*-
# Desktop-only web UI for poking the MK-52 emulator. Not used on the Pi.
#
# Usage:
#   python3 webui/server.py            # http://127.0.0.1:8080/
#   python3 webui/server.py 8888       # custom port
import http.server
import json
import os
import queue
import sys
import threading

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(THIS_DIR)
sys.path.insert(0, os.path.join(ROOT, "controller"))

from emulator import Машина  # noqa: E402

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


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet the default access log
        pass

    def do_GET(self):
        if self.path == "/":
            self._serve_file("index.html", "text/html; charset=utf-8")
        elif self.path == "/events":
            self._serve_sse()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/press":
            self.send_error(404)
            return
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
