# Realistic Audio-Level Simulation

This guide explains how to test the complete acoustic localization pipeline using realistic audio simulation - from microphone signals through DSP processing to server fusion.

## Overview

The simulation system has two modes:

### Mode 1: Direct Packet Simulation (Simple)
Bypasses nodes entirely and sends pre-calculated packets directly to the server.
- **Script:** `scripts/simulate_drone.py`
- **Use case:** Quick testing of fusion algorithms

### Mode 2: Audio-Level Simulation (Realistic) ✨
Generates realistic microphone audio signals that are processed by actual node agents.
- **Scripts:** `scripts/drone_position_sim.py` + actual node agents
- **Use case:** Testing the full pipeline including DSP, detection, and direction estimation

---

## Mode 2: Audio-Level Simulation (Full Pipeline)

### Architecture

```
Drone Position Simulator
        ↓ (writes position to /tmp/drone_sim_state.json)
        ↓
Node Agent 1, 2, 3
  ↓ (reads position)
  ↓ (generates realistic audio)
  ↓ (applies acoustic propagation)
  ↓ (processes via DSP pipeline)
  ↓ (detects presence)
  ↓ (estimates direction)
  ↓ (sends UDP packets)
  ↓
Fusion Server
  ↓ (receives packets)
  ↓ (performs 3D localization)
  ↓ (updates web UI via WebSocket)
  ↓
Web Interface
```

### How It Works

1. **Drone Position Simulator** moves a virtual drone through 3D space and writes its position to a shared JSON file

2. **Node Agents** (running in simulator mode):
   - Read the drone position from the shared file
   - Calculate distance from each microphone to the drone
   - Generate realistic audio signals:
     - Multiple harmonic frequencies (150, 300, 450 Hz - typical drone motor sounds)
     - Frequency modulation (varying motor speed)
     - Broadband aerodynamic noise
     - Inverse square law for amplitude (energy ∝ 1/distance²)
     - Microphone directional response (cardioid pattern)
   - Process audio through the real DSP pipeline:
     - RMS energy calculation
     - Crest factor detection
     - Band power estimation
     - Direction estimation using microphone array geometry
   - Send packets to fusion server

3. **Fusion Server** receives packets and performs 3D localization as in the real system

### Setup Instructions

#### Terminal 1: Start Fusion Server
```bash
cd ~/projects/microphone-location-v2
source venv-server/bin/activate
python -m server.run_all --config configs/server.yaml --verbose
```

#### Terminal 2: Start Drone Position Simulator
```bash
cd ~/projects/microphone-location-v2
source venv-server/bin/activate
python scripts/drone_position_sim.py --pattern circle --speed 2.0 --height 5.0
```

#### Terminals 3-5: Start Node Agents
```bash
# Terminal 3 - Node 1
cd ~/projects/microphone-location-v2
source venv-node/bin/activate
python -m node.node_agent --config configs/node-1.yaml --verbose run

# Terminal 4 - Node 2
source venv-node/bin/activate
python -m node.node_agent --config configs/node-2.yaml --verbose run

# Terminal 5 - Node 3
source venv-node/bin/activate
python -m node.node_agent --config configs/node-3.yaml --verbose run
```

#### Browser: Open Web Interface
Navigate to: **http://localhost:3000**

You should see:
- Node status showing real-time energy levels
- Direction vectors updating based on drone position
- 3D visualization with moving red drone marker (estimated position)
- **Green drone marker** (true position from simulation) - toggle on/off
- Energy and confidence charts

### Development Feature: True Position Visualization ✨

When running audio simulation, the web interface automatically detects simulation mode and displays:

**Visual Markers:**
- 🔴 **Red Sphere**: Estimated position from the localization algorithm
- 🟢 **Green Sphere**: Actual drone position from the simulator (ground truth)
- **Blue Spheres**: Microphone node positions

**Toggle Control:**
- A "Show True Position" checkbox appears in the 3D view controls
- Toggle on/off to show/hide the green marker and its trail
- Enabled by default when simulation is detected

**Benefits:**
- Visually compare estimated vs. actual positions in real-time
- Measure localization error distance
- Evaluate algorithm performance under different conditions
- Debug and tune the fusion algorithm parameters

**Automatic Detection:**
The toggle appears automatically when `drone_position_sim.py` is running (creates `/tmp/drone_sim_state.json`) and disappears when using real hardware.

---

## Configuration

### Node Configuration (`configs/node-*.yaml`)

Each node config must have:

```yaml
# Global position in surveillance area
global_position: [0, 0, 1]  # [x, y, z] in meters

# Enable simulator mode
use_simulator: true

# Microphone array geometry
array_mode: triangle
triangle_positions:
  - [0.15, 0.0, 0.0]
  - [-0.075, 0.13, 0.0]
  - [-0.075, -0.13, 0.0]
```

The `global_position` is critical - it tells the audio simulator where the node is located in the surveillance area.

### Simulation Parameters

