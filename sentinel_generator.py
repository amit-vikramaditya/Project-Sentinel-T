import numpy as np
import pandas as pd

class SentinelGenerator:
    """
    Simulates various types of CAN bus message arrival patterns to demonstrate
    physical clock fingerprints, now including receiver-side OS jitter.
    """
    def __init__(self, num_samples=5000, base_interval=0.010):
        self.num_samples = num_samples
        self.base_interval = base_interval

    def _apply_receiver_jitter(self, intervals, jitter_std):
        """
        Simulates OS-level latency (scheduling/interrupts) at the receiver.
        Adds uncorrelated noise to the intervals.
        """
        if jitter_std <= 0:
            return intervals
        
        noise = np.random.normal(0, jitter_std, len(intervals))
        return intervals + noise

    def generate_attacker(self, receiver_jitter=0.0):
        """Perfect machine: zero entropy, zero drift."""
        intervals = np.full(self.num_samples, self.base_interval)
        return self._apply_receiver_jitter(intervals, receiver_jitter)

    def generate_smart_attacker(self, noise_std=0.00005, receiver_jitter=0.0):
        """Random but memoryless: Gaussian noise around the nominal interval."""
        noise = np.random.normal(0, noise_std, self.num_samples)
        intervals = self.base_interval + noise
        return self._apply_receiver_jitter(intervals, receiver_jitter)

    def generate_real_ecu(self, receiver_jitter=0.0):
        """
        Physical Clock: Simulates thermal drift (slow correlation) 
        and O-U jitter (mean-reverting process).
        """
        intervals = []
        # Thermal drift (slow, correlated sine wave)
        thermal_drift = np.sin(np.linspace(0, 4, self.num_samples)) * 0.00002

        # Ornstein-Uhlenbeck parameters for jitter
        current_jitter = 0.0
        theta = 0.15
        sigma = 0.00001

        for i in range(self.num_samples):
            current_jitter += -theta * current_jitter + sigma * np.random.normal()
            intervals.append(self.base_interval + current_jitter + thermal_drift[i])

        intervals = np.array(intervals)
        return self._apply_receiver_jitter(intervals, receiver_jitter)

if __name__ == "__main__":
    gen = SentinelGenerator()
    # Example with 50us receiver jitter
    df = pd.DataFrame({
        "Attacker_Static": gen.generate_attacker(receiver_jitter=0.00005),
        "Attacker_Smart": gen.generate_smart_attacker(receiver_jitter=0.00005),
        "Real_ECU": gen.generate_real_ecu(receiver_jitter=0.00005)
    })
    df.to_csv("sentinel_physics_data_jittered.csv", index=False)
    print(f"Generated {gen.num_samples} samples with receiver jitter.")

# --- MODULE LEVEL CONVENIENCE FUNCTIONS ---
def generate_smart_attacker(num_samples=5000, noise_std=0.00005):
    return SentinelGenerator(num_samples=num_samples).generate_smart_attacker(noise_std=noise_std)

def generate_real_ecu(num_samples=5000):
    return SentinelGenerator(num_samples=num_samples).generate_real_ecu()