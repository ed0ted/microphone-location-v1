#!/bin/bash
#
# Launch script for Acoustic Drone Localization Fusion Server (Pi 5)
#
# Usage:
#   ./launch-server.sh
#

set -e

# Configuration
PROJECT_DIR="/opt/drone-server"
VENV_DIR="$PROJECT_DIR/venv"
CONFIG_FILE="$PROJECT_DIR/configs/server.yaml"
LOG_DIR="/var/log/drone-server"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
echo "Fusion Server Launcher"
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
    echo "Please run setup-server.sh first"
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
    echo "Please run setup-server.sh first"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check Python dependencies
log_info "Checking dependencies..."
python3 -c "import flask, flask_socketio, numpy, scipy" 2>/dev/null || {
    log_error "Missing Python dependencies"
    echo "Please run setup-server.sh first"
    exit 1
}

# Get network info
log_info "Network configuration:"
LISTEN_HOST=$(grep "listen_host:" "$CONFIG_FILE" | head -1 | awk '{print $2}')
LISTEN_PORT=$(grep "listen_port:" "$CONFIG_FILE" | awk '{print $2}')
WEB_PORT=$(grep -A 2 "web:" "$CONFIG_FILE" | grep "port:" | awk '{print $2}')

echo "  UDP Listener: $LISTEN_HOST:$LISTEN_PORT"
echo "  Web Interface: port $WEB_PORT"

# Check if port is available
if command -v lsof &> /dev/null; then
    if lsof -Pi :$WEB_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "Port $WEB_PORT already in use"
        echo "  Killing existing process..."
        sudo lsof -ti:$WEB_PORT | xargs sudo kill -9 2>/dev/null || true
        sleep 1
    fi
fi

# Check network interface
IP_ADDR=$(hostname -I | awk '{print $1}')
log_info "Server IP address: $IP_ADDR"

echo ""
log_info "Starting Fusion Server..."
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Web Interface URLs:${NC}"
echo -e "  Local:   ${GREEN}http://localhost:$WEB_PORT${NC}"
echo -e "  Network: ${GREEN}http://$IP_ADDR:$WEB_PORT${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Launch server
cd "$PROJECT_DIR"

# Check if log file is specified
LOG_FILE="$LOG_DIR/server.log"

# Run with logging
exec python3 -m server.run_all \
    --config "$CONFIG_FILE" \
    --verbose \
    2>&1 | tee -a "$LOG_FILE"

