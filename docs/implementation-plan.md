# Acoustic Drone Detection Prototype – Implementation Blueprint

This document captures the **final implementation design** for the multi-node acoustic localization prototype. It turns the ideas from `project-overview.md` into actionable hardware, firmware, server, and UX tasks so another engineer can build, deploy, and operate the full stack with minimal guesswork.

---

## 1. Architecture Summary

```
            +------------------+          +----------------------------+
            | Pi Zero Node (x3)|   UDP    |      Raspberry Pi 5        |
  MAX4466 ->|  ADS1115 Sampler |--------->|  Fusion + Web Visualization |
  Tetrahedron  Signal Features |          |   Flask + Socket.IO + UI    |
            +------------------+          +----------------------------+
```

- **Sensor nodes (Pi Zero 2 W preferred)** capture four analog channels each, compute spectral/energy features, and stream compact JSON or CBOR packets to the Pi 5 over Wi-Fi at 10 Hz.
- **Fusion server (Pi 5)** hosts three services: UDP ingestion, localization worker, and Flask/Socket.IO UI. The Pi 5 also provides NTP, DHCP, and Wi-Fi AP functionality to keep the field network deterministic.
- **Local kiosk UI** (three.js + Plotly) runs on the Pi 5 display in Chromium kiosk mode, showing real-time 3D position estimates, node health, and telemetry charts.

---

## 2. Hardware & Physical Layout

| Component | Quantity | Notes |
| --- | --- | --- |
| Raspberry Pi Zero / Zero 2 W | 3 | GPIO header soldered, each node powered via 5 V battery pack with filtering. |
| Raspberry Pi 5 (8 GB) | 1 | Acts as AP (`hostapd`), DHCP/DNS (`dnsmasq`), and visualization host. |
| MAX4466 microphone breakout | 12 | Four per node, configured for ~20× gain, arranged as ~18 cm edge tetrahedron. |
| ADS1115 16-bit ADC | 3 | One per node, wired on I²C1, addresses 0x48/0x49/0x4A. |
| Tripods / mounts | 3 | 1 m high, hold tetrahedral arrays pointing up. |

**Global coordinate anchors** (meters, right-handed frame, +Z up):

- Node 1: (0, 0, 1)
- Node 2: (20, 0, 1)
- Node 3: (0, 20, 1)

**Tetrahedron local coordinates** (meters, relative to node origin):

| Mic | (x, y, z) |
| --- | --- |
| M0 | (0.00, 0.00, 0.18) |
| M1 | (0.00, 0.17, -0.06) |
| M2 | (-0.15, -0.09, -0.06) |
| M3 | (0.15, -0.09, -0.06) |

Node orientation is standardized so that +X points toward the USB/power connector, +Y toward the silkscreen logo, and +Z upward from the PCB.

---

## 3. Shared Conventions

| Item | Value |
| --- | --- |
| Operating systems | Raspberry Pi OS Lite (32-bit) on Pi Zero nodes, Raspberry Pi OS Desktop (64-bit) on Pi 5. |
| Time sync | `chrony` with Pi 5 as local NTP server; all timestamps UTC, microsecond resolution. |
| Processing cadence | 100 ms hop size per node; Pi 5 fusion loop runs at 20 Hz (50 ms period). |
| Data transport | UDP/IPv4 unicast to Pi 5 port 5005; packets < 512 B; optional fallback to CBOR for bandwidth savings. |
| Encoding | UTF-8 JSON for readability during bring-up; `application/cbor` for production if packet loss observed. |
| Security | WPA2 passphrase on AP, SSH key auth only, `ufw` locked to SSH/HTTP/UDP 5005. |
| Versioning | Git repo mirrored on Pi 5; nodes pull via LAN to avoid Internet requirement. |

---

## 4. Pi Zero Sensor Node Implementation

### 4.1 Software Stack & Services

- Create `/opt/drone-node` virtual environment; install `numpy`, `scipy`, `smbus2`, `adafruit-circuitpython-ads1x15`, `pyyaml`, `uvloop`, `orjson`.
- Systemd units:
  - `drone-node.service`: launches `node_agent.py` after `network-online.target`, restarts on failure with 5 s delay, `RestartSec=5`.
  - `drone-node-watchdog.timer`: optional timer to run self-diagnostics daily (raw capture, config backup).
- Logging: `journald` plus rotating JSON lines written to `/var/log/drone-node/frames/*.jsonl`.

### 4.2 Process Architecture

