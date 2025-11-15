#!/bin/bash
#
# Calibration script for Drone Localization Node
#
# This script runs the ambient noise calibration process
# to establish baseline noise levels for each microphone.
#
# Usage:
#   ./calibrate-node.sh [node-id] [duration]
#
# Example:
#   ./calibrate-node.sh 1 60
#

set -e

# Configuration
PROJECT_DIR="/opt/drone-node"
VENV_DIR="$PROJECT_DIR/venv"
CONFIG_BASE="$PROJECT_DIR/configs"

# Parse arguments
NODE_ID="${1:-1}"
DURATION="${2:-60}"
CONFIG_FILE="$CONFIG_BASE/node-${NODE_ID}.yaml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "========================================"
echo "Acoustic Drone Localization"
echo "Node Calibration"
echo "========================================"
echo ""
echo "Node ID: $NODE_ID"
echo "Duration: $DURATION seconds"
echo "Config: $CONFIG_FILE"
echo ""

# Check config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}ERROR:${NC} Config file not found: $CONFIG_FILE"
    exit 1
fi

# Check virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}ERROR:${NC} Virtual environment not found"
    echo "Please run setup-node.sh first"
    exit 1
fi

# Activate venv
source "$VENV_DIR/bin/activate"

echo -e "${YELLOW}IMPORTANT:${NC} Ensure the environment is QUIET during calibration!"
echo "Press Enter to start, or Ctrl+C to cancel"
read

echo ""
echo "Starting calibration..."
echo "Please keep the environment quiet for ${DURATION} seconds..."
echo ""

# Run calibration
cd "$PROJECT_DIR"
python3 -m node.node_agent \
    --config "$CONFIG_FILE" \
    calibrate \
    --duration "$DURATION"

echo ""
echo -e "${GREEN}Calibration complete!${NC}"
echo ""
echo "Updated calibration values in: $CONFIG_FILE"
echo ""
echo "Next step: Launch the node with:"
echo "  ./scripts/launch-node.sh $NODE_ID"
echo ""

