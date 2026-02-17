import numpy as np

class DriftTracker:
    """
    Uses a 2D Kalman Filter to track the state of a physical clock.
    State x = [phase_offset, frequency_drift]^T
    
    Tuning Rescue: R is increased to 1e-4 to allow the filter to ignore 
    high-frequency OS jitter and focus on the low-frequency physical drift.
    """
    def __init__(self, base_interval=0.010, q_noise=1e-12, r_noise=1e-10):
        self.base_interval = base_interval
        self.update_count = 0
        
        # State: [offset, drift]
        self.x = np.array([[0.0], [0.0]])
        
        # State Covariance
        self.P = np.eye(2) * 0.1
        
        # Transition Matrix
        self.F = np.array([[1.0, 1.0],
                           [0.0, 1.0]])
        
        # Observation Matrix
        self.H = np.array([[1.0, 0.0]])
        
        # Process Noise Covariance (Q) - Low for physical stability
        self.Q = np.eye(2) * q_noise
        
        # Measurement Noise Covariance (R) - High to dampen OS jitter
        self.R = np.array([[r_noise]])

    def update(self, observed_interval):
        """Standard update using an interval value."""
        self.update_count += 1
        # 1. Prediction Step
        x_pred = self.F @ self.x
        P_pred = self.F @ self.P @ self.F.T + self.Q
        
        # 2. Measurement
        z = observed_interval - self.base_interval
        
        # 3. Innovation (Residual)
        residual = z - (self.H @ x_pred)[0, 0]
        
        # 4. Update Step
        S = self.H @ P_pred @ self.H.T + self.R
        K = P_pred @ self.H.T @ np.linalg.inv(S)
        
        self.x = x_pred + K * residual
        self.P = (np.eye(2) - K @ self.H) @ P_pred
        
        return residual, self.x[1, 0]

    def update_from_can_socket(self, timestamp_s):
        """
        TASK 1 PREP: Logic for using Kernel Timestamps.
        Expects a high-precision float timestamp (seconds).
        """
        if not hasattr(self, 'last_timestamp'):
            self.last_timestamp = timestamp_s
            return 0.0, 0.0
        
        interval = timestamp_s - self.last_timestamp
        self.last_timestamp = timestamp_s
        return self.update(interval)

    def process_stream(self, intervals):
        """Processes a sequence of intervals and returns tracking history."""
        residuals = []
        drifts = []
        
        for interval in intervals:
            res, drift = self.update(interval)
            residuals.append(res)
            drifts.append(drift)
            
        return np.array(residuals), np.array(drifts)