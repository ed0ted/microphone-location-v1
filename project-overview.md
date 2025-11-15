Here’s a full, updated spec you can give to teammates / another LLM / use yourself when building the prototype.

---

# 1. Aim of the project

**Goal:**
Build a working **acoustic drone detection & localization prototype** using:

* 3 × **Raspberry Pi Zero** nodes with **tetrahedral microphone arrays**
* 1 × **Raspberry Pi 5** as the **central fusion & visualization server**

The system should:

1. **Detect** when a drone is present using its sound.
2. **Estimate an approximate 3D position** of the drone in a local coordinate frame (x, y, z).
3. **Improve elevation sense** (z) by using a **3D tetrahedral mic arrangement** on each node instead of a flat mic array.
4. Display all of this on a **web-based 3D map** served by the Pi 5.

We accept that with the **ADS1115 + MAX4466** front-end this will be **coarse localization** (meters of error, not centimeters).

---

# 2. Hardware overview

## 2.1. Available parts

* **3 × Raspberry Pi Zero**
  → Acoustic sensor nodes (“nodes”).

* **1 × Raspberry Pi 5**
  → Central data fusion + web UI.

* **12 × MAX4466 analog mic boards**
  → 4 mics per node → tetrahedral mic array.

* **3 × ADS1115 16-bit ADC modules (I²C)**
  → 1 per node, reading 4 mic channels each.

* Wi-Fi router / hotspot / Pi 5 as AP
  → To connect all Pis on a local network.

## 2.2. Logical modules

* **Node 1, Node 2, Node 3** (Pi Zero + ADS1115 + 4 mics):

  * Capture analog sound.
  * Compute per-mic energy in short frames.
  * Send per-frame data via UDP to Pi 5.

* **Central Fusion Server (Pi 5):**

  * Receives data from all nodes.
  * Computes:

    * total energy per node,
    * approximate 3D position via intensity-based localization,
    * per-node approximate direction using tetrahedral energy.
  * Hosts a **web UI with 3D visualization** of nodes + estimated drone position.

---

# 3. Physical layout

## 3.1. Node placement in the field

Define a simple **global coordinate system** for your test area:

* Node 1 at: **(0, 0, 1)** m
* Node 2 at: **(20, 0, 1)** m
* Node 3 at: **(0, 20, 1)** m

(You can scale these numbers depending on your area; 20 m baselines are a good start for ~20–30 m covered area.)

* All z ≈ 1 m (mounted on tripods or stands ~1 m high).
* The area roughly covered: a ~20×20 m square inside the triangle formed by the nodes.

You will hardcode these 3D positions per node in the software.

## 3.2. Microphone layout on each node (tetrahedron)

Each node has a **tetrahedral array** of 4 mics:

* 4 MAX4466 modules mounted at the vertices of a tetrahedron.
* The **center of the tetrahedron** is the node’s local origin.
* Each mic faces **outward** toward its vertex (approximate).

### Example geometry (local coordinates, in meters)

Let the node’s local axes be:

* +X = “right”
* +Y = “front”
* +Z = “up”

You can use an approximate regular tetrahedron centered at the origin:

* Mic 0 (“top”):
  **(0.0, 0.0, 0.18)**
* Mic 1:
  **(0.0, 0.17, -0.06)**
* Mic 2:
  **(-0.15, -0.09, -0.06)**
* Mic 3:
  **(0.15, -0.09, -0.06)**

This gives a structure with edge lengths ~0.25–0.30 m.

**Mechanical advice:**

* Mount all 4 MAX4466 modules on rods or a 3D frame approximating these positions.
* Keep the tetrahedron small but not tiny: **15–25 cm** scale is fine.
* The mic front faces (ports) should point along the line from the center to their vertex coordinates (approx).

These coordinates will be used later to define **direction vectors** for each mic.

---

# 4. Wiring per node (Pi Zero + ADS1115 + 4 MAX4466)

Each node is the same hardware pattern, just with different **NODE_ID** and **global position**.

## 4.1. Wiring: Raspberry Pi Zero ↔ ADS1115 (I²C)

**Pi Zero header pins:**

* **3.3V** → pin 1 (or 17)
* **GND** → any GND (e.g. pin 6, 9, 14, 20, 25, 30, 34, 39)
* **SDA** → pin 3 (GPIO2 / SDA1)
* **SCL** → pin 5 (GPIO3 / SCL1)

**ADS1115 module pins:**

* `VDD` → Pi **3.3V**
* `GND` → Pi **GND**
* `SDA` → Pi **SDA (pin 3)**
* `SCL` → Pi **SCL (pin 5)**
* `ADDR` → GND

  * This sets its I²C address to **0x48** (per node, one ADC only).
