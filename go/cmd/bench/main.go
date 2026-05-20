// Tiny benchmark binary to measure Šaг wall time on the host that runs it.
// Mirrors the Python tools/benchmark.py output format so we can directly
// compare CPython vs Go on the same Pi.
package main

import (
	"fmt"
	"time"

	"github.com/gmamaladze/mk-52-retrofit/go/mk52"
)

const (
	OriginalIterPerShag = 560
	TickMS              = 30
)

func main() {
	m := mk52.NewМашина()
	// Warmup
	for i := 0; i < 50; i++ {
		m.Шаг()
	}

	const N = 200
	t0 := time.Now()
	for i := 0; i < N; i++ {
		m.Шаг()
	}
	perShag := time.Since(t0) / N
	perShagMs := float64(perShag) / float64(time.Millisecond)

	wall := perShagMs
	if wall < TickMS {
		wall = TickMS
	}
	effectiveIPS := float64(mk52.ИТЕРАЦИЙ_В_ШАГЕ) * 1000.0 / wall
	originalIPS := float64(OriginalIterPerShag) * 1000.0 / TickMS
	pct := 100.0 * effectiveIPS / originalIPS

	fmt.Printf("Runtime: Go\n")
	fmt.Printf("ИТЕРАЦИЙ_В_ШАГЕ = %d  (original МК-52 = %d)\n\n",
		mk52.ИТЕРАЦИЙ_В_ШАГЕ, OriginalIterPerShag)
	fmt.Printf("  Šaг wall time:       %6.3f ms\n", perShagMs)
	fmt.Printf("  Effective iter/sec:  %9.0f\n", effectiveIPS)
	fmt.Printf("  Original МК-52:      %9.0f\n", originalIPS)
	fmt.Printf("  Speed vs original:   %6.1f%%\n", pct)

	iterPerMs := float64(mk52.ИТЕРАЦИЙ_В_ШАГЕ) / perShagMs
	maxForTick := int(iterPerMs * TickMS)
	fmt.Printf("\n  Max ИТЕРАЦИЙ_В_ШАГЕ that fits in %d ms: ~%d\n", TickMS, maxForTick)
	if maxForTick >= OriginalIterPerShag {
		fmt.Printf("  → Set ИТЕРАЦИЙ_В_ШАГЕ = %d for full original speed.\n", OriginalIterPerShag)
	} else {
		fmt.Printf("  → Original-speed (%d) not reachable; chip will run at %.0f%% of original.\n",
			OriginalIterPerShag, 100.0*float64(maxForTick)/OriginalIterPerShag)
	}
}