```
node_agent.py
 ├── ConfigLoader (YAML -> dataclasses)
 ├── AdcSampler Thread (reads ADS1115, feeds queue)
 ├── FeatureExtractor (DSP pipeline, 100 ms frames)
 ├── PacketPublisher (UDP client, heartbeats + CRC)
 ├── HealthMonitor (battery/temp sensors optional)
 └── CLI (calibrate, capture, status)
```

Each module communicates through lock-free `queue.SimpleQueue` instances. CPU affinity pins the sampler thread to isolate it from Python GC jitter.

### 4.3 Data Acquisition & DSP

1. **ADS1115 setup**: continuous-conversion, PGA ±1.024 V, 860 SPS. Multiplexer cycles channels 0→3 at ~215 SPS per channel.
2. **Resampling**: a 4-tap polyphase FIR replicates per-channel streams to 860 SPS equivalent amplitude envelope, sufficient for energy analysis.
3. **Pre-processing**:
   - Running mean subtraction (1 s window) to remove DC offsets.
   - First-order high-pass (fc ≈ 20 Hz) implemented via `y[n] = α(y[n-1] + x[n] - x[n-1])`.
4. **Feature windows** (computed every 100 ms, using Hann window of 1.6 s with 87.5% overlap):
   - RMS per mic.
   - Peak and crest factor (`peak / rms`).
   - Goertzel at 120 Hz and 240 Hz (common rotor harmonics).
   - Broadband energy ratio between top mic vs. base triad (adds elevation sensitivity).
   - Node-level sum of RMS and log-energy for dynamic range compression.

Pseudo-code:

```python
while True:
    samples = adc_sampler.read_block()
    dsp_state.update(samples)
    if dsp_state.should_emit_frame():
        frame = dsp_state.compute_features()
        packet_queue.put(frame)
```

### 4.4 Detection & Direction

- Noise floor per mic tracked via exponential moving average (time constant ~30 s) updated when `present=false`.
- Detection logic:

```python
signal = sum(max(rms[i] - noise[i], 0) for i in range(4))
threshold = noise_sum * 3.5
present = hysteresis.update(signal > threshold)
```

- Direction vector uses tetrahedral unit vectors `v_i`:
  1. Weight: `w_i = clamp(rms[i] - noise[i], 0, max_val)`.
  2. Local vector: `d = normalize(Σ w_i v_i)`.
  3. Confidence: `conf = min(signal / (signal + noise_sum), 1.0)`.
- Output also includes bandwidth-limited `dir_rate` (derivative) so fusion layer can penalize abrupt changes.

### 4.5 Packet Schema

```jsonc
{
  "node_id": 1,
  "seq": 15234,
  "ts_us": 1731597605123456,
  "present": true,
  "mic_rms": [0.18, 0.24, 0.21, 0.19],
  "noise_rms": [0.05, 0.06, 0.05, 0.05],
  "crest": [2.1, 2.2, 1.9, 2.0],
  "bandpower": [0.03, 0.01],      // 120 Hz, 240 Hz
  "dir_local": [0.12, 0.91, 0.39],
  "dir_conf": 0.73,
  "supply_v": 4.93,
  "temp_c": 38.5,
  "crc32": "8cfe12ab"
}
```

Heartbeat packets (2 Hz) maintain `present=false` and refresh noise baselines even when idle.

### 4.6 Configuration & Calibration

- Config file `/etc/drone-node/config.yaml`:

```yaml
node_id: 1
fusion_host: 10.0.0.1
fusion_port: 5005
tetrahedron_vectors:
  - [0.00, 0.00, 1.00]
  - [0.00, 0.95, -0.32]
  - [-0.87, -0.49, -0.32]
  - [0.87, -0.49, -0.32]
pga_voltage: 1.024
calibration:
  mic_bias_mv: [2.51, 2.50, 2.52, 2.49]
  noise_rms: [0.045, 0.048, 0.044, 0.046]
```

- CLI commands:
  - `drone-node calibrate --duration 60` → records 60 s ambient noise, updates `noise_rms`.
  - `drone-node capture --seconds 10` → dumps raw ADS1115 data for lab analysis (`.npy`).
  - `drone-node status` → prints config, health, last packet time.

### 4.7 Reliability Features

- Hardware watchdog via `/dev/watchdog`, pinged every 5 s.
- Local SQLite ring buffer storing last 5 min of frames; backlog forwarded once link recovers (marked `replayed=true` so fusion ignores for localization but keeps diagnostics).
- Brown-out detection using ADC reading of supply voltage; below 4.7 V triggers graceful shutdown.

