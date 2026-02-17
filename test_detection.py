import numpy as np
import matplotlib.pyplot as plt
from sentinel_generator import SentinelGenerator
from drift_tracker import DriftTracker

def run_stress_test(receiver_jitter_us=50):
    jitter_s = receiver_jitter_us / 1e6
    print(f"--- Running OS Jitter Stress Test ({receiver_jitter_us}us) ---")
    
    gen = SentinelGenerator(num_samples=3000)
    
    # 1. Generate Data with Receiver Jitter
    real_ecu = gen.generate_real_ecu(receiver_jitter=jitter_s)
    smart_attacker = gen.generate_smart_attacker(receiver_jitter=jitter_s)
    
    # 2. Initialize Trackers
    # We increase R (measurement noise) to account for the noisier environment
    tracker_ecu = DriftTracker(q_noise=1e-12, r_noise=jitter_s**2)
    tracker_smart = DriftTracker(q_noise=1e-12, r_noise=jitter_s**2)
    
    # 3. Process Streams
    res_ecu, drift_ecu = tracker_ecu.process_stream(real_ecu)
    res_smart, drift_smart = tracker_smart.process_stream(smart_attacker)
    
    # 4. Visualization
    plt.figure(figsize=(14, 10))
    
    # Estimated Drift
    plt.subplot(3, 1, 1)
    plt.plot(drift_ecu, label="Est. Drift (Real ECU)", color='green')
    plt.plot(drift_smart, label="Est. Drift (Smart Attacker)", color='red', linestyle='--', alpha=0.5)
    plt.title(f"Clock Drift Tracking (Receiver Jitter: {receiver_jitter_us}us)")
    plt.ylabel("Drift Rate")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Raw Residuals
    plt.subplot(3, 1, 2)
    plt.scatter(range(len(res_ecu)), np.abs(res_ecu), s=1, color='green', alpha=0.3, label="ECU Residuals")
    plt.scatter(range(len(res_smart)), np.abs(res_smart), s=1, color='red', alpha=0.3, label="Smart Residuals")
    plt.title("Instantaneous Residuals (Absolute)")
    plt.ylabel("Error (s)")
    plt.legend()
    
    # Moving Average Residuals (to see the signal through the noise)
    window = 50
    ma_ecu = np.convolve(np.abs(res_ecu), np.ones(window)/window, mode='valid')
    ma_smart = np.convolve(np.abs(res_smart), np.ones(window)/window, mode='valid')
    
    plt.subplot(3, 1, 3)
    plt.plot(ma_ecu, label=f"ECU MA({window})", color='green', linewidth=2)
    plt.plot(ma_smart, label=f"Smart MA({window})", color='red', linewidth=2)
    plt.title(f"Smoothed Residuals (Window={window})")
    plt.xlabel("Message Count")
    plt.ylabel("Mean Error (s)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("stress_test_results.png")
    print("[OK] Stress test results saved to stress_test_results.png")

    # Metrics
    mean_ecu = np.mean(np.abs(res_ecu))
    mean_smart = np.mean(np.abs(res_smart))
    ratio = mean_smart / mean_ecu
    
    print(f"Mean Residual Error (ECU):    {mean_ecu:.6e}")
    print(f"Mean Residual Error (Smart):  {mean_smart:.6e}")
    print(f"Detection Ratio (Smart/ECU):  {ratio:.2f}x")
    
    if ratio > 1.2:
        print(f"[RESULT] Success: The Gap persists at {ratio:.2f}x despite OS jitter.")
    else:
        print("[RESULT] Fail: The signal-to-noise ratio is too low for detection.")

if __name__ == "__main__":
    run_stress_test(receiver_jitter_us=50)