// Keystroke-based program loader. Ports controller/emulator/keystroke_loader.py.
// Direct M-array writes via ВвестиКод don't survive the chip's shift-register
// data path; driving the chip through F+ПРГ → opcodes → F+АВТ does, because
// the chip's own microcode places opcodes at the right addresses.

package mk52

import (
	"fmt"
	"strings"
	"time"
)

// Key (x, y) by name — mirrors controller/keypad.py.
var keyXY = map[string][2]int{
	"0": {2, 1}, "1": {3, 1}, "2": {4, 1}, "3": {5, 1}, "4": {6, 1},
	"5": {7, 1}, "6": {8, 1}, "7": {9, 1}, "8": {10, 1}, "9": {11, 1},
	"+": {2, 8}, "-": {3, 8}, "*": {4, 8}, "/": {5, 8},
	"↔": {6, 8}, ".": {7, 8}, "/-/": {8, 8}, "ВП": {9, 8},
	"Сx": {10, 8}, "В↑": {11, 8},
	"С/П": {2, 9}, "БП": {3, 9}, "В/О": {4, 9}, "ПП": {5, 9},
	"X→П": {6, 9}, "→ШГ": {7, 9}, "П→X": {8, 9}, "←ШГ": {9, 9},
	"K": {10, 9}, "F": {11, 9},
}

var singleTokens = map[string]bool{
	"0": true, "1": true, "2": true, "3": true, "4": true,
	"5": true, "6": true, "7": true, "8": true, "9": true,
	"+": true, "-": true, "*": true, "/": true,
	"↔": true, ".": true, "/-/": true, "ВП": true,
	"Сx": true, "В↑": true,
	"С/П": true, "БП": true, "В/О": true, "ПП": true,
}

var fPrefix = map[string]string{
	"x^2": "*", "x²": "*", "x2": "*",
	"√": "-", "КвКор": "-", "корень": "-",
	"1/x": "/",
	"x^y": "↔", "xy": "↔",
	"π": "+", "пи": "+",
	"10^x": "0", "10x": "0",
	"e^x": "1", "ex": "1",
	"lg": "2", "ln": "3",
	"sin": "7", "cos": "8", "tg": "9",
	"arcsin": "4", "arccos": "5", "arctg": "6",
	"x=0":  "←ШГ",
	"x#0":  "С/П", "x≠0": "С/П", "x!=0": "С/П", "x<>0": "С/П",
	"x<0":  "→ШГ",
	"x>=0": "В/О", "x≥0": "В/О", "x⩾0": "В/О",
	"L0": "П→X", "L1": "X→П", "L2": "БП", "L3": "ПП",
	"Вx": "В↑", "Bx": "В↑",
}

var kPrefix = map[string]string{
	"[x]": "7",
	"{x}": "8", "(x)": "8",
	"max": "9",
	"|x|": "4",
	"ЗН":  "5",
	"СЧ":  "В↑",
	"НОП": "ВП", "КНОП": "ВП",
}

// aliases normalize loader.py's МНЕМОНИКИ_КОМАНД synonym set to a canonical
// token recognized above.
var aliases = map[string]string{
	"^": "В↑", "↑": "В↑", "В^": "В↑",
	"<->": "↔", "XY": "↔", "X↔Y": "↔",
	"x": "*", "х": "*", "×": "*", "⋅": "*",
	":": "/", "÷": "/",
	"+/-": "/-/",
	"В/0": "В/О",
	",":   ".",
	"FВx": "Вx", "FBx": "Вx",
	"Fx^2": "x^2", "Fx2": "x^2", "Fx²": "x^2",
	"F√":   "√", "FКвКор": "√", "Fквкор": "√", "Fкорень": "√",
	"F10^x": "10^x", "F10x": "10^x",
	"Fe^x":  "e^x", "Fex": "e^x",
	"Flg": "lg", "Fln": "ln",
	"Fsin": "sin", "Fcos": "cos", "Ftg": "tg",
	"Farcsin": "arcsin", "Farccos": "arccos", "Farctg": "arctg",
	"Fπ": "π", "Fпи": "π", "пи": "π",
	"F1/x": "1/x", "Fx^y": "x^y", "Fxy": "x^y",
	"FL0": "L0", "FL1": "L1", "FL2": "L2", "FL3": "L3",
	"Fx=0": "x=0", "Fx<0": "x<0",
	"Fx>=0": "x>=0", "Fx≥0": "x>=0", "Fx⩾0": "x>=0",
	"Fx#0":  "x#0", "Fx≠0": "x#0", "Fx!=0": "x#0", "Fx<>0": "x#0",
	"K|x|": "|x|", "К|x|": "|x|",
	"K[x]": "[x]", "К[x]": "[x]",
	"K{x}": "{x}", "К{x}": "{x}", "K(x)": "(x)", "К(x)": "(x)",
	"Kmax": "max", "Кmax": "max",
	"KЗН":  "ЗН", "КЗН": "ЗН",
	"KНОП": "НОП", "КНОП": "НОП",
	"KСЧ":  "СЧ", "КСЧ": "СЧ",
}

