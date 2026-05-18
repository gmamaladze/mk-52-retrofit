# МК-52 retrofit

A Soviet programmable calculator (Электроника МК-52) emulator, ported from
the [original JS by Felix Lazarev](https://pmk.arbinada.com/mk61emuweb.html#)
to Python, plus a Raspberry Pi hardware retrofit that runs the emulator
behind real keypad + LCD hardware.

Two ways to use it:

- **Desktop web UI** — emulator + on-screen keypad in your browser, for
  development and demos.
- **Raspberry Pi controller** — same emulator driving a physical keypad
  and Grove RGB LCD via GPIO/I²C.

---

## Desktop web UI

```bash
python3 webui/server.py            # http://127.0.0.1:8080/
```

Pick a program from the dropdown and click *Load to MK-52*, or type a number
on the keypad and click the **A↑** key to load by number (mirrors the
original МК-52 "load from ROM" workflow). Then **В/О**, **С/П** to run.

## Raspberry Pi

```bash
# Clone, swap GPIO library (RPi.GPIO is broken on Pi 5), install deps.
sudo apt remove -y python3-rpi.gpio
sudo apt install -y python3-lgpio
cd controller && sudo pip install -r requirements.txt

# Auto-install systemd service so the controller starts at boot.
cd ..
sudo bash tools/install-pi.sh
```

The script auto-detects your user, repo path, and uses PyPy if installed.
Idempotent — re-run after `git pull`. Verify with `systemctl status mk-52`.

Smoke tests, the rpi-lgpio behavioral notes, and the per-Pi status log
table live in [doc/raspberry-pi-deployment.md](doc/raspberry-pi-deployment.md).

## Programs

10 example programs in `programs/`, numbered 01–10 (lunar landing, Newton's
sqrt, factorial, GCD, dice, …). See [doc/programs.md](doc/programs.md) for
the list, the A↑ "load from ROM" workflow, and how to add new programs.

## Tests

HTTP-driven integration tests:

```bash
python3 webui/server.py &           # tests need a running server
python3 -m unittest tests.test_live tests.test_programs
```

11 live-arithmetic cases (`1 + 1`, √, etc.) and 5 program-execution cases
(counter, factorial, …). The tests drive the chip via keystrokes and assert
on the parsed display, so they exercise the same path real users hit.

## Performance

The chip's microcode interpreter is the hot loop — a tight int-bit-op
function that CPython evaluates at about 36 % of the original МК-52's
speed. PyPy's JIT compiles it down to ~1 % of CPython's time, giving
**~65× speedup**, comfortably above original chip speed.

```bash
brew install pypy3                  # macOS
sudo apt install pypy3              # Pi / Debian / Ubuntu
pypy3 -m pip install pyyaml
pypy3 webui/server.py
```

`tools/benchmark.py` reports the max iteration rate a given runtime can
sustain in the 30 ms tick. Run on the Pi to see the actual numbers and
adjust `controller/emulator/machine.py:ИТЕРАЦИЙ_В_ШАГЕ` accordingly.

## Layout

```
controller/         Python port of the chip emulator and the Pi controller
  emulator/           ИК13 / ИР2 chip simulation + program loader
  driver/             Grove RGB LCD (I²C)
  app.py              Pi entry point — keypad → emulator → LCD
  keypad.py           GPIO keypad scanner
webui/              Desktop browser UI (single-file Python http.server)
programs/           YAML library of example programs (numbered 01–10)
tests/              Integration tests against a running server
tools/              install-pi.sh, benchmark.py
doc/                Hardware schematics, deployment notes, program list
mk-52.service       systemd unit template (install-pi.sh writes the real one)
```
