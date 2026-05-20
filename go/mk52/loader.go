// Source-code loader. Ports controller/emulator/loader.py.
// МК-52 mode (расширенный=false), so the 98-step program memory and the
// underscore-suffixed Перестановки_адресов_страниц_памяти_ variant are used.

package mk52

import (
	"fmt"
	"strconv"
)

// мнемоника is one row of the opcode table: opcode, list of source-string
// aliases that map to it, and whether the low nibble is a register index
// (e.g. "ИП5" → 0x60 + 5 = 0x65).
type мнемоника struct {
	opcode    byte
	aliases   []string
	hasSuffix bool
}

var МНЕМОНИКИ_КОМАНД = []мнемоника{
	{0x15, []string{"10^x", "10x", "F10^x", "F10x"}, false},
	{0x54, []string{"НОП", "KНОП", "КНОП"}, false},
	{0x16, []string{"e^x", "ex", "Fe^x", "Fex"}, false},
	{0x17, []string{"lg", "Flg"}, false},
	{0x18, []string{"ln", "Fln"}, false},
	{0x30, []string{"ЧМ", "KЧМ", "КЧМ"}, false},
	{0x19, []string{"arcsin", "Farcsin"}, false},
	{0x31, []string{"|x|", "K|x|", "К|x|"}, false},
	{0x1A, []string{"arccos", "Farccos"}, false},
	{0x32, []string{"ЗН", "KЗН", "КЗН"}, false},
	{0x1B, []string{"arctg", "Farctg"}, false},
	{0x33, []string{"ГМ", "KГМ", "КГМ"}, false},
	{0x1C, []string{"sin", "Fsin"}, false},
	{0x34, []string{"[x]", "K[x]", "К[x]"}, false},
	{0x1D, []string{"cos", "Fcos"}, false},
	{0x35, []string{"{x}", "(x)", "K{x}", "К{x}", "K(x)", "К(x)"}, false},
	{0x1E, []string{"tg", "Ftg"}, false},
	{0x36, []string{"max", "Kmax", "Кmax"}, false},
	{0x10, []string{"+"}, false},
	{0x11, []string{"-"}, false},
	{0x12, []string{"*", "x", "х", "×", "⋅"}, false},
	{0x13, []string{"/", ":", "÷"}, false},
	{0x20, []string{"пи", "π", "Fпи", "Fπ"}, false},
	{0x26, []string{"МГ", "KМГ", "КМГ"}, false},
	{0x21, []string{"КвКор", "квкор", "корень", "√", "FКвКор", "Fквкор", "Fкорень", "F√"}, false},
	{0x22, []string{"x^2", "x2", "x²", "Fx^2", "Fx2", "Fx²"}, false},
	{0x23, []string{"1/x", "F1/x"}, false},
	{0x14, []string{"<->", "XY", "↔", "X↔Y"}, false},
	{0x0E, []string{"^", "В^", "↑", "В↑"}, false},
	{0x24, []string{"x^y", "xy", "Fx^y", "Fxy"}, false},
	{0x27, []string{"K-", "К-"}, false},
	{0x28, []string{"Kx", "Кх", "K*", "К*"}, false},
	{0x29, []string{"K/", "К/", "K:", "К:", "K÷", "К÷"}, false},
	{0x2A, []string{"МЧ", "KМЧ", "КМЧ"}, false},
	{0x0F, []string{"Вx", "FВx"}, false},
	{0x3B, []string{"СЧ", "KСЧ", "КСЧ"}, false},
	{0x0A, []string{",", "."}, false},
	{0x0B, []string{"/-/", "+/-"}, false},
	{0x0C, []string{"ВП"}, false},
	{0x0D, []string{"Сx"}, false},
	{0x25, []string{"->", "↻", "→", "F->", "F↻", "F→"}, false},
	{0x37, []string{"/\\", "⋀", "K/\\", "К/\\", "K⋀", "К⋀"}, false},
	{0x38, []string{"\\/", "⋁", "K\\/", "К\\/", "K⋁", "К⋁"}, false},
	{0x39, []string{"(+)", "⊕", "K(+)", "К(+)", "K⊕", "К⊕"}, false},
	{0x3A, []string{"ИНВ", "KИНВ", "КИНВ"}, false},
	{0x52, []string{"В/О", "В/0"}, false},
	{0x50, []string{"С/П"}, false},
	{0x59, []string{"x>=0", "x≥0", "x⩾0", "Fx>=0", "Fx≥0", "Fx⩾0"}, false},
	{0x57, []string{"x#0", "x!=0", "x<>0", "x≠0", "Fx#0", "Fx!=0", "Fx<>0", "Fx≠0"}, false},
	{0x51, []string{"БП"}, false},
	{0x53, []string{"ПП"}, false},
	{0x58, []string{"L2", "FL2"}, false},
	{0x5A, []string{"L3", "FL3"}, false},
	{0x5C, []string{"x<0", "Fx<0"}, false},
	{0x5E, []string{"x=0", "Fx=0"}, false},
	{0x5D, []string{"L0", "FL0"}, false},
	{0x5B, []string{"L1", "FL1"}, false},
	{0x40, []string{"П", "XП"}, true},
	{0x60, []string{"ИП", "ПX", "Пx"}, true},
	{0x70, []string{"Kx#0", "Кx#0", "Kx!=0", "Кx!=0", "Kx<>0", "Кx<>0", "Kx≠0", "Кx≠0"}, true},
	{0x80, []string{"KБП", "КБП"}, true},
	{0x90, []string{"Kx>=0", "Кx>=0", "Kx≥0", "Кx≥0", "Kx⩾0", "Кx⩾0"}, true},
	{0xA0, []string{"KПП", "КПП"}, true},
	{0xB0, []string{"KП", "КП", "KXП", "КXП"}, true},
	{0xC0, []string{"Kx<0", "Кx<0"}, true},
	{0xD0, []string{"KИП", "КИП", "KПX", "КПX"}, true},
	{0xE0, []string{"Kx=0", "Кx=0"}, true},
}