**Drone Position Simulator:**
```bash
python scripts/drone_position_sim.py \
  --pattern circle \      # Movement pattern
  --speed 2.0 \           # Speed in m/s
  --height 5.0 \          # Height in meters
  --radius 8.0 \          # Pattern radius
  --rate 20.0             # Update rate in Hz
```

**Available Patterns:**
- `circle` - Circular flight path
- `line` - Back and forth along X-axis
- `hover` - Stationary hover
- `figure8` - Figure-8 pattern
- `diagonal` - Diagonal back and forth

---

## Audio Generation Details

### Drone Sound Model

The simulator generates realistic drone audio:

**Frequency Content:**
- Base frequency: 150 Hz (typical quadcopter motor speed)
- Harmonics: 300, 450, 600, 750 Hz
- Amplitude decreases with harmonic order
- Frequency modulation: ±3% to simulate varying motor speed

**Acoustic Propagation:**
- **Inverse Square Law:** Energy = SourcePower / (distance²)
- **Source Power:** Configurable (default: 0.3V RMS at 1 meter)
- **Minimum Distance:** 0.5m to avoid singularity

**Microphone Response:**
- **Pattern:** Cardioid (directional sensitivity)
- **Formula:** response = 0.5 + 0.5 * cos(angle)
- **Effect:** Microphones are more sensitive to sounds from their pointing direction

**Noise:**
- **Background:** Gaussian noise at ~0.02V RMS
- **Broadband:** Low-pass filtered noise for aerodynamic effects

### Multi-Microphone Effects

Each microphone in the array receives:
1. Different signal amplitude (due to position)
2. Different directional gain (due to orientation)
3. Independent noise

This creates realistic directional cues that the DSP can detect.

---

## Troubleshooting

### Problem: Nodes show no detection

**Check:**
1. Is `drone_position_sim.py` running?
2. Does `/tmp/drone_sim_state.json` exist?
   ```bash
   cat /tmp/drone_sim_state.json
   ```
3. Are node configs set to `use_simulator: true`?
4. Are node `global_position` values correct?

### Problem: Drone detected but position is wrong

**Check:**
1. Node `global_position` matches server config `nodes` positions
2. Server config (`configs/server.yaml`) has correct node positions
3. Grid bounds in server config cover the drone's movement area

### Problem: "Failed to initialize realistic audio sim"

**Check node logs for details. Common causes:**
- Missing `global_position` in node config
- Invalid `array_mode` or microphone positions
- Import errors (ensure all dependencies installed)

### Problem: High CPU usage

- Reduce `--rate` in `drone_position_sim.py` (try 10 Hz instead of 20)
- Check node frame rate (`frame_hop_ms` in node config)
- Check if all 3 nodes are needed (can test with just 2)

### Problem: "Show True Position" toggle not appearing

**Check:**
1. Is `drone_position_sim.py` running?
2. Does `/tmp/drone_sim_state.json` exist and contain valid data?
   ```bash
   cat /tmp/drone_sim_state.json
   ```
3. Is the fusion server reading the file? (Check server logs for "simulation_mode")

The toggle appears automatically when simulation state is detected and hides when not available.

---

## Comparison: Mode 1 vs Mode 2

| Feature | Mode 1 (Direct) | Mode 2 (Audio-Level) |
|---------|----------------|---------------------|
| **Speed** | Fast | Slower (real DSP) |
| **Realism** | Approximation | High fidelity |
| **Tests DSP** | ❌ No | ✅ Yes |
| **Tests Direction** | ❌ Calculated | ✅ Estimated from audio |
| **Tests Detection** | ❌ Always present | ✅ Real threshold logic |
| **Noise Effects** | ❌ No | ✅ Yes |
| **Setup Complexity** | Simple (1 script) | Complex (4 processes) |

**Recommendation:**
- Use **Mode 1** for quick testing of fusion algorithms
- Use **Mode 2** for validating the complete system before hardware deployment

---

## Example: Testing Different Scenarios

### Scenario 1: High-speed drone
```bash
python scripts/drone_position_sim.py --pattern circle --speed 5.0 --height 8.0
```

### Scenario 2: Low hovering drone
```bash
python scripts/drone_position_sim.py --pattern hover --height 2.0
```

### Scenario 3: Distant drone (lower energy)
Edit the audio simulator source power or increase height:
```bash
python scripts/drone_position_sim.py --pattern circle --height 15.0
```

### Scenario 4: Fast maneuvers
```bash
python scripts/drone_position_sim.py --pattern figure8 --speed 4.0 --radius 12.0
```

Monitor the web interface to see how the localization performs under different conditions!

---

## Advanced: Modifying Audio Characteristics

Edit `node/drone_audio_sim.py` to change:

- **Frequency content:** Modify `self.base_freqs` and `self.freq_amplitudes`
- **Source power:** Adjust `base_amplitude` calculation
- **Noise level:** Change `noise_level` parameter
- **Directional pattern:** Modify `directional_gain` calculation

After changes, restart the node agents to apply them.

