# -*- coding: utf-8 -*-
# Машина — MK-52 emulator orchestrator. Ported from emulator/emulator.js
# (Такт, Шаг, Нажатие_кнопки, Отобразить_индикатор, Включить, Выключить).
# Wires four chips (ИК1302, ИК1303, ИР2_1, ИР2_2) and drives them from a
# background thread at the same 30 ms tick rate as the original setInterval.

import os
import threading
import time

from .chips import ИК13, ИР2
from .loader import Адрес_команды, ПРОГРАММНЫХ_ШАГОВ, разобрать_команду
from .rom import ПЗУ

Символы_разрядов = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "L", "С", "Г", "Е", " "]


class Машина:

    ПЕРИОД_ШАГА = 0.030  # seconds — matches setInterval(Шаг, 30) in JS
    # Шаг iteration count. Original JS used 560 (calibrated so chip-time matches
    # real-time). CPython spends 89% of Такт runtime on int bit-ops; at 560 a
    # Шаг takes ~76 ms wall-clock on a Mac, so we run at ИТЕРАЦИЙ_В_ШАГЕ/560 of
    # original. Under PyPy the JIT makes Шаг ~65× faster — 560 fits well inside
    # the 30 ms tick. On a Pi Zero (armv6, CPython only, no PyPy build) Šaг at
    # 200 iters takes ~1270 ms wall-clock and blocks press_button that long; a
    # value like 10–20 keeps the chip lock cycling fast so keystrokes feel
    # responsive, at the same effective chip rate (limited by host CPU anyway).
    # Override via MK52_ITERS_PER_SHAG env var. Default 200 suits a desktop.
    ИТЕРАЦИЙ_В_ШАГЕ = int(os.environ.get("MK52_ITERS_PER_SHAG", "200"))

    def __init__(self, on_display=None, on_log=None):
        self.on_display = on_display
        self.on_log = on_log
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.Мера_угла = 10  # 10=радианы, 11=градусы, 12=грады

        self.ИК1302 = ИК13()
        self.ИК1303 = ИК13()
        self.ИР2_1 = ИР2()
        self.ИР2_2 = ИР2()
        self._Заполнить_ПЗУ()

        self.Индикатор = [0] * 13
        self.Индик_зпт = [False] * 13
        self.Индик_ст = [-1] * 13

    def _Заполнить_ПЗУ(self):
        self.ИК1302.ПЗУ_команд = ПЗУ["ИК1302"]["команды"]
        self.ИК1302.ПЗУ_синхропрограмм = ПЗУ["ИК1302"]["синхропрограммы"]
        self.ИК1302.ПЗУ_микрокоманд = ПЗУ["ИК1302"]["микрокоманды"]
        self.ИК1303.ПЗУ_команд = ПЗУ["ИК1303"]["команды"]
        self.ИК1303.ПЗУ_синхропрограмм = ПЗУ["ИК1303"]["синхропрограммы"]
        self.ИК1303.ПЗУ_микрокоманд = ПЗУ["ИК1303"]["микрокоманды"]

    def Такт(self):
        # Reference implementation, kept for clarity; the hot path in Шаг
        # inlines this to skip method-dispatch overhead in CPython.
        self.ИК1302.вход = self.ИР2_2.выход
        self.ИК1302.Такт()
        self.ИК1303.вход = self.ИК1302.выход
        self.ИК1303.Такт()
        self.ИР2_1.вход = self.ИК1303.выход
        self.ИР2_1.Такт()
        self.ИР2_2.вход = self.ИР2_1.выход
        self.ИР2_2.Такт()
        self.ИК1302.M[((self.ИК1302.микротакт >> 2) + 41) % 42] = self.ИР2_2.выход

    def Шаг(self):
        # Pre-bind everything used in the inner loop. CPython turns each
        # self.X / obj.method into a dict lookup; binding once cuts ~20% off
        # the 23 520-iteration hot path.
        ИК1302 = self.ИК1302
        ИК1303 = self.ИК1303
        ИР2_1 = self.ИР2_1
        ИР2_2 = self.ИР2_2
        ИК1302_Такт = ИК1302.Такт
        ИК1303_Такт = ИК1303.Такт
        ИК1302_M = ИК1302.M
        ИР2_1_M = ИР2_1.M
        ИР2_2_M = ИР2_2.M
        Индикатор = self.Индикатор
        Индик_зпт = self.Индик_зпт

        ИК1303.клав_y = 1
        ИК1303.клав_x = self.Мера_угла
        ИК1302_R = ИК1302.R
        ИК1302_зпт_внутр = ИК1302.индик_зпт

        # ИР2 state read once; written back after the hot loop.
        ИР2_1_мт = ИР2_1.микротакт
        ИР2_2_мт = ИР2_2.микротакт
        ИР2_2_выход = ИР2_2.выход

        for _ in range(self.ИТЕРАЦИЙ_В_ШАГЕ):
            for _ in range(42):
                ИК1302.вход = ИР2_2_выход
                ИК1302_Такт()
                ИК1303.вход = ИК1302.выход
                ИК1303_Такт()
                # ИР2_1.Такт() inlined: shift one slot of M[252].
                ИР2_1_вход_byte = ИК1303.выход
                ИР2_1_выход = ИР2_1_M[ИР2_1_мт]
                ИР2_1_M[ИР2_1_мт] = ИР2_1_вход_byte
                ИР2_1_мт = ИР2_1_мт + 1
                if ИР2_1_мт > 251:
                    ИР2_1_мт = 0
                # ИР2_2.Такт() inlined.
                ИР2_2_выход = ИР2_2_M[ИР2_2_мт]
                ИР2_2_M[ИР2_2_мт] = ИР2_1_выход
                ИР2_2_мт = ИР2_2_мт + 1
                if ИР2_2_мт > 251:
                    ИР2_2_мт = 0
                # ИК1302 feedback path (same as Такт()).
                _i = (ИК1302.микротакт >> 2) + 41
                if _i >= 42:
                    _i -= 42
                ИК1302_M[_i] = ИР2_2_выход
            if ИК1302.обн_индик:
                Индикатор[0] = ИК1302_R[24]
                Индикатор[1] = ИК1302_R[21]
                Индикатор[2] = ИК1302_R[18]
                Индикатор[3] = ИК1302_R[15]
                Индикатор[4] = ИК1302_R[12]
                Индикатор[5] = ИК1302_R[9]
                Индикатор[6] = ИК1302_R[6]
                Индикатор[7] = ИК1302_R[3]
                Индикатор[8] = ИК1302_R[0]
                Индикатор[9] = ИК1302_R[33]
                Индикатор[10] = ИК1302_R[30]
                Индикатор[11] = ИК1302_R[27]
                Индик_зпт[0] = ИК1302_зпт_внутр[9]
                Индик_зпт[1] = ИК1302_зпт_внутр[8]
                Индик_зпт[2] = ИК1302_зпт_внутр[7]
                Индик_зпт[3] = ИК1302_зпт_внутр[6]
                Индик_зпт[4] = ИК1302_зпт_внутр[5]
                Индик_зпт[5] = ИК1302_зпт_внутр[4]
                Индик_зпт[6] = ИК1302_зпт_внутр[3]
                Индик_зпт[7] = ИК1302_зпт_внутр[2]
                Индик_зпт[8] = ИК1302_зпт_внутр[1]
                Индик_зпт[9] = ИК1302_зпт_внутр[12]
                Индик_зпт[10] = ИК1302_зпт_внутр[11]
                Индик_зпт[11] = ИК1302_зпт_внутр[10]
                ИК1302.обн_индик = False

        # Flush ИР2 state back.
        ИР2_1.микротакт = ИР2_1_мт
        ИР2_2.микротакт = ИР2_2_мт
        ИР2_2.выход = ИР2_2_выход

        Индик_ст = self.Индик_ст
        обновить = False
        for i in range(13):
            if Индик_ст[i] != Индикатор[i]:
                обновить = True
            Индик_ст[i] = Индикатор[i]
        if обновить:
            self.Отобразить_индикатор()
        ИК1302.клав_x = 0
        ИК1302.клав_y = 0

    def Отобразить_индикатор(self):
        is_dimmed = self.ИК1302.запятая != 11
        digits = ""
        points = ""
        for i in range(12):
            digits += Символы_разрядов[self.Индикатор[i]]
            points += ("," if self.Индик_зпт[i] else " ")
        if self.on_display is not None:
            self.on_display(digits, points, is_dimmed)

    def Нажатие_кнопки(self, x, y):
        # Run two Šaги per press: the first with the key set (chip's keyboard
        # scan registers it), the second with the key cleared (chip's post-
        # press microcode settles: exit digit-entry after В↑, finalize push,
        # etc.). On fast hosts both fit inside a single press_button so the
        # cost is trivial; on slow hosts (Pi Zero) skipping the second Šaг
        # leaves the chip mid-settle when the next press arrives and merges
        # state across keys (e.g. "7 В↑ 3 +" produces 14 instead of 10).
        with self._lock:
            self.ИК1302.клав_x = x
            self.ИК1302.клав_y = y
            self.Шаг()
            self.Шаг()

    # Compatibility alias matching the old Emulator.press_button.
    press_button = Нажатие_кнопки

    def Ввести_код(self, source: str) -> int:
        """Parse MK-52 source and write opcodes directly into program memory.
        Returns the number of program steps written. Tokens are whitespace-
        separated; an optional 'NN.' line-number prefix is stripped.
        """
        tokens = source.split()
        # Strip optional 'NN.' / 'AN.' line-number prefixes; the JS parser
        # used the prefix to set the target step index, but for a simple
        # in-order listing we just drop it.
        стрипнутые = []
        for t in tokens:
            if len(t) >= 3 and t[2] == "." and (t[0].isdigit() or t[0] in "A-") and t[1].isdigit():
                t = t[3:]
            if t:
                стрипнутые.append(t)
        commands = стрипнутые[:ПРОГРАММНЫХ_ШАГОВ]

        chips = {
            1: self.ИР2_1, 2: self.ИР2_2,
            3: self.ИК1302, 4: self.ИК1303,
        }
        with self._lock:
            перестановка = (self.ИР2_1.микротакт // 84) % len(
                # 3 permutations
                (0, 1, 2)
            )
            def записать(номер, код):
                ст = код >> 4
                мл = код & 0xF
                chip_id, адрес = Адрес_команды(номер, перестановка)
                chip = chips[chip_id]
                chip.M[адрес] = ст
                chip.M[адрес - 3] = мл

            for i, tok in enumerate(commands):
                записать(i, разобрать_команду(tok))
            # Zero remaining program steps so a previous listing doesn't bleed through.
            for i in range(len(commands), ПРОГРАММНЫХ_ШАГОВ):
                записать(i, 0)
            # Ensure the program counter is reset (В/О behavior).
            self.ИК1302.R[36] = 0
            self.ИК1302.R[39] = 0
        return len(commands)

    def _Цикл(self):
        next_at = time.monotonic()
        while not self._stop.is_set():
            with self._lock:
                self.Шаг()
            next_at += self.ПЕРИОД_ШАГА
            sleep = next_at - time.monotonic()
            if sleep > 0:
                self._stop.wait(sleep)
            else:
                next_at = time.monotonic()  # we fell behind; resync

    def __enter__(self):
        if self.on_log is not None:
            self.on_log("Initializing...")
        # Prime the chips with one Шаг so the first display refresh fires.
        with self._lock:
            self.Шаг()
        self._stop.clear()
        self._thread = threading.Thread(target=self._Цикл, daemon=True, name="МК-52 Шаг")
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
