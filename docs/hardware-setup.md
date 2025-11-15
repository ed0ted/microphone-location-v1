# Hardware Setup Guide

## Acoustic Drone Localization System

This document provides comprehensive instructions for assembling and wiring the hardware components for the acoustic drone detection and localization system.

---

## Table of Contents

1. [Hardware Inventory](#hardware-inventory)
2. [System Architecture](#system-architecture)
3. [Triangle Microphone Array Assembly](#triangle-microphone-array-assembly)
4. [Node Wiring (Pi Zero + ADS1115 + 3 Microphones)](#node-wiring)
5. [Pi 5 Central Server Setup](#pi-5-central-server-setup)
6. [Physical Deployment](#physical-deployment)
7. [Testing and Verification](#testing-and-verification)
8. [Troubleshooting](#troubleshooting)

---

## Hardware Inventory

### Per Node (×3 nodes total):
- **1× Raspberry Pi Zero 2 W** with SD card (16GB minimum)
- **1× ADS1115 16-bit ADC** (I²C module)
- **3× GY-MAX4466 microphone modules**
- **1× 5V power supply** (2A minimum, USB micro)
- Jumper wires (female-to-female recommended)
- Mounting hardware (tripod or custom frame)

### Central Server:
- **1× Raspberry Pi 5** (4GB+ RAM recommended)
- **1× Official Pi 5 power supply** (27W USB-C)
- **1× Display** (HDMI, any resolution)
- **1× Keyboard and mouse** (for initial setup)
- SD card (32GB minimum, Class 10)

### Network:
- Option A: Existing WiFi router
- Option B: Use Pi 5 as WiFi Access Point (recommended for lowest latency)

### Tools Required:
- Small screwdriver
- Wire strippers/cutters
- Multimeter (recommended for testing)
- Soldering iron (optional, for permanent connections)
- 3D printer (optional, for custom mounts)

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Surveillance Area                   │
│                    (~20m × 20m)                      │
│                                                      │
│    Node 1 (0,0,1)        Target Drone               │
│         🎤                    ✈️                    │
│        /|\                                           │
│       🎤🎤                                           │
│                                                      │
│                                                      │
│                                                      │
│                            Node 3 (0,20,1)           │
│                                  🎤                  │
│                                 /|\                  │
│                                🎤🎤                  │
│                                                      │
│                                                      │
│         Node 2 (20,0,1)                              │
│              🎤                                      │
│             /|\                                      │
│            🎤🎤                                      │
└─────────────────────────────────────────────────────┘
                         │
                         │ UDP Data
                         │ (WiFi)
                         ↓
              ┌──────────────────┐
              │  Raspberry Pi 5   │
              │  Fusion Server    │
              │   + Web UI        │
              └──────────────────┘
                         │
                         ↓
                   📺 Display
```

### Data Flow:
1. Each node samples 3 microphones at ~860 Hz
2. Node computes RMS energy, direction vector, noise floor
3. Node sends UDP packet every ~100ms to Pi 5
4. Pi 5 fuses data from all nodes
5. Pi 5 estimates 3D drone position
6. Web UI displays position in real-time

---

## Triangle Microphone Array Assembly

### Microphone Layout

Each node uses **3 microphones arranged in a horizontal equilateral triangle** with all microphones pointing upward.

**Design Parameters:**
- Triangle radius: **15 cm** from center to each microphone
- All microphones at **same height** (horizontal plane)
- All microphone ports facing **upward** (+Z direction)

**Microphone Positions (local node coordinates):**
```
        Y (forward)
        ↑
        │     Mic 1
        │       ○
        │      /│\
        │     / │ \
        │    /  │  \
        │   /   │   \
        │  /    │    \
        │ /     │     \
        │/      │      \
   Mic 2○───────┼───────○ Mic 0  → X (right)
        │       │
        │      (0,0)
        │
```

**Coordinates:**
- **Mic 0 (Right):**    X = +15.0 cm,  Y = 0 cm,      Z = 0 cm
- **Mic 1 (Back-Left):** X = -7.5 cm,  Y = +13.0 cm,  Z = 0 cm
- **Mic 2 (Front-Left):** X = -7.5 cm,  Y = -13.0 cm,  Z = 0 cm

### Assembly Options

#### Option A: Flat Mounting Plate
1. Cut a circular or triangular plate (~25cm diameter)
2. Drill 3 holes at the positions above
3. Mount MAX4466 modules facing upward
4. Mount Pi Zero and ADS1115 in center
5. Attach to tripod or pole at ~1m height

#### Option B: 3D Printed Frame
Create a custom 3D printed frame with:
- Central hub for Pi Zero and ADS1115
- Three arms at 120° intervals
- Mounting clips for MAX4466 modules
- Cable management channels

#### Option C: Simple Wire Frame
1. Use stiff wire (coat hanger) to form triangle
2. Attach microphones with zip ties
3. Keep wiring neat and away from mic ports

### Best Practices:
- ✅ Keep microphones at **exact same height**
- ✅ Point all microphones **straight up**
- ✅ Minimize vibration and mechanical coupling
- ✅ Keep cables away from microphone ports
- ❌ Avoid metal plates directly behind mics (reflections)
- ❌ Don't block microphone ports with foam/fabric

---

## Node Wiring

### Wiring Diagram (Per Node)

```
Raspberry Pi Zero 2 W                    ADS1115 ADC
┌──────────────────┐                    ┌──────────────┐
│                  │                    │              │
│  Pin 1  [3.3V]───┼────────────────────┤ VDD          │
│  Pin 3  [SDA]────┼────────────────────┤ SDA          │
│  Pin 5  [SCL]────┼────────────────────┤ SCL          │
│  Pin 6  [GND]────┼───────┬────────────┤ GND          │
│                  │       │            │ ADDR (to GND)│
└──────────────────┘       │            │              │
                           │            │ A0  A1  A2  A3
                           │            └──┬───┬───┬───┘
                           │               │   │   │
                           │            ┌──┴───┴───┴──┐
                           │            │  Used: A0   │
                           │            │        A1   │
                           │            │        A2   │
                           │            │ Unused: A3  │
                           │            └──┬───┬───┬──┘
                           │               │   │   │
                    ┌──────┴───────────────┼───┼───┼──────┐
                    │                      │   │   │      │
              ┌─────▼──────┐         ┌────▼───▼───▼────┐ │
              │  MAX4466   │         │    MAX4466      │ │
              │   Mic 0    │         │     Mic 1       │ │
              │  (Right)   │         │  (Back-Left)    │ │
              ├────────────┤         ├─────────────────┤ │
              │ VCC → 3.3V │         │  VCC → 3.3V     │ │
              │ GND → GND  │◄────────┤  GND → GND      │ │
              │ OUT → A0   │         │  OUT → A1       │ │
              └────────────┘         └─────────────────┘ │
                                              │           │
                                     ┌────────▼──────────┐│
                                     │    MAX4466        ││
                                     │     Mic 2         ││
                                     │  (Front-Left)     ││
                                     ├───────────────────┤│
                                     │  VCC → 3.3V       ││
                                     │  GND → GND        │◄┘
                                     │  OUT → A2         │
                                     └───────────────────┘
```

### Step-by-Step Wiring Instructions

#### 1. Enable I²C on Raspberry Pi Zero

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
# Finish and reboot
```

#### 2. Connect ADS1115 to Raspberry Pi Zero

| ADS1115 Pin | Pi Zero Pin | Wire Color (suggested) |
|-------------|-------------|------------------------|
| VDD         | Pin 1 (3.3V)| Red                    |
| GND         | Pin 6 (GND) | Black                  |
| SDA         | Pin 3 (GPIO2)| Blue                  |
| SCL         | Pin 5 (GPIO3)| Yellow                |
| ADDR        | GND         | Black (bridge to GND)  |
| ALERT/RDY   | (leave unconnected) | —          |

**Important:** 
- Use **3.3V**, NOT 5V! Raspberry Pi GPIO pins are 3.3V only.
- The ADDR pin connected to GND sets I²C address to **0x48**.

#### 3. Connect MAX4466 Microphones to ADS1115

Each MAX4466 module has 3 pins:

| MAX4466 Pin | Connection | Notes |
|-------------|------------|-------|
| VCC         | 3.3V (Pi or ADS1115) | Power supply |
| GND         | GND (common ground)  | Ground reference |
| OUT         | ADS1115 A0/A1/A2     | Analog audio signal |

**Wiring:**
- **Mic 0 (Right):** OUT → ADS1115 A0
- **Mic 1 (Back-Left):** OUT → ADS1115 A1
- **Mic 2 (Front-Left):** OUT → ADS1115 A2
- **(A3 unused)**

**All VCC pins:** Connect to 3.3V rail  
**All GND pins:** Connect to common GND

#### 4. Verify I²C Connection

```bash
sudo i2cdetect -y 1
```

Expected output:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- 48 -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- -- --
```

If you see **48**, the ADS1115 is detected correctly! ✅

### Power Considerations

- **Pi Zero 2 W:** ~300-500 mA typical
- **ADS1115:** ~1 mA typical
- **MAX4466 (×3):** ~3 mA total
- **Total per node:** ~500 mA
- **Recommended supply:** 5V, 2A USB power adapter

Use good quality power supplies with low noise for best audio performance.

---

## Pi 5 Central Server Setup

### Hardware Assembly

1. **Insert SD card** with Raspberry Pi OS (64-bit recommended)
2. **Connect display** via HDMI
3. **Connect keyboard and mouse** via USB
4. **Power on** with official 27W USB-C power supply

### Initial Configuration

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Set hostname
sudo hostnamectl set-hostname drone-fusion-server

# Configure WiFi Access Point (see wifi-access-point.md)
# OR connect to existing WiFi network
```

### Network Configuration

**Static IP recommended:** `192.168.50.1`

Edit `/etc/dhcpcd.conf`:
```bash
interface wlan0
static ip_address=192.168.50.1/24
static routers=192.168.50.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

---

## Physical Deployment

### Node Placement

Deploy the 3 nodes in a **triangle configuration** covering your surveillance area:

**Recommended Layout (20m baseline):**
- **Node 1:** Position (0, 0, 1) — Origin point, 1m above ground
- **Node 2:** Position (20, 0, 1) — 20m along X-axis (East), 1m high
- **Node 3:** Position (0, 20, 1) — 20m along Y-axis (North), 1m high

**Mounting:**
- Use tripods, poles, or stands to mount nodes at **~1 meter height**
- Ensure nodes are **level** (use bubble level)
- Orient all nodes the **same direction** (align local X/Y axes)
- Clear line-of-sight between nodes is not required
- Avoid mounting near large reflective surfaces

**Field Calibration:**
1. Measure actual node positions with measuring tape or GPS
2. Update `configs/server.yaml` with measured coordinates
3. Mark node positions on ground with stakes or markers

### Orientation Convention

**Global coordinate system:**
```
        Y (North)
        ↑
        │
        │
        │
        └────────→ X (East)
       (0,0)     
        
        Z = height above ground
```

**Each node's local coordinate system should align with global:**
- Node X-axis points East (global +X)
- Node Y-axis points North (global +Y)
- Node Z-axis points Up (global +Z)

---

## Testing and Verification

### 1. Hardware Test (Per Node)

```bash
# SSH into node
ssh pi@<node-ip>

# Test I²C
sudo i2cdetect -y 1
# Should show 0x48

# Test Python I²C access
python3 -c "import smbus2; bus = smbus2.SMBus(1); print('I2C OK')"
```

### 2. Microphone Test

```bash
cd /path/to/microphone-location-v2

# Capture 10 seconds of raw data
python -m node.node_agent --config configs/node-1.yaml capture --duration 10

# Check output file
ls -lh capture-node1.npy
# Should be ~330 KB for 10 seconds at 860 Hz, 3 channels
```

### 3. Calibration (Ambient Noise)

```bash
# Run calibration in quiet environment for 60 seconds
python -m node.node_agent --config configs/node-1.yaml calibrate --duration 60

# Check updated config
cat configs/node-1.yaml | grep calibration_noise_rms
# Should show measured noise levels per channel
```

### 4. Live Test

```bash
# Terminal 1: Start fusion server
python -m server.run_all --config configs/server.yaml --verbose

# Terminal 2: Start Node 1
python -m node.node_agent --config configs/node-1.yaml --verbose run

# Terminal 3: Start Node 2
python -m node.node_agent --config configs/node-2.yaml --verbose run

# Terminal 4: Start Node 3
python -m node.node_agent --config configs/node-3.yaml --verbose run

# Open browser: http://192.168.50.1/
# Should see 3D visualization with node markers
```

### 5. Drone Test

1. Fly drone in surveillance area
2. Observe web interface:
   - Red sphere should track drone position
   - Node energy levels should increase
   - Confidence should be > 0.5
   - Position should update smoothly

---

## Troubleshooting

### Problem: Node won't start / I²C error

**Solution:**
```bash
# Check I²C is enabled
sudo raspi-config  # Enable I2C

# Check wiring
sudo i2cdetect -y 1

# Check permissions
sudo usermod -a -G i2c pi

# Reboot
sudo reboot
```

### Problem: Low microphone signal

**Possible causes:**
- Gain potentiometer on MAX4466 too low → **Turn clockwise**
- Microphone port blocked → **Clear obstruction**
- Loose connection → **Check wiring**
- Wrong voltage (5V instead of 3.3V) → **Use 3.3V!**

**Test:**
```python
# Read raw voltages
import board, busio
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15.ads1115 import ADS1115

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)
chan = AnalogIn(ads, ADS1115.P0)

# Should read ~1.5-1.8V DC bias with small AC variations
print(chan.voltage)
```

### Problem: Nodes not communicating with Pi 5

**Check:**
1. Network connectivity: `ping 192.168.50.1`
2. Firewall: `sudo ufw status` (should be inactive or allow port 5005)
3. Config IP addresses match
4. Pi 5 server is running

**Debug:**
```bash
# On Pi 5, listen on UDP port
sudo tcpdump -i wlan0 udp port 5005
# Should see packets from nodes
```

### Problem: Poor localization accuracy

**Possible causes:**
- **Ambient noise too high** → Calibrate in quieter environment
- **Node positions incorrect** → Re-measure and update configs
- **Nodes not level** → Use level during installation
- **Microphone array geometry wrong** → Check mic positions
- **Low SNR (drone too far)** → Works best within 20-30m

**Improve accuracy:**
- Increase `grid_step` resolution in `server.yaml` (slower but more accurate)
- Adjust `direction_weight` parameter
- Add 4th microphone and switch to tetrahedron mode

---

## Next Steps

- **[WiFi Access Point Setup](wifi-access-point.md)** — Configure Pi 5 as AP
- **[WSL Testing Guide](wsl-testing.md)** — Test system on Windows WSL
- **[Deployment Scripts](../scripts/)** — Automated deployment tools

---

**Document Version:** 1.0  
**Last Updated:** November 2024  
**Author:** Acoustic Drone Localization Team

