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

## Programs

10 example programs ship in `programs/`, numbered 01–10. On the Pi, press a
program number on the keypad and hit **A↑** to load it from "ROM". See
[doc/programs.md](doc/programs.md) for the full list and how to add more.

## Raspberry Pi

`requirements.txt` swaps `RPi.GPIO` for [`rpi-lgpio`](https://pypi.org/project/rpi-lgpio/)
(drop-in, no source changes, works on Pi 5 and under PyPy). The full
install steps, smoke tests, and the open questions to verify on actual
hardware live in [doc/raspberry-pi-deployment.md](doc/raspberry-pi-deployment.md).

Performance: CPython runs the chip simulator at ~36 % of original МК-52
speed; PyPy is ~65× faster on the same loop and reaches full speed with
headroom. `tools/benchmark.py` measures the ceiling on a given host.