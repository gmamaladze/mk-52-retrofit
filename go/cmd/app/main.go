//go:build linux

// Combined Pi entrypoint — equivalent to controller/app.py:
//   - Драйвит chip simulator via Машина
//   - Reads keypad events from GPIO
//   - Writes display state to physical LCD (async, frame-dropping)
//   - Serves the same HTTP API the desktop browser uses
//
// All four share ONE Машина instance, so the LCD and browser see the same
// chip state.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/gmamaladze/mk-52-retrofit/go/mk52"
)

func main() {
	host := flag.String("host", "0.0.0.0", "HTTP bind address")
	port := flag.Int("port", 8080, "HTTP port")
	gpioChip := flag.String("gpiochip", "/dev/gpiochip0", "GPIO chip device")
	i2cBus := flag.Int("i2c-bus", 1, "I²C bus number")
	i2cAddr := flag.Int("i2c-addr", 0x27, "I²C LCD address")
	noLCD := flag.Bool("no-lcd", false, "skip LCD init (useful if not wired)")
	noKeypad := flag.Bool("no-keypad", false, "skip keypad init (useful if not wired)")
	flag.Parse()

	root, _ := os.Getwd()
	if _, err := os.Stat(filepath.Join(root, "webui/index.html")); err != nil {
		root = filepath.Dir(root) // running from go/
	}
	webuiDir := filepath.Join(root, "webui")
	progDir := filepath.Join(root, "programs")

	m := mk52.NewМашина()

	// LCD (optional — bring up only if requested and wired).
	var lcd *mk52.LCD
	if !*noLCD {
		var err error
		lcd, err = mk52.NewLCD(*i2cBus, *i2cAddr)
		if err != nil {
			log.Printf("LCD init failed (continuing without): %v", err)
		} else {
			defer lcd.Close()
			lcd.Show("George's MK 52  ", 1)
		}
	}

	// Async LCD writer — drop stale frames so the chip thread never blocks
	// on the slow I²C write.
	type lcdFrame struct{ digits, points string }
	lcdCh := make(chan lcdFrame, 1)
	if lcd != nil {
		go func() {
			for f := range lcdCh {
				lcd.Show(mk52.FormatDisplay(f.digits, f.points), 1)
			}
		}()
	}

	m.OnDisplay = func(digits, points string, isDimmed bool) {
		if lcd == nil {
			return
		}
		// Drop any pending stale frame, then queue the new one.
		select {
		case <-lcdCh:
		default:
		}
		select {
		case lcdCh <- lcdFrame{digits, points}:
		default:
		}
	}

	srv := mk52.NewServer(m, progDir)
	m.Start()
	defer m.Stop()

	// Keypad (optional).
	stopKbd := make(chan struct{})
	if !*noKeypad {
		var pins [14]int
		// Pin numbers from controller/app.py — these match the original wiring.
		copy(pins[:], []int{24, 23, 22, 21, 19, 18, 16, 15, 13, 12, 11, 10, 8, 7})
		kbd, err := mk52.NewKeypad(*gpioChip, pins)
		if err != nil {
			log.Printf("keypad init failed (continuing without): %v", err)
		} else {
			defer kbd.Close()
			go keypadLoop(m, srv, kbd.Run(stopKbd), lcd, progDir)
		}
	}

	ctx, cancel := context.WithCancel(context.Background())
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		close(stopKbd)
		cancel()
	}()

	if err := srv.Serve(ctx, *host, *port, webuiDir); err != nil {
		log.Fatalf("server: %v", err)
	}
}

// keypadLoop reads keypad events, intercepts A↑ for ROM-load, and forwards
// everything else to НажатиеКнопки. Mirrors controller/app.py:main.
func keypadLoop(m *mk52.Машина, srv *mk52.Server, events <-chan mk52.KeyEvent,
	lcd *mk52.LCD, progDir string) {
	var digitBuffer string
	for ev := range events {
		// A↑ — load from ROM. Maps to row 0 col 1 = (3, 0).
		if ev.X == 3 && ev.Y == 0 {
			loadFromROM(m, lcd, progDir, digitBuffer)
			digitBuffer = ""
			continue
		}
		if ev.Y == 1 && ev.X >= 2 && ev.X <= 11 {
			digitBuffer += string(rune('0' + (ev.X - 2)))
			if len(digitBuffer) > 2 {
				digitBuffer = digitBuffer[len(digitBuffer)-2:]
			}
		} else {
			digitBuffer = ""
		}
		m.НажатиеКнопки(ev.X, ev.Y)
		time.Sleep(100 * time.Millisecond)
	}
}

func loadFromROM(m *mk52.Машина, lcd *mk52.LCD, progDir, digits string) {
	if digits == "" {
		if lcd != nil {
			lcd.Show("ENTER NUMBER    ", 1)
			time.Sleep(time.Second)
		}
		return
	}
	var n int
	if _, err := fmt.Sscanf(digits, "%d", &n); err != nil {
		return
	}
	pattern := filepath.Join(progDir, fmt.Sprintf("%02d-*.yaml", n))
	matches, _ := filepath.Glob(pattern)
	if len(matches) == 0 {
		if lcd != nil {
			lcd.Show(fmt.Sprintf("NO PROG %02d      ", n), 1)
			time.Sleep(1500 * time.Millisecond)
		}
		return
	}
	prog, err := mk52.ReadProgramFile(matches[0])
	if err != nil {
		log.Printf("rom load: %v", err)
		return
	}
	title := prog.Title
	if len(title) > 9 {
		title = title[:9]
	}
	if lcd != nil {
		lcd.Show(fmt.Sprintf("LOAD %02d %s", n, padRight(title, 9)), 1)
		time.Sleep(400 * time.Millisecond)
	}
	// Pause LCD broadcast during keystroke entry so flicker doesn't overwrite.
	saved := m.OnDisplay
	m.OnDisplay = nil
	steps, err := m.EnterProgram(prog.Code, 0)
	m.OnDisplay = saved
	if err != nil {
		log.Printf("rom enter: %v", err)
		return
	}
	if lcd != nil {
		lcd.Show(fmt.Sprintf("OK %02d STEPS     ", steps), 1)
		time.Sleep(1200 * time.Millisecond)
	}
}

func padRight(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return s + strings.Repeat(" ", n-len(s))
}
