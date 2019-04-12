import websocket
import json
import threading


class Emulator:

    def __init__(self, url, on_display=None):
        self.url = url
        self.on_display = on_display

    def __enter__(self):

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

    def press_button(self, x, y):
        message = {
            'action': 'button',
            'x': x,
            'y': y
        }
        self.ws.send(json.dumps(message))

    def display(self, message):
        text = ''
        digits = message['digits']
        points = message['points']
        for position in range(0, 12):
            text += digits[position]
            point = points[position]
            if point != ' ':
                text += point
        if self.on_display is not None:
            self.on_display(text)
