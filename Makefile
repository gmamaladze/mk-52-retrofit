# MK-52 Retrofit Makefile

# Default deployment settings
PI_TARGET ?= george@192.168.2.178
GOOS      ?= linux
GOARCH    ?= arm
GOARM     ?= 6

# Build settings
APP_NAME := mk52-app
SRC_DIR  := go
MAIN_DIR := ./cmd/app

.PHONY: all build test clean deploy run-server bench

all: build

build:
	cd $(SRC_DIR) && GOOS=$(GOOS) GOARCH=$(GOARCH) GOARM=$(GOARM) \
		go build -ldflags="-s -w" -o ../$(APP_NAME) $(MAIN_DIR)

test:
	cd $(SRC_DIR) && go test ./...

run-server:
	cd $(SRC_DIR) && go run ./cmd/server

bench:
	cd $(SRC_DIR) && go run ./cmd/bench

clean:
	rm -f $(APP_NAME)

# Installation script to run on the Raspberry Pi
define REMOTE_INSTALL_SCRIPT
set -e
INSTALL_USER=$${USER}
REPO_ROOT="$$HOME/mk-52-retrofit"

if [ ! -d "$$REPO_ROOT" ]; then
    echo "ERROR: $$REPO_ROOT not found — rsync the repo first"
    exit 1
fi

echo "Stopping service..."
sudo systemctl stop mk-52 2>/dev/null || true

echo "Installing binary..."
sudo install -m 755 /tmp/$(APP_NAME)-new /usr/local/bin/$(APP_NAME)
rm -f /tmp/$(APP_NAME)-new

echo "Updating systemd unit..."
sudo tee /etc/systemd/system/mk-52.service > /dev/null <<EOF
[Unit]
Description=МК-52 controller (Go) — physical keypad/LCD + web UI on :8080
After=local-fs.target network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/$(APP_NAME)
WorkingDirectory=$${REPO_ROOT}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
User=$${INSTALL_USER}

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mk-52.service
sudo systemctl restart mk-52.service

echo "Verifying service..."
sleep 2
systemctl is-active mk-52.service
echo
echo "Web UI: http://$$(hostname -I | awk '{print $$1}'):8080/"
echo "Logs:   sudo journalctl -u mk-52 -f"
endef
export REMOTE_INSTALL_SCRIPT

deploy: build
	@echo "Deploying to $(PI_TARGET)..."
	scp -q $(APP_NAME) $(PI_TARGET):/tmp/$(APP_NAME)-new
	echo "$$REMOTE_INSTALL_SCRIPT" | ssh -t $(PI_TARGET) 'bash -s'
