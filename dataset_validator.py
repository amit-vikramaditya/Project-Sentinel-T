"""
CAN Dataset Loader and Validator
Replays CAN datasets through Sentinel-T for validation testing.
"""

import pandas as pd
import numpy as np
from drift_tracker import DriftTracker
from collections import defaultdict
import time


class DatasetValidator:
    """Validates Sentinel-T performance on CAN datasets."""
    
    def __init__(self, threshold_us=200, q_noise=1e-12, r_noise=1e-10):
        self.threshold_us = threshold_us
        self.q_noise = q_noise
        self.r_noise = r_noise
        self.trackers = {}
        self.results = []
        
    def process_dataset(self, csv_file, verbose=True):
        """
        Process a CAN dataset CSV file.
        
        Expected columns: timestamp, can_id, dlc, data, ecu_name, label
        """
        # Load dataset
        df = pd.read_csv(csv_file)
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Processing: {csv_file}")
            print(f"{'='*60}")
            print(f"Total messages: {len(df)}")
            print(f"Unique ECUs: {df['can_id'].nunique()}")
            print(f"Time span: {df['timestamp'].max():.2f}s")
            print(f"Attack messages: {len(df[df['label'] == 'ATTACK'])}")
        
        # Initialize results tracking
        predictions = []
        ground_truth = []
        
        # Process each message
        for idx, row in df.iterrows():
            can_id = row['can_id']
            timestamp = row['timestamp']
            true_label = row['label']
            
            # Initialize tracker for this CAN ID if not exists
            if can_id not in self.trackers:
                self.trackers[can_id] = DriftTracker(
                    q_noise=self.q_noise,
                    r_noise=self.r_noise
                )
            
            # Update tracker
            residual, drift = self.trackers[can_id].update_from_can_socket(timestamp)
            
            # Classification logic
            if self.trackers[can_id].update_count < 10:
                predicted_label = "WARMUP"  # Don't classify during warmup
            else:
                res_us = abs(residual) * 1e6
                predicted_label = "ATTACK" if res_us >= self.threshold_us else "NORMAL"
            
            # Store results (skip warmup for metrics)
            if predicted_label != "WARMUP":
                predictions.append(predicted_label)
                ground_truth.append(true_label)
                
                self.results.append({
                    "timestamp": timestamp,
                    "can_id": f"0x{can_id:03x}",
                    "ecu_name": row.get('ecu_name', 'Unknown'),
                    "residual_us": abs(residual) * 1e6,
                    "drift_ppm": drift * 1e6,
                    "true_label": true_label,
                    "predicted_label": predicted_label,
                    "correct": predicted_label == true_label
                })
        
        # Calculate metrics
        metrics = self._calculate_metrics(ground_truth, predictions)
        
        if verbose:
            self._print_metrics(metrics)
        
        return metrics, pd.DataFrame(self.results)
    
    def _calculate_metrics(self, ground_truth, predictions):
        """Calculate classification metrics."""
        # Convert to numpy arrays
        y_true = np.array([1 if label == "ATTACK" else 0 for label in ground_truth])
        y_pred = np.array([1 if label == "ATTACK" else 0 for label in predictions])
        
        # Confusion matrix components
        tp = np.sum((y_true == 1) & (y_pred == 1))  # True Positives
        tn = np.sum((y_true == 0) & (y_pred == 0))  # True Negatives
        fp = np.sum((y_true == 0) & (y_pred == 1))  # False Positives
        fn = np.sum((y_true == 1) & (y_pred == 0))  # False Negatives
        
        # Metrics
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0  # Also called TPR
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0  # False Positive Rate
        tnr = tn / (tn + fp) if (tn + fp) > 0 else 0  # True Negative Rate (Specificity)
        
        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,  # Detection rate
            "f1_score": f1_score,
            "fpr": fpr,
            "tnr": tnr,
            "tp": int(tp),
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "total": len(y_true)
        }
    
    def _print_metrics(self, metrics):
        """Pretty print metrics."""
        print(f"\n{'='*60}")
        print("DETECTION PERFORMANCE METRICS")
        print(f"{'='*60}")
        
        # Confusion Matrix
        print("\n📊 Confusion Matrix:")
        print(f"                  Predicted NORMAL | Predicted ATTACK")
        print(f"  Actual NORMAL:  {metrics['tn']:8d}      | {metrics['fp']:8d}")
        print(f"  Actual ATTACK:  {metrics['fn']:8d}      | {metrics['tp']:8d}")
        
        # Classification Metrics
        print(f"\n📈 Classification Metrics:")
        print(f"  Accuracy:       {metrics['accuracy']*100:6.2f}%")
        print(f"  Precision:      {metrics['precision']*100:6.2f}%")
        print(f"  Recall (TPR):   {metrics['recall']*100:6.2f}%  ← Detection Rate")
        print(f"  F1-Score:       {metrics['f1_score']:6.4f}")
        
        print(f"\n🎯 Error Rates:")
        print(f"  False Positive Rate: {metrics['fpr']*100:6.2f}%")
        print(f"  False Negative Rate: {(1-metrics['recall'])*100:6.2f}%")
        
        print(f"\n💡 Summary:")
        print(f"  Total Messages: {metrics['total']}")
        print(f"  Correctly Classified: {metrics['tp'] + metrics['tn']}")
        print(f"  Misclassified: {metrics['fp'] + metrics['fn']}")
        
        # Verdict
        if metrics['recall'] >= 0.95 and metrics['fpr'] <= 0.05:
            print(f"\n✅ EXCELLENT: High detection rate with low false positives!")
        elif metrics['recall'] >= 0.80:
            print(f"\n✔️  GOOD: Acceptable detection performance")
        else:
            print(f"\n⚠️  NEEDS TUNING: Detection rate below target")


def run_validation_suite():
    """Run complete validation on all benchmark datasets."""
    
    import glob
    dataset_files = sorted(glob.glob("datasets/*.csv"))
    
    if not dataset_files:
        print("❌ No datasets found in datasets/ directory")
        print("   Run: python dataset_generator.py first")
        return
    
    print("\n" + "="*70)
    print("  SENTINEL-T VALIDATION SUITE")
    print("  Testing on Realistic Automotive CAN Datasets")
    print("="*70)
    
    all_metrics = {}
    
    for dataset_file in dataset_files:
        validator = DatasetValidator(threshold_us=200)
        metrics, results_df = validator.process_dataset(dataset_file, verbose=True)
        
        dataset_name = dataset_file.split('/')[-1].replace('.csv', '')
        all_metrics[dataset_name] = metrics
        
        # Save detailed results
        results_file = dataset_file.replace('.csv', '_results.csv')
        results_df.to_csv(results_file, index=False)
        print(f"📝 Detailed results saved: {results_file}")
    
    # Summary comparison table
    print("\n" + "="*70)
    print("SUMMARY: Performance Across All Datasets")
    print("="*70)
    print(f"{'Dataset':<25} | {'Accuracy':>10} | {'Recall':>10} | {'FPR':>10}")
    print("-" * 70)
    
    for name, metrics in all_metrics.items():
        print(f"{name:<25} | {metrics['accuracy']*100:>9.2f}% | "
              f"{metrics['recall']*100:>9.2f}% | {metrics['fpr']*100:>9.2f}%")
    
    print("="*70)
    
    return all_metrics


if __name__ == "__main__":
    # Run validation on all datasets
    metrics = run_validation_suite()
