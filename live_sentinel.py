import time
from can_receiver import CANReceiver
from drift_tracker import DriftTracker

def run_live_monitor(interface="vcan0"):
    """
    Real-time monitoring engine using Kernel Timestamps and 
    State Space Modeling to detect clock drift.
    """
    print(f"--- Sentinel-T Live Monitor ---")
    print(f"Interface: {interface}")
    print(f"Model: Kalman Filter (R=1e-10, Q=1e-12)")
    print(f"{'ID':<6} | {'Drift (ppm)':<12} | {'Error (us)':<10} | {'Status':<10}")
    print("-" * 50)

    try:
        receiver = CANReceiver(interface)
        # We initialize trackers per CAN ID dynamically
        trackers = {}
        
        while True:
            # Note: can_receiver.py has receive_frame() as the method name
            can_id, data, t_kernel = receiver.receive()
            
            if t_kernel == 0.0:
                continue

            if can_id not in trackers:
                trackers[can_id] = DriftTracker(q_noise=1e-12, r_noise=1e-10)
            
            # Update the specific tracker for this sender
            residual, drift = trackers[can_id].update_from_can_socket(t_kernel)
            
            # Metrics
            drift_ppm = drift * 1e8
            res_us = abs(residual) * 1e6
            
            # Thresholding Logic (1000us as per Demo Safety Directive)
            if trackers[can_id].update_count < 10:
                status = "\033[93mWARMUP\033[0m"   # Yellow
            elif res_us < 200:
                status = "\033[92mPHYSICAL\033[0m" # Green
            else:
                status = "\033[91mANOMALY\033[0m"  # Red

            # Log to console
            print(f"0x{can_id:03x} | {drift_ppm:10.2f} | {res_us:8.2f} | {status}")

    except KeyboardInterrupt:
        print("\n[!] Monitor stopped by user.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    finally:
        if 'receiver' in locals():
            receiver.close()

if __name__ == "__main__":
    # Note: Requires vcan0 to be set up:
    # sudo modprobe vcan
    # sudo ip link add dev vcan0 type vcan
    # sudo ip link set up vcan0
    run_live_monitor("vcan0")
