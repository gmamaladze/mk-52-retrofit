# -*- coding: utf-8 -*-
"""Measure emulator throughput on the current Python runtime.

Run on whichever host you're targeting:

    python3 tools/benchmark.py          # CPython
    pypy3   tools/benchmark.py          # PyPy

The original МК-52 emulator (JS) ran at 560 iterations per 30 ms tick,
which is the rate at which user-visible chip speed matches real hardware.
This script reports how close the current runtime gets.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "controller"))

from emulator import Машина  # noqa: E402

ORIGINAL_ITER_PER_SHAG = 560
TICK_MS = 30  # ПЕРИОД_ШАГА = 30 ms


def bench(n_shagi):
    m = Машина()
    m._Заполнить_ПЗУ()
    # Warmup for PyPy JIT.
    for _ in range(max(50, n_shagi // 10)):
        m.Шаг()
    t0 = time.perf_counter()
    for _ in range(n_shagi):
        m.Шаг()
    return (time.perf_counter() - t0) / n_shagi  # seconds per Шаг


def main():
    runtime = "PyPy" if hasattr(sys, "pypy_version_info") else "CPython"
    print(f"Runtime: {runtime} {sys.version.split()[0]}")
    print(f"ИТЕРАЦИЙ_В_ШАГЕ = {Машина.ИТЕРАЦИЙ_В_ШАГЕ}  (original МК-52 = {ORIGINAL_ITER_PER_SHAG})")
    print()

    n = 200
    per_shag = bench(n)
    per_shag_ms = per_shag * 1000

    # Effective iteration rate, accounting for the 30 ms tick floor.
    wall_per_shag_ms = max(per_shag_ms, TICK_MS)
    effective_iter_per_sec = Машина.ИТЕРАЦИЙ_В_ШАГЕ * 1000.0 / wall_per_shag_ms
    original_iter_per_sec = ORIGINAL_ITER_PER_SHAG * 1000.0 / TICK_MS
    pct = 100.0 * effective_iter_per_sec / original_iter_per_sec

    print(f"  Шаг wall time:        {per_shag_ms:6.2f} ms")
    print(f"  Effective iter/sec:   {effective_iter_per_sec:9,.0f}")
    print(f"  Original МК-52:       {original_iter_per_sec:9,.0f}")
    print(f"  Speed vs original:    {pct:6.1f}%  ({'BELOW' if pct < 100 else 'AT or ABOVE'} original)")
    print()

    # What ИТЕРАЦИЙ_В_ШАГЕ would saturate the 30 ms tick?
    iters_per_ms = Машина.ИТЕРАЦИЙ_В_ШАГЕ / per_shag_ms
    max_iter_for_tick = int(iters_per_ms * TICK_MS)
    print(f"  Max ИТЕРАЦИЙ_В_ШАГЕ that fits in {TICK_MS} ms: ~{max_iter_for_tick}")
    if max_iter_for_tick >= ORIGINAL_ITER_PER_SHAG:
        print(f"  → You can set ИТЕРАЦИЙ_В_ШАГЕ = {ORIGINAL_ITER_PER_SHAG} for full original speed.")
    else:
        print(f"  → Original-speed (560) not reachable on this runtime; "
              f"chip will run at {100.0 * max_iter_for_tick / ORIGINAL_ITER_PER_SHAG:.0f}% of original.")


if __name__ == "__main__":
    main()