// TokenToKeys returns the keystroke sequence that types `tok` in program mode.
func TokenToKeys(tok string) ([]string, error) {
	if a, ok := aliases[tok]; ok {
		tok = a
	}
	if singleTokens[tok] {
		return []string{tok}, nil
	}
	if base, ok := fPrefix[tok]; ok {
		return []string{"F", base}, nil
	}
	if base, ok := kPrefix[tok]; ok {
		return []string{"K", base}, nil
	}

	// Register addressing: П<n>, ИП<n>, ПX<n>, Пx<n>
	rs := []rune(tok)
	if len(rs) == 3 {
		head := string(rs[:2])
		last := rs[2]
		if (head == "ИП" || head == "ПX" || head == "Пx") && last >= '0' && last <= '9' {
			return []string{"П→X", string(last)}, nil
		}
	}
	if len(rs) == 2 && rs[0] == 'П' && rs[1] >= '0' && rs[1] <= '9' {
		return []string{"X→П", string(rs[1])}, nil
	}

	// Two-digit address byte (chip auto-combines two digits into one BCD).
	if len(tok) == 2 && tok[0] >= '0' && tok[0] <= '9' && tok[1] >= '0' && tok[1] <= '9' {
		return []string{string(tok[0]), string(tok[1])}, nil
	}

	return nil, fmt.Errorf("unknown program token: %q", tok)
}

func splitSource(source string) []string {
	tokens := strings.Fields(source)
	cleaned := make([]string, 0, len(tokens))
	for _, t := range tokens {
		// Strip optional "NN." / "AN." line-number prefix.
		if len(t) >= 3 && t[2] == '.' &&
			((t[0] >= '0' && t[0] <= '9') || t[0] == 'A' || t[0] == '-') &&
			t[1] >= '0' && t[1] <= '9' {
			t = t[3:]
		}
		if t != "" {
			cleaned = append(cleaned, t)
		}
	}
	return cleaned
}

// EnterProgram types `source` into program memory via the keypad.
// Sequence: Сx → F+АВТ → В/О → F+ПРГ → opcodes → F+АВТ → В/О.
// keySettle is the delay between keypresses (defaults to 180ms if zero).
func (m *Машина) EnterProgram(source string, keySettle time.Duration) (int, error) {
	if keySettle == 0 {
		keySettle = 180 * time.Millisecond
	}
	tokens := splitSource(source)

	sequence := []string{"Сx", "F", "/-/", "В/О", "F", "ВП"} // → prog mode at step 0
	for _, tok := range tokens {
		keys, err := TokenToKeys(tok)
		if err != nil {
			return 0, err
		}
		sequence = append(sequence, keys...)
	}
	sequence = append(sequence, "F", "/-/", "В/О") // exit prog mode, reset PC

	for _, k := range sequence {
		xy, ok := keyXY[k]
		if !ok {
			return 0, fmt.Errorf("internal: no key xy for %q", k)
		}
		m.НажатиеКнопки(xy[0], xy[1])
		time.Sleep(keySettle)
	}
	return len(tokens), nil
}
