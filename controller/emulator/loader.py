# -*- coding: utf-8 -*-
# Source-code loader. Ports Ввести_код / Адрес_команды / мнемоники_команд
# from emulator/emulator.js. МК-52 mode only (расширенный=False), so the
# 98-step program memory and Перестановки_адресов_страниц_памяти_ variant
# are used.

# Each entry: (opcode, (mnemonic aliases…), has_register_suffix)
# has_register_suffix=True means the opcode's low nibble carries a register
# index (e.g. "ИП5" → 0x60 + 5 = 0x65). Field index 2 in the original JS
# table; only the values 1 (suffix) and "anything else" (no suffix) matter
# to the parser.
МНЕМОНИКИ_КОМАНД = (
    (0x15, ("10^x", "10x", "F10^x", "F10x"), False),
    (0x54, ("НОП", "KНОП", "КНОП"), False),
    (0x16, ("e^x", "ex", "Fe^x", "Fex"), False),
    (0x17, ("lg", "Flg"), False),
    (0x18, ("ln", "Fln"), False),
    (0x30, ("ЧМ", "KЧМ", "КЧМ"), False),
    (0x19, ("arcsin", "Farcsin"), False),
    (0x31, ("|x|", "K|x|", "К|x|"), False),
    (0x1A, ("arccos", "Farccos"), False),
    (0x32, ("ЗН", "KЗН", "КЗН"), False),
    (0x1B, ("arctg", "Farctg"), False),
    (0x33, ("ГМ", "KГМ", "КГМ"), False),
    (0x1C, ("sin", "Fsin"), False),
    (0x34, ("[x]", "K[x]", "К[x]"), False),
    (0x1D, ("cos", "Fcos"), False),
    (0x35, ("{x}", "(x)", "K{x}", "К{x}", "K(x)", "К(x)"), False),
    (0x1E, ("tg", "Ftg"), False),
    (0x36, ("max", "Kmax", "Кmax"), False),
    (0x10, ("+",), False),
    (0x11, ("-",), False),
    (0x12, ("*", "x", "х", "×", "⋅"), False),
    (0x13, ("/", ":", "÷"), False),
    (0x20, ("пи", "π", "Fпи", "Fπ"), False),
    (0x26, ("МГ", "KМГ", "КМГ"), False),
    (0x21, ("КвКор", "квкор", "корень", "√", "FКвКор", "Fквкор", "Fкорень", "F√"), False),
    (0x22, ("x^2", "x2", "x²", "Fx^2", "Fx2", "Fx²"), False),
    (0x23, ("1/x", "F1/x"), False),
    (0x14, ("<->", "XY", "↔", "X↔Y"), False),
    (0x0E, ("^", "В^", "↑", "В↑"), False),
    (0x24, ("x^y", "xy", "Fx^y", "Fxy"), False),
    (0x27, ("K-", "К-"), False),
    (0x28, ("Kx", "Кх", "K*", "К*"), False),
    (0x29, ("K/", "К/", "K:", "К:", "K÷", "К÷"), False),
    (0x2A, ("МЧ", "KМЧ", "КМЧ"), False),
    (0x0F, ("Вx", "FВx"), False),
    (0x3B, ("СЧ", "KСЧ", "КСЧ"), False),
    (0x0A, (",", "."), False),
    (0x0B, ("/-/", "+/-"), False),
    (0x0C, ("ВП",), False),
    (0x0D, ("Сx",), False),
    (0x25, ("->", "↻", "→", "F->", "F↻", "F→"), False),
    (0x37, ("/\\", "⋀", "K/\\", "К/\\", "K⋀", "К⋀"), False),
    (0x38, ("\\/", "⋁", "K\\/", "К\\/", "K⋁", "К⋁"), False),
    (0x39, ("(+)", "⊕", "K(+)", "К(+)", "K⊕", "К⊕"), False),
    (0x3A, ("ИНВ", "KИНВ", "КИНВ"), False),
    (0x52, ("В/О", "В/0"), False),
    (0x50, ("С/П",), False),
    (0x59, ("x>=0", "x≥0", "x⩾0", "Fx>=0", "Fx≥0", "Fx⩾0"), False),
    (0x57, ("x#0", "x!=0", "x<>0", "x≠0", "Fx#0", "Fx!=0", "Fx<>0", "Fx≠0"), False),
    (0x51, ("БП",), False),
    (0x53, ("ПП",), False),
    (0x58, ("L2", "FL2"), False),
    (0x5A, ("L3", "FL3"), False),
    (0x5C, ("x<0", "Fx<0"), False),
    (0x5E, ("x=0", "Fx=0"), False),
    (0x5D, ("L0", "FL0"), False),
    (0x5B, ("L1", "FL1"), False),
    (0x40, ("П", "XП"), True),
    (0x60, ("ИП", "ПX", "Пx"), True),
    (0x70, ("Kx#0", "Кx#0", "Kx!=0", "Кx!=0", "Kx<>0", "Кx<>0", "Kx≠0", "Кx≠0"), True),
    (0x80, ("KБП", "КБП"), True),
    (0x90, ("Kx>=0", "Кx>=0", "Kx≥0", "Кx≥0", "Kx⩾0", "Кx⩾0"), True),
    (0xA0, ("KПП", "КПП"), True),
    (0xB0, ("KП", "КП", "KXП", "КXП"), True),
    (0xC0, ("Kx<0", "Кx<0"), True),
    (0xD0, ("KИП", "КИП", "KПX", "КПX"), True),
    (0xE0, ("Kx=0", "Кx=0"), True),
)

