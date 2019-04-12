import emulator
import time


def main():
    def on_display(text):
        print(text)

    with emulator.Emulator("ws://localhost:8080/", on_display=on_display) as em:
        print('Ok')
        em.press_button(3, 1)
        em.press_button(4, 1)
        time.sleep(1)


if __name__ == "__main__":
    main()
