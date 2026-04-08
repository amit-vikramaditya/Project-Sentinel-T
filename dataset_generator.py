"""
Realistic Automotive CAN Dataset Generator
Simulates real vehicle traffic patterns with labeled attack scenarios.

Based on patterns from actual automotive CAN buses:
- Engine Controller: 500ms interval
- ABS/Brake: 20ms interval (safety-critical)
- Steering: 10ms interval (safety-critical)
- Infotainment: 100ms interval
- Dashboard: 1000ms interval
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
from config import DEFAULT_DURATION_S, AUTOMOTIVE_ECUS, ECU_OU_THETA, ECU_OU_SIGMA, ECU_THERMAL_AMPLITUDE, SMART_ATTACKER_NOISE_STD, REPLAY_JITTER_STD

class AutomotiveCANGenerator:
    """Generates realistic multi-ECU CAN traffic with attacks."""
    
    def __init__(self, duration_seconds=DEFAULT_DURATION_S):
        self.duration = duration_seconds
        self.start_time = 0.0
        
        # Realistic ECU configurations (from config.py)
        self.ecus = AUTOMOTIVE_ECUS
    
    def _generate_ecu_traffic(self, ecu_config, attack_window=None):
        """Generate traffic for a single ECU with realistic clock drift."""
        messages = []
        current_time = self.start_time
        interval = ecu_config["interval"]
        
        # Physical clock characteristics
        thermal_drift = np.sin(np.linspace(0, 2*np.pi, int(self.duration/interval))) * 0.00002
        current_jitter = 0.0
        theta = 0.15
        sigma = 0.00001
        
        msg_count = 0
        while current_time < self.duration:
            # Ornstein-Uhlenbeck jitter (mean-reverting)
            current_jitter += -theta * current_jitter + sigma * np.random.normal()
            
            # Add thermal drift if within bounds
            drift_component = thermal_drift[min(msg_count, len(thermal_drift)-1)] if msg_count < len(thermal_drift) else 0
            
            # Check if this is during attack window
            is_attack = False
            if attack_window:
                if attack_window[0] <= current_time <= attack_window[1]:
                    is_attack = True
            
            actual_interval = interval + current_jitter + drift_component
            current_time += actual_interval
            
            # Generate realistic payload based on ECU type
            data = self._generate_payload(ecu_config["name"], current_time)
            
            messages.append({
                "timestamp": current_time,
                "can_id": ecu_config["id"],
                "dlc": 8,
                "data": data,
                "ecu_name": ecu_config["name"],
                "label": "ATTACK" if is_attack else "NORMAL"
            })
            
            msg_count += 1
        
        return messages
    
    def _generate_payload(self, ecu_name, timestamp):
        """Generate realistic data payloads based on ECU function."""
        if ecu_name == "Steering_Angle":
            # Steering angle: -180 to +180 degrees
            angle = int(90 * np.sin(timestamp * 0.5))  # Simulated turning
            return f"{angle:08X}"
        
        elif ecu_name == "ABS_Brake":
            # Brake pressure: 0-255
            pressure = int(50 + 30 * np.sin(timestamp * 0.3))  # Simulated braking
            return f"{pressure:02X}000000"
        
        elif ecu_name == "Engine_RPM":
            # RPM: 800-6000
            rpm = int(1500 + 1000 * np.sin(timestamp * 0.1))
            return f"{rpm:04X}0000"
        
        elif ecu_name == "Vehicle_Speed":
            # Speed: 0-200 km/h
            speed = int(60 + 40 * np.sin(timestamp * 0.05))
            return f"{speed:02X}000000"
        
        elif ecu_name == "Fuel_Level":
            # Fuel: 0-100%
            fuel = max(0, int(80 - timestamp * 0.01))  # Slowly decreasing
            return f"{fuel:02X}000000"
        
        else:  # Dashboard
            # Status bits
            return "A5A5A5A5"
    
    def _inject_attack(self, can_id, start_time, end_time, attack_type="injection"):
        """Generate attack traffic."""
        messages = []
        
        if attack_type == "injection":
            # Perfect timing attacker (no drift)
            current_time = start_time
            interval = 0.010  # 10ms perfectly
            
            while current_time < end_time:
                messages.append({
                    "timestamp": current_time,
                    "can_id": can_id,
                    "dlc": 8,
                    "data": "DEADBEEF",
                    "ecu_name": "ATTACKER",
                    "label": "ATTACK"
                })
                current_time += interval  # NO jitter, NO drift
        
        elif attack_type == "smart_injection":
            # Smart attacker with Gaussian noise
            current_time = start_time
            base_interval = 0.010
            
            while current_time < end_time:
                noise = np.random.normal(0, 0.00005)
                messages.append({
                    "timestamp": current_time,
                    "can_id": can_id,
                    "dlc": 8,
                    "data": "DEADBEEF",
                    "ecu_name": "SMART_ATTACKER",
                    "label": "ATTACK"
                })
                current_time += base_interval + noise  # Gaussian jitter only
        
        elif attack_type == "replay":
            # Replay attack: simulates an attacker that re-transmits messages
            # at the victim ECU's nominal rate but with a fixed propagation
            # delay (capture-to-replay latency) and a small amount of jitter
            # from the replayer's own software clock.
            current_time = start_time
            base_interval = 0.010
            replay_offset = 0.0015  # 1.5 ms constant capture-to-replay delay

            while current_time < end_time:
                jitter = np.random.normal(0, REPLAY_JITTER_STD)
                messages.append({
                    "timestamp": current_time + replay_offset,
                    "can_id": can_id,
                    "dlc": 8,
                    "data": "CAFEBABE",   # replayed payload marker
                    "ecu_name": "REPLAYER",
                    "label": "ATTACK"
                })
                current_time += base_interval + jitter

        elif attack_type == "fuzzing":
            # High-rate random data flood
            current_time = start_time
            interval = 0.001  # 1ms - very fast
            
            while current_time < end_time:
                random_id = random.choice([0x666, 0x777, 0x888])
                random_data = f"{random.randint(0, 0xFFFFFFFF):08X}"
                messages.append({
                    "timestamp": current_time,
                    "can_id": random_id,
                    "dlc": 8,
                    "data": random_data,
                    "ecu_name": "FUZZER",
                    "label": "ATTACK"
                })
                current_time += interval
        
        return messages
    
    def generate_dataset(self, attack_scenario=None):
        """
        Generate complete dataset with optional attack.
        
        attack_scenario format:
        {
            "type": "injection" | "smart_injection" | "fuzzing",
            "target_id": 0x100,
            "start_time": 100,
            "end_time": 150
        }
        """
        all_messages = []
        
        # Generate normal traffic from all ECUs
        for ecu in self.ecus:
            attack_window = None
            if attack_scenario and ecu["id"] == attack_scenario.get("target_id"):
                attack_window = (attack_scenario["start_time"], attack_scenario["end_time"])
            
            ecu_messages = self._generate_ecu_traffic(ecu, attack_window)
            all_messages.extend(ecu_messages)
        
        # Inject attack traffic if specified
        if attack_scenario:
            attack_messages = self._inject_attack(
                attack_scenario["target_id"],
                attack_scenario["start_time"],
                attack_scenario["end_time"],
                attack_scenario["type"]
            )
            all_messages.extend(attack_messages)
        
        # Sort by timestamp
        all_messages.sort(key=lambda x: x["timestamp"])
        
        # Create DataFrame
        df = pd.DataFrame(all_messages)
        
        # Add statistics
        normal_count = len(df[df["label"] == "NORMAL"])
        attack_count = len(df[df["label"] == "ATTACK"])
        
        print(f"✅ Generated {len(df)} CAN messages:")
        print(f"   - Normal traffic: {normal_count} messages")
        print(f"   - Attack traffic: {attack_count} messages")
        print(f"   - Duration: {self.duration}s")
        print(f"   - ECUs: {len(self.ecus)}")
        
        return df


def create_benchmark_datasets():
    """Create standard benchmark datasets for testing."""
    
    datasets = {}
    
    # Dataset 1: Normal Traffic Only (Baseline)
    print("\n📊 Dataset 1: Normal Traffic")
    gen = AutomotiveCANGenerator(duration_seconds=60)
    datasets["normal"] = gen.generate_dataset()
    
    # Dataset 2: Injection Attack
    print("\n📊 Dataset 2: Injection Attack")
    gen = AutomotiveCANGenerator(duration_seconds=120)
    attack = {
        "type": "injection",
        "target_id": 0x100,  # Targeting steering
        "start_time": 60,
        "end_time": 90
    }
    datasets["injection_attack"] = gen.generate_dataset(attack)
    
    # Dataset 3: Smart Injection Attack
    print("\n📊 Dataset 3: Smart Injection Attack")
    gen = AutomotiveCANGenerator(duration_seconds=120)
    attack = {
        "type": "smart_injection",
        "target_id": 0x101,  # Targeting ABS
        "start_time": 60,
        "end_time": 90
    }
    datasets["smart_attack"] = gen.generate_dataset(attack)
    
    # Dataset 4: Fuzzing Attack
    print("\n📊 Dataset 4: Fuzzing Attack")
    gen = AutomotiveCANGenerator(duration_seconds=120)
    attack = {
        "type": "fuzzing",
        "target_id": 0x666,
        "start_time": 60,
        "end_time": 70  # Short burst
    }
    datasets["fuzzing_attack"] = gen.generate_dataset(attack)

    # Dataset 5: Replay Attack
    print("\n📊 Dataset 5: Replay Attack")
    gen = AutomotiveCANGenerator(duration_seconds=120)
    attack = {
        "type": "replay",
        "target_id": 0x100,   # Replaying steering messages
        "start_time": 60,
        "end_time": 90
    }
    datasets["replay_attack"] = gen.generate_dataset(attack)
    
    return datasets


if __name__ == "__main__":
    print("=" * 60)
    print("  Automotive CAN Dataset Generator")
    print("  Realistic Multi-ECU Traffic with Attack Scenarios")
    print("=" * 60)
    
    # Create benchmark datasets
    datasets = create_benchmark_datasets()
    
    # Save to CSV
    import os
    os.makedirs("datasets", exist_ok=True)
    
    for name, df in datasets.items():
        filename = f"datasets/{name}.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Saved: {filename}")
    
    print("\n" + "=" * 60)
    print("✅ All datasets generated successfully!")
    print("=" * 60)
