#!/bin/bash
# Quick launcher for audio-level simulation
# This script starts all components in tmux panes

set -e

PROJECT_DIR="$HOME/projects/microphone-location-v2"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Audio-Level Drone Simulation Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}tmux not found. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y tmux
fi

# Kill existing session if it exists
tmux kill-session -t drone-sim 2>/dev/null || true

echo -e "${GREEN}Creating tmux session 'drone-sim'...${NC}"
echo ""
echo -e "${YELLOW}This will start:${NC}"
echo "  - Pane 0: Fusion Server"
echo "  - Pane 1: Drone Position Simulator"
echo "  - Pane 2: Node 1 Agent"
echo "  - Pane 3: Node 2 Agent"
echo "  - Pane 4: Node 3 Agent"
echo ""
echo -e "${GREEN}Press Enter to continue...${NC}"
read

# Create new session with first pane (server)
tmux new-session -d -s drone-sim -n 'drone-sim'

# Pane 0: Fusion Server
tmux send-keys -t drone-sim:0.0 "cd $PROJECT_DIR" C-m
tmux send-keys -t drone-sim:0.0 "source venv-server/bin/activate" C-m
tmux send-keys -t drone-sim:0.0 "echo '=== FUSION SERVER ===' && sleep 1" C-m
tmux send-keys -t drone-sim:0.0 "python -m server.run_all --config configs/server.yaml --verbose" C-m

# Split and create pane 1: Drone Position Simulator
tmux split-window -t drone-sim:0 -h
tmux send-keys -t drone-sim:0.1 "cd $PROJECT_DIR" C-m
tmux send-keys -t drone-sim:0.1 "source venv-server/bin/activate" C-m
tmux send-keys -t drone-sim:0.1 "echo '=== DRONE POSITION SIMULATOR ===' && sleep 2" C-m
tmux send-keys -t drone-sim:0.1 "python scripts/drone_position_sim.py --pattern circle --speed 2.0 --height 5.0" C-m

# Split pane 0 vertically for Node 1
tmux select-pane -t drone-sim:0.0
tmux split-window -t drone-sim:0 -v
tmux send-keys -t drone-sim:0.2 "cd $PROJECT_DIR" C-m
tmux send-keys -t drone-sim:0.2 "source venv-node/bin/activate" C-m
tmux send-keys -t drone-sim:0.2 "echo '=== NODE 1 ===' && sleep 3" C-m
tmux send-keys -t drone-sim:0.2 "python -m node.node_agent --config configs/node-1.yaml --verbose run" C-m

# Split pane 1 vertically for Node 2
tmux select-pane -t drone-sim:0.1
tmux split-window -t drone-sim:0 -v
tmux send-keys -t drone-sim:0.3 "cd $PROJECT_DIR" C-m
tmux send-keys -t drone-sim:0.3 "source venv-node/bin/activate" C-m
tmux send-keys -t drone-sim:0.3 "echo '=== NODE 2 ===' && sleep 3" C-m
tmux send-keys -t drone-sim:0.3 "python -m node.node_agent --config configs/node-2.yaml --verbose run" C-m

# Split pane 2 for Node 3
tmux select-pane -t drone-sim:0.2
tmux split-window -t drone-sim:0 -v
tmux send-keys -t drone-sim:0.4 "cd $PROJECT_DIR" C-m
tmux send-keys -t drone-sim:0.4 "source venv-node/bin/activate" C-m
tmux send-keys -t drone-sim:0.4 "echo '=== NODE 3 ===' && sleep 3" C-m
tmux send-keys -t drone-sim:0.4 "python -m node.node_agent --config configs/node-3.yaml --verbose run" C-m

# Balance the layout
tmux select-layout -t drone-sim:0 tiled

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Simulation started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Tmux commands:${NC}"
echo "  Attach:      ${BLUE}tmux attach -t drone-sim${NC}"
echo "  Detach:      ${BLUE}Ctrl+B, then D${NC}"
echo "  Switch pane: ${BLUE}Ctrl+B, then arrow keys${NC}"
echo "  Kill all:    ${BLUE}tmux kill-session -t drone-sim${NC}"
echo ""
echo -e "${YELLOW}Web Interface:${NC}"
echo "  ${BLUE}http://localhost:3000${NC}"
echo ""
echo "Attaching to session in 3 seconds..."
sleep 3

tmux attach -t drone-sim

