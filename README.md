# МК-52 retrofit

Soviet programmable calculator (Электроника МК-52) emulator + Raspberry Pi
hardware retrofit that runs it behind a real keypad and an I²C LCD.

Originally ported from [Felix Lazarev's JS emulator](https://pmk.arbinada.com/mk61emuweb.html#)
to Python; the production runtime is now Go (~24× faster than CPython on
a Pi Zero, ~170× on a desktop), and Python under `controller/` and
`webui/server.py` stays in the repo as a working reference.

The same Go binary drives the physical keypad, the LCD, and a browser web
UI from one process — they all share one chip emulator instance, so a key
typed on the keypad updates the browser and vice versa.

---

## Desktop

```bash
cd go && go run ./cmd/server                    # http://127.0.0.1:8080/
cd go && go run ./cmd/server -port 8888         # custom port
cd go && go run ./cmd/server -host 0.0.0.0      # expose on the LAN
```

Pick a program from the dropdown and click *Load to MK-52*, or type a
number on the keypad and click **A↑** to load by program number (mirrors
the original МК-52 "load from ROM" workflow). Then **В/О**, **С/П** to run.

Python still works for desktop too, if you'd rather:

```bash
python3 webui/server.py                         # http://127.0.0.1:8080/
```

## Raspberry Pi

The Pi runs a single Go binary as a systemd service. Deploy from any host
that has Go installed — the script cross-compiles, scp's the binary, and
sets up the unit:

```bash
bash tools/deploy-pi.sh user@<pi-ip>              # default armv6 (Pi Zero v1 / Pi 1)
GOARM=7 bash tools/deploy-pi.sh user@<pi-ip>      # Pi 2/3
GOARCH=arm64 bash tools/deploy-pi.sh user@<pi-ip> # Pi 4/5
```

Pi prerequisites (one-time): I²C enabled (`sudo raspi-config nonint do_i2c 0`),
user in the `gpio` and `i2c` groups (default on Pi OS), and passwordless
sudo if you want re-runs to be non-interactive. The repo should sit at
`~/mk-52-retrofit` (clone or rsync).

After deploy, verify with `systemctl status mk-52` and follow live logs
with `journalctl -u mk-52 -f`. The unit launches `/usr/local/bin/mk52-app`,
which serves both the web UI on `:8080` and drives the connected keypad +
LCD. Browser and physical keypad share the same chip state.

## Programs

10 example programs in `programs/`, numbered 01–10 (lunar landing, Newton's
sqrt, factorial, GCD, dice, …). On the Pi, type a number on the keypad and
press **A↑** to load it from "ROM"; in the browser, pick from the dropdown
or use the same A↑ button. See [doc/programs.md](doc/programs.md) for the
full list, the YAML schema, and how to add more.

## Tests

HTTP-driven integration tests — they drive the chip through the same
endpoints a real client uses, so they work against either the Go or Python
backend:

```bash
cd go && go test ./mk52                          # in-process Go tests
go run ./cmd/server &                            # or python3 webui/server.py &
python3 -m unittest tests.test_live tests.test_programs   # 16 cases
```

11 live-arithmetic cases (`1 + 1`, √, ...) and 5 program-execution cases
(counter, factorial, ...).

## Performance

Chip-loop benchmarks on a Pi Zero v1 (armv6, the slowest supported host):

| Runtime | Šaг wall time | Effective chip speed |
|---|---|---|
| Python (CPython) | 1270 ms | ~1 % of original МК-52 |
| Go               |   52 ms | ~20 % of original — **24× CPython** |

On a Pi 4/5 (ARM64) Go comfortably exceeds original chip speed. Apple
Silicon runs at 0.16 ms per Šaг (170× CPython).

`go/cmd/bench` prints these numbers on whichever host runs it:

```bash
cd go && go run ./cmd/bench
# or, for the Pi: GOOS=linux GOARCH=arm GOARM=6 go build -o /tmp/mk52-bench ./cmd/bench
```

## Layout

```
go/                  Go source — production runtime
  mk52/                chip simulator, HTTP server, GPIO/I²C drivers
  cmd/app/             combined Pi binary (keypad + LCD + web UI)
  cmd/server/          desktop-only web UI binary
  cmd/bench/           Šaг throughput benchmark
controller/          Python source — reference (was the original runtime)
  emulator/            ИК13 / ИР2 chip simulation + program loader
  driver/              I²C HD44780 LCD
  app.py               original Pi entry point
  keypad.py            GPIO keypad scanner
webui/               browser UI assets (index.html, served by both Go and Python)
programs/            YAML program library (numbered 01–10)
tests/               HTTP-driven integration tests (work against either backend)
tools/               deploy-pi.sh, benchmark.py, install-pi.sh (legacy Python)
doc/                 hardware schematics, deployment notes, program list
mk-52.service        legacy systemd unit (Python-era; deploy-pi.sh writes the Go one)
```
