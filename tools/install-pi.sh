#!/bin/bash
# Install the МК-52 controller as a systemd service that starts at boot.
# Run on the Pi as:  sudo bash tools/install-pi.sh
#
# Auto-detects:
#   - the user that ran sudo (so the service runs as them, not root)
#   - the path to this repo (so the unit doesn't hard-code /home/pi/...)
#   - whether pypy3 is installed (prefers it for the ~65× chip-loop speedup)
#
# Idempotent: re-running updates the unit and restarts the service.

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Must run as root: sudo $0"
    exit 1
fi

INSTALL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$REPO_ROOT/controller" ]; then
    echo "ERROR: controller/ not found under $REPO_ROOT"
    exit 1
fi

if command -v pypy3 >/dev/null 2>&1; then
    PYTHON="$(command -v pypy3)"
    echo "Using PyPy: $PYTHON"
else
    PYTHON=/usr/bin/python3
    echo "Using CPython: $PYTHON"
    echo "  (install pypy3 for ~65× speedup — see doc/raspberry-pi-deployment.md)"
fi

# Tear down the old standalone web-UI unit if it was installed by an earlier
# version of this script — controller/app.py now runs the web UI in-process
# so the chip state is shared with the physical keypad/LCD.
if systemctl list-unit-files mk-52-webui.service >/dev/null 2>&1; then
    echo "Removing obsolete mk-52-webui.service (web UI now runs in-process)"
    systemctl disable --now mk-52-webui.service 2>/dev/null || true
    rm -f /etc/systemd/system/mk-52-webui.service
fi

UNIT=/etc/systemd/system/mk-52.service
echo "Writing $UNIT (User=$INSTALL_USER, controller + web UI in one process)"
cat > "$UNIT" <<EOF
[Unit]
Description=МК-52 controller (physical keypad/LCD + web UI on :8080)
After=local-fs.target network-online.target
Wants=network-online.target

[Service]
ExecStart=$PYTHON -u app.py
WorkingDirectory=$REPO_ROOT/controller
Environment=MK52_WEBUI_HOST=0.0.0.0
Environment=MK52_WEBUI_PORT=8080
# Pi-Zero CPython is the slowest supported host (~1% of original МК-52 speed).
# 100 iters/Šaг × 2 Šaги per press ≈ 1.3 s/press end-to-end. Lower iters
# breaks В↑ settle; higher iters lengthens press latency without gain.
Environment=MK52_ITERS_PER_SHAG=100
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
User=$INSTALL_USER

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mk-52.service
systemctl restart mk-52.service

echo
echo "Installed and started. The controller now drives the physical keypad,"
echo "the LCD, AND a web UI on :8080 — all sharing the same emulator state."
echo
echo "Useful commands:"
echo "  systemctl status mk-52        # check state"
echo "  journalctl -u mk-52 -f        # follow logs"
echo "  systemctl restart mk-52       # after pulling new code"
echo
echo "Web UI: http://<this-pi-ip>:8080/"
