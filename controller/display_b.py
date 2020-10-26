# -*- coding: utf-8 -*-
import driver.lcd_i2c_driver


class Display:
    # Display symbols are only: ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "L", "С", "Г", "Е", " "];
    def __init__(self):
        self.lcd = driver.lcd_i2c_driver.lcd()
        self.lcd.lcd_backlight("on")
        self.lcd.lcd_clear()


    def log(self, text):
        self.lcd.lcd_display_string(text, 1)

    def show(self, digits, points, is_dimmed):
        text = ''
        for position in range(0, 12):
            text += digits[position]
            point = points[position]
            if point != ' ':
                text += point
        text = text.replace("Г", "r")
        text = text.ljust(16)
        self.lcd.lcd_display_string(text, 1)
