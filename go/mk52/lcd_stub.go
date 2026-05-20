//go:build !linux

package mk52

import (
	"strings"
)

// FormatDisplay formats the chip's (digits, points) into the 16-char string
// the LCD shows. Mirrors display_b.show: digit followed by ',' if the
// decimal-point indicator is set at that position; pad to 16 chars; HD44780
// has no Cyrillic, so Г (\u0413) → 'r', Е (\u0415) → 'E', С (\u0421) → 'C'.
func FormatDisplay(digits, points string) string {
	dRunes := []rune(digits)
	pRunes := []rune(points)
	var b strings.Builder
	for i := 0; i < 12 && i < len(dRunes); i++ {
		b.WriteRune(dRunes[i])
		if i < len(pRunes) && pRunes[i] != ' ' {
			b.WriteRune(pRunes[i])
		}
	}
	s := b.String()
	s = strings.ReplaceAll(s, "\u0413", "r")
	s = strings.ReplaceAll(s, "\u0415", "E")
	s = strings.ReplaceAll(s, "\u0421", "C")
	for len([]rune(s)) < 16 {
		s += " "
	}
	return s
}
