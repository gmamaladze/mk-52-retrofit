//go:build linux

package main

import (
	"flag"
	"fmt"
	"log"
	"time"

	"github.com/gmamaladze/mk-52-retrofit/go/mk52"
)

func main() {
	i2cBus := flag.Int("i2c-bus", 1, "I²C bus number")
	i2cAddr := flag.Int("i2c-addr", 0x27, "I²C LCD address")
	line1 := flag.String("line1", "Booting...      ", "Text for line 1")
	line2 := flag.String("line2", "                ", "Text for line 2")
	flag.Parse()

	lcd, err := mk52.NewLCD(*i2cBus, *i2cAddr)
	if err != nil {
		log.Fatalf("LCD init failed: %v", err)
	}
	defer lcd.Close()

	lcd.Show(padRight(*line1, 16), 1)
	lcd.Show(padRight(*line2, 16), 2)
	
	// Small delay to ensure the last write is finished before closing the file
	time.Sleep(100 * time.Millisecond)
}

func padRight(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return s + fmt.Sprintf("%*s", n-len(s), "")
}