---

## 5. Raspberry Pi 5 Fusion & Visualization Server

### 5.1 Services & Process Layout

| Service | Description |
| --- | --- |
| `fusion-receiver.service` | UDP listener (`fusion_receiver.py`), validates packets, updates shared state table (Redis or in-memory). |
| `localization.service` | Worker (`localization.py`) pulling latest frames, running solver, publishing results to message bus (ZeroMQ PUB or Redis). |
| `drone-ui.service` | Flask + Socket.IO app (`app.py`) served via `gunicorn`/`eventlet`, exposes REST + WebSockets. |
| `hostapd/dnsmasq` | Provide Wi-Fi AP `DRONE-NET`, addresses `10.0.0.1/24`. |
| `chronyd` | Acts as NTP server for nodes; syncs to GPS or upstream Internet when available. |

Directory layout:

```
/opt/drone-server
├── fusion_receiver.py
├── localization.py
├── models/
│   └── node_geometry.yaml
├── web/
│   ├── app.py
│   ├── templates/
│   └── static/
└── data/
    ├── raw/
    └── reports/
```

### 5.2 Ingestion Layer

- Receives UDP datagrams, decodes JSON with `orjson`, verifies `crc32`.
- Rejects packets older than 500 ms, duplicates (seq check), or from unknown node IDs.
- Maintains `NodeState` objects:

```python
NodeState = TypedDict(
    "NodeState",
    {
        "last_frame": Frame,
        "noise": List[float],
        "last_seen": datetime,
        "online": bool,
        "history": Deque[Frame]
    }
)
```

- History holds 5 s of frames to smooth energies and compute temporal derivatives.
- Emits events to localization worker through `asyncio.Queue`.

### 5.3 Localization Algorithm

1. Gather freshest frame from each node with `present=true` (require ≥2 nodes, ideally 3).
2. Compute node energies `E_n = Σ mic_rms` and normalized distribution `ê_n`.
3. Evaluate coarse search grid (x: −5→25 m, y: −5→25 m, z: 0→25 m, step 1 m):
   - Distances `d_n = ||candidate - node_position_n||`.
   - Predicted intensities `P_n = 1 / d_n^2`, normalized.
   - Error term: `err = Σ (P_n - ê_n)^2 + λ Σ (1 - dot(dir_n_global, unit(node→candidate)))`.
4. Pick minimal error candidate; refine with gradient descent or Nelder–Mead seeded at coarse minimum for sub-meter precision.
5. Estimate confidence from `1 / (1 + err)` scaled by detection SNR.
6. Apply exponential smoothing (`α = 0.4`) to position and `β = 0.2` to velocity estimate for UI stability.

Localization output payload:

```json
{
  "timestamp": 1731597605.123,
  "present": true,
  "position": {"x": 11.2, "y": 7.8, "z": 5.1},
  "velocity": {"x": 0.3, "y": -0.1, "z": 0.0},
  "confidence": 0.62,
  "error": 0.14,
  "node_details": [
    {"id": 1, "energy": 0.64, "dir": [0.2, 0.9, 0.4], "online": true},
    {"id": 2, "energy": 0.21, "dir": [0.8, 0.1, 0.2], "online": true},
    {"id": 3, "energy": 0.15, "dir": [0.1, 0.3, 0.9], "online": true}
  ]
}
```

### 5.4 Data Persistence & APIs

- Raw frames optionally persisted in `data/raw/YYYYMMDD-node.jsonl` (compressed nightly).
- Localization history stored in SQLite for quick retrieval; `reports/` holds CSV summaries of detection episodes (start/end, max confidence, estimated trajectory length).
- REST endpoints:
  - `GET /api/state`: most recent localization output.
  - `GET /api/history?seconds=60`: downsampled trajectory (5 Hz) for the last N seconds (default 60).
  - `GET /api/nodes`: health metrics (last_seen, RSSI, temp, supply).
- Optional MQTT bridge publishes `fusion/state` and `fusion/events`.

---

## 6. Web Interface (Pi 5 Display)

### 6.1 Frontend Stack

- Build tool: Vite (vanilla JS + ES modules).
- Libraries: three.js for 3D, Plotly for charts, Socket.IO client for realtime updates, Tailwind or simple CSS for layout.
- Structure:

```
web/static/
├── index.html
├── main.js        // bootstrap, socket connection
├── scene.js       // three.js scene setup
├── charts.js      // Plotly traces (energy, confidence)
└── styles.css
```

