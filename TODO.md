# TODO

- [ ] **Restructure project folder structure**: Align with Golang best practices (e.g., move `go.mod` to root or use a clearer `pkg/` vs `cmd/` separation).
- [ ] **Improve boot time feedback**: Address long boot times without progress indication on the LCD. Consider a splash screen or incremental status updates during service initialization.
- [ ] **Fix A↑ loading**: Loading via Web UI works correctly, but physical loading using the **A↑** key is currently unreliable or failing.
- [ ] **Embed sample programs**: Verify if programs are included in the binary. If not, use `go:embed` to bundle the `programs/` directory into the final executable for easier deployment.
- [ ] **Expand program library**: Add more advanced and useful sample programs beyond the current basic examples.
