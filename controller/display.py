import grove_rgb_lcd as lcd

class Display:

    def __init__(self):
        lcd.setRGB(0, 255, 0)

    def show(self, text):
        print(text)
