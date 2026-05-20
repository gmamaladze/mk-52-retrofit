// Машина — MK-52 emulator orchestrator. Ported from controller/emulator/machine.py.
// Wires four chips (ИК1302, ИК1303, ИР2_1, ИР2_2) and drives them from a
// background goroutine at the same 30 ms tick rate as the JS original.

package mk52

import (
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const ПериодШага = 30 * time.Millisecond

// ИТЕРАЦИЙ_В_ШАГЕ — inner-loop iteration count. Original JS used 560 (calibrated
// so chip-time matches real-time). Override via MK52_ITERS_PER_SHAG.
var ИТЕРАЦИЙ_В_ШАГЕ = envInt("MK52_ITERS_PER_SHAG", 200)

// СимволыРазрядов maps display nibble (0-15) to displayed character.
var СимволыРазрядов = []string{
	"0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
	"-", "L", "С", "Г", "Е", " ",
}

// DisplayFn receives the formatted display state from the chip every Šaг
// when content changes.
type DisplayFn func(digits, points string, isDimmed bool)

// LogFn receives status strings (init/log).
type LogFn func(text string)

type Машина struct {
	OnDisplay DisplayFn
	OnLog     LogFn
	МераУгла  int // 10=radians, 11=degrees, 12=grads

	mu sync.Mutex

	ИК1302 *ИК13
	ИК1303 *ИК13
	ИР2_1  *ИР2
	ИР2_2  *ИР2

	Индикатор [13]uint8
	ИндикЗпт  [13]bool
	индикСт   [13]int

	stop chan struct{}
	done chan struct{}
}

func envInt(name string, def int) int {
	v := os.Getenv(name)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
}

func NewМашина() *Машина {
	m := &Машина{
		МераУгла: 10,
		ИК1302: &ИК13{
			ПЗУ_команд:         ПЗУ_ИК1302_команды,
			ПЗУ_синхропрограмм: ПЗУ_ИК1302_синхропрограммы,
			ПЗУ_микрокоманд:    ПЗУ_ИК1302_микрокоманды,
		},
		ИК1303: &ИК13{
			ПЗУ_команд:         ПЗУ_ИК1303_команды,
			ПЗУ_синхропрограмм: ПЗУ_ИК1303_синхропрограммы,
			ПЗУ_микрокоманд:    ПЗУ_ИК1303_микрокоманды,
		},
		ИР2_1: &ИР2{},
		ИР2_2: &ИР2{},
	}
	for i := range m.индикСт {
		m.индикСт[i] = -1
	}
	return m
}

// Шаг runs one chip step: ИТЕРАЦИЙ_В_ШАГЕ iterations × 42 microticks each,
// driving all four chips together. Hot path; ported from machine.py Шаг().
func (m *Машина) Шаг() {
	ИК1302 := m.ИК1302
	ИК1303 := m.ИК1303
	ИР2_1 := m.ИР2_1
	ИР2_2 := m.ИР2_2

	ИК1303.клав_y = 1
	ИК1303.клав_x = m.МераУгла

	// Pre-pull state into locals for hot loop.
	ИР2_1_мт := ИР2_1.микротакт
	ИР2_2_мт := ИР2_2.микротакт
	ИР2_2_выход := ИР2_2.выход

	for iter := 0; iter < ИТЕРАЦИЙ_В_ШАГЕ; iter++ {
		for inner := 0; inner < 42; inner++ {
			// Inlined ИК1302.Такт / ИК1303.Такт via their existing methods.
			ИК1302.вход = ИР2_2_выход
			ИК1302.Такт()
			ИК1303.вход = ИК1302.выход
			ИК1303.Такт()

			// Inlined ИР2_1.Такт: shift one slot in M[252].
			ИР2_1_вход := ИК1303.выход
			ИР2_1_выход := ИР2_1.M[ИР2_1_мт]
			ИР2_1.M[ИР2_1_мт] = ИР2_1_вход
			ИР2_1_мт++
			if ИР2_1_мт > 251 {
				ИР2_1_мт = 0
			}

			// Inlined ИР2_2.Такт.
			ИР2_2_выход = ИР2_2.M[ИР2_2_мт]
			ИР2_2.M[ИР2_2_мт] = ИР2_1_выход
			ИР2_2_мт++
			if ИР2_2_мт > 251 {
				ИР2_2_мт = 0
			}

			// ИК1302 feedback path: M[((микротакт >> 2) + 41) mod 42] ← ИР2_2.выход
			i := (ИК1302.микротакт >> 2) + 41
			if i >= 42 {
				i -= 42
			}
			ИК1302.M[i] = ИР2_2_выход
		}

		if ИК1302.обн_индик {
			R := &ИК1302.R
			зпт := &ИК1302.индик_зпт
			m.Индикатор[0] = R[24]
			m.Индикатор[1] = R[21]
			m.Индикатор[2] = R[18]
			m.Индикатор[3] = R[15]
			m.Индикатор[4] = R[12]
			m.Индикатор[5] = R[9]
			m.Индикатор[6] = R[6]
			m.Индикатор[7] = R[3]
			m.Индикатор[8] = R[0]
			m.Индикатор[9] = R[33]
			m.Индикатор[10] = R[30]
			m.Индикатор[11] = R[27]
			m.ИндикЗпт[0] = зпт[9]
			m.ИндикЗпт[1] = зпт[8]
			m.ИндикЗпт[2] = зпт[7]
			m.ИндикЗпт[3] = зпт[6]
			m.ИндикЗпт[4] = зпт[5]
			m.ИндикЗпт[5] = зпт[4]
			m.ИндикЗпт[6] = зпт[3]
			m.ИндикЗпт[7] = зпт[2]
			m.ИндикЗпт[8] = зпт[1]
			m.ИндикЗпт[9] = зпт[12]
			m.ИндикЗпт[10] = зпт[11]
			m.ИндикЗпт[11] = зпт[10]
			ИК1302.обн_индик = false
		}
	}

	// Flush ИР2 microtakt state back.
	ИР2_1.микротакт = ИР2_1_мт
	ИР2_2.микротакт = ИР2_2_мт
	ИР2_2.выход = ИР2_2_выход

	// Check whether the display changed; fire on_display if so.
	обновить := false
	for i := 0; i < 13; i++ {
		if m.индикСт[i] != int(m.Индикатор[i]) {
			обновить = true
		}
		m.индикСт[i] = int(m.Индикатор[i])
	}
	if обновить {
		m.ОтобразитьИндикатор()
	}
	ИК1302.клав_x = 0
	ИК1302.клав_y = 0
}

// ОтобразитьИндикатор formats the display state and invokes OnDisplay.
func (m *Машина) ОтобразитьИндикатор() {
	isDimmed := m.ИК1302.запятая != 11
	var digits, points strings.Builder
	for i := 0; i < 12; i++ {
		digits.WriteString(СимволыРазрядов[m.Индикатор[i]])
		if m.ИндикЗпт[i] {
			points.WriteByte(',')
		} else {
			points.WriteByte(' ')
		}
	}
	if m.OnDisplay != nil {
		m.OnDisplay(digits.String(), points.String(), isDimmed)
	}
}

// НажатиеКнопки presses key at (x, y), runs two Šaги (press + settle).
func (m *Машина) НажатиеКнопки(x, y int) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.ИК1302.клав_x = x
	m.ИК1302.клав_y = y
	m.Шаг()
	m.Шаг()
}

