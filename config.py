"""
Sentinel-T Central Configuration
All tunable parameters in one place – no magic numbers scattered across modules.
"""

# ── CAN Interface ─────────────────────────────────────────────────────────────
CAN_INTERFACE = "vcan0"

# ── Simulation defaults ───────────────────────────────────────────────────────
DEFAULT_NUM_SAMPLES  = 5000
DEFAULT_BASE_INTERVAL = 0.010   # seconds  (100 Hz)
DEFAULT_DURATION_S   = 300      # seconds for dataset generation

# ── Kalman Filter noise matrices ──────────────────────────────────────────────
KALMAN_Q_NOISE = 1e-12   # Process noise  – trust the physics model
KALMAN_R_NOISE = 1e-10   # Measurement noise – dampen OS scheduling jitter

# ── Detection thresholds ──────────────────────────────────────────────────────
DETECTION_THRESHOLD_US = 200   # microseconds; below → PHYSICAL, above → ANOMALY
WARMUP_PACKETS         = 10    # packets before filter is considered converged

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE   = "sentinel.log"
LOG_LEVEL  = "INFO"            # DEBUG | INFO | WARNING | ERROR

# ── ECU clock-simulation parameters ──────────────────────────────────────────
ECU_THERMAL_AMPLITUDE = 0.00002   # seconds  (±20 µs sinusoidal drift)
ECU_OU_THETA          = 0.15      # O-U mean-reversion rate
ECU_OU_SIGMA          = 0.00001   # O-U noise intensity

# ── Attacker parameters ───────────────────────────────────────────────────────
SMART_ATTACKER_NOISE_STD = 0.00005  # seconds (±50 µs Gaussian jitter)
REPLAY_JITTER_STD        = 0.00002  # seconds; small jitter on replayed timestamps

# ── Automotive ECU definitions (dataset generator) ────────────────────────────
AUTOMOTIVE_ECUS = [
    {"id": 0x100, "interval": 0.010, "name": "Steering_Angle",  "critical": True},
    {"id": 0x101, "interval": 0.020, "name": "ABS_Brake",        "critical": True},
    {"id": 0x200, "interval": 0.100, "name": "Engine_RPM",       "critical": False},
    {"id": 0x201, "interval": 0.100, "name": "Vehicle_Speed",    "critical": False},
    {"id": 0x300, "interval": 0.500, "name": "Fuel_Level",       "critical": False},
    {"id": 0x400, "interval": 1.000, "name": "Dashboard_Lights", "critical": False},
]
