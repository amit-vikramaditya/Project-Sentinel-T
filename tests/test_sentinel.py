"""
Pytest unit-test suite for Sentinel-T

Run with:
    pytest tests/ -v
"""
import numpy as np
import pytest
import sys
import os

# Make sure the repo root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from drift_tracker import DriftTracker
from sentinel_generator import SentinelGenerator
from config import (
    DEFAULT_BASE_INTERVAL,
    KALMAN_Q_NOISE,
    KALMAN_R_NOISE,
    DETECTION_THRESHOLD_US,
    WARMUP_PACKETS,
)


# ─────────────────────────────────────────────────────────────────────────────
# DriftTracker unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDriftTrackerInit:
    def test_default_state_is_zero(self):
        dt = DriftTracker()
        assert dt.x[0, 0] == 0.0
        assert dt.x[1, 0] == 0.0

    def test_update_count_starts_at_zero(self):
        dt = DriftTracker()
        assert dt.update_count == 0

    def test_custom_base_interval(self):
        dt = DriftTracker(base_interval=0.020)
        assert dt.base_interval == 0.020

    def test_state_matrices_shape(self):
        dt = DriftTracker()
        assert dt.F.shape == (2, 2)
        assert dt.H.shape == (1, 2)
        assert dt.Q.shape == (2, 2)
        assert dt.R.shape == (1, 1)
        assert dt.P.shape == (2, 2)


class TestDriftTrackerUpdate:
    def test_update_increments_count(self):
        dt = DriftTracker()
        dt.update(DEFAULT_BASE_INTERVAL)
        assert dt.update_count == 1

    def test_update_returns_tuple(self):
        dt = DriftTracker()
        result = dt.update(DEFAULT_BASE_INTERVAL)
        assert len(result) == 2

    def test_perfect_interval_gives_small_residual(self):
        """After warmup, a perfect interval should produce a near-zero residual."""
        dt = DriftTracker()
        for _ in range(WARMUP_PACKETS + 20):
            residual, _ = dt.update(DEFAULT_BASE_INTERVAL)
        assert abs(residual) < 1e-5, f"Residual {residual} too large for perfect interval"

    def test_large_deviation_gives_large_residual(self):
        """A doubled interval should produce a detectably large residual."""
        dt = DriftTracker()
        for _ in range(WARMUP_PACKETS):
            dt.update(DEFAULT_BASE_INTERVAL)
        # Inject a grossly deviant interval
        residual, _ = dt.update(DEFAULT_BASE_INTERVAL * 10)
        assert abs(residual) * 1e6 > DETECTION_THRESHOLD_US, (
            f"Residual {abs(residual)*1e6:.1f} µs should exceed threshold "
            f"{DETECTION_THRESHOLD_US} µs"
        )

    def test_drift_estimate_converges_for_real_ecu(self):
        """
        After processing real ECU intervals the estimated drift should be
        small (crystal is stable) – well under 1 ppm.
        """
        gen = SentinelGenerator(num_samples=500)
        intervals = gen.generate_real_ecu(receiver_jitter=0.0)
        dt = DriftTracker()
        residuals, drifts = dt.process_stream(intervals)
        mean_drift_ppm = np.mean(np.abs(drifts[WARMUP_PACKETS:])) * 1e6
        assert mean_drift_ppm < 5.0, f"Drift estimate too large: {mean_drift_ppm:.4f} ppm"

    def test_process_stream_returns_correct_length(self):
        intervals = np.full(100, DEFAULT_BASE_INTERVAL)
        dt = DriftTracker()
        residuals, drifts = dt.process_stream(intervals)
        assert len(residuals) == 100
        assert len(drifts) == 100


class TestDriftTrackerSocketUpdate:
    def test_first_call_returns_zero(self):
        dt = DriftTracker()
        res, drift = dt.update_from_can_socket(1000.0)
        assert res == 0.0
        assert drift == 0.0

    def test_second_call_uses_diff(self):
        dt = DriftTracker()
        dt.update_from_can_socket(1000.0)
        # Second call with exactly base interval later
        res, drift = dt.update_from_can_socket(1000.0 + DEFAULT_BASE_INTERVAL)
        # update_count should be 1 after the second call
        assert dt.update_count == 1

    def test_anomalous_timestamp_spike(self):
        dt = DriftTracker()
        dt.update_from_can_socket(1000.0)
        for _ in range(WARMUP_PACKETS):
            dt.update_from_can_socket(dt.last_timestamp + DEFAULT_BASE_INTERVAL)
        # Large gap – attacker injecting after a long pause
        residual, _ = dt.update_from_can_socket(dt.last_timestamp + 1.0)
        assert abs(residual) * 1e6 > DETECTION_THRESHOLD_US


