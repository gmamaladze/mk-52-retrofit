import websocket
import json
import threading
import subprocess
import time
import requests


class Emulator:

    def __init__(self, url, on_display=None, on_log=None):
        self.url = url
        self.on_display = on_display
        self.on_log = on_log

    def __enter__(self):
        self.server = subprocess.Popen('node server.js', shell=True, cwd='../emulator/', stdout=subprocess.PIPE,)
        time.sleep(2)
        while True:
            if self.on_log is not None:
                self.on_log("Initializing...")
            try:
                r = requests.post("http://localhost:8080/ping")
                if r.status_code == requests.codes.ok:
                    break
            except:
                pass
            time.sleep(0.5)

        opened_event = threading.Event()

        def on_message(ws, json_message):
            message = json.loads(json_message)
            if message['action'] == 'display':
                self.display(message)

        def on_error(ws, error):
            print(error)

        def on_close(ws):
            print("Connection to emulator was closed.")

        def on_open(ws):
            print("Connection to emulator was opened.")
            message = {
                'action': 'sync'
            }
            ws.send(json.dumps(message))
            opened_event.set()

        self.ws = websocket.WebSocketApp(self.url,
                                         on_open=on_open,
                                         on_message=on_message,
                                         on_error=on_error,
                                         on_close=on_close)
        # self.ws.enableTrace(True)
        thread = threading.Thread(target=self.ws.run_forever)
        thread.start()
        opened_event.wait()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ws.close()
        self.server.kill()

    def press_button(self, x, y):
        message = {
            'action': 'button',
            'x': x,
            'y': y
        }
        self.ws.send(json.dumps(message))

    def display(self, message):
        digits = message['digits']
        points = message['points']
        is_dimmed = message['is_dimmed']
        if self.on_display is not None:
            self.on_display(digits, points, is_dimmed)
