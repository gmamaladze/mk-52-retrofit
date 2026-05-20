// HTTP server providing the same endpoints as webui/server.py.
// Drives a single Машина instance and fans display refreshes out via SSE.

package mk52

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

// Frame is one display state — fields named to match the Python JSON shape.
type Frame struct {
	Digits   string `json:"digits"`
	Points   string `json:"points"`
	IsDimmed bool   `json:"is_dimmed"`
}

// ProgramInfo is one entry in /programs (mirrors the Python YAML schema).
type ProgramInfo struct {
	ID           string `json:"id"           yaml:"id"`
	Title        string `json:"title"        yaml:"title"`
	Description  string `json:"description"  yaml:"description"`
	Author       string `json:"author"       yaml:"author"`
	Instructions string `json:"instructions" yaml:"instructions"`
	Code         string `json:"code"         yaml:"code"`
}

// Server bundles a Машина, its display fan-out, and the HTTP endpoints.
type Server struct {
	M          *Машина
	ProgramDir string

	mu          sync.RWMutex
	lastFrame   Frame
	subscribers map[chan Frame]struct{}

	// digit buffer for A↑ ("load from ROM") — last 2 digit keys pressed.
	dbMu        sync.Mutex
	digitBuffer string
}

// NewServer wires a Машина into a Server. It replaces m.OnDisplay so that
// every chip refresh is broadcast to all SSE subscribers.
func NewServer(m *Машина, programDir string) *Server {
	s := &Server{
		M:           m,
		ProgramDir:  programDir,
		subscribers: make(map[chan Frame]struct{}),
		lastFrame:   Frame{Digits: "            ", Points: "            "},
	}
	// Chain our broadcast in front of any pre-existing OnDisplay.
	prev := m.OnDisplay
	m.OnDisplay = func(digits, points string, isDimmed bool) {
		if prev != nil {
			prev(digits, points, isDimmed)
		}
		s.broadcast(Frame{Digits: digits, Points: points, IsDimmed: isDimmed})
	}
	return s
}

func (s *Server) broadcast(f Frame) {
	s.mu.Lock()
	s.lastFrame = f
	for ch := range s.subscribers {
		select {
		case ch <- f:
		default: // drop frame if subscriber is behind
		}
	}
	s.mu.Unlock()
}

func (s *Server) subscribe() chan Frame {
	ch := make(chan Frame, 16)
	s.mu.Lock()
	s.subscribers[ch] = struct{}{}
	s.mu.Unlock()
	return ch
}

func (s *Server) unsubscribe(ch chan Frame) {
	s.mu.Lock()
	delete(s.subscribers, ch)
	s.mu.Unlock()
	close(ch)
}

// Handler returns an http.Handler with all the routes wired up.
func (s *Server) Handler(webuiDir string) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		http.ServeFile(w, r, filepath.Join(webuiDir, "index.html"))
	})

	mux.HandleFunc("/display", func(w http.ResponseWriter, r *http.Request) {
		s.mu.RLock()
		f := s.lastFrame
		s.mu.RUnlock()
		writeJSON(w, http.StatusOK, f)
	})

	mux.HandleFunc("/programs", func(w http.ResponseWriter, r *http.Request) {
		programs, err := s.loadPrograms()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, programs)
	})

	mux.HandleFunc("/events", s.handleEvents)
	mux.HandleFunc("/press", s.handlePress)
	mux.HandleFunc("/load", s.handleLoad)

	return mux
}

func (s *Server) handleEvents(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	ch := s.subscribe()
	defer s.unsubscribe(ch)

	// Send current frame immediately so fresh page isn't blank.
	s.mu.RLock()
	first := s.lastFrame
	s.mu.RUnlock()
	if err := writeSSE(w, flusher, first); err != nil {
		return
	}

	for {
		select {
		case f, ok := <-ch:
			if !ok {
				return
			}
			if err := writeSSE(w, flusher, f); err != nil {
				return
			}
		case <-r.Context().Done():
			return
		}
	}
}

func writeSSE(w http.ResponseWriter, flusher http.Flusher, f Frame) error {
	b, err := json.Marshal(f)
	if err != nil {
		return err
	}
	if _, err := fmt.Fprintf(w, "data: %s\n\n", b); err != nil {
		return err
	}
	flusher.Flush()
	return nil
}

type pressReq struct {
	X int `json:"x"`
	Y int `json:"y"`
}

