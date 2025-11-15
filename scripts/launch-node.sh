#!/bin/bash
#
# Launch script for Acoustic Drone Localization Node (Pi Zero)
#
# Usage:
#   ./launch-node.sh [node-id]
#
# Example:
#   ./launch-node.sh 1
#

set -e

# Configuration
PROJECT_DIR="/opt/drone-node"
VENV_DIR="$PROJECT_DIR/venv"
CONFIG_BASE="$PROJECT_DIR/configs"
LOG_DIR="/var/log/drone-node"

# Parse arguments
NODE_ID="${1:-1}"
CONFIG_FILE="$CONFIG_BASE/node-${NODE_ID}.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo "========================================"
echo "Acoustic Drone Localization System"
echo "Node Agent Launcher"
echo "========================================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    log_warn "Not running on Raspberry Pi"
else
    MODEL=$(tr -d '\0' < /proc/device-tree/model)
    log_info "Device: $MODEL"
fi

# Check project directory
if [ ! -d "$PROJECT_DIR" ]; then
    log_error "Project directory not found: $PROJECT_DIR"
    echo "Please run setup-node.sh first"
    exit 1
fi

# Check config file
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

log_info "Using config: $CONFIG_FILE"

# Check virtual environment
if [ ! -d "$VENV_DIR" ]; then
    log_error "Virtual environment not found: $VENV_DIR"
    echo "Please run setup-node.sh first"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check Python dependencies
log_info "Checking dependencies..."
python3 -c "import numpy, scipy, yaml" 2>/dev/null || {
    log_error "Missing Python dependencies"
    echo "Please run setup-node.sh first"
    exit 1
}

# Check I2C (if not using simulator)
USE_SIM=$(grep "use_simulator:" "$CONFIG_FILE" | awk '{print $2}')
if [ "$USE_SIM" != "true" ]; then
    log_info "Checking I2C hardware..."
    if ! command -v i2cdetect &> /dev/null; then
        log_warn "i2c-tools not installed"
    else
        i2cdetect -y 1 &> /dev/null || log_warn "I2C not available"
    fi
fi

# Get network info
log_info "Network configuration:"
FUSION_HOST=$(grep "fusion_host:" "$CONFIG_FILE" | awk '{print $2}')
FUSION_PORT=$(grep "fusion_port:" "$CONFIG_FILE" | awk '{print $2}')
echo "  Fusion Server: $FUSION_HOST:$FUSION_PORT"

# Test network connectivity
log_info "Testing connection to fusion server..."
if ping -c 1 -W 2 "$FUSION_HOST" &> /dev/null; then
    log_info "✓ Fusion server reachable"
else
    log_warn "✗ Cannot reach fusion server at $FUSION_HOST"
    echo "  The node will start but may not send data"
fi

echo ""
log_info "Starting Node Agent (ID: $NODE_ID)..."
echo ""

# Launch node agent
cd "$PROJECT_DIR"

# Check if log file is specified
LOG_FILE="$LOG_DIR/node-${NODE_ID}.log"

# Run with logging
exec python3 -m node.node_agent \
    --config "$CONFIG_FILE" \
    run \
    --verbose \
    2>&1 | tee -a "$LOG_FILE"

