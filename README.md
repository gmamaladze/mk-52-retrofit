https://pmk.arbinada.com/mk61emuweb.html#


http://lordbss.narod.ru/pmk38.html


https://www.raspberrypi.org/documentation/linux/usage/systemd.md


```
sudo systemctl stop mk-52.service
sudo systemctl start mk-52.service
```

## Desktop web UI

```
python3 webui/server.py        # http://127.0.0.1:8080/
```

Performance: the chip simulator is a tight int-bit-op loop. CPython runs it
at ~36 % of the original МК-52's speed; **PyPy is ~65× faster** for the same
loop and runs at full chip speed with idle headroom. For desktop use:

```
brew install pypy3
pypy3 -m pip install pyyaml
pypy3 webui/server.py
```

## Raspberry Pi install

```
sudo apt remove -y python3-rpi.gpio        # if preinstalled, conflicts with the pip drop-in
cd controller && pip install -r requirements.txt
```

`requirements.txt` pulls [`rpi-lgpio`](https://pypi.org/project/rpi-lgpio/),
a drop-in replacement for `RPi.GPIO` that uses `lgpio` underneath. Same
`import RPi.GPIO as GPIO` API so the source doesn't change. Two reasons for
the swap:

- `RPi.GPIO` is deprecated and doesn't work on Pi 5.
- `RPi.GPIO` is a CPython C extension; `rpi-lgpio` is cffi-based, so it
  also works under PyPy.

Verify edge-detect behavior on your Pi — `keypad.add_event_detect` is the
one spot where `rpi-lgpio` and `RPi.GPIO` [diverge slightly](https://github.com/waveform80/rpi-lgpio/blob/main/docs/differences.rst).

## PyPy on the Pi (optional, for speed)

PyPy has ARM builds (`apt install pypy3`); combined with the `rpi-lgpio`
swap above it gives ~65× chip-loop speedup, bringing the emulator from
~36 % of original МК-52 speed up to full speed with headroom. The
[benchmark script](tools/benchmark.py) reports what your Pi can sustain.