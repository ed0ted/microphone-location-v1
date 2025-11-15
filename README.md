# Acoustic Drone Localization System

A real-time 3D acoustic localization system for drone detection using distributed microphone arrays on Raspberry Pi nodes.

## 🎯 Features

- **3-Microphone Triangle Arrays** - Optimized horizontal arrays on each node
- **Real-time 3D Tracking** - Interactive web-based visualization
- **Distributed Architecture** - 3× Pi Zero 2 W nodes + 1× Pi 5 fusion server
- **WiFi Access Point Mode** - Low-latency local network
- **Flexible Deployment** - Supports both triangle (3-mic) and tetrahedron (4-mic) modes
- **WSL Testing** - Full simulation mode for development without hardware

## 📋 Hardware Requirements

### Per Node (×3):
- Raspberry Pi Zero 2 W
- ADS1115 16-bit ADC (I²C)
- 3× GY-MAX4466 microphone modules
- Power supply (5V, 2A)

### Central Server:
- Raspberry Pi 5 (4GB+ RAM)
- Display (HDMI)
- Power supply (27W USB-C)

**Total Cost:** ~$300-400 for complete 3-node system

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

**On each Pi Zero node:**
```bash
cd /path/to/microphone-location-v2
sudo ./scripts/setup-node.sh 1  # Use 1, 2, or 3 for node ID
```

**On Pi 5 server:**
```bash
cd /path/to/microphone-location-v2
sudo ./scripts/setup-server.sh
```

### Option 2: Manual Setup

**Node Setup:**
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip i2c-tools
python3 -m venv /opt/drone-node
source /opt/drone-node/bin/activate
pip install -r requirements-node.txt

# Configure and calibrate
nano configs/node-1.yaml
python -m node.node_agent --config configs/node-1.yaml calibrate --duration 60
python -m node.node_agent --config configs/node-1.yaml run
```

**Server Setup:**
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
python3 -m venv /opt/drone-server
source /opt/drone-server/bin/activate
pip install -r requirements-server.txt

python -m server.run_all --config configs/server.yaml
```

**Access Web Interface:** `http://<pi5-ip>:80`

## 🧪 Testing Without Hardware (WSL)

Full simulation mode for development on Windows:

```bash
# In WSL Ubuntu
cd ~/microphone-location-v2

# Update configs for localhost
sed -i 's/192.168.50.1/127.0.0.1/g' configs/*.yaml

# Terminal 1: Server
python -m server.run_all --config configs/server.yaml --verbose

# Terminals 2-4: Nodes
python -m node.node_agent --config configs/node-1.yaml run
python -m node.node_agent --config configs/node-2.yaml run
python -m node.node_agent --config configs/node-3.yaml run
```

**Web Interface:** `http://localhost:8080`

See [WSL Testing Guide](docs/wsl-testing.md) for detailed instructions.

## 📖 Documentation

### Setup Guides
- **[Hardware Setup](docs/hardware-setup.md)** - Complete wiring and assembly guide
- **[WiFi Access Point](docs/wifi-access-point.md)** - Configure Pi 5 as AP for low-latency networking
- **[WSL Testing](docs/wsl-testing.md)** - Test and develop on Windows without hardware

### Technical Documentation
- **[Project Overview](project-overview.md)** - System architecture and design rationale
- **[Implementation Plan](docs/implementation-plan.md)** - Detailed implementation blueprint

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│                Surveillance Area                     │
│                   (~20m × 20m)                       │
│                                                      │
│    Node 1              Drone ✈️           Node 3    │
│     🎤🎤🎤                                 🎤🎤🎤     │
│    (0,0,1)                               (0,20,1)   │
│                                                      │
│                   Node 2                             │
│                    🎤🎤🎤                              │
│                   (20,0,1)                           │
└──────────────────────┬──────────────────────────────┘
                       │ UDP over WiFi
                       ↓
              ┌─────────────────┐
              │  Raspberry Pi 5  │
              │  Fusion Server   │
              │   192.168.50.1   │
              └────────┬─────────┘
                       │
                   📺 Display
              3D Position Tracking
```

### Data Flow:
1. Each node samples 3 microphones at ~860 Hz
2. Node computes RMS energy, direction vector, noise floor
3. Node sends UDP packet every ~100ms to Pi 5
4. Pi 5 fuses data from all 3 nodes
5. Pi 5 estimates 3D drone position via grid search
6. Web UI displays position in real-time

## 📁 Repository Structure

```
microphone-location-v2/
├── node/                      # Pi Zero node package
│   ├── node_agent.py         # Main node agent
│   ├── ads_sampler.py        # ADC sampling (real + simulated)
│   ├── dsp.py                # Signal processing & feature extraction
│   ├── config.py             # Configuration management
│   └── packets.py            # Network packet handling
│
├── server/                    # Pi 5 fusion server
│   ├── run_all.py            # Main entry point
│   ├── localization.py       # 3D localization algorithm
│   ├── fusion_receiver.py    # UDP packet receiver
│   ├── state_store.py        # Shared state management
│   ├── config.py             # Server configuration
│   └── web/                  # Web interface
│       ├── app.py            # Flask + Socket.IO server
│       ├── templates/        # HTML templates
│       │   └── index.html
│       └── static/           # JS, CSS assets
│           ├── main.js       # 3D visualization (Three.js)
│           └── styles.css    # Modern UI styling
│
├── configs/                   # Configuration files
│   ├── node-1.yaml           # Node 1 config
│   ├── node-2.yaml           # Node 2 config
│   ├── node-3.yaml           # Node 3 config
│   └── server.yaml           # Fusion server config
│
├── scripts/                   # Deployment scripts
│   ├── setup-node.sh         # Automated node setup
│   ├── setup-server.sh       # Automated server setup
│   ├── launch-node.sh        # Node launcher
│   ├── launch-server.sh      # Server launcher
│   └── calibrate-node.sh     # Calibration helper
│
├── docs/                      # Documentation
│   ├── hardware-setup.md     # Hardware assembly guide
│   ├── wifi-access-point.md  # WiFi AP configuration
│   ├── wsl-testing.md        # WSL testing guide
│   └── implementation-plan.md # Technical design doc
│
├── requirements-node.txt      # Node Python dependencies
├── requirements-server.txt    # Server Python dependencies
└── README.md                  # This file
```

## 🔧 Configuration

### Triangle Array Mode (3 Microphones)

Each node uses 3 microphones in a horizontal equilateral triangle, all pointing upward:

```yaml
array_mode: triangle

