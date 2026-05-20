//go:build linux

// GPIO keypad matrix scanner. Direct port of controller/keypad.py using
// the /dev/gpiochip* chardev interface (works on Pi 5 and under PyPy-style
// non-mem-mapped setups).

package mk52

import (
	"fmt"
	"time"

	"github.com/warthog618/go-gpiocdev"
)

// Key event yielded by Keypad.Run.
type KeyEvent struct {
	X, Y int
	Txt  string
}

// Keypad matrix layout, mirrors keypad.py ROW_COLUMN_TO_KEY.
var rowColumnToKey = [4][10]string{
	{"", "A↑", "↑↓", "", "", "", "", "", "", ""},
	{"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"},
	{"+", "-", "×", "÷", "↔", ".", "/-/", "ВП", "Сx", "В↑"},
	{"С/П", "БП", "В/О", "ПП", "X→П", "→ШГ", "П→X", "←ШГ", "K", "F"},
}

var columnToX = [10]int{2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
var rowToY = [4]int{0, 1, 8, 9}

// Keypad scans a 4×10 button matrix. Constructor parameters mirror the
// Python class — 14 board-numbered GPIO pins (pins 1..14 in the original
// signature: 4 rows + 10 columns), reshuffled internally as keypad.py did.
type Keypad struct {
	chip       *gpiocdev.Chip
	rowLines   []*gpiocdev.Line
	colLines   []*gpiocdev.Line
	scanPeriod time.Duration
}

// NewKeypad wires up the keypad on the given gpiochip device.
//
// The pin ordering matches controller/keypad.py:
//
//	Keypad(_1, _2, _3, _4, _5, _6, _7, _8, _9, _10, _11, _12, _13, _14)
//	  column_channels = [_4, _6, _5, _11, _9, _8, _7, _3, _2, _10]
//	  row_channels    = [_1, _12, _13, _14]
//
// Pass the same 14 pins (in BOARD numbering on a 40-pin header — same as
// the Python call). pins is converted to BCM/chardev offsets via boardToBCM.
func NewKeypad(chipPath string, boardPins [14]int) (*Keypad, error) {
	chip, err := gpiocdev.NewChip(chipPath, gpiocdev.WithConsumer("mk-52"))
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", chipPath, err)
	}

	colBoard := [10]int{boardPins[3], boardPins[5], boardPins[4], boardPins[10],
		boardPins[8], boardPins[7], boardPins[6], boardPins[2], boardPins[1], boardPins[9]}
	rowBoard := [4]int{boardPins[0], boardPins[11], boardPins[12], boardPins[13]}

	rowLines := make([]*gpiocdev.Line, 4)
	colLines := make([]*gpiocdev.Line, 10)

	for i, pin := range rowBoard {
		bcm, ok := boardToBCM[pin]
		if !ok {
			chip.Close()
			return nil, fmt.Errorf("unknown board pin %d", pin)
		}
		l, err := chip.RequestLine(bcm, gpiocdev.AsInput, gpiocdev.WithPullDown)
		if err != nil {
			chip.Close()
			return nil, fmt.Errorf("request row pin %d (BCM %d) as input: %w", pin, bcm, err)
		}
		rowLines[i] = l
	}
	for i, pin := range colBoard {
		bcm, ok := boardToBCM[pin]
		if !ok {
			chip.Close()
			return nil, fmt.Errorf("unknown board pin %d", pin)
		}
		l, err := chip.RequestLine(bcm, gpiocdev.AsOutput(1))
		if err != nil {
			chip.Close()
			return nil, fmt.Errorf("request col pin %d (BCM %d) as output: %w", pin, bcm, err)
		}
		colLines[i] = l
	}

	return &Keypad{
		chip:       chip,
		rowLines:   rowLines,
		colLines:   colLines,
		scanPeriod: 100 * time.Microsecond,
	}, nil
}

// Close releases all GPIO lines and the chip.
func (k *Keypad) Close() error {
	for _, l := range k.rowLines {
		if l != nil {
			_ = l.Close()
		}
	}
	for _, l := range k.colLines {
		if l != nil {
			_ = l.Close()
		}
	}
	return k.chip.Close()
}

// Run scans the matrix and emits KeyEvent values on the returned channel.
// Stops when stop is closed. Mirrors keypad.get_key_presses.
func (k *Keypad) Run(stop <-chan struct{}) <-chan KeyEvent {
	out := make(chan KeyEvent, 4)
	go func() {
		defer close(out)
		for {
			select {
			case <-stop:
				return
			default:
			}

			// Drive all columns high and look for any row going high.
			for _, l := range k.colLines {
				_ = l.SetValue(1)
			}
			time.Sleep(k.scanPeriod)

			rowIdx := -1
			for i, l := range k.rowLines {
				v, err := l.Value()
				if err == nil && v == 1 {
					rowIdx = i
					break
				}
			}
			if rowIdx < 0 {
				time.Sleep(k.scanPeriod * 10)
				continue
			}

			// Drive each column low one at a time; whichever column makes
			// the row go low identifies the pressed button.
			colIdx := -1
			for i, l := range k.colLines {
				_ = l.SetValue(0)
				time.Sleep(k.scanPeriod)
				v, err := k.rowLines[rowIdx].Value()
				_ = l.SetValue(1)
				if err == nil && v == 0 {
					colIdx = i
					break
				}
			}
			if colIdx < 0 {
				continue
			}

			ev := KeyEvent{
				X:   columnToX[colIdx],
				Y:   rowToY[rowIdx],
				Txt: rowColumnToKey[rowIdx][colIdx],
			}
			select {
			case out <- ev:
			case <-stop:
				return
			}

			// Debounce: wait until the row goes low again.
			for {
				v, _ := k.rowLines[rowIdx].Value()
				if v == 0 {
					break
				}
				time.Sleep(5 * time.Millisecond)
			}
		}
	}()
	return out
}

// boardToBCM maps Raspberry Pi 40-pin header BOARD numbering to BCM GPIO
// numbering — only the pins that can be GPIOs are listed.
var boardToBCM = map[int]int{
	3: 2, 5: 3, 7: 4, 8: 14, 10: 15, 11: 17, 12: 18, 13: 27, 15: 22, 16: 23,
	18: 24, 19: 10, 21: 9, 22: 25, 23: 11, 24: 8, 26: 7, 27: 0, 28: 1,
	29: 5, 31: 6, 32: 12, 33: 13, 35: 19, 36: 16, 37: 26, 38: 20, 40: 21,
}