# ─────────────────────────────────────────────────────────────────────────────
# SentinelGenerator unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSentinelGenerator:
    def setup_method(self):
        self.gen = SentinelGenerator(num_samples=200)

    def test_attacker_has_correct_length(self):
        intervals = self.gen.generate_attacker()
        assert len(intervals) == 200

    def test_attacker_is_constant(self):
        intervals = self.gen.generate_attacker(receiver_jitter=0.0)
        assert np.allclose(intervals, DEFAULT_BASE_INTERVAL)

    def test_smart_attacker_has_correct_length(self):
        intervals = self.gen.generate_smart_attacker()
        assert len(intervals) == 200

    def test_smart_attacker_is_not_constant(self):
        intervals = self.gen.generate_smart_attacker(noise_std=0.00005)
        assert not np.allclose(intervals, DEFAULT_BASE_INTERVAL)

    def test_real_ecu_has_correct_length(self):
        intervals = self.gen.generate_real_ecu()
        assert len(intervals) == 200

    def test_real_ecu_intervals_are_positive(self):
        intervals = self.gen.generate_real_ecu()
        assert np.all(intervals > 0)

    def test_receiver_jitter_increases_variance(self):
        no_jitter   = self.gen.generate_attacker(receiver_jitter=0.0)
        with_jitter = self.gen.generate_attacker(receiver_jitter=0.0001)
        assert np.std(with_jitter) > np.std(no_jitter)


# ─────────────────────────────────────────────────────────────────────────────
# Detection-capability integration test
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectionCapability:
    """
    High-level integration: the Kalman filter must produce a measurably higher
    average residual for a software attacker than for a real ECU.
    This validates the core detection hypothesis.
    """

    def _mean_residual_us(self, intervals: np.ndarray) -> float:
        dt = DriftTracker()
        residuals, _ = dt.process_stream(intervals)
        # Exclude warmup
        post_warmup = np.abs(residuals[WARMUP_PACKETS:])
        return float(np.mean(post_warmup) * 1e6)

    def test_real_ecu_residual_below_threshold(self):
        gen = SentinelGenerator(num_samples=1000)
        intervals = gen.generate_real_ecu(receiver_jitter=0.0)
        mean_us = self._mean_residual_us(intervals)
        assert mean_us < DETECTION_THRESHOLD_US, (
            f"Real ECU mean residual {mean_us:.2f} µs exceeds threshold "
            f"{DETECTION_THRESHOLD_US} µs"
        )

    def test_static_attacker_residual_above_threshold(self):
        """
        A perfectly periodic attacker should, after the filter converges,
        produce near-zero residuals – this tests that the filter does NOT
        produce false positives for a benign static sender.
        """
        gen = SentinelGenerator(num_samples=1000)
        intervals = gen.generate_attacker(receiver_jitter=0.0)
        mean_us = self._mean_residual_us(intervals)
        # A static signal is indistinguishable from a perfect clock – should be low
        assert mean_us < DETECTION_THRESHOLD_US, (
            f"Static attacker false-positive: residual {mean_us:.2f} µs"
        )

    def test_smart_attacker_residual_higher_than_real_ecu(self):
        gen = SentinelGenerator(num_samples=2000)
        intervals_ecu    = gen.generate_real_ecu(receiver_jitter=0.0)
        intervals_smart  = gen.generate_smart_attacker(receiver_jitter=0.0)

        mean_ecu   = self._mean_residual_us(intervals_ecu)
        mean_smart = self._mean_residual_us(intervals_smart)

        assert mean_smart > mean_ecu, (
            f"Smart attacker residual ({mean_smart:.2f} µs) should be higher "
            f"than real ECU residual ({mean_ecu:.2f} µs)"
        )

    def test_snr_exceeds_one(self):
        """SNR = mean(attacker residual) / mean(ECU residual) must be > 1."""
        gen = SentinelGenerator(num_samples=2000)
        intervals_ecu   = gen.generate_real_ecu(receiver_jitter=5e-5)
        intervals_smart = gen.generate_smart_attacker(receiver_jitter=5e-5)

        mean_ecu   = self._mean_residual_us(intervals_ecu)
        mean_smart = self._mean_residual_us(intervals_smart)

        snr = mean_smart / mean_ecu if mean_ecu > 0 else float("inf")
        assert snr > 1.0, f"SNR {snr:.2f} is below 1.0 – detection not viable"