* `ALERT/RDY` → leave unconnected for now.

> ⚠️ Important:
> Use **3.3V** for ADS1115. Raspberry Pi GPIOs are **not 5V tolerant**.

## 4.2. Wiring: ADS1115 ↔ 4 × MAX4466 mics

Each **MAX4466** module:

* `VCC` → **3.3V** (same 3.3V as Pi & ADS1115).
* `GND` → **GND** (common ground with Pi & ADS1115).
* `OUT` → one of ADC inputs:

  * Mic 0 OUT → ADS1115 `A0`
  * Mic 1 OUT → ADS1115 `A1`
  * Mic 2 OUT → ADS1115 `A2`
  * Mic 3 OUT → ADS1115 `A3`

Connect all 4 mics in a clean star-like pattern, and keep **analog runs short** (a few tens of cm max) to reduce noise.

## 4.3. Enabling I²C on Pi Zero

On each Pi Zero:

```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
sudo apt update
sudo apt install -y python3-pip python3-smbus i2c-tools
sudo i2cdetect -y 1   # should show 0x48
```

If you see `48` in the grid → ADS1115 is detected and wiring is correct.

---

# 5. Networking layout

All Pis must be on the **same IP network**:

* Easiest: use a **Wi-Fi router or hotspot**.

  * Pi 5 connects via Wi-Fi or Ethernet.
  * Each Pi Zero connects via Wi-Fi.
* Alternatively: Pi 5 acts as a Wi-Fi Access Point and Pi Zeros connect to it.

All communication is:

* **UDP from Pi Zeros → Pi 5**, on a fixed port (e.g. 5005).
* No time synchronization required; we only use **relative energy**, not precise TDoA.

---

# 6. Software architecture

There are two main software components:

1. **Node software** (`node.py`) on each Pi Zero.
2. **Central fusion + web server** (`server.py` + `static/` files) on the Pi 5.

## 6.1. Data flow

1. Every ~80–100 ms, **each node**:

   * Samples 4 channels from ADS1115.
   * Computes **RMS energy** for each mic over a small frame.
   * Tracks **baseline** (noise floor) per mic via exponential moving average.
   * Computes **net energy = RMS − baseline** (clamped ≥ 0).
   * Packages data in a JSON payload:

     ```json
     {
       "node_id": "node1",
       "t": 1731582512.142,
       "node_pos": [0.0, 0.0, 1.0],
       "energies": [E0, E1, E2, E3]
     }
     ```
   * Sends via UDP to Pi 5 at `SERVER_IP:SERVER_PORT`.

2. **Pi 5 server**:

   * Receives packets from each node, stores the latest payload per node.

   * Periodically (e.g. every 200 ms):

     * Reads the latest energies.
     * Computes:

       * Total energy per node.
       * An approximate **3D direction vector** per node using tetrahedral geometry.
       * Then performs **3D localization** using:

         * Relative intensities (inverse square law).
         * Optional direction constraints.
     * Outputs:

       * `drone_present` flag.
       * Estimated `x, y, z` of drone.
       * Optional error metric.

   * Emits updates via **WebSocket (Socket.IO)** to the web frontend.

   * Serves a web page with **three.js** 3D visualization of nodes + drone.

---

# 7. Software on each node (Pi Zero)

## 7.1. Responsibilities

Each node’s script (`node.py`) must:

1. Initialize I²C and ADS1115.
2. Set ADC data rate and gain.
3. Continuously:

   * Read 4 channels.
   * Buffer samples for a **frame** (e.g. 20 samples per channel).
   * For each frame:

     * Compute **RMS energy** for each mic.
     * Update **baseline** using exponential moving average:

       * `baseline[i] = (1–alpha) * baseline[i] + alpha * rms`
     * Compute **net_energy[i] = max(rms - baseline[i], 0)`.
     * Send a UDP JSON packet to the Pi 5.

## 7.2. Key configuration in node script

At the top of `node.py`:

* `NODE_ID = "node1"` / `"node2"` / `"node3"`
* `NODE_POS = (0.0, 0.0, 1.0)` etc. → global coordinates of node
* `SERVER_IP = "<Pi5_IP>"`
* `SERVER_PORT = 5005`
* `FRAME_SIZE = 20`
* `ADC_DATA_RATE = 250`
* `BASELINE_ALPHA ≈ 0.01`

## 7.3. Node main loop (pseudocode)

```python
init_i2c_and_ads1115()

buffers = [[], [], [], []]
baseline = [0.0, 0.0, 0.0, 0.0]

