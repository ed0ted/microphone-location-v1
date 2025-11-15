#!/bin/bash
#
# Setup script for Drone Localization Node (Pi Zero)
#
# This script installs all dependencies and sets up the node
# for running the acoustic localization system.
#
# Usage:
#   sudo ./setup-node.sh [node-id]
#
# Example:
#   sudo ./setup-node.sh 1
#

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo)"
    exit 1
fi

# Configuration
PROJECT_DIR="/opt/drone-node"
NODE_ID="${1:-1}"
REPO_URL="https://github.com/your-username/microphone-location-v2.git"

echo "========================================"
echo "Drone Localization Node Setup"
echo "Node ID: $NODE_ID"
echo "========================================"
echo ""

# Update system
echo "[1/7] Updating system packages..."
apt update
apt upgrade -y

# Install system dependencies
echo "[2/7] Installing system dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    i2c-tools \
    git \
    vim \
    htop

# Enable I2C
echo "[3/7] Enabling I2C..."
raspi-config nonint do_i2c 0

# Clone or update repository
echo "[4/7] Setting up project directory..."
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
echo "[5/7] Creating Python virtual environment..."
python3 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"

# Install Python dependencies
echo "[6/7] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements-node.txt || {
    echo "  Warning: Some packages may have failed (hardware libraries)"
    echo "  Installing minimal set..."
    pip install numpy scipy pyyaml smbus2 orjson uvloop || true
}

# Configure node
echo "[7/7] Configuring node..."

# Update config file with node ID
if [ -f "configs/node-${NODE_ID}.yaml" ]; then
    echo "  Using existing config: configs/node-${NODE_ID}.yaml"
else
    echo "  Warning: Config file configs/node-${NODE_ID}.yaml not found"
    echo "  Please create it manually"
fi

# Create systemd service
echo "  Creating systemd service..."
cat > /etc/systemd/system/drone-node.service <<EOF
[Unit]
Description=Acoustic Drone Localization Node
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python -m node.node_agent --config $PROJECT_DIR/configs/node-${NODE_ID}.yaml run
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit config: sudo nano $PROJECT_DIR/configs/node-${NODE_ID}.yaml"
echo "  2. Run calibration: sudo -u pi $PROJECT_DIR/scripts/calibrate-node.sh $NODE_ID"
echo "  3. Test manually: sudo -u pi $PROJECT_DIR/scripts/launch-node.sh $NODE_ID"
echo "  4. Enable auto-start: sudo systemctl enable drone-node"
echo "  5. Start service: sudo systemctl start drone-node"
echo "  6. Check status: sudo systemctl status drone-node"
echo ""

