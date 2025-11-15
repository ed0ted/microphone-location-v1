# Raspberry Pi 5 WiFi Access Point Setup

## Configure Pi 5 as WiFi Hotspot for Drone Localization System

This guide configures the Raspberry Pi 5 to act as a WiFi Access Point, providing network connectivity for the three Pi Zero 2 W nodes. This approach minimizes latency compared to using an external router.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Starting the Access Point](#starting-the-access-point)
6. [Connecting Nodes](#connecting-nodes)
7. [Troubleshooting](#troubleshooting)
8. [Performance Optimization](#performance-optimization)

---

## Overview

**Network Architecture:**
```
                    Internet (optional)
                           │
                           │ (eth0)
                    ┌──────▼──────┐
                    │ Pi 5 Server │
                    │ 192.168.50.1│
                    └──────┬──────┘
                           │ (wlan0 - AP mode)
                           │ SSID: DroneLocalization
                 ┌─────────┴─────────┐
                 │                   │
         ┌───────▼────┐      ┌──────▼─────┐      ┌──────▼─────┐
         │  Node 1    │      │   Node 2   │      │   Node 3   │
         │192.168.50.11│     │192.168.50.12│     │192.168.50.13│
         └────────────┘      └────────────┘      └────────────┘
```

**Benefits:**
- ⚡ **Low latency** (< 5ms vs ~15ms through router)
- 🔒 **Isolated network** (no interference from other devices)
- 📶 **Strong signal** (nodes within range)
- 🛠️ **Full control** over network configuration

---

## Prerequisites

- Raspberry Pi 5 with Raspberry Pi OS (Bookworm or later)
- WiFi capability enabled (built-in on Pi 5)
- Ethernet connection (optional, for internet access)
- Root/sudo access

---

## Installation Steps

### 1. Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Required Packages

```bash
sudo apt install -y hostapd dnsmasq iptables
```

**Package purposes:**
- `hostapd` - Creates the WiFi Access Point
- `dnsmasq` - DHCP server (assigns IP addresses to nodes)
- `iptables` - Network routing (optional, for internet sharing)

### 3. Stop Services (for configuration)

```bash
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
```

---

## Configuration

### 1. Configure Static IP for wlan0

Edit `/etc/dhcpcd.conf`:

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end:

```conf
# Static IP for Access Point
interface wlan0
    static ip_address=192.168.50.1/24
    nohook wpa_supplicant
```

**Save and exit** (Ctrl+X, Y, Enter)

### 2. Configure DHCP Server (dnsmasq)

Backup original config:
```bash
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
```

Create new config:
```bash
sudo nano /etc/dnsmasq.conf
```

Add:

```conf
# Drone Localization System - DHCP Configuration

# Interface to use
interface=wlan0

# DHCP range: .10 to .50 with 24-hour lease
dhcp-range=192.168.50.10,192.168.50.50,255.255.255.0,24h

# Gateway (this Pi)
dhcp-option=option:router,192.168.50.1

# DNS servers (Google DNS)
dhcp-option=option:dns-server,8.8.8.8,8.8.4.4

# Domain name
domain=dronelocal

# Static leases for nodes (optional but recommended)
dhcp-host=node1,192.168.50.11,infinite
dhcp-host=node2,192.168.50.12,infinite
dhcp-host=node3,192.168.50.13,infinite

# Log DHCP transactions
log-dhcp

# Bind only to wlan0
bind-interfaces
```

**Save and exit**

### 3. Configure Access Point (hostapd)

Create config file:
```bash
sudo nano /etc/hostapd/hostapd.conf
```

Add:

```conf
# Drone Localization System - WiFi AP Configuration

# Interface
interface=wlan0

# Driver
driver=nl80211

# Network name (SSID)
ssid=DroneLocalization

# WiFi mode: 802.11ac (5GHz) for lower latency
# Use 802.11n (2.4GHz) if nodes don't support 5GHz
hw_mode=a
channel=36

# Enable 802.11ac
ieee80211ac=1

# Channel width: 80 MHz for high throughput
vht_oper_chwidth=1
vht_oper_centr_freq_seg0_idx=42

# Country code (set to your country)
country_code=US

# Security: WPA2
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_passphrase=DroneSystem2024
rsn_pairwise=CCMP

# Performance optimization
wmm_enabled=1
```

**Important:** If your Pi Zero 2 W nodes don't support 5GHz, use this instead:

```conf
# Alternative: 2.4GHz configuration for better compatibility
hw_mode=g
channel=6
ieee80211n=1
```

**Save and exit**

Link config:
```bash
sudo nano /etc/default/hostapd
```

Add/uncomment:
```conf
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

**Save and exit**

### 4. Enable IP Forwarding (Optional - for internet sharing)

If you want nodes to access internet through Pi 5's Ethernet:

```bash
sudo nano /etc/sysctl.conf
```

Uncomment:
```conf
net.ipv4.ip_forward=1
```

**Save and apply:**
```bash
sudo sysctl -p
```

### 5. Configure iptables (for internet sharing)

Only if you enabled IP forwarding:

```bash
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
```

Save rules:
```bash
sudo sh -c "iptables-save > /etc/iptables.ipv4.nat"
```

Auto-restore on boot:
```bash
sudo nano /etc/rc.local
```

Add before `exit 0`:
```bash
iptables-restore < /etc/iptables.ipv4.nat
```

---

## Starting the Access Point

### 1. Enable Services

```bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq
```

### 2. Start Services

```bash
sudo systemctl start hostapd
sudo systemctl start dnsmasq
```

### 3. Verify Status

```bash
sudo systemctl status hostapd
sudo systemctl status dnsmasq
```

Both should show **active (running)** in green.

### 4. Check WiFi AP

From another device:
- Look for WiFi network **"DroneLocalization"**
- Connect with password: **DroneSystem2024**
- Should receive IP in range 192.168.50.x

---

## Connecting Nodes

### Configure Pi Zero 2 W Nodes

On each node, edit WiFi configuration:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

Add:

```conf
network={
    ssid="DroneLocalization"
    psk="DroneSystem2024"
    key_mgmt=WPA-PSK
}
```

**Reboot node:**
```bash
sudo reboot
```

### Verify Connection

From Pi 5:
```bash
# Check connected clients
arp -a | grep 192.168.50

# Check DHCP leases
cat /var/lib/misc/dnsmasq.leases

# Ping nodes
ping 192.168.50.11  # Node 1
ping 192.168.50.12  # Node 2
ping 192.168.50.13  # Node 3
```

### Assign Hostnames (optional)

On Pi 5, edit `/etc/hosts`:
```bash
sudo nano /etc/hosts
```

Add:
```
192.168.50.11   node1
192.168.50.12   node2
192.168.50.13   node3
```

Now you can use: `ssh pi@node1` instead of IP addresses.

---

## Troubleshooting

### Problem: hostapd won't start

**Check:**
```bash
sudo journalctl -u hostapd -n 50
```

**Common issues:**
- **"Failed to set beacon parameters"** → Channel conflict, try different channel
- **"Could not configure driver mode"** → WiFi already in use, disable wpa_supplicant:
  ```bash
  sudo systemctl disable wpa_supplicant
  sudo rfkill unblock wifi
  ```

### Problem: No internet on nodes

**Check IP forwarding:**
```bash
cat /proc/sys/net/ipv4/ip_forward
# Should output: 1
```

**Check iptables:**
```bash
sudo iptables -L -v -n
sudo iptables -t nat -L -v -n
```

**Test from node:**
```bash
ping 8.8.8.8  # Google DNS
```

### Problem: Nodes can't connect

**Check AP is running:**
```bash
sudo systemctl status hostapd
sudo iw dev wlan0 info
```

**Check DHCP:**
```bash
sudo systemctl status dnsmasq
sudo journalctl -u dnsmasq -n 50
```

**Restart everything:**
```bash
sudo systemctl restart dhcpcd
sudo systemctl restart dnsmasq
sudo systemctl restart hostapd
```

### Problem: Poor WiFi performance

**Optimize channel selection:**

Check for interference:
```bash
sudo apt install wavemon
sudo wavemon
```

**5GHz channels:** 36, 40, 44, 48 (usually clear)  
**2.4GHz channels:** 1, 6, 11 (non-overlapping)

**Change in `/etc/hostapd/hostapd.conf`:**
```conf
channel=44  # for 5GHz
# or
channel=11  # for 2.4GHz
```

Then restart:
```bash
sudo systemctl restart hostapd
```

---

## Performance Optimization

### 1. WiFi Power Management

Disable power saving:
```bash
sudo iw dev wlan0 set power_save off
```

Make permanent:
```bash
sudo nano /etc/rc.local
```

Add before `exit 0`:
```bash
/sbin/iw dev wlan0 set power_save off
```

### 2. QoS Configuration

Edit `/etc/hostapd/hostapd.conf`:

Add:
```conf
# QoS for low latency
wmm_enabled=1
wmm_ac_vo_cwmin=3
wmm_ac_vo_cwmax=4
wmm_ac_vo_aifs=2
wmm_ac_vo_txop_limit=94
```

Restart hostapd:
```bash
sudo systemctl restart hostapd
```

### 3. Reduce DHCP Lease Query Frequency

Edit `/etc/dnsmasq.conf`:
```conf
# Longer lease = less overhead
dhcp-range=192.168.50.10,192.168.50.50,255.255.255.0,24h

# Assign static IPs to nodes (recommended)
dhcp-host=<node1-mac>,192.168.50.11,infinite
dhcp-host=<node2-mac>,192.168.50.12,infinite
dhcp-host=<node3-mac>,192.168.50.13,infinite
```

Find MAC addresses:
```bash
cat /var/lib/misc/dnsmasq.leases
```

### 4. Monitor Performance

**Latency test:**
```bash
# From Pi 5 to nodes
ping -c 100 192.168.50.11 | tail -1
# Should see avg < 5ms
```

**Throughput test:**
```bash
# Install iperf3 on Pi 5 and one node
sudo apt install iperf3

# On Pi 5:
iperf3 -s

# On node:
iperf3 -c 192.168.50.1
# Should see > 50 Mbps for UDP data
```

---

## Network Diagram with IPs

```
┌─────────────────────────────────────────────────────┐
│                                                      │
│              Pi 5 Access Point                      │
│          IP: 192.168.50.1/24                       │
│          SSID: DroneLocalization                    │
│          Password: DroneSystem2024                  │
│                                                      │
└────────────────┬────────────────────────────────────┘
                 │
       ┌─────────┴─────────┬─────────────┐
       │                   │             │
  ┌────▼────┐        ┌─────▼────┐  ┌────▼────┐
  │ Node 1  │        │  Node 2  │  │ Node 3  │
  │ .50.11  │        │  .50.12  │  │ .50.13  │
  └─────────┘        └──────────┘  └─────────┘
  (0, 0, 1)          (20, 0, 1)    (0, 20, 1)
```

---

## Security Considerations

### Change Default Password

**Edit `/etc/hostapd/hostapd.conf`:**
```conf
wpa_passphrase=YourStrongPassword123!
```

### Disable AP When Not in Use

```bash
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
```

### Firewall Rules

```bash
# Allow only specific ports
sudo ufw allow from 192.168.50.0/24 to any port 5005 proto udp
sudo ufw allow from 192.168.50.0/24 to any port 80 proto tcp
sudo ufw enable
```

---

## Auto-Start on Boot

Create systemd service to ensure everything starts in order:

```bash
sudo nano /etc/systemd/system/drone-network.service
```

```ini
[Unit]
Description=Drone Localization Network Setup
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl start hostapd
ExecStart=/usr/bin/systemctl start dnsmasq
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable drone-network.service
```

---

## Next Steps

- **[Hardware Setup](hardware-setup.md)** — Wire and assemble nodes
- **[WSL Testing](wsl-testing.md)** — Test without hardware
- **[Deployment Guide](deployment.md)** — Deploy to field

---

**Document Version:** 1.0  
**Last Updated:** November 2024  
**Tested On:** Raspberry Pi 5 (4GB), Raspberry Pi OS Bookworm

