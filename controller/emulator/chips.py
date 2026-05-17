# -*- coding: utf-8 -*-
# Микросхемы ИР2 (RAM shift register) and ИК13 (calculator chip).
# Ported from emulator/emulator.js lines 677-837. Identifiers preserved verbatim.
#
# Performance notes (CPython): the inner loop in ИК13.Такт() runs roughly
# 47 000 times per Шаг (560 × 42 × 2 chips). Python attribute lookups are
# dict-based and ~10× slower than V8 field reads, so we read self.* into
# locals at the top and write back at the bottom. This is the standard
# CPython hot-loop idiom — algorithm is unchanged.

J = (
    0, 1, 2, 3, 4, 5,
    3, 4, 5, 3, 4, 5,
    3, 4, 5, 3, 4, 5,
    3, 4, 5, 3, 4, 5,
    6, 7, 8, 0, 1, 2,
    3, 4, 5, 6, 7, 8,
    0, 1, 2, 3, 4, 5,
)


class ИР2:
    __slots__ = ("M", "вход", "выход", "микротакт")

    def __init__(self):
        self.M = [0] * 252
        self.вход = 0
        self.выход = 0
        self.микротакт = 0

    def Такт(self):
        мт = self.микротакт
        M = self.M
        self.выход = M[мт]
        M[мт] = self.вход
        мт += 1
        if мт > 251:
            мт = 0
        self.микротакт = мт


