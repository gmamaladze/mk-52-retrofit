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

UNIT=/etc/systemd/system/mk-52.service
echo "Writing $UNIT (User=$INSTALL_USER, WorkingDirectory=$REPO_ROOT/controller)"

cat > "$UNIT" <<EOF
[Unit]
Description=МК-52 emulator controller
After=local-fs.target

[Service]
ExecStart=$PYTHON -u app.py
WorkingDirectory=$REPO_ROOT/controller
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
echo "Installed and started. Useful commands:"
echo "  systemctl status mk-52        # check state"
echo "  journalctl -u mk-52 -f        # follow logs"
echo "  systemctl restart mk-52       # after pulling new code"
echo "  systemctl stop mk-52          # stop now"
echo "  systemctl disable mk-52       # don't start on boot"
