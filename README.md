# Project Sentinel-T: Chronomorphic IDS

**Detecting CAN Bus attacks by fingerprinting the physical clock drift of ECUs (using Kernel-Level Timestamping).**

## Overview
Sentinel-T is a Physical-Layer Intrusion Detection System for CAN networks. It identifies spoofing and masquerade attacks by analyzing the subtle, unique timing fingerprints caused by the physical crystal oscillators in Electronic Control Units (ECUs).

## The Science
We utilize a **2D Kalman Filter** to differentiate between **Physical Thermal Drift** (slowly changing, correlated frequency) and **Software-Generated Noise** (Gaussian/memoryless jitter), allowing us to detect unauthorized message injections that perfectly mimic data content but fail to replicate physical silicon timing.

## Quick Start

### 1. Prerequisites
Ensure `can-utils` is installed and a virtual CAN interface is active:
```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

### 2. Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Running the Monitor
```bash
python3 live_sentinel.py
```

### 4. Simulating Traffic
In another terminal, simulate a real ECU:
```bash
cangen vcan0 -g 10 -I 100
```
Or simulate an attacker:
```bash
while true; do cansend vcan0 666#DEADBEEF; sleep 0.01; done
```

## Features
- **Kernel-Level Precision:** Uses Linux `SO_TIMESTAMP` for microsecond accuracy.
- **Dynamic State Tracking:** Real-time Kalman Filter estimation of clock phase and frequency.
- **Zero-Trust Architecture:** Authenticates senders based on hardware signatures, not data IDs.
