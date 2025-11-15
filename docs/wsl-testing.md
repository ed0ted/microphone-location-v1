### ✅ All paths use **`~/projects/microphone-location-v2`**

(instead of `/mnt/d/microphone-location-v2`)

### ✅ All warnings about slow NTFS / hanging venv are fixed

(we now assume the project lives in the Linux filesystem)

### ✅ The instructions reflect the **correct, working WSL setup**

with proper venv creation, configs, performance tips, etc.

---

# ✅ **UPDATED WSL TESTING GUIDE**

### (Fully rewritten for your current working WSL setup using `~/projects/microphone-location-v2`)

---

# **WSL Testing Guide**

## Running the Acoustic Drone Localization System on Windows WSL

*(Updated for project directory: `~/projects/microphone-location-v2`)*

This guide explains how to set up, run, and test the entire drone localization system on **Windows WSL 2**, using only simulation mode—no hardware required.

---

# **Table of Contents**

1. Prerequisites
2. WSL Installation
3. Environment Setup
4. Installing Dependencies
5. Configuration for Simulation
6. Running the System
7. Accessing the Web Interface
8. Troubleshooting
9. Performance Tips
10. Development workflow

---

# 1. **Prerequisites**

* Windows 10 2004+ or Windows 11
* WSL 2 installed
* 8 GB RAM minimum
* Python 3.10 (Ubuntu default)
* Modern browser (Chrome/Firefox/Edge)

---

# 2. **WSL Installation**

### 1. Install WSL

Open **PowerShell as Administrator**:

```powershell
wsl --install
```

Reboot when asked.

### 2. Check version

```powershell
wsl --list --verbose
```

Should show:

```
Ubuntu — Version 2
```

If not:

```powershell
wsl --set-version Ubuntu 2
```

### 3. Update Ubuntu

Inside WSL:

```bash
sudo apt update
sudo apt upgrade -y
```

---

# 3. **Environment Setup**

### 1. Install essential tools

```bash
sudo apt install -y \
    python3 python3-venv python3-pip \
    git curl build-essential net-tools tmux
```

---

## **2. Clone or copy the project into Linux filesystem**

Your project must live in **Linux FS** to avoid issues with venv and symlinks.

### If cloning from GitHub:

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/your-username/microphone-location-v2.git
cd microphone-location-v2
```

### If copying from `/mnt/d/…`:

```bash
mkdir -p ~/projects
rsync -av /mnt/d/microphone-location-v2/ ~/projects/microphone-location-v2/
cd ~/projects/microphone-location-v2
```

---

## **3. Create Python virtual environments (now works properly)**

```bash
cd ~/projects/microphone-location-v2

python3 -m venv venv-server
python3 -m venv venv-node
```

Since we’re in Linux FS, these venvs will install instantly and correctly.

---

# 4. **Installing Dependencies**

## **Node / Each Node Agent**

```bash
source venv-node/bin/activate
pip install --upgrade pip
pip install -r requirements-node.txt
deactivate
```

## **Server**

```bash
source venv-server/bin/activate
pip install --upgrade pip
pip install -r requirements-server.txt
deactivate
```

---

# 5. **Configuration for Simulation (required for WSL)**

### Confirm you’re inside the Linux project directory:

```bash
cd ~/projects/microphone-location-v2
```

### Update node configurations:

Open `configs/node-X.yaml` and ensure:

```yaml
use_simulator: true
fusion_host: 127.0.0.1
fusion_port: 5005

network:
  host: 127.0.0.1
  port: 5005
```

### Update server config:

Edit `configs/server.yaml`:

```yaml
listen_host: 0.0.0.0
listen_port: 5005

web:
  host: 0.0.0.0
  port: 8080
```

---

# 6. **Running the System**

You can use **tmux (recommended)** or multiple terminals.

---

## **Method A: Using tmux (best UX)**

```bash
    sudo apt update
    sudo apt install tmux
    
cd ~/projects/microphone-location-v2
tmux new -s drone
```

Split window:

* `Ctrl+B` + `"` (horizontal)
* `Ctrl+B` + `%` (vertical)

### Pane 1 — Server

```bash
cd ~/projects/microphone-location-v2
source venv-server/bin/activate
python -m server.run_all --config configs/server.yaml --verbose
```

### Pane 2 — Node 1

```bash
cd ~/projects/microphone-location-v2
source venv-node/bin/activate
python -m node.node_agent --config configs/node-1.yaml run --verbose
```

### Pane 3 — Node 2

```bash
source venv-node/bin/activate
python -m node.node_agent --config configs/node-2.yaml run --verbose
```

### Pane 4 — Node 3

```bash
source venv-node/bin/activate
python -m node.node_agent --config configs/node-3.yaml run --verbose
```

Detach from tmux:

```
Ctrl+B, then D
```

Reattach:

```bash
tmux attach -t drone
```

---

## **Method B: Using launch script**

```bash
cd ~/projects/microphone-location-v2
nano launch-wsl.sh
```

*(Same script as before — now using correct Linux path)*

Make executable:

```bash
chmod +x launch-wsl.sh
./launch-wsl.sh
```

---

# 7. **Access the Web UI**

Open browser on Windows:

👉 **[http://localhost:8080](http://localhost:8080)**

You should see:

* 3D visualization
* Node positions
* Red drone marker (simulated path)
* Node status table
* Live metrics

---

# 8. **Troubleshooting**

### **Problem: venv empty / stuck creation**

Fixed because project is now in:

```
~/projects/microphone-location-v2
```

### **Problem: nodes cannot reach server**

Check server is listening:

```bash
netstat -tuln | grep 5005
```

### **Problem: UI stuck at "Connecting…"**

Check WebSocket:

```bash
netstat -tuln | grep 8080
```

Check server log pane for:

* CORS errors
* WebSocket handshake issues

---

# 9. **Performance Tips**

### Enable better performance inside WSL:

Create:

```
%USERPROFILE%\.wslconfig
```

Add:

```ini
[wsl2]
memory=8GB
processors=4
```

Restart WSL:

```powershell
wsl --shutdown
```

### Work ONLY inside Linux filesystem:

❌ `/mnt/c/...`
❌ `/mnt/d/...`
❌ `/mnt/e/...`

✔ `~/projects/...`

This avoids:

* Python venv hangs
* Slow disk I/O
* Permission issues
* Broken symlinks

---

# 10. **Development workflow**

### Use Windows apps to edit code:

* VS Code (with WSL remote)
* PyCharm WSL plugin

### Run code inside WSL:

```bash
cd ~/projects/microphone-location-v2
```

### Auto-sync from Windows → WSL (optional)

```bash
rsync -av /mnt/d/microphone-location-v2/ ~/projects/microphone-location-v2/
```