// АДРЕСА_СТРАНИЦ_ПАМЯТИ: page addresses inside the chip M arrays.
// {chip_id, address} where chip_id 1=ИР2_1, 2=ИР2_2, 3=ИК1302, 4=ИК1303, 5=ИК1306.
var АДРЕСА_СТРАНИЦ_ПАМЯТИ = [15][2]int{
	{1, 41}, {1, 83}, {1, 125}, {1, 167}, {1, 209}, {1, 251},
	{2, 41}, {2, 83}, {2, 125}, {2, 167}, {2, 209}, {2, 251},
	{3, 41}, {4, 41}, {5, 41},
}

// ПЕРЕСТАНОВКИ_АДРЕСОВ_СТРАНИЦ_ПАМЯТИ: МК-52 mode (no ИК1306), 14 entries each.
var ПЕРЕСТАНОВКИ_АДРЕСОВ_СТРАНИЦ_ПАМЯТИ = [3][14]int{
	{1, 2, 3, 4, 5, 13, 12, 6, 7, 8, 9, 10, 11, 0},
	{3, 4, 5, 0, 1, 13, 12, 8, 9, 10, 11, 6, 7, 2},
	{5, 0, 1, 2, 3, 13, 12, 10, 11, 6, 7, 8, 9, 4},
}

const ПРОГРАММНЫХ_ШАГОВ = 98

// АдресКоманды returns (chip_id, address-within-chip) for program step `номер`
// under permutation index 0..2 (= ИР2_1.микротакт / 84).
func АдресКоманды(номер, перестановка int) (int, int) {
	целчасть := номер / 7
	остаток := номер % 7
	pageIdx := ПЕРЕСТАНОВКИ_АДРЕСОВ_СТРАНИЦ_ПАМЯТИ[перестановка][целчасть]
	chipID := АДРЕСА_СТРАНИЦ_ПАМЯТИ[pageIdx][0]
	base := АДРЕСА_СТРАНИЦ_ПАМЯТИ[pageIdx][1]
	if остаток == 0 {
		return chipID, base
	}
	return chipID, base - 42 + остаток*6
}

// РазобратьКоманду translates one source token into its opcode byte. Falls
// back to base-16 parse for raw numerics (e.g. jump address "54" → 0x54).
func РазобратьКоманду(команда string) (byte, error) {
	// hasSuffix matches need rune-level slicing because the body is Russian
	// ("ИП", "ПX") — multi-byte UTF-8.
	rs := []rune(команда)
	for _, m := range МНЕМОНИКИ_КОМАНД {
		if m.hasSuffix {
			if len(rs) == 0 {
				continue
			}
			body := string(rs[:len(rs)-1])
			suffix := string(rs[len(rs)-1:])
			for _, a := range m.aliases {
				if a == body {
					n, err := strconv.ParseInt(suffix, 16, 32)
					if err != nil {
						return 0, fmt.Errorf("bad register suffix in %q: %v", команда, err)
					}
					return m.opcode + byte(n), nil
				}
			}
		} else {
			for _, a := range m.aliases {
				if a == команда {
					return m.opcode, nil
				}
			}
		}
	}
	n, err := strconv.ParseInt(команда, 16, 32)
	if err != nil {
		return 0, fmt.Errorf("unknown token %q", команда)
	}
	return byte(n), nil
}
