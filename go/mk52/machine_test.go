package mk52

import (
	"strings"
	"testing"
	"time"
)

// newPrimedMachine builds a Машина and pumps a few Šaги to get the chip
// past initialization so subsequent Šaги are representative.
func newPrimedMachine(t testing.TB) *Машина {
	m := NewМашина()
	for i := 0; i < 5; i++ {
		m.Шаг()
	}
	return m
}

// parseInt assumes a halted display showing an integer value (no exponent).
// Mirrors the Python tests/api.py parse_display, simplified to integers.
func parseInt(digits, points string) (int, bool) {
	// Trim leading sign char (positions 0..0 is space or '-').
	sign := 1
	if strings.HasPrefix(digits, "-") {
		sign = -1
	}
	// Pull digit chars from positions 1-7 (ignore exponent for these tests).
	var n int
	any := false
	for i := 1; i < 8 && i < len(digits); i++ {
		c := digits[i]
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
			any = true
		}
	}
	if !any {
		return 0, false
	}
	return sign * n, true
}

// pressAndSettle simulates a button press, waits for the display to update,
// and returns the latest digits/points.
func pressAndSettle(t *testing.T, m *Машина, x, y int) (digits, points string) {
	m.НажатиеКнопки(x, y)
	// Run a few more Šaги to let display flush.
	for i := 0; i < 2; i++ {
		m.Шаг()
	}
	digits, points, _ = displayState(m)
	return
}

func displayState(m *Машина) (digits, points string, dimmed bool) {
	dimmed = m.ИК1302.запятая != 11
	var d, p strings.Builder
	for i := 0; i < 12; i++ {
		d.WriteString(СимволыРазрядов[m.Индикатор[i]])
		if m.ИндикЗпт[i] {
			p.WriteByte(',')
		} else {
			p.WriteByte(' ')
		}
	}
	return d.String(), p.String(), dimmed
}

// TestLive_OnePlusOne exercises the chip via simulated keypresses.
// 1 В↑ 1 + → 2 on the display.
func TestLive_OnePlusOne(t *testing.T) {
	m := newPrimedMachine(t)
	m.НажатиеКнопки(10, 8) // Сx
	m.НажатиеКнопки(3, 1)  // 1
	m.НажатиеКнопки(11, 8) // В↑
	m.НажатиеКнопки(3, 1)  // 1
	digits, _ := pressAndSettle(t, m, 2, 8) // +
	n, ok := parseInt(digits, "")
	if !ok || n != 2 {
		t.Fatalf("1+1: digits=%q, parsed=%d ok=%v (want 2)", digits, n, ok)
	}
}

func TestLive_SqrtTwentyFive(t *testing.T) {
	m := newPrimedMachine(t)
	m.НажатиеКнопки(10, 8) // Сx
	m.НажатиеКнопки(4, 1)  // 2
	m.НажатиеКнопки(7, 1)  // 5
	m.НажатиеКнопки(11, 9) // F
	digits, _ := pressAndSettle(t, m, 3, 8) // F-stick + - = √
	n, ok := parseInt(digits, "")
	if !ok || n != 5 {
		t.Fatalf("√25: digits=%q, parsed=%d ok=%v (want 5)", digits, n, ok)
	}
}

// BenchmarkШаг — wall time per Šaг. Compare against CPython 27ms (Mac M-series)
// or 1270ms (Pi Zero).
func BenchmarkШаг(b *testing.B) {
	m := newPrimedMachine(b)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		m.Шаг()
	}
}

// BenchmarkШаг_RealTime — how much wall time 100 Šaги take (for comparison
// against the Python tools/benchmark.py output format).
func BenchmarkШаг_RealTime(b *testing.B) {
	m := newPrimedMachine(b)
	for n := 0; n < b.N; n++ {
		t0 := time.Now()
		for i := 0; i < 100; i++ {
			m.Шаг()
		}
		_ = time.Since(t0)
	}
}
