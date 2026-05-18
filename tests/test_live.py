# -*- coding: utf-8 -*-
# Live-calculation tests: drive the keypad through the HTTP API, assert that
# the display reflects the expected result. No program is loaded — every
# operation is a key press.

import math
import unittest

from .api import display, parse_display, press, press_seq, reset_calc, wait_server


class TestLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        wait_server()

    def setUp(self):
        reset_calc()

    def assertX(self, expected, tol=1e-6):
        actual = parse_display()
        d = display()
        self.assertIsNotNone(
            actual,
            f"display in error/blank state: digits={d['digits']!r} points={d['points']!r}")
        self.assertAlmostEqual(actual, expected, delta=tol,
            msg=f"expected {expected}, got {actual} (digits={d['digits']!r})")

    # ----- single-digit arithmetic -----

    def test_addition(self):
        press_seq(["1", "В↑", "1", "+"])
        self.assertX(2)

    def test_subtraction(self):
        press_seq(["5", "В↑", "3", "-"])
        self.assertX(2)

    def test_multiplication(self):
        press_seq(["6", "В↑", "7", "*"])
        self.assertX(42)

    def test_division(self):
        press_seq(["8", "В↑", "2", "/"])
        self.assertX(4)

    # ----- two-digit and chained -----

    def test_two_digit_entry(self):
        press_seq(["1", "2", "В↑", "3", "+"])
        self.assertX(15)

    def test_chained_ops(self):
        # (5 + 3) * 2 = 16
        press_seq(["5", "В↑", "3", "+", "В↑", "2", "*"])
        self.assertX(16)

    def test_negation(self):
        press_seq(["7", "/-/"])
        self.assertX(-7)

    # ----- F-prefix math -----

    def test_square(self):
        press_seq(["5", "F", "*"])  # F + × = x²
        self.assertX(25)

    def test_sqrt(self):
        press_seq(["2", "5", "F", "-"])  # F + - = √
        self.assertX(5)

    def test_reciprocal(self):
        press_seq(["4", "F", "/"])  # F + ÷ = 1/x
        self.assertX(0.25)

    # ----- decimal -----

    def test_decimal_entry(self):
        press_seq(["1", ".", "5", "В↑", "2", ".", "5", "+"])
        self.assertX(4)


if __name__ == "__main__":
    unittest.main()