func (s *Server) handlePress(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var p pressReq
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		http.Error(w, "expected JSON {x, y}", http.StatusBadRequest)
		return
	}

	// A↑ (3, 0) — load from "ROM" using the buffered digits.
	if p.X == 3 && p.Y == 0 {
		writeJSON(w, http.StatusOK, s.loadFromRom())
		return
	}

	s.dbMu.Lock()
	if p.Y == 1 && p.X >= 2 && p.X <= 11 {
		s.digitBuffer += string(rune('0' + (p.X - 2)))
		if len(s.digitBuffer) > 2 {
			s.digitBuffer = s.digitBuffer[len(s.digitBuffer)-2:]
		}
	} else {
		s.digitBuffer = ""
	}
	s.dbMu.Unlock()

	s.M.НажатиеКнопки(p.X, p.Y)
	w.WriteHeader(http.StatusNoContent)
}

type loadReq struct {
	Code string `json:"code"`
}

func (s *Server) handleLoad(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var p loadReq
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		http.Error(w, "expected JSON {code}", http.StatusBadRequest)
		return
	}
	steps, err := s.M.EnterProgram(p.Code, 0)
	if err != nil {
		http.Error(w, fmt.Sprintf("load failed: %v", err), http.StatusBadRequest)
		return
	}
	writeJSON(w, http.StatusOK, map[string]int{"steps": steps})
}

type romResponse struct {
	OK      bool   `json:"ok"`
	Steps   int    `json:"steps,omitempty"`
	Message string `json:"message"`
}

func (s *Server) loadFromRom() romResponse {
	s.dbMu.Lock()
	digits := s.digitBuffer
	s.digitBuffer = ""
	s.dbMu.Unlock()

	if digits == "" {
		return romResponse{Message: "A↑: type a program number first"}
	}
	var n int
	if _, err := fmt.Sscanf(digits, "%d", &n); err != nil {
		return romResponse{Message: fmt.Sprintf("A↑: bad number %q", digits)}
	}
	prog, err := s.findProgram(n)
	if err != nil {
		return romResponse{Message: fmt.Sprintf("A↑: no program #%02d", n)}
	}
	steps, err := s.M.EnterProgram(prog.Code, 0)
	if err != nil {
		return romResponse{Message: fmt.Sprintf("A↑: load failed: %v", err)}
	}
	return romResponse{
		OK:    true,
		Steps: steps,
		Message: fmt.Sprintf("A↑: loaded #%02d (%s, %d steps) — press В/О then С/П",
			n, prog.Title, steps),
	}
}

func (s *Server) findProgram(n int) (*ProgramInfo, error) {
	pattern := filepath.Join(s.ProgramDir, fmt.Sprintf("%02d-*.yaml", n))
	matches, err := filepath.Glob(pattern)
	if err != nil || len(matches) == 0 {
		return nil, fmt.Errorf("no program #%02d", n)
	}
	sort.Strings(matches)
	return ReadProgramFile(matches[0])
}

func ReadProgramFile(path string) (*ProgramInfo, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p ProgramInfo
	if err := yaml.Unmarshal(b, &p); err != nil {
		return nil, err
	}
	if p.ID == "" {
		// fall back to filename stem
		p.ID = strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))
	}
	return &p, nil
}

func (s *Server) loadPrograms() ([]ProgramInfo, error) {
	matches, err := filepath.Glob(filepath.Join(s.ProgramDir, "*.yaml"))
	if err != nil {
		return nil, err
	}
	sort.Strings(matches)
	out := make([]ProgramInfo, 0, len(matches))
	for _, m := range matches {
		p, err := ReadProgramFile(m)
		if err != nil {
			continue
		}
		out = append(out, *p)
	}
	return out, nil
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	_ = enc.Encode(v)
}

// Serve runs the HTTP server on host:port. Blocks until ctx is cancelled
// or the server errors.
func (s *Server) Serve(ctx context.Context, host string, port int, webuiDir string) error {
	addr := fmt.Sprintf("%s:%d", host, port)
	srv := &http.Server{
		Addr:    addr,
		Handler: s.Handler(webuiDir),
	}
	errCh := make(chan error, 1)
	go func() {
		fmt.Printf("MK-52 web UI: http://%s/\n", addr)
		errCh <- srv.ListenAndServe()
	}()
	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		return srv.Shutdown(shutdownCtx)
	case err := <-errCh:
		return err
	}
}
