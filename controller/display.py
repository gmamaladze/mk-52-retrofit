import grove_rgb_lcd as lcd



class Display:

    # Display symbols are only: ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "L", "С", "Г", "Е", " "];

    RUSSIAN_R_PATTERN = [
        0b01111,
        0b01000,
        0b01000,
        0b01000,
        0b01000,
        0b01000,
        0b01000,
        0b00000
    ]

    CUSTOM_CHAR_CODE = 0

    def __init__(self):
        lcd.create_char(Display.CUSTOM_CHAR_CODE, Display.RUSSIAN_R_PATTERN)

    def show(self, digits, points, is_dimmed):
        text = ''
        for position in range(0, 12):
            text += digits[position]
            point = points[position]
            if point != ' ':
                text += point
        text = text.replace("Г", chr(Display.CUSTOM_CHAR_CODE))
        lcd.setText(text)

        if is_dimmed:
            lcd.setRGB(0x00, 0xFF, 0x00)
        else:
            lcd.setRGB(0x73, 0xFB, 0xDE)
