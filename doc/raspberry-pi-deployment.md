# Raspberry Pi deployment

Step-by-step for bringing this repo up on a fresh Pi, plus the smoke tests
to run *before* declaring the deployment good. The library swap is done in
`controller/requirements.txt` (`RPi.GPIO` → `rpi-lgpio`), but the actual
hardware behavior is unverified until you run the checks below.

## Why the library swap

`controller/keypad.py` and `controller/app.py` `import RPi.GPIO as GPIO`.
We don't change those imports — instead we install
[`rpi-lgpio`](https://pypi.org/project/rpi-lgpio/), which registers under the
same `RPi.GPIO` module name but uses `lgpio` underneath. Reasons:

- The original `RPi.GPIO` is deprecated and **does not work on Pi 5**.
- It's a CPython C extension; under PyPy it goes through `cpyext` (slow,
  flaky). `rpi-lgpio` is cffi-based and works under both runtimes.

## Install

```bash
# Remove the system RPi.GPIO so it doesn't shadow the pip drop-in.
sudo apt remove -y python3-rpi.gpio

# Make sure the lgpio system library is present (rpi-lgpio uses it).
sudo apt install -y python3-lgpio

# Install Python deps system-wide so systemd's /usr/bin/python3 finds them.
cd ~/mk-52-retrofit/controller
sudo pip install -r requirements.txt
```

If you prefer a venv, update `mk-52.service`'s `ExecStart` to point at the
venv's Python.

## Smoke tests (run in order)

### 1. Import resolves to rpi-lgpio, not the C extension

```bash
python3 -c "import RPi.GPIO; print(RPi.GPIO.__file__)"
```

The printed path should contain `rpi_lgpio` or look like a normal Python file
(`/site-packages/RPi/__init__.py`). If it ends in `.so` it's still the
original `RPi.GPIO` C extension — the apt-remove step didn't take.

### 2. Basic GPIO setup doesn't crash

```bash
sudo python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(11, GPIO.OUT, initial=1)
GPIO.output(11, 0)
GPIO.cleanup()
print('GPIO basic setup: OK')
"
```

`sudo` is needed because `lgpio` opens `/dev/gpiochip*` which requires root
(or membership in the `gpio` group).

### 3. Keypad event detection

This is the one place `rpi-lgpio` is documented to differ from `RPi.GPIO` —
`add_event_detect` + `event_detected` polling. See the
[rpi-lgpio differences page](https://github.com/waveform80/rpi-lgpio/blob/main/docs/differences.rst).

```bash
cd ~/mk-52-retrofit/controller
sudo python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BOARD)
import keypad
kbd = keypad.Keypad(24,23,22,21,19,18,16,15,13,12,11,10,8,7)
print('setup OK; press 5 keys to test...')
import itertools
for x, y, txt in itertools.islice(kbd.get_key_presses(), 5):
    print(f'  pressed ({x},{y}) = {txt}')
print('keypad event detection: OK')
"
```

Press 5 different keys. If they all register correctly, the event-detect
path is good. **If keys are missed or double-trigger**, that's the edge
behavior difference — falling back to manual polling in `keypad.py` is a
small change (drop `add_event_detect`/`event_detected`, replace with a
tight `GPIO.input()` loop). Not blocking, but it'd want a follow-up commit.

### 4. End-to-end via systemd

```bash
sudo systemctl restart mk-52.service
sudo systemctl status mk-52.service       # should be `active (running)`
sudo journalctl -u mk-52.service -f       # leave running; press keys on the
                                          # physical keypad and verify the
                                          # LCD updates
```

## Performance (optional)

CPython gets the chip simulator to about 36 % of original МК-52 speed on
desktop hardware; the Pi will likely be lower (10–20 %). PyPy closes that
gap — typically 65× speedup on the chip loop. To try:

```bash
sudo apt install -y pypy3
sudo pypy3 -m pip install rpi-lgpio pyyaml smbus
```

Then run `pypy3 tools/benchmark.py` to see what your Pi can sustain. The
script prints the max `ИТЕРАЦИЙ_В_ШАГЕ` that fits in the 30 ms tick — if
that's ≥ 560, you're at original speed. Update
`controller/emulator/machine.py:ИТЕРАЦИЙ_В_ШАГЕ` to suit.

To switch the systemd service over, change `ExecStart` in `mk-52.service`
from `/usr/bin/python3` to `/usr/bin/pypy3`.

## Known unknowns / risks

- **Edge-detect timing on the keypad.** See smoke test 3. Most likely
  symptom: missed keystrokes or duplicated ones during fast typing.
- **`lgpio` permission**. `rpi-lgpio` requires `/dev/gpiochip*` access.
  The `pi` user is in the `gpio` group on a stock Pi OS image — verify
  with `groups pi`. Custom users need adding to the group.
- **Pi 5 vs older Pis**. `rpi-lgpio` claims support back to Pi 1.
  Untested in this project on any specific model — fill this in once
  you've run the smoke tests.
- **Display drivers (`display_a.py`, `display_b.py`, `grove_rgb_lcd.py`)**.
  Use I2C via `smbus`, not GPIO. Not affected by the library swap, but
  worth re-confirming end-to-end after the GPIO change.

## Status log

Fill in as you test:

| Date | Pi model | Pi OS version | Step 1 | Step 2 | Step 3 | Step 4 | Notes |
|------|----------|---------------|--------|--------|--------|--------|-------|
|      |          |               |        |        |        |        |       |
