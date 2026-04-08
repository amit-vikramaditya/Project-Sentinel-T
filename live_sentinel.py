import time
from can_receiver import CANReceiver
from drift_tracker import DriftTracker
from logger import get_logger
from config import (
    CAN_INTERFACE,
    KALMAN_Q_NOISE,
    KALMAN_R_NOISE,
    DETECTION_THRESHOLD_US,
    WARMUP_PACKETS,
)

log = get_logger(__name__)

def run_live_monitor(interface=CAN_INTERFACE):
    """
    Real-time monitoring engine using Kernel Timestamps and 
    State Space Modeling to detect clock drift.
    """
    log.info("Sentinel-T Live Monitor starting on interface: %s", interface)
    log.info("Model: Kalman Filter  Q=%.0e  R=%.0e", KALMAN_Q_NOISE, KALMAN_R_NOISE)
    log.info("Detection threshold: %d µs  |  Warmup: %d packets",
             DETECTION_THRESHOLD_US, WARMUP_PACKETS)
    print(f"{'ID':<6} | {'Drift (ppm)':<12} | {'Error (us)':<10} | {'Status':<10}")
    print("-" * 50)

    try:
        receiver = CANReceiver(interface)
        # We initialize trackers per CAN ID dynamically
        trackers = {}
        
        while True:
            can_id, data, t_kernel = receiver.receive()
            
            if t_kernel == 0.0:
                continue

            if can_id not in trackers:
                trackers[can_id] = DriftTracker(q_noise=KALMAN_Q_NOISE, r_noise=KALMAN_R_NOISE)
                log.debug("New tracker created for CAN ID 0x%03x", can_id)
            
            # Update the specific tracker for this sender
            residual, drift = trackers[can_id].update_from_can_socket(t_kernel)
            
            # Metrics
            drift_ppm = drift * 1e8
            res_us = abs(residual) * 1e6
            
            # Thresholding Logic
            if trackers[can_id].update_count < WARMUP_PACKETS:
                status = "\033[93mWARMUP\033[0m"   # Yellow
            elif res_us < DETECTION_THRESHOLD_US:
                status = "\033[92mPHYSICAL\033[0m" # Green
            else:
                status = "\033[91mANOMALY\033[0m"  # Red
                log.warning("ANOMALY detected  CAN-ID=0x%03x  residual=%.1f µs", can_id, res_us)

            # Log to console
            print(f"0x{can_id:03x} | {drift_ppm:10.2f} | {res_us:8.2f} | {status}")

    except KeyboardInterrupt:
        log.info("Monitor stopped by user.")
    except Exception as e:
        log.error("Fatal error: %s", e)
    finally:
        if 'receiver' in locals():
            receiver.close()
            log.info("CAN socket closed.")

if __name__ == "__main__":
    # Note: Requires vcan0 to be set up:
    # sudo modprobe vcan
    # sudo ip link add dev vcan0 type vcan
    # sudo ip link set up vcan0
    run_live_monitor(CAN_INTERFACE)