triangle_positions:
  - [0.15, 0.0, 0.0]      # Mic 0: Right
  - [-0.075, 0.13, 0.0]   # Mic 1: Back-Left
  - [-0.075, -0.13, 0.0]  # Mic 2: Front-Left

triangle_vectors:
  - [0.0, 0.0, 1.0]       # All point directly upward
  - [0.0, 0.0, 1.0]       # Optimal for elevated sources (drones)
  - [0.0, 0.0, 1.0]       # Horizontal direction from spatial diversity
```

### Tetrahedron Mode (4 Microphones)

For improved elevation sensing, switch to 4-mic tetrahedron mode:

```yaml
array_mode: tetrahedron

tetrahedron_positions:
  - [0.0, 0.0, 0.18]      # Top
  - [0.0, 0.17, -0.06]    # Front
  - [-0.15, -0.09, -0.06] # Back-Left
  - [0.15, -0.09, -0.06]  # Back-Right
```

## 🎛️ Usage

### Running the System

**Start all services automatically:**

On each node:
```bash
sudo systemctl enable drone-node
sudo systemctl start drone-node
```

On server:
```bash
sudo systemctl enable drone-server
sudo systemctl start drone-server
```

**Or run manually:**

```bash
# On nodes
./scripts/launch-node.sh 1  # Node 1
./scripts/launch-node.sh 2  # Node 2
./scripts/launch-node.sh 3  # Node 3

# On server
./scripts/launch-server.sh
```

### Calibration

Before first use, calibrate ambient noise levels:

```bash
./scripts/calibrate-node.sh 1 60  # Node 1, 60 seconds
```

Keep environment QUIET during calibration!

### Monitoring

**Check system status:**
```bash
sudo systemctl status drone-node   # On nodes
sudo systemctl status drone-server # On server
```

**View logs:**
```bash
sudo journalctl -u drone-node -f   # Node logs
sudo journalctl -u drone-server -f # Server logs
```

**Monitor network:**
```bash
# On server
sudo tcpdump -i wlan0 udp port 5005
```

## 📊 Performance

### Expected Accuracy

With this hardware configuration:

| Metric | Best Case | Typical | Notes |
|--------|-----------|---------|-------|
| Horizontal (X-Y) | 3-5 m | 5-8 m | Depends on SNR |
| Vertical (Z) | 4-6 m | 6-10 m | Limited with triangle mode |
| Detection Range | 30 m | 20 m | Clear line-of-sight |
| Update Rate | 10 Hz | 5 Hz | Network dependent |
| Latency | 100 ms | 200 ms | WiFi AP mode |

### Limitations

- **Coarse localization** (meters, not centimeters) due to MAX4466/ADS1115 sampling rate
- **SNR dependent** - accuracy degrades with distance and ambient noise
- **No TDoA** - uses intensity-based localization only
- Triangle mode has **reduced elevation sensing** vs tetrahedron

## 🐛 Troubleshooting

### Problem: Node won't detect ADS1115

```bash
# Check I²C
sudo i2cdetect -y 1
# Should see 0x48

# Enable I²C
sudo raspi-config  # Interface Options -> I2C -> Enable
```

### Problem: No data reaching server

```bash
# Check network
ping 192.168.50.1  # From node

# Check firewall
sudo ufw allow 5005/udp

# Check server logs
sudo journalctl -u drone-server -f
```

### Problem: Poor localization

- **Calibrate nodes** in quiet environment
- **Check node positions** in `configs/server.yaml`
- **Increase SNR** - fly drone closer
- **Adjust grid search** - smaller `grid_step` (slower but more accurate)

See [Hardware Setup](docs/hardware-setup.md#troubleshooting) for more solutions.

## 🔬 Development

### Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=node --cov=server
```

### Code Style

```bash
black node/ server/
flake8 node/ server/
mypy node/ server/
```

### Adding Features

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Test thoroughly in simulation mode
4. Test on real hardware
5. Submit pull request

## 📝 License

[Add your license here]

## 🙏 Acknowledgments

- Based on acoustic drone detection research
- Uses Three.js for 3D visualization
- Plotly for real-time charts
- Flask + Socket.IO for web interface

## 📧 Contact

[Add contact information]

---

**Version:** 2.0  
**Last Updated:** November 2024  
**Hardware:** Raspberry Pi Zero 2 W, Raspberry Pi 5, ADS1115, MAX4466
