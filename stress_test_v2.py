import numpy as np
import matplotlib
matplotlib.use("Agg") # Headless
import matplotlib.pyplot as plt
from sentinel_generator import generate_smart_attacker, generate_real_ecu
from drift_tracker import DriftTracker

# --- CONFIGURATION ---
NUM_SAMPLES = 5000
# 10 microseconds of "Kernel Noise" (The benefit of SocketCAN SO_TIMESTAMP)
RECEIVER_JITTER_STD = 0.000010 

def add_jitter(intervals):
    """Simulates the Raspberry Pi reading packets late due to OS load."""
    noise = np.random.normal(0, RECEIVER_JITTER_STD, len(intervals))
    return intervals + noise

# --- GENERATE DATA ---
print("1. Generating streams...")
attacker_data = add_jitter(generate_smart_attacker(num_samples=NUM_SAMPLES))
physical_data = add_jitter(generate_real_ecu(num_samples=NUM_SAMPLES))

# --- RUN DETECTORS ---
print(f"2. Running Kalman Filters (Receiver Noise = {RECEIVER_JITTER_STD*1e6:.0f} us)...")

tracker_attacker = DriftTracker()
tracker_physical = DriftTracker()

_, drift_attacker = tracker_attacker.process_stream(attacker_data)
_, drift_physical = tracker_physical.process_stream(physical_data)

# --- METRIC: RESIDUAL ERROR (How confused is the filter?) ---
# We calculate the standard deviation of the drift estimate.
# Real hardware should have a stable (but moving) drift.
# Attackers should look like "White Noise" to the filter.
# We skip the first 100 samples (warm-up)
error_attacker = np.std(drift_attacker[100:])
error_physical = np.std(drift_physical[100:])

print("\n--- STRESS TEST RESULTS ---")
print(f"Attacker 'Stability' Metric: {error_attacker:.8f} (Higher is worse)")
print(f"Physical 'Stability' Metric: {error_physical:.8f} (Lower is better)")

ratio = error_attacker / error_physical
print(f"\nSignal-to-Noise Ratio (The Gap): {ratio:.2f}x")

if ratio > 1.5:
    print("VERDICT: SUCCESS. Physics is still visible through Linux noise.")
else:
    print("VERDICT: FAILURE. Linux noise killed the signal. We need C++.")

# --- VISUALIZATION ---
plt.figure(figsize=(10, 6))
plt.plot(drift_physical[100:], label='Real ECU Drift (Recovered)', color='green')
plt.plot(drift_attacker[100:], label='Attacker Drift (Noise)', color='red', alpha=0.5)
plt.title(f"Kalman Filter Output under {RECEIVER_JITTER_STD*1e6:.0f}us Jitter")
plt.legend()
plt.savefig("stress_test_v2.png")
print("[OK] Figure saved to stress_test_v2.png")