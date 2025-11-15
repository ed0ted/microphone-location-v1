#!/bin/bash
#
# Setup script for Drone Localization Fusion Server (Pi 5)
#
# This script installs all dependencies and sets up the Pi 5
# as the central fusion server with web interface.
#
# Usage:
#   sudo ./setup-server.sh
#

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo)"
    exit 1
fi

# Configuration
PROJECT_DIR="/opt/drone-server"
REPO_URL="https://github.com/your-username/microphone-location-v2.git"

echo "========================================"
echo "Drone Localization Fusion Server Setup"
echo "========================================"
echo ""

# Update system
echo "[1/6] Updating system packages..."
apt update
apt upgrade -y

# Install system dependencies
echo "[2/6] Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    vim \
    htop \
    nginx \
    net-tools

# Clone or update repository
echo "[3/6] Setting up project directory..."
if [ -d "$PROJECT_DIR" ]; then
    echo "  Project directory exists, updating..."
    cd "$PROJECT_DIR"
    git pull || true
else
    echo "  Cloning repository..."
    git clone "$REPO_URL" "$PROJECT_DIR" || {
        echo "  Failed to clone from $REPO_URL"
        echo "  Please update REPO_URL in this script or copy files manually"
        mkdir -p "$PROJECT_DIR"
    }
fi

cd "$PROJECT_DIR"

# Create virtual environment
echo "[4/6] Creating Python virtual environment..."
python3 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"

# Install Python dependencies
echo "[5/6] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements-server.txt

# Configure server
echo "[6/6] Configuring server..."

# Create systemd service
echo "  Creating systemd service..."
cat > /etc/systemd/system/drone-server.service <<EOF
[Unit]
Description=Acoustic Drone Localization Fusion Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m server.run_all --config $PROJECT_DIR/configs/server.yaml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Configure firewall (if enabled)
if command -v ufw &> /dev/null; then
    echo "  Configuring firewall..."
    ufw allow 5005/udp comment 'Drone node data'
    ufw allow 80/tcp comment 'Web interface'
    ufw allow 8080/tcp comment 'Alt web interface'
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit config: sudo nano $PROJECT_DIR/configs/server.yaml"
echo "  2. Test manually: sudo -u pi $PROJECT_DIR/scripts/launch-server.sh"
echo "  3. Enable auto-start: sudo systemctl enable drone-server"
echo "  4. Start service: sudo systemctl start drone-server"
echo "  5. Check status: sudo systemctl status drone-server"
echo "  6. View logs: sudo journalctl -u drone-server -f"
echo ""
echo "Web Interface: http://$(hostname -I | awk '{print $1}'):80"
echo ""

