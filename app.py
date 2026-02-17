import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Force non-GUI backend
import matplotlib.pyplot as plt

# =========================
# CONFIGURATION
# =========================
NUM_SAMPLES = 5000
BASE_INTERVAL = 0.010  # 10ms (100Hz)

# =========================
# 1. ATTACKER (Perfect Machine)
# Zero entropy, zero drift
# =========================
def generate_attacker():
    return np.full(NUM_SAMPLES, BASE_INTERVAL)

# =========================
# 2. SMART ATTACKER (Gaussian Noise)
# Random but memoryless
# =========================
def generate_smart_attacker():
    noise = np.random.normal(0, 0.00005, NUM_SAMPLES)
    return BASE_INTERVAL + noise

# =========================
# 3. REAL ECU (Physical Clock)
# Thermal drift + O-U jitter
# =========================
def generate_real_ecu():
    intervals = []

    # Thermal drift (slow, correlated)
    thermal_drift = np.sin(np.linspace(0, 4, NUM_SAMPLES)) * 0.00002

    # Ornstein-Uhlenbeck parameters
    current_jitter = 0.0
    theta = 0.15
    sigma = 0.00001

    for i in range(NUM_SAMPLES):
        current_jitter += -theta * current_jitter + sigma * np.random.normal()
        intervals.append(BASE_INTERVAL + current_jitter + thermal_drift[i])

    return np.array(intervals)

# =========================
# EXECUTION
# =========================
df = pd.DataFrame({
    "Attacker_Static": generate_attacker(),
    "Attacker_Smart": generate_smart_attacker(),
    "Real_ECU": generate_real_ecu()
})

# Save raw data
df.to_csv("sentinel_physics_data.csv", index=False)

# =========================
# ANALYSIS: CUMULATIVE CLOCK SKEW
# =========================
skew_real = np.cumsum(df["Real_ECU"] - BASE_INTERVAL)
skew_smart = np.cumsum(df["Attacker_Smart"] - BASE_INTERVAL)

# =========================
# VISUALIZATION
# =========================
plt.figure(figsize=(12, 6))

plt.plot(
    skew_real,
    label="Real ECU (Physical Drift)",
    linewidth=2
)

plt.plot(
    skew_smart,
    label="Smart Attacker (Random Noise)",
    linestyle="--",
    alpha=0.7
)

plt.title("Physical Clock Skew vs Statistical Noise")
plt.xlabel("Message Count")
plt.ylabel("Cumulative Clock Drift (seconds)")
plt.legend()
plt.grid(True, alpha=0.3)

# Save figure instead of showing
plt.savefig("sentinel_gap.png", dpi=150, bbox_inches="tight")
plt.close()

print("[OK] Data saved  -> sentinel_physics_data.csv")
print("[OK] Figure saved -> sentinel_gap.png")
print("[RESULT] Physics drifts. Math cancels. Detection gap exposed.")
