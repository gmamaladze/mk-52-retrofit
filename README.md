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

The Pi runs a single Go binary that owns the chip emulator and drives the
physical keypad, the I²C LCD, and the web UI from one process. Source
lives in `go/`. Deploy from a host that has Go installed (cross-compiles
the binary, scp's it, installs the systemd service):

```bash
bash tools/deploy-pi.sh user@<pi-ip>           # default armv6 (Pi Zero v1 / Pi 1)
GOARM=7 bash tools/deploy-pi.sh user@<pi-ip>   # Pi 2/3
GOARCH=arm64 bash tools/deploy-pi.sh user@<pi-ip>  # Pi 4/5
```

Pi prerequisites (run once): I²C enabled (`sudo raspi-config nonint do_i2c 0`),
user in `gpio` + `i2c` groups (default on Pi OS), passwordless sudo if you
want re-runs to be non-interactive. The repo should be at `~/mk-52-retrofit`
(rsync or `git clone`).

Verify with `systemctl status mk-52` and `journalctl -u mk-52 -f`. The
Python codebase under `controller/` and `webui/` stays in the repo as
reference but is no longer the runtime — the systemd unit points at
`/usr/local/bin/mk52-app`.

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

The chip's microcode interpreter is the hot loop. Numbers measured on the
Pi Zero v1 (armv6, CPython's slowest target):

| Runtime | Šaг wall time | Effective chip speed |
|---|---|---|
| CPython         | 1270 ms | 1 % of original МК-52 |
| Go (this binary) | 52 ms  | 20 % of original — **24× CPython** |

On a Pi 4/5 (ARM64) Go comfortably exceeds original speed. The Mac M-series
runs at 0.16 ms per Šaг (170× CPython).

`go/cmd/bench` prints these numbers on whichever host runs it. Build with
`tools/deploy-pi.sh` or `GOOS=linux GOARCH=arm GOARM=6 go build ./cmd/bench`.

## Layout

```
go/                  Go source (production runtime)
  mk52/                chip simulator, HTTP server, GPIO/I²C drivers
  cmd/app/             combined Pi binary (keypad + LCD + web UI)
  cmd/server/          desktop-only web UI binary
  cmd/bench/           Šaг throughput benchmark
controller/          Python source (reference; was the original runtime)
  emulator/            ИК13 / ИР2 chip simulation + program loader
  driver/              I²C HD44780 LCD
  app.py               original Pi entry point
  keypad.py            GPIO keypad scanner
webui/               browser UI assets (index.html, served by Go)
programs/            YAML library of example programs (numbered 01–10)
tests/               HTTP-driven integration tests (work against either backend)
tools/               deploy-pi.sh, install-pi.sh (legacy), benchmark.py
doc/                 Hardware schematics, deployment notes, program list
mk-52.service        systemd unit template (Python-era; deploy-pi.sh writes the Go one)
```
