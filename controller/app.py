import emulator
import display
import time


def main():
    dsp = display.Display()

    with emulator.Emulator("ws://localhost:8080/", on_display=dsp.show) as em:
        em.press_button(3, 1)
        time.sleep(0.2)
        em.press_button(4, 1)
        time.sleep(1)


if __name__ == "__main__":
    main()
