"""
demo.py – Offline Simulation Demo for Project Sentinel-T
=========================================================
Runs a complete clock-fingerprinting detection scenario entirely in software
(no CAN hardware or virtual interface required).

Usage:
    python demo.py

What it does:
  1. Simulates 500 CAN messages each from a real ECU, a dumb attacker, and
     a smart attacker (all using SentinelGenerator).
  2. Feeds each stream through a DriftTracker (Kalman filter).
  3. Classifies each message and prints a live dashboard.
  4. Saves a summary plot to demo_output.png.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sentinel_generator import SentinelGenerator
from drift_tracker import DriftTracker
from logger import get_logger
from config import (
    DEFAULT_NUM_SAMPLES,
    DEFAULT_BASE_INTERVAL,
    DETECTION_THRESHOLD_US,
    WARMUP_PACKETS,
    KALMAN_Q_NOISE,
    KALMAN_R_NOISE,
)

log = get_logger(__name__)

DEMO_SAMPLES    = 500
RECEIVER_JITTER = 5e-5   # 50 µs – realistic OS jitter

ANSI_GREEN  = "\033[92m"
ANSI_RED    = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET  = "\033[0m"


def classify(residual_us: float, update_count: int) -> str:
    if update_count < WARMUP_PACKETS:
        return "WARMUP"
    return "PHYSICAL" if residual_us < DETECTION_THRESHOLD_US else "ANOMALY"


def coloured_status(status: str) -> str:
    if status == "PHYSICAL":
        return f"{ANSI_GREEN}{status}{ANSI_RESET}"
    if status == "ANOMALY":
        return f"{ANSI_RED}{status}{ANSI_RESET}"
    return f"{ANSI_YELLOW}{status}{ANSI_RESET}"


def run_stream(name: str, intervals: np.ndarray, can_id: int) -> dict:
    """Process an interval stream and return classification summary."""
    tracker = DriftTracker(q_noise=KALMAN_Q_NOISE, r_noise=KALMAN_R_NOISE)
    counts = {"PHYSICAL": 0, "ANOMALY": 0, "WARMUP": 0}
    residuals_us = []

    for interval in intervals:
        residual, _ = tracker.update(interval)
        res_us = abs(residual) * 1e6
        residuals_us.append(res_us)
        status = classify(res_us, tracker.update_count)
        counts[status] += 1

    log.info(
        "[%s] CAN-ID=0x%03x  PHYSICAL=%d  ANOMALY=%d  WARMUP=%d",
        name, can_id, counts["PHYSICAL"], counts["ANOMALY"], counts["WARMUP"]
    )
    return {"name": name, "can_id": can_id, "counts": counts, "residuals_us": residuals_us}


def print_live_table(results: list[dict]) -> None:
    """Pretty-print classification table to console."""
    print()
    print("=" * 65)
    print(f"  SENTINEL-T OFFLINE DEMO  |  threshold = {DETECTION_THRESHOLD_US} µs")
    print("=" * 65)
    header = f"{'Stream':<22} | {'PHYSICAL':>10} | {'ANOMALY':>8} | {'WARMUP':>7}"
    print(header)
    print("-" * 65)
    for r in results:
        name     = r["name"]
        physical = r["counts"]["PHYSICAL"]
        anomaly  = r["counts"]["ANOMALY"]
        warmup   = r["counts"]["WARMUP"]
        verdict  = "✅ SAFE" if anomaly == 0 else "🚨 ATTACK DETECTED"
        print(f"{name:<22} | {physical:>10} | {anomaly:>8} | {warmup:>7}  {verdict}")
    print("=" * 65)


def save_plot(results: list[dict]) -> None:
    """Save residual-over-time plot for all streams."""
    fig, axes = plt.subplots(len(results), 1, figsize=(14, 4 * len(results)), sharex=True)
    if len(results) == 1:
        axes = [axes]

    colours = ["#27ae60", "#e74c3c", "#9b59b6", "#e67e22"]

    for ax, r, colour in zip(axes, results, colours):
        res_us = np.array(r["residuals_us"])
        ax.plot(res_us, color=colour, linewidth=0.8, alpha=0.7, label=r["name"])
        ax.axhline(DETECTION_THRESHOLD_US, color="black", linestyle="--",
                   linewidth=1.5, label=f"Threshold ({DETECTION_THRESHOLD_US} µs)")
        ax.axvspan(0, WARMUP_PACKETS, alpha=0.08, color="grey", label="Warmup")
        ax.set_ylabel("Residual (µs)", fontsize=10)
        ax.set_title(f"Stream: {r['name']}  (CAN ID 0x{r['can_id']:03x})",
                     fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)

    axes[-1].set_xlabel("Message Index", fontsize=11)
    plt.suptitle(
        "Project Sentinel-T – Offline Demo: Kalman Filter Residuals per Stream",
        fontsize=13, fontweight="bold", y=1.01
    )
    plt.tight_layout()
    output_file = "demo_output.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close()
    log.info("Demo plot saved to %s", output_file)
    print(f"\n✅ Plot saved → {output_file}")


def main() -> None:
    log.info("Sentinel-T Offline Demo starting …")
    gen = SentinelGenerator(num_samples=DEMO_SAMPLES, base_interval=DEFAULT_BASE_INTERVAL)

    streams = [
        ("Real_ECU",       gen.generate_real_ecu(receiver_jitter=RECEIVER_JITTER),       0x100),
        ("Dumb_Attacker",  gen.generate_attacker(receiver_jitter=RECEIVER_JITTER),        0x666),
        ("Smart_Attacker", gen.generate_smart_attacker(receiver_jitter=RECEIVER_JITTER),  0x777),
    ]

    results = [run_stream(name, intervals, can_id)
               for name, intervals, can_id in streams]

    print_live_table(results)
    save_plot(results)
    log.info("Demo complete.")


if __name__ == "__main__":
    main()
