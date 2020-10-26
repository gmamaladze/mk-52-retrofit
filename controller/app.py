import emulator
import display_a
import display_b
import keypad
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BOARD)


def main():
    # dsp = display_b.Display()
    dsp = display_b.Display()
    dsp.log("George's MK 52")

    kbd = keypad.Keypad(24, 23, 22, 21, 19, 18, 16, 15, 13, 12, 11, 10, 8, 7)

    with emulator.Emulator("ws://localhost:8080/", on_display=dsp.show, on_log=dsp.log) as em:
        for x, y, txt in kbd.get_key_presses():
            em.press_button(x, y)


if __name__ == "__main__":
    main()
