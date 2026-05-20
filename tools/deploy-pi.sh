#!/bin/bash
# Build the Go controller binary on this host, ship it to a Pi, install as
# the systemd autostart service. Replaces the older Python install.
#
# Run from the repo root, on the host that has Go installed:
#
#   bash tools/deploy-pi.sh                       # default user@192.168.2.177
#   bash tools/deploy-pi.sh pi@192.168.1.50       # custom target
#   GOARM=7 bash tools/deploy-pi.sh user@host     # Pi 2/3 (armv7)
#   GOARCH=arm64 bash tools/deploy-pi.sh user@host  # Pi 4/5 (aarch64)
#
# Defaults to ARMv6 (Pi Zero v1 / Pi 1). Sets up:
#   - /usr/local/bin/mk52-app           (the Go binary)
#   - /etc/systemd/system/mk-52.service (autostart unit)
# Disables any prior mk-52 service that pointed at the Python entrypoint.

set -e

TARGET="${1:-george@192.168.2.177}"
GOOS="${GOOS:-linux}"
GOARCH="${GOARCH:-arm}"
GOARM="${GOARM:-6}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/go"

echo "Building mk52-app for $GOOS/$GOARCH${GOARM:+v$GOARM}..."
out=$(mktemp -d)/mk52-app
GOOS="$GOOS" GOARCH="$GOARCH" GOARM="$GOARM" go build -ldflags="-s -w" -o "$out" ./cmd/app
ls -lh "$out"

echo "Copying to $TARGET:/tmp/mk52-app-new..."
scp -q "$out" "$TARGET:/tmp/mk52-app-new"

echo "Installing on the Pi..."
ssh -t "$TARGET" 'bash -s' <<'REMOTE'
set -e
INSTALL_USER=${USER}
REPO_ROOT="$HOME/mk-52-retrofit"
if [ ! -d "$REPO_ROOT" ]; then
    echo "ERROR: $REPO_ROOT not found — rsync the repo first"
    exit 1
fi

sudo systemctl stop mk-52 2>/dev/null || true
sudo install -m 755 /tmp/mk52-app-new /usr/local/bin/mk52-app
rm -f /tmp/mk52-app-new

sudo tee /etc/systemd/system/mk-52.service > /dev/null <<EOF
[Unit]
Description=МК-52 controller (Go) — physical keypad/LCD + web UI on :8080
After=local-fs.target network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/mk52-app
WorkingDirectory=${REPO_ROOT}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
User=${INSTALL_USER}

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mk-52.service
sudo systemctl restart mk-52.service
sleep 2
systemctl is-active mk-52.service
echo
echo "Web UI: http://$(hostname -I | awk '{print $1}'):8080/"
echo "Logs:   sudo journalctl -u mk-52 -f"
REMOTE

echo "Done."
