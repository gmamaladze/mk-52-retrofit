# -*- coding: utf-8 -*-
# Program tests: enter programs into program memory by keystroke (F+ПРГ,
# type opcodes, F+АВТ) and verify execution via the display.

import unittest

from .api import (
    display, load_program, parse_display, press, reset_calc, run_and_wait,
    wait_server,
)


class TestPrograms(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_server()

    def setUp(self):
        reset_calc()

    def assertResult(self, expected, tol=1e-6):
        d = display()
        val = parse_display(d)
        self.assertIsNotNone(
            val,
            f"display in error/blank state: digits={d['digits']!r} points={d['points']!r}")
        self.assertAlmostEqual(val, expected, delta=tol,
            msg=f"expected {expected}, got {val} (digits={d['digits']!r})")

    def test_constant_stop(self):
        # The simplest program: a single-step С/П. Load first (which clears
        # state), then key in 7, then run — X stays 7.
        load_program("С/П")
        press("7")
        d = run_and_wait()
        self.assertEqual(parse_display(d), 7)

    def test_double_via_register(self):
        # 5 stored in R1, then load R1 twice and add -> 10. (Avoids the
        # digit-entry-mode quirk by using a register to break entry mode.)
        load_program("5 П1 ИП1 ИП1 + С/П")
        d = run_and_wait()
        self.assertEqual(parse_display(d), 10)

    def test_square_with_input(self):
        # Program squares X. Load first (clears state), then key in 6, run.
        load_program("x² С/П")
        press("6")
        d = run_and_wait()
        self.assertEqual(parse_display(d), 36)

    def test_counter_loop(self):
        # Counter: each С/П increments R1 and displays it.
        # Step 0: 0  store R1=0
        # Step 2: ИП1 С/П  (display)
        # Step 4: ИП1 1 + П1 БП 02
        load_program("0 П1 ИП1 С/П ИП1 1 + П1 БП 02")
        d = run_and_wait()
        self.assertEqual(parse_display(d), 0)
        d = run_and_wait()
        self.assertEqual(parse_display(d), 1)
        d = run_and_wait()
        self.assertEqual(parse_display(d), 2)
        d = run_and_wait()
        self.assertEqual(parse_display(d), 3)

    def test_squares_stream(self):
        # Squares 1², 2², 3²...
        load_program("0 П1 ИП1 1 + П1 ИП1 x² С/П БП 02")
        d = run_and_wait()
        self.assertEqual(parse_display(d), 1)   # 1²
        d = run_and_wait()
        self.assertEqual(parse_display(d), 4)   # 2²
        d = run_and_wait()
        self.assertEqual(parse_display(d), 9)   # 3²


if __name__ == "__main__":
    unittest.main()