# Page addresses inside the chip M arrays. Each entry is (chip_id, address)
# where chip_id is 1=ИР2_1, 2=ИР2_2, 3=ИК1302, 4=ИК1303, 5=ИК1306.
АДРЕСА_СТРАНИЦ_ПАМЯТИ = (
    (1, 41), (1, 83), (1, 125), (1, 167), (1, 209), (1, 251),
    (2, 41), (2, 83), (2, 125), (2, 167), (2, 209), (2, 251),
    (3, 41), (4, 41), (5, 41),
)

# МК-52 page-address permutations (the underscore-suffixed variant in JS,
# 14 entries — ИК1306 absent).
ПЕРЕСТАНОВКИ_АДРЕСОВ_СТРАНИЦ_ПАМЯТИ = (
    (1, 2, 3, 4, 5, 13, 12, 6, 7, 8, 9, 10, 11, 0),
    (3, 4, 5, 0, 1, 13, 12, 8, 9, 10, 11, 6, 7, 2),
    (5, 0, 1, 2, 3, 13, 12, 10, 11, 6, 7, 8, 9, 4),
)

ПРОГРАММНЫХ_ШАГОВ = 98  # МК-52 program memory size


def Адрес_команды(номер: int, перестановка: int) -> tuple[int, int]:
    """Return (chip_id, address-within-chip) for program step `номер`
    under permutation index 0..2 (= ИР2_1.микротакт // 84)."""
    целчасть, остаток = divmod(номер, 7)
    page_idx = ПЕРЕСТАНОВКИ_АДРЕСОВ_СТРАНИЦ_ПАМЯТИ[перестановка][целчасть]
    chip_id, base = АДРЕСА_СТРАНИЦ_ПАМЯТИ[page_idx]
    if остаток == 0:
        return chip_id, base
    return chip_id, base - 42 + остаток * 6


def разобрать_команду(команда: str) -> int:
    """Translate one source token into its opcode byte. Falls back to
    base-16 parse for raw numerics (e.g. jump addresses '54' → 0x54)."""
    for opcode, aliases, has_suffix in МНЕМОНИКИ_КОМАНД:
        if has_suffix:
            if команда[:-1] in aliases:
                return opcode + int(команда[-1], 16)
        else:
            if команда in aliases:
                return opcode
    return int(команда, 16)