class ИК13:
    __slots__ = (
        "ПЗУ_микрокоманд", "ПЗУ_синхропрограмм", "ПЗУ_команд",
        "M", "R", "ST",
        "S", "S1", "L", "T", "П",
        "микротакт", "микрокоманда",
        "вход", "выход",
        "АМК", "АСП", "АК", "МОД",
        "индик_зпт",
        "клав_x", "клав_y", "запятая",
        "обн_индик",
    )

    def __init__(self):
        self.ПЗУ_микрокоманд = ()
        self.ПЗУ_синхропрограмм = ()
        self.ПЗУ_команд = ()
        self.M = [0] * 42
        self.R = [0] * 42
        self.ST = [0] * 42
        self.S = 0
        self.S1 = 0
        self.L = 0
        self.T = 0
        self.П = 0
        self.микротакт = 0
        self.микрокоманда = 0
        self.вход = 0
        self.выход = 0
        self.АМК = 0
        self.АСП = 0
        self.АК = 0
        self.МОД = 0
        self.индик_зпт = [False] * 14
        self.клав_x = 0
        self.клав_y = 0
        self.запятая = 0
        self.обн_индик = False

    def Такт(self):
        # --- read state into locals ---
        мт = self.микротакт
        АК = self.АК
        S = self.S
        S1 = self.S1
        L = self.L
        T = self.T
        АСП = self.АСП
        АМК = self.АМК
        МОД = self.МОД
        запятая = self.запятая
        обн_индик = self.обн_индик
        R = self.R
        M = self.M
        ST = self.ST
        индик_зпт = self.индик_зпт
        ПЗУ_команд = self.ПЗУ_команд
        ПЗУ_синхропрограмм = self.ПЗУ_синхропрограмм
        ПЗУ_микрокоманд = self.ПЗУ_микрокоманд
        J_ = J
        клав_x = self.клав_x
        клав_y = self.клав_y

        сигнал_I = мт >> 2
        сигнал_D = мт // 12
        if мт == 0:
            АК = R[36] + 16 * R[39]
            if (ПЗУ_команд[АК] & 0xfc0000) == 0:
                T = 0
        команда = ПЗУ_команд[АК]
        k = мт // 36
        if k < 3:
            АСП = команда & 0xff
        elif k == 3:
            АСП = (команда >> 8) & 0xff
        elif k == 4:
            АСП = (команда >> 16) & 0xff
            if АСП > 0x1f:
                if мт == 144:
                    R[37] = АСП & 0xf
                    R[40] = АСП >> 4
                АСП = 0x5f
        МОД = (команда >> 24) & 0xff
        АМК = ПЗУ_синхропрограмм[АСП * 9 + J_[сигнал_I]] & 0x3f
        if АМК > 59:
            АМК = (АМК - 60) * 2
            if L == 0:
                АМК += 1
            АМК += 60
        мк = ПЗУ_микрокоманд[АМК]

        альфа = 0
        бета = 0
        гамма = 0

        top2 = (мк >> 24) & 3
        if top2 >= 2:
            if (мт // 12) != клав_x - 1 and клав_y > 0:
                S1 |= клав_y

        if мк & 1:
            альфа |= R[сигнал_I]
        if мк & 2:
            альфа |= M[сигнал_I]
        if мк & 4:
            альфа |= ST[сигнал_I]
        if мк & 8:
            альфа |= (~R[сигнал_I]) & 0xf
        if (мк & 16) and L == 0:
            альфа |= 0xa
        if мк & 32:
            альфа |= S
        if мк & 64:
            альфа |= 4

        мк7 = мк >> 7
        if мк7 & 16:
            бета |= 1
        if мк7 & 8:
            бета |= 6
        if мк7 & 4:
            бета |= S1
        if мк7 & 2:
            бета |= (~S) & 0xf
        if мк7 & 1:
            бета |= S

        if команда & 0xfc0000:
            if клав_y == 0:
                T = 0
        else:
            обн_индик = True
            if (мт // 12) == клав_x - 1 and клав_y > 0:
                S1 = клав_y
                T = 1
            if 0 <= сигнал_D < 12 and L > 0:
                запятая = сигнал_D
            индик_зпт[сигнал_D] = L > 0

        мк12 = мк >> 12
        if мк12 & 4:
            гамма = (~T) & 1
        if мк12 & 2:
            гамма |= (~L) & 1
        if мк12 & 1:
            гамма |= L & 1

        сумма = альфа + бета + гамма
        сигма = сумма & 0xf
        П = сумма >> 4

        if МОД == 0 or сигнал_I >= 36:
            sw = (мк >> 15) & 7
            if sw:
                if sw == 1:
                    R[сигнал_I] = R[(сигнал_I + 3) % 42]
                elif sw == 2:
                    R[сигнал_I] = сигма
                elif sw == 3:
                    R[сигнал_I] = S
                elif sw == 4:
                    R[сигнал_I] = R[сигнал_I] | S | сигма
                elif sw == 5:
                    R[сигнал_I] = S | сигма
                elif sw == 6:
                    R[сигнал_I] = R[сигнал_I] | S
                else:  # 7
                    R[сигнал_I] = R[сигнал_I] | сигма
            if (мк >> 18) & 1:
                R[(сигнал_I + 41) % 42] = сигма
            if (мк >> 19) & 1:
                R[(сигнал_I + 40) % 42] = сигма

        if (мк >> 21) & 1:
            L = П & 1
        if (мк >> 20) & 1:
            M[сигнал_I] = S

        sw = (мк >> 22) & 3
        if sw == 1:
            S = S1
        elif sw == 2:
            S = сигма
        elif sw == 3:
            S = S1 | сигма

        sw = top2  # (мк >> 24) & 3 — same value as above
        if sw == 1:
            S1 = сигма
        elif sw == 3:
            S1 = S1 | сигма
        # sw == 2 is a no-op in original JS

        sw = (мк >> 26) & 3
        if sw == 1:
            j1 = (сигнал_I + 1) % 42
            j2 = (сигнал_I + 2) % 42
            ST[j2] = ST[j1]
            ST[j1] = ST[сигнал_I]
            ST[сигнал_I] = сигма
        elif sw == 2:
            j1 = (сигнал_I + 1) % 42
            j2 = (сигнал_I + 2) % 42
            x = ST[сигнал_I]
            ST[сигнал_I] = ST[j1]
            ST[j1] = ST[j2]
            ST[j2] = x
        elif sw == 3:
            j1 = (сигнал_I + 1) % 42
            j2 = (сигнал_I + 2) % 42
            x = ST[сигнал_I]
            y = ST[j1]
            z = ST[j2]
            ST[сигнал_I] = сигма | y
            ST[j1] = x | z
            ST[j2] = y | x

        self.выход = M[сигнал_I] & 0xf
        M[сигнал_I] = self.вход
        мт += 4
        if мт > 167:
            мт = 0

        # --- write back ---
        self.микротакт = мт
        self.АК = АК
        self.S = S
        self.S1 = S1
        self.L = L
        self.T = T
        self.П = П
        self.АСП = АСП
        self.АМК = АМК
        self.МОД = МОД
        self.микрокоманда = мк
        self.запятая = запятая
        self.обн_индик = обн_индик
