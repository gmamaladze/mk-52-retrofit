// Web-UI-only entry point. Equivalent to webui/server.py.
// On the Pi this is replaced by cmd/app, which drives both the keypad/LCD
// and the web UI from one process.
package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/gmamaladze/mk-52-retrofit/go/mk52"
)

func main() {
	host := flag.String("host", "127.0.0.1", "bind address (use 0.0.0.0 for LAN)")
	port := flag.Int("port", 8080, "HTTP port")
	flag.Parse()

	// Auto-detect repo paths relative to the binary's working directory.
	root, _ := os.Getwd()
	if _, err := os.Stat(filepath.Join(root, "webui/index.html")); err != nil {
		// Try the parent (running from go/ subdir).
		root = filepath.Dir(root)
	}
	webuiDir := filepath.Join(root, "webui")
	progDir := filepath.Join(root, "programs")

	m := mk52.NewМашина()
	srv := mk52.NewServer(m, progDir)
	m.Start()
	defer m.Stop()

	ctx, cancel := context.WithCancel(context.Background())
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
	}()

	if err := srv.Serve(ctx, *host, *port, webuiDir); err != nil {
		log.Fatalf("server: %v", err)
	}
}