while True:
    t = time.time()
    for i in range(4):
        v = read_voltage_from_channel(i)
        buffers[i].append(v)

    if len(buffers[0]) >= FRAME_SIZE:
        energies = []
        for i in range(4):
            rms = compute_rms(buffers[i])
            baseline[i] = (1 - BASELINE_ALPHA) * baseline[i] + BASELINE_ALPHA * rms
            net = max(rms - baseline[i], 0.0)
            energies.append(net)
            buffers[i].clear()

        payload = {
            "node_id": NODE_ID,
            "t": t,
            "node_pos": NODE_POS,
            "energies": energies,
        }
        send_udp_json(payload, SERVER_IP, SERVER_PORT)
```

---

# 8. Software on Pi 5 (central fusion + web UI)

## 8.1. Components

* `server.py`:

  * UDP listener for node packets.
  * Fusion logic:

    * Intensity-based localization.
    * Optional direction vector from tetrahedral array.
  * Flask HTTP server to serve frontend.
  * Socket.IO server to push real-time updates to frontend.

* `static/`:

  * `index.html` → basic page with three.js & Socket.IO.
  * `app.js` → three.js scene + logic to display nodes and drone.

## 8.2. Direction estimation per node (using tetrahedral array)

Given:

* Local mic directions `v0, v1, v2, v3` (unit vectors).
* Net energies `E0, E1, E2, E3`.

Compute a rough direction vector in node-local coordinates:

[
\vec{d}*\text{local} \propto \sum*{i=0}^{3} E_i \cdot \vec{v}_i
]

Then normalize:

```python
d = sum(E[i] * v[i] for i in range(4))
d = d / ||d||
```

If all nodes share the same orientation (they should), you can treat this as also being in global frame with just a translation, or apply a rotation if needed.

This **direction vector** is not super accurate but helps constrain the 3D search.

## 8.3. Intensity-based 3D localization (simple version)

1. Collect latest energies from all nodes:

   * `E_node[n] = sum(energies_from_node_n)`.
   * If `max(E_node) < threshold` → no drone.

2. Normalize:

   * Total energy: `sumE = sum(E_node.values())`
   * `E_meas[n] = E_node[n] / sumE`.

3. Define a **search grid** over your volume (coarse):

   * `x ∈ [-5, 25]` (step 2 m)
   * `y ∈ [-5, 25]` (step 2 m)
   * `z ∈ [0, 20]` (step 2 m)

4. For each candidate point (x, y, z):

   * Compute distance from node n:

     * `d_n = distance( (x,y,z), NODE_POS[n] )`

   * Predicted energy:

     * `E_pred_raw[n] = 1 / (d_n ^ 2)` (simple inverse square)

   * Normalize predicted:

     * `sum_pred = sum(E_pred_raw.values())`
     * `E_pred[n] = E_pred_raw[n] / sum_pred`.

   * Compute **error**:
     [
     err = \sum_n (E_pred[n] - E_meas[n])^2
     ]

   * Optionally add a direction penalty using `d_local` / `d_global`.

5. Pick the point with **minimum error** as the estimated drone position.

6. Broadcast result over Socket.IO:

```json
{
  "present": true,
  "x": X_est,
  "y": Y_est,
  "z": Z_est,
  "error": err_min
}
```

## 8.4. Web UI (three.js)

The frontend:

* Draws:

  * Axes (for reference).
  * Green spheres at `NODE_POS` for each node.
  * A red sphere at estimated `(x, y, z)` for the drone (if `present=true`).
* Uses Socket.IO to receive `drone_update` events and move the red sphere in real time.
* Optionally displays energy values and error.

---

# 9. Expected performance (honest summary)

With this setup:

* **Detection**: robust for moderate SNR; you’ll clearly see when the drone is active.
* **Horizontal position (x–y)**:

  * ~3–5 m best-case under good conditions.
  * More often 5–8 m error.
* **Height (z)**:

  * Tetrahedral layout improves sense of “above vs level”, but still coarse.
  * Expect several meters of uncertainty.
* **Direction per node**:

  * Quadrant-level, ±20–40° azimuth/elevation under good SNR.

You trade precision for **simplicity and speed of implementation**, which is acceptable for a hackathon-style prototype and as a platform for future upgrades (e.g. replacing ADS1115 with a true multichannel audio front-end for TDoA).

---

If you want, next step I can turn this into a **clean one-page PDF-style spec** (with a more formal structure and maybe a small ASCII diagram) or extend it with **calibration procedure instructions** (how to collect ground-truth data and tune parameters).
