//go:build linux

// I²C HD44780 16×N display via a PCF8574 backpack — direct port of
// controller/driver/lcd_i2c_driver.py + display_b.py logic.

package mk52

import (
	"fmt"
	"os"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	i2cSlave = 0x0703 // Linux I²C ioctl: SLAVE address

	lcdClearDisplay   = 0x01
	lcdReturnHome     = 0x02
	lcdEntryModeSet   = 0x04
	lcdDisplayControl = 0x08
	lcdFunctionSet    = 0x20
	lcdSetCgramAddr   = 0x40
	lcdSetDdramAddr   = 0x80

	lcdEntryLeft = 0x02
	lcdDisplayOn = 0x04
	lcd4BitMode  = 0x00
	lcd2Line     = 0x08
	lcd5x8Dots   = 0x00
	lcdBacklight = 0x08
	lcdEnable    = 0x04 // En bit (PCF8574 P2)
	lcdRegSelect = 0x01 // Rs bit (PCF8574 P0)
)

// LCD drives a 16×N HD44780 via a PCF8574 I²C backpack at address `addr`
// (typically 0x27) on /dev/i2c-<bus> (typically bus 1).
type LCD struct {
	f  *os.File
	mu sync.Mutex

	// cgram maps rune (e.g. '0', 'r') to CGRAM slot (0-7).
	cgram     [8]rune
	cgramNext int
}

// NewLCD opens /dev/i2c-<bus>, claims the slave at addr, and initializes
// the HD44780 in 4-bit, 2-line mode with the backlight on.
func NewLCD(bus, addr int) (*LCD, error) {
	path := fmt.Sprintf("/dev/i2c-%d", bus)
	f, err := os.OpenFile(path, os.O_RDWR, 0)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", path, err)
	}
	if errno := ioctl(f.Fd(), i2cSlave, uintptr(addr)); errno != 0 {
		_ = f.Close()
		return nil, fmt.Errorf("ioctl I2C_SLAVE %#x: %v", addr, errno)
	}
	lcd := &LCD{f: f}
	for i := range lcd.cgram {
		lcd.cgram[i] = -1
	}

	// Wait for LCD to power up.
	time.Sleep(100 * time.Millisecond)

	// HD44780 init dance: MUST be sent in the HIGH nibble (DB4-DB7).
	// 0x30 = 8-bit mode.
	lcd.write4(0x30)
	time.Sleep(5 * time.Millisecond)
	lcd.write4(0x30)
	time.Sleep(5 * time.Millisecond)
	lcd.write4(0x30)
	time.Sleep(5 * time.Millisecond)
	// 0x20 = switch to 4-bit mode.
	lcd.write4(0x20)
	time.Sleep(5 * time.Millisecond)

	lcd.write(lcdFunctionSet|lcd2Line|lcd5x8Dots|lcd4BitMode, 0)
	lcd.write(lcdDisplayControl|lcdDisplayOn, 0)
	lcd.write(lcdClearDisplay, 0)
	lcd.write(lcdEntryModeSet|lcdEntryLeft, 0)
	time.Sleep(200 * time.Millisecond)
	return lcd, nil
}

// Close closes the I²C file descriptor.
func (l *LCD) Close() error { return l.f.Close() }

func ioctl(fd, req, arg uintptr) syscall.Errno {
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, fd, req, arg)
	return errno
}

func (l *LCD) writeByte(b byte) {
	_, _ = l.f.Write([]byte{b})
}

func (l *LCD) strobe(data byte) {
	l.writeByte(data | lcdEnable | lcdBacklight)
	time.Sleep(500 * time.Microsecond)
	l.writeByte((data & ^byte(lcdEnable)) | lcdBacklight)
	time.Sleep(100 * time.Microsecond)
}

func (l *LCD) write4(data byte) {
	l.writeByte(data | lcdBacklight)
	l.strobe(data)
}

func (l *LCD) write(cmd, mode byte) {
	l.write4(mode | (cmd & 0xF0))
	l.write4(mode | ((cmd << 4) & 0xF0))
}

func (l *LCD) CreateChar(slot int, mask [8]byte) {
	l.write(lcdSetCgramAddr|byte(slot<<3), 0)
	for i := 0; i < 8; i++ {
		l.write(mask[i], lcdRegSelect)
	}
	l.write(lcdSetDdramAddr, 0)
}

// Show writes `text` to 1-based `line` (line 1 = top, line 2 = bottom on 16×2).
func (l *LCD) Show(text string, line int) {
	l.mu.Lock()
	defer l.mu.Unlock()

	// 1. Identify which characters in `text` need custom glyphs.
	present := make(map[rune]bool)
	for _, r := range text {
		if _, ok := Font7Seg[r]; ok {
			present[r] = true
		}
	}

	// 2. Ensure all needed custom glyphs are in CGRAM.
	for r := range present {
		found := -1
		for slot, val := range l.cgram {
			if val == r {
				found = slot
				break
			}
		}
		if found == -1 {
			// Evict and load.
			slot := l.cgramNext
			l.cgram[slot] = r
			l.CreateChar(slot, Font7Seg[r])
			l.cgramNext = (l.cgramNext + 1) % 8
		}
	}

	// 3. Render.
	switch line {
	case 1:
		l.write(0x80, 0)
	case 2:
		l.write(0xC0, 0)
	case 3:
		l.write(0x94, 0)
	case 4:
		l.write(0xD4, 0)
	}
	for _, r := range text {
		b := byte('?')
		if _, ok := Font7Seg[r]; ok {
			for slot, val := range l.cgram {
				if val == r {
					b = byte(slot)
					break
				}
			}
			// Fallback to standard ROM character if not in CGRAM (avoids '?' when >8 distinct custom chars)
			if b == '?' && r < 0x100 {
				b = byte(r)
			}
		} else if r < 0x100 {
			b = byte(r)
		}
		l.write(b, lcdRegSelect)
	}
}

// Clear blanks the display and homes the cursor.
func (l *LCD) Clear() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.write(lcdClearDisplay, 0)
	l.write(lcdReturnHome, 0)
}

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
