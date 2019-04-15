import time
import RPi.GPIO as GPIO


class Keypad:

    SCAN_INTERVAL_SECONDS = 0.0001
    BOUNCE_TIME_MILLISECONDS = 200

    ROW_COLUMN_TO_KEY = [
        ['', 'A↑', '↑↓', '', '', '', '', '', '', ''],
        ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
        ['+', '-', '×', '÷', '↔', '.', '/-/', 'ВП', 'Сx', 'В↑'],
        ['С/П', 'БП', 'В/О', 'ПП', 'X→П', '→ШГ', 'П→X', '←ШГ', 'K', 'F']
    ]

    COLUMN_TO_X = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    ROW_TO_Y = [0, 1, 8, 9]

    def __init__(self, _1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13, _14):
        self.column_channels = [_4, _6, _5, _11, _9, _7, _8, _3, _2, _10]
        self.row_channels = [_1, _12, _13, _14]
        self.subscribed = False
        for row_channel in self.row_channels:
            GPIO.setup(row_channel, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        for column_channel in self.column_channels:
            GPIO.setup(column_channel, GPIO.OUT, initial=1)

    def subscribe(self):
        if self.subscribed:
            return
        for column_channel in self.column_channels:
            GPIO.output(column_channel, 1)
        for row_channel in self.row_channels:
            GPIO.add_event_detect(row_channel, GPIO.RISING, bouncetime=1000)
        self.subscribed = True

    def unsubscribe(self):
        if not self.subscribed:
            return
        for row_channel in self.row_channels:
            GPIO.remove_event_detect(row_channel)
        for column_channel in self.column_channels:
            GPIO.output(column_channel, 0)
        self.subscribed = False

    def try_detect_row_idx(self):
        for i, row_channel in enumerate(self.row_channels):
            if GPIO.event_detected(row_channel):
                return i, True
        return -1, False

    def try_detect_column_idx(self, row_idx):
        row_channel = self.row_channels[row_idx]
        for j, column_channel in enumerate(self.column_channels):
            GPIO.output(column_channel, 1)
            time.sleep(Keypad.SCAN_INTERVAL_SECONDS)
            if GPIO.input(row_channel):
                return j, True
        return -1, False

    def get_key_presses(self):
        while True:
            self.subscribe()
            time.sleep(Keypad.SCAN_INTERVAL_SECONDS)
            row_idx, detected = self.try_detect_row_idx()

            if not detected:
                continue

            self.unsubscribe()
            column_idx, detected = self.try_detect_column_idx(row_idx)
            if not detected:
                continue

            yield self.COLUMN_TO_X[column_idx], self.ROW_TO_Y[row_idx], self.ROW_COLUMN_TO_KEY[row_idx][column_idx]