### 6.2 Features

- **3D Map**: shows node markers (green), bounding volume grid, and drone marker (red) with height cues. Camera orbits slowly; user can pinch/drag using touchscreen.
- **Telemetry Table**: per-node energy, direction vector, battery, temperature, last seen.
- **Timeline Strips**: last 30 s of total energy and solver confidence; highlight detection windows.
- **Alerts Banner**: indicates missing nodes, stale data, or watchdog resets.
- **Control Buttons**: toggle between grid map and top-down heat map, start/stop recording, download latest report.

### 6.3 Kiosk Mode

- Enable Chromium autostart with `~/.config/lxsession/LXDE-pi/autostart`:

```
@/usr/bin/chromium-browser --start-fullscreen --kiosk http://localhost/
```

- System monitors UI process and restarts if closed.

---

## 7. Networking, Time, and Security

1. **Wi-Fi AP**: Pi 5 hosts SSID `DRONE-NET` (2.4 GHz), channel fixed to avoid DFS, WPA2 passphrase stored in `secrets/`.
2. **DHCP leases**: `dnsmasq` reserves `10.0.0.101-103` for nodes; Pi 5 is `10.0.0.1`.
3. **Firewall**: `ufw allow 22/tcp`, `80/tcp`, `5005/udp`; default deny inbound.
4. **NTP**: `chrony` configured to sync upstream if Internet exists; otherwise free-runs with GPS module (optional) for better accuracy.
5. **SSH**: disable password logins; manage host keys with Ansible inventory.
6. **Updates**: Pi 5 acts as Git remote; nodes fetch firmware via LAN to keep dependencies consistent even offline.

---

## 8. Deployment Workflow

1. **Prepare Pi 5**:
   - Flash OS, update packages, install `hostapd`, `dnsmasq`, `chrony`, `python3-venv`, `nginx`, `git`.
   - Clone repo to `/opt/drone-server`, create virtualenv, install dependencies.
   - Configure services (`systemctl enable fusion-receiver localization drone-ui`).

2. **Prepare Pi Zero Nodes** (repeat ×3):
   - Flash OS Lite, enable SSH, I²C (`raspi-config`), configure Wi-Fi to `DRONE-NET`.
   - Install OS packages, clone repo to `/opt/drone-node`, set up virtualenv.
   - Copy node-specific config from `configs/node-XX.yaml`.
   - Enable `drone-node.service` and watchdog timer.

3. **Calibrate**:
   - Place nodes in quiet area; run `drone-node calibrate`.
   - Validate mic wiring by running `drone-node capture --seconds 5` and verifying channel ordering in notebook.

4. **Field Setup**:
   - Position tripods at planned coordinates; check orientation (compass + bubble level).
   - Power nodes; verify they appear online in UI before powering drone/speaker.

---

## 9. Testing & Validation

1. **Bench Functional Test**: inject known sine tones via speaker near each mic, confirm RMS/direction reflect expected orientation.
2. **Synthetic Localization Test**: simulate packets with known patterns via `simulator.py` to verify fusion math before field work.
3. **Walk Test**: carry drone sound source through area; log GPS path; compare to fused trajectory and adjust inverse-square scaling (`gain` factor per node).
4. **Environmental Overnight Test**: run for ≥8 h to capture false positives due to wind/birds; tune crest factor threshold and Goertzel gates.
5. **Network Resilience Test**: intentionally drop Wi-Fi (disable AP) and confirm nodes buffer frames, watchdog resets recover, and UI shows offline state.
6. **Latency Measurement**: use synchronized timestamps to measure node-to-UI latency (goal < 400 ms). Profile each stage if over budget.

Test artifacts stored under `data/tests/YYYYMMDD/`.

---

## 10. Future Enhancements

- Upgrade ADC front-end to simultaneous-sampling (e.g., ICS-52000 or PCM1863) for TDoA localization.
- Add automated calibration routine using known speaker positions to refine mic gains and tetrahedral geometry.
- Integrate GNSS or camera feed for cross-validation.
- Implement ML-based drone classifier (SVM or lightweight CNN) using additional spectral features.
- Provide cloud export (MQTT over LTE) for remote monitoring if needed.

---

With the above blueprint, teams can implement firmware, server software, and UI layers in parallel while sharing assumptions about timing, packet formats, networking, and testing criteria. Each subsection maps directly to code modules (`node_agent.py`, `fusion_receiver.py`, `localization.py`, `web/app.py`) to streamline execution. 
