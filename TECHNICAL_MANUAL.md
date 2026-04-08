# Project Sentinel-T — Complete Technical Manual

**Version:** 1.1  
**Last Updated:** April 2026  
**Author:** Amit Vikramaditya

> This manual is written for students with basic Python knowledge. Even if you have never run the project before, following this guide step-by-step will get you from a blank machine to a running Sentinel-T detection system.

---

## Table of Contents

- [Part 1 — What Is This Project?](#part-1--what-is-this-project)
- [Part 2 — Prerequisites & Installation](#part-2--prerequisites--installation)
- [Part 3 — File-by-File Code Reference](#part-3--file-by-file-code-reference)
- [Part 4 — How to Run Each Script](#part-4--how-to-run-each-script)
- [Part 5 — Running Tests](#part-5--running-tests)
- [Part 6 — Configuration Reference](#part-6--configuration-reference)
- [Part 7 — Troubleshooting](#part-7--troubleshooting)
- [Part 8 — Glossary](#part-8--glossary)

---

## Part 1 — What Is This Project?

Project Sentinel-T is a **security monitor for vehicle CAN networks**. It watches the timing of messages on the CAN bus and uses a mathematical algorithm (Kalman Filter) to determine whether each message was sent by a legitimate ECU (a real hardware device inside the car) or by an attacker running software.

The core idea: every physical clock chip (crystal oscillator) in every ECU has a unique, slowly-drifting time signature caused by temperature changes and manufacturing imperfections. Software cannot fake this signature. Sentinel-T measures this signature and raises an alarm when it doesn't match.

**You do NOT need a real car or CAN hardware to run this project.** The `demo.py` script runs entirely in software on any computer.

---

## Part 2 — Prerequisites & Installation

### 2.1 What You Need

**Minimum (Offline Demo only):**
- Any Linux, macOS, or Windows machine
- Python 3.10 or newer
- ~100 MB disk space

**For the Live Monitor (Optional — Linux only):**
- Ubuntu 20.04/22.04/24.04 or Debian Linux
- Root/sudo access (to load kernel modules)
- `can-utils` package

### 2.2 Step-by-Step Setup

**Step 1: Clone the repository**
```bash
git clone https://github.com/amit-vikramaditya/Project-Sentinel-T.git
cd Project-Sentinel-T
```

**Step 2: Create a Python virtual environment** (recommended — keeps packages isolated)
```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# OR on Windows:
# .venv\Scripts\activate
```

You should see `(.venv)` appear at the start of your terminal prompt.

**Step 3: Install required Python packages**
```bash
pip install -r requirements.txt
```

This installs: `numpy`, `pandas`, `matplotlib`, `pytest`, and `python-pptx`.

**Step 4: Verify the installation**
```bash
python -c "import numpy, pandas, matplotlib, pptx, pytest; print('All packages OK')"
```

If you see `All packages OK`, you are ready to go.

### 2.3 Setting Up the Virtual CAN Bus (Linux only, for Live Monitor)

> Skip this section if you only want to run `demo.py` or the tests.

```bash
# 1. Load the virtual CAN kernel module
sudo modprobe vcan

# 2. Create a virtual CAN interface
sudo ip link add dev vcan0 type vcan

# 3. Bring the interface up
sudo ip link set up vcan0

# 4. Verify it is running
ip link show vcan0
```

You should see output like:
```
5: vcan0: <NOARP,UP,LOWER_UP> mtu 72 qdisc noqueue state UNKNOWN ...
```

**Install can-utils (for traffic simulation tools):**
```bash
sudo apt install can-utils
```

---

## Part 3 — File-by-File Code Reference

This section explains every Python file in the project: what it does, what its inputs and outputs are, and when you would use it.

---

### `config.py` — Central Configuration

**What it does:**  
A single file containing all the constants and parameters used throughout the project. Instead of searching five different files to find "what is the detection threshold?", you can look it up here. **If you want to tune the system, this is the only file you need to edit.**

**Key parameters:**

| Parameter | Default Value | Meaning |
|-----------|---------------|---------|
| `CAN_INTERFACE` | `"vcan0"` | Name of the CAN network interface |
| `DEFAULT_BASE_INTERVAL` | `0.010` | Expected message interval in seconds (100 Hz) |
| `KALMAN_Q_NOISE` | `1e-12` | How much the drift is expected to change per step (very low = trusts physics) |
| `KALMAN_R_NOISE` | `1e-10` | How noisy the measurements are (higher = ignores jitter) |
| `DETECTION_THRESHOLD_US` | `200` | Residual error above this (µs) → ANOMALY |
| `WARMUP_PACKETS` | `10` | How many messages before classification starts |
| `AUTOMOTIVE_ECUS` | List of 6 ECUs | The ECU configurations used in dataset generation |

**You would edit this file when:**
- You want to test a different threshold (e.g., 100 µs instead of 200 µs)
- You are connecting to a real CAN interface (change `CAN_INTERFACE`)
- You want the filter to be more/less aggressive (adjust Q and R)

---

### `logger.py` — Structured Logging

**What it does:**  
Sets up a logging system used by other modules. Instead of `print()` statements, modules call `log.info()`, `log.warning()`, etc. This gives each message a timestamp, severity level, and module name. Logs go to:
1. The terminal (with colour coding)
2. A file called `sentinel.log` (rotated automatically when it reaches 1 MB)

**How to use it in another module:**
```python
from logger import get_logger
log = get_logger(__name__)

log.info("System started")
log.warning("ANOMALY detected on CAN-ID 0x100")
log.error("Cannot bind to vcan0")
```

**Colour scheme:**
- 🔵 DEBUG — Detailed internal information
- 🟢 INFO — Normal operation
- 🟡 WARNING — ANOMALY events, non-fatal issues
- 🔴 ERROR — Fatal errors

---

### `can_receiver.py` — CAN Socket & Kernel Timestamp Tap

**What it does:**  
Opens a raw Linux CAN socket, enables microsecond-precision kernel timestamping, and receives CAN frames with their arrival timestamps. This is the lowest-level component — it talks directly to the Linux kernel.

**Key class:** `CANReceiver`

| Method | Description |
|--------|-------------|
| `__init__(interface)` | Opens socket, enables SO_TIMESTAMP, binds to interface |
| `receive()` | Blocks until a frame arrives; returns `(can_id, data, timestamp_s)` |
| `close()` | Closes the socket |

**Important:** This module only works on Linux because it uses:
- `PF_CAN` socket family (Linux-specific)
- `SO_TIMESTAMP` socket option (standard POSIX, but CAN sockets are Linux-only)

**What `SO_TIMESTAMP` does:**  
When enabled, the Linux kernel records *exactly when the CAN frame arrived at the network interface* — before your Python code even runs. This timestamp is more precise than calling `time.time()` yourself, because it avoids the delay caused by the OS scheduler running other programs before your code gets to execute.

**Example output from `receive()`:**
```
can_id = 0x100
data   = b'\xDE\xAD\xBE\xEF\x00\x00\x00\x00'
t_kernel = 1712591234.567891   # seconds since epoch, microsecond precision
```

---

### `drift_tracker.py` — The Kalman Filter Engine

**What it does:**  
Implements the mathematical heart of Sentinel-T. For each ECU (identified by its CAN ID), a `DriftTracker` object maintains a running estimate of that ECU's clock state using a **2D Kalman Filter**.

**Key class:** `DriftTracker`

**State being tracked:**
```
x = [phase_offset,    ← how much the clock has drifted from nominal (seconds)
     frequency_drift] ← how fast the drift is changing (seconds per interval)
```

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `update(interval)` | Observed interval (seconds) | `(residual, drift)` | Core Kalman update step |
| `update_from_can_socket(timestamp)` | Kernel timestamp (float) | `(residual, drift)` | Computes interval internally then calls update() |
| `process_stream(intervals)` | Array of intervals | `(residuals, drifts)` | Batch processing for simulation |

**Understanding the output:**
- **`residual`** (in seconds) — How surprised the filter was by this measurement. Convert to µs by multiplying by 1,000,000. If consistently high → likely an attacker.
- **`drift`** (in seconds/interval) — The estimated clock drift rate. For a real ECU, this should be a smooth, slowly-changing value.

**How the Kalman Filter works (simplified):**

Every time a CAN message arrives, the filter does two things:

1. **Predict** — "Based on what I know, I predict the ECU's clock will have drifted by this much."
2. **Update** — "I just observed the actual interval. How wrong was my prediction? Update my estimate."

Over time, for a real ECU, the predictions become very accurate (small residuals). For an attacker whose timing is structurally different, the predictions are consistently wrong (large residuals).

---

### `sentinel_generator.py` — ECU/Attacker Interval Simulator

**What it does:**  
Generates synthetic CAN message interval sequences that simulate different types of senders. Used for testing and the offline demo.

**Key class:** `SentinelGenerator`

| Method | What it simulates | Typical residual after filter |
|--------|-------------------|------------------------------|
| `generate_real_ecu()` | Physical crystal: thermal drift + O-U jitter | **< 50 µs** |
| `generate_attacker()` | Perfect machine: zero variance | **< 50 µs** (indistinguishable without multi-feature) |
| `generate_smart_attacker()` | Software timer: Gaussian noise | **50–200 µs** |

**The `receiver_jitter` parameter:**  
All three generator methods accept a `receiver_jitter` parameter (in seconds). This simulates the noise added by the *receiving* computer's operating system — the scheduling latency that exists even when the sender is legitimate. Setting `receiver_jitter=0.00005` (50 µs) is a realistic default.

---

### `dataset_generator.py` — Automotive CAN Dataset Generator

**What it does:**  
Generates complete, realistic automotive CAN datasets containing traffic from multiple ECUs plus injected attack traffic. Datasets are saved as CSV files in the `datasets/` folder.

**Key class:** `AutomotiveCANGenerator`

**ECUs simulated:**

| CAN ID | Name | Interval | Safety-Critical |
|--------|------|----------|----------------|
| 0x100 | Steering_Angle | 10 ms | ✅ Yes |
| 0x101 | ABS_Brake | 20 ms | ✅ Yes |
| 0x200 | Engine_RPM | 100 ms | ❌ No |
| 0x201 | Vehicle_Speed | 100 ms | ❌ No |
| 0x300 | Fuel_Level | 500 ms | ❌ No |
| 0x400 | Dashboard_Lights | 1000 ms | ❌ No |

**Attack types:**

| Type | Description | Timing characteristic |
|------|-------------|----------------------|
| `"injection"` | Perfect machine sends at exact 10 ms | Zero jitter, zero drift |
| `"smart_injection"` | Software timer with Gaussian noise | Memoryless ±50 µs jitter |
| `"fuzzing"` | High-rate (1 ms) flood of random IDs/data | Very fast, random |
| `"replay"` | Re-transmits at nominal rate + 1.5 ms delay | Small jitter, fixed offset |

**Output CSV columns:**

| Column | Description |
|--------|-------------|
| `timestamp` | Simulated time (seconds from start) |
| `can_id` | CAN arbitration ID (hex integer) |
| `dlc` | Data length code (always 8) |
| `data` | Payload as hex string |
| `ecu_name` | Human-readable sender name |
| `label` | `"NORMAL"` or `"ATTACK"` (ground truth) |

---

### `dataset_validator.py` — Batch Detection Validator

**What it does:**  
Replays a dataset CSV file through the Kalman filter pipeline and computes classification performance metrics.

**Key class:** `DatasetValidator`

**Metrics computed:**

| Metric | Formula | What it means |
|--------|---------|----------------|
| Accuracy | (TP+TN)/(TP+TN+FP+FN) | Overall correct classification rate |
| Precision | TP/(TP+FP) | Of all ATTACK predictions, how many were right |
| Recall (TPR) | TP/(TP+FN) | Of all actual attacks, how many were detected |
| F1-Score | 2·(P·R)/(P+R) | Harmonic mean of Precision and Recall |
| False Positive Rate | FP/(FP+TN) | How often a normal message is flagged as attack |

**True Positive (TP):** Attack message correctly classified as ATTACK  
**True Negative (TN):** Normal message correctly classified as NORMAL  
**False Positive (FP):** Normal message wrongly classified as ATTACK (false alarm)  
**False Negative (FN):** Attack message wrongly classified as NORMAL (missed attack)

---

### `live_sentinel.py` — Real-Time Live Monitor

**What it does:**  
The main operational entry point for live deployment. Opens the CAN socket, continuously receives frames, runs each through its per-ECU DriftTracker, and prints a colour-coded status dashboard.

**Terminal output format:**
```
ID     | Drift (ppm)  | Error (us)   | Status
0x100  |       -0.12  |       0.47   | PHYSICAL   ← green
0x666  |       12.34  |     421.88   | ANOMALY    ← red
0x100  |       -0.08  |       0.53   | PHYSICAL   ← green
```

**Status codes:**

| Status | Meaning | Colour |
|--------|---------|--------|
| `WARMUP` | Filter is still converging (first 10 packets) | Yellow |
| `PHYSICAL` | Residual < 200 µs → hardware clock behaviour | Green |
| `ANOMALY` | Residual ≥ 200 µs → likely software attack | Red |

**ANOMALY events are also written to `sentinel.log`** as WARNING-level log entries, so you can review attack history after a session.

---

### `demo.py` — Offline Simulation Demo

**What it does:**  
Runs a complete three-stream detection scenario in pure Python, with no CAN hardware, no virtual interface, and no root access required. Works on any operating system.

**What it demonstrates:**
1. A `Real_ECU` stream (physical drift + O-U jitter) → classified PHYSICAL
2. A `Dumb_Attacker` stream (perfectly periodic) → classified PHYSICAL (cannot be distinguished by timing alone)
3. A `Smart_Attacker` stream (Gaussian noise jitter) → ANOMALY events detected

**Output:**
- Console table showing classification counts and verdict
- `demo_output.png` — three-panel plot of residuals over time

---

### `stress_test_v2.py` — OS Jitter Robustness Test

**What it does:**  
Tests how well the Kalman filter performs under different levels of operating system scheduling noise. Sweeps through jitter values and computes the Signal-to-Noise Ratio (SNR) at each level.

**Run it with:**
```bash
python stress_test_v2.py
```

**Output:**
- `stress_test_results.png` — Three-panel plot: drift estimates, instantaneous residuals, smoothed residuals
- Console printout of mean residuals and SNR ratio

---

### `visualize_results.py` — Performance Charts Generator

**What it does:**  
Generates publication-quality performance charts from dataset validation results. Requires the `datasets/` folder to be populated first (run `dataset_generator.py` then `dataset_validator.py`).

**Charts generated:**
- `validation_results.png` — 6-panel overview: accuracy bars, residual distributions, confusion matrix, detection rates, dataset composition, summary table
- `roc_curve.png` — ROC-style curve showing true positive rate vs. false positive rate at different thresholds

---

### `simulate_traffic.py` — CAN Traffic Simulator

**What it does:**  
Sends simulated CAN frames to a live `vcan0` interface. Useful for testing the live monitor with a controlled "smart attacker" pattern (Gaussian jitter).

**Requires:** Active `vcan0` interface (Linux only)

---

### `app.py` — Original Proof-of-Concept

**What it does:**  
The original single-file demonstration script. Generates 5,000 samples from three senders (attacker, smart attacker, real ECU), computes cumulative clock skew, and saves a comparison plot. This was the first prototype that proved the concept.

**Output files:**
- `sentinel_physics_data.csv` — Raw interval data
- `sentinel_gap.png` — Cumulative skew comparison chart

---

### `tests/test_sentinel.py` — Automated Test Suite

**What it does:**  
Contains 24 `pytest` unit tests that verify the correct behaviour of the `DriftTracker` and `SentinelGenerator` classes, and validates the core detection hypothesis (smart attacker residuals are measurably higher than real ECU residuals).

**Test groups:**

| Class | Tests | What they check |
|-------|-------|----------------|
| `TestDriftTrackerInit` | 4 | Initial state, matrix shapes |
| `TestDriftTrackerUpdate` | 6 | Update counting, residual values, convergence |
| `TestDriftTrackerSocketUpdate` | 3 | Timestamp-based update path |
| `TestSentinelGenerator` | 7 | Lengths, constant check, jitter effect |
| `TestDetectionCapability` | 4 | End-to-end: ECU < threshold, SNR > 1 |

---

## Part 4 — How to Run Each Script

### Quick Reference

| Task | Command | Hardware needed? |
|------|---------|-----------------|
| Offline demo (recommended first run) | `python demo.py` | ❌ No |
| Run all unit tests | `pytest tests/ -v` | ❌ No |
| Generate benchmark datasets | `python dataset_generator.py` | ❌ No |
| Validate datasets | `python dataset_validator.py` | ❌ No |
| Generate performance charts | `python visualize_results.py` | ❌ No |
| Run stress test | `python stress_test_v2.py` | ❌ No |
| Original proof-of-concept | `python app.py` | ❌ No |
| Live monitor | `python live_sentinel.py` | ✅ Linux + vcan0 |
| Send simulated traffic | `python simulate_traffic.py` | ✅ Linux + vcan0 |

---

### Scenario A: First-Time Demo (Any Platform)

This is the **recommended starting point** for anyone new to the project.

```bash
# 1. Activate your virtual environment
source .venv/bin/activate

# 2. Run the offline demo
python demo.py
```

**Expected output:**
```
2026-04-08T12:00:00 [__main__] INFO Sentinel-T Offline Demo starting …
...
=================================================================
  SENTINEL-T OFFLINE DEMO  |  threshold = 200 µs
=================================================================
Stream                 |   PHYSICAL |  ANOMALY |  WARMUP
-----------------------------------------------------------------
Real_ECU               |        491 |        0 |       9  ✅ SAFE
Dumb_Attacker          |        491 |        0 |       9  ✅ SAFE
Smart_Attacker         |        483 |        8 |       9  🚨 ATTACK DETECTED
=================================================================

✅ Plot saved → demo_output.png
```

Open `demo_output.png` to see the residual plots.

---

### Scenario B: Generate and Validate Datasets

This creates synthetic datasets, runs detection, and produces charts.

```bash
# Step 1: Generate the datasets (creates datasets/ folder with 5 CSV files)
python dataset_generator.py

# Step 2: Run detection on each dataset (adds *_results.csv files)
python dataset_validator.py

# Step 3: Generate performance charts
python visualize_results.py
```

**Files produced:**
- `datasets/normal.csv` — Baseline traffic only
- `datasets/injection_attack.csv` — With perfect injector
- `datasets/smart_attack.csv` — With smart injector
- `datasets/fuzzing_attack.csv` — With fuzzing attack
- `datasets/replay_attack.csv` — With replay attack
- `datasets/*_results.csv` — Per-message classification results
- `validation_results.png` — 6-panel chart
- `roc_curve.png` — Threshold sensitivity curve

---

### Scenario C: Live Monitor (Linux + vcan0 Required)

**Terminal 1 — Start the monitor:**
```bash
python live_sentinel.py
```

**Terminal 2 — Simulate a legitimate ECU (100 Hz):**
```bash
cangen vcan0 -g 10 -I 100
```

**Terminal 3 — Simulate an attacker:**
```bash
while true; do cansend vcan0 666#DEADBEEF; sleep 0.01; done
```

**What you should see in Terminal 1:**
```
ID     | Drift (ppm)  | Error (us)   | Status
0x100  |       -0.08  |       0.53   | PHYSICAL
0x100  |       -0.09  |       0.49   | PHYSICAL
0x666  |       14.22  |     534.11   | ANOMALY
0x100  |       -0.07  |       0.51   | PHYSICAL
0x666  |       -8.91  |     421.88   | ANOMALY
```

ECUs at 0x100 stay GREEN (PHYSICAL). The attacker at 0x666 stays RED (ANOMALY).

---

### Scenario D: Generate the PowerPoint Presentation

```bash
python generate_presentation.py
```

This creates `Sentinel_T_Presentation.pptx` in the project root directory.

---

## Part 5 — Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

**Expected output (all 24 tests should pass):**
```
tests/test_sentinel.py::TestDriftTrackerInit::test_default_state_is_zero PASSED
tests/test_sentinel.py::TestDriftTrackerInit::test_update_count_starts_at_zero PASSED
...
24 passed in 0.57s
```

### Run a Specific Test Class

```bash
pytest tests/ -v -k "TestDetectionCapability"
```

### Run with Coverage Report (if pytest-cov is installed)

```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

---

## Part 6 — Configuration Reference

All settings are in `config.py`. Here is a guide to what to change for common scenarios:

### Change the Detection Threshold

More sensitive (fewer missed attacks, more false alarms):
```python
DETECTION_THRESHOLD_US = 100   # stricter
```

Less sensitive (fewer false alarms, more missed attacks):
```python
DETECTION_THRESHOLD_US = 500   # relaxed
```

### Connect to a Real CAN Interface

If your machine has a CAN adapter (e.g., PEAK PCAN-USB) showing as `can0`:
```python
CAN_INTERFACE = "can0"
```

### Adjust the Kalman Filter

More trust in the physics model (better for stable environments):
```python
KALMAN_Q_NOISE = 1e-13   # lower = slower drift estimate
KALMAN_R_NOISE = 1e-9    # higher = ignore more measurement noise
```

More responsive (better for noisy or fast-changing environments):
```python
KALMAN_Q_NOISE = 1e-11   # higher = more responsive
KALMAN_R_NOISE = 1e-11   # lower = trust measurements more
```

### Change the Log Level

See DEBUG messages (very verbose, useful for development):
```python
LOG_LEVEL = "DEBUG"
```

Only see errors:
```python
LOG_LEVEL = "ERROR"
```

---

## Part 7 — Troubleshooting

### Problem: `ModuleNotFoundError: No module named 'numpy'`

**Solution:** You forgot to activate the virtual environment or install packages.
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Problem: `OSError: [Errno 1] Operation not permitted` when running `live_sentinel.py`

**Solution:** Raw CAN sockets require root access, or your user needs to be in the `netdev` group.
```bash
sudo python live_sentinel.py
# OR
sudo ip link set vcan0 group 0
sudo setcap cap_net_raw+ep $(which python3)
```

### Problem: `OSError: Could not bind to vcan0`

**Solution:** The virtual CAN interface is not set up.
```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

If `modprobe vcan` fails with `FATAL: Module vcan not found`, your kernel does not have the vcan module:
```bash
sudo apt install linux-modules-extra-$(uname -r)
```

### Problem: `No result files found in datasets/`

**Solution:** You need to run the generator and validator first:
```bash
python dataset_generator.py
python dataset_validator.py
python visualize_results.py
```

### Problem: All Smart Attacker messages are classified as PHYSICAL

This is not necessarily a bug. The smart attacker uses Gaussian jitter (±50 µs). With the default threshold of 200 µs, most of its messages fall below the threshold. Anomalies only appear when the Gaussian noise occasionally produces a large deviation. 

To detect the smart attacker more aggressively, lower the threshold:
```python
# In config.py
DETECTION_THRESHOLD_US = 50
```

Note: this will also increase false positives on legitimate ECUs.

### Problem: `pytest` not found

```bash
pip install pytest
```

### Problem: `demo_output.png` is not being saved

Make sure matplotlib is installed:
```bash
pip install matplotlib
```

---

## Part 8 — Glossary

| Term | Definition |
|------|-----------|
| **CAN Bus** | Controller Area Network — the main communication network inside a vehicle |
| **ECU** | Electronic Control Unit — a computer inside the car (e.g., engine controller, brake controller) |
| **CAN ID** | The identifier on a CAN message. Determines arbitration priority; does NOT identify the sender |
| **Intrusion Detection System (IDS)** | A system that monitors network traffic and raises alerts when it detects attacks |
| **Kalman Filter** | A recursive algorithm that estimates hidden state variables from noisy measurements |
| **Phase Offset (φ)** | How much an ECU's clock has drifted from the ideal timing (in seconds) |
| **Frequency Drift (φ̇)** | How fast the phase offset is changing — the clock's deviation from nominal frequency |
| **Residual** | The difference between what the Kalman filter predicted and what was actually measured |
| **SO_TIMESTAMP** | A Linux kernel socket option that records the exact time a network packet arrived |
| **SocketCAN** | Linux kernel subsystem for CAN bus — provides a standard socket API (like TCP/IP) for CAN |
| **vcan0** | Virtual CAN interface — software-simulated CAN bus for testing without hardware |
| **Ornstein-Uhlenbeck Process** | A mean-reverting stochastic process that models the bounded, correlated jitter of a crystal oscillator |
| **Thermal Drift** | The change in clock frequency caused by temperature variations in the ECU's environment |
| **Process Noise (Q)** | Kalman filter parameter: expected rate of change of the hidden state |
| **Measurement Noise (R)** | Kalman filter parameter: expected noise in each measurement |
| **SNR** | Signal-to-Noise Ratio — ratio of attacker residual to ECU residual; must be > 1 for detection to work |
| **TPR** | True Positive Rate (also Recall or Detection Rate) — fraction of attacks correctly detected |
| **FPR** | False Positive Rate — fraction of legitimate messages wrongly flagged as attacks |
| **ppm** | Parts Per Million — unit for very small frequency deviations (1 ppm = 0.0001%) |
| **OBD-II** | On-Board Diagnostics port — a standardised connector under the dashboard that provides access to the CAN bus |
| **AUTOSAR SecOC** | Automotive Open System Architecture — Secure Onboard Communication standard |

---

*End of Technical Manual — Project Sentinel-T*