// ВвестиКод parses MK-52 source and writes opcodes directly into program
// memory. Returns the number of program steps written. Tokens are whitespace-
// separated; an optional "NN." line-number prefix is stripped.
func (m *Машина) ВвестиКод(source string) (int, error) {
	tokens := strings.Fields(source)
	cleaned := make([]string, 0, len(tokens))
	for _, t := range tokens {
		if len(t) >= 3 && t[2] == '.' &&
			((t[0] >= '0' && t[0] <= '9') || t[0] == 'A' || t[0] == '-') &&
			t[1] >= '0' && t[1] <= '9' {
			t = t[3:]
		}
		if t != "" {
			cleaned = append(cleaned, t)
		}
	}
	if len(cleaned) > ПРОГРАММНЫХ_ШАГОВ {
		cleaned = cleaned[:ПРОГРАММНЫХ_ШАГОВ]
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	перестановка := (m.ИР2_1.микротакт / 84) % 3
	chips := [5]interface {
		writeM(addr int, val uint8)
	}{nil, m.ИР2_1, m.ИР2_2, m.ИК1302, m.ИК1303}

	записать := func(номер int, код byte) {
		ст := uint8(код >> 4)
		мл := uint8(код & 0xf)
		chipID, адрес := АдресКоманды(номер, перестановка)
		chips[chipID].writeM(адрес, ст)
		chips[chipID].writeM(адрес-3, мл)
	}

	for i, tok := range cleaned {
		op, err := РазобратьКоманду(tok)
		if err != nil {
			return 0, err
		}
		записать(i, op)
	}
	for i := len(cleaned); i < ПРОГРАММНЫХ_ШАГОВ; i++ {
		записать(i, 0)
	}
	m.ИК1302.R[36] = 0
	m.ИК1302.R[39] = 0
	return len(cleaned), nil
}

// writeM helpers so ИР2 and ИК13 can be addressed uniformly from ВвестиКод.
func (chip *ИР2) writeM(addr int, val uint8)  { chip.M[addr] = val }
func (chip *ИК13) writeM(addr int, val uint8) { chip.M[addr] = val }

// Start spawns the background ticker goroutine. Stop() to halt.
func (m *Машина) Start() {
	if m.OnLog != nil {
		m.OnLog("Initializing...")
	}
	m.mu.Lock()
	m.Шаг() // prime so first display refresh fires
	m.mu.Unlock()
	m.stop = make(chan struct{})
	m.done = make(chan struct{})
	go m.цикл()
}

// Stop signals the ticker to exit and waits for it.
func (m *Машина) Stop() {
	if m.stop != nil {
		close(m.stop)
		<-m.done
		m.stop = nil
	}
}

func (m *Машина) цикл() {
	defer close(m.done)
	nextAt := time.Now()
	for {
		select {
		case <-m.stop:
			return
		default:
		}
		m.mu.Lock()
		m.Шаг()
		m.mu.Unlock()
		nextAt = nextAt.Add(ПериодШага)
		sleep := time.Until(nextAt)
		if sleep > 0 {
			select {
			case <-m.stop:
				return
			case <-time.After(sleep):
			}
		} else {
			nextAt = time.Now() // fell behind; resync
		}
	}
}
