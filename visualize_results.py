"""
Performance Visualization for Sentinel-T Validation Results
Generates publication-quality charts showing detection performance.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
import glob

def create_performance_visualizations():
    """Create comprehensive performance visualization charts."""
    
    # Load all result files
    result_files = glob.glob("datasets/*_results.csv")
    
    if not result_files:
        print("No result files found. Run dataset_validator.py first.")
        return
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # Color scheme
    colors = {
        'normal': '#2ecc71',        # Green
        'attack': '#e74c3c',        # Red
        'correct': '#27ae60',       # Dark green
        'incorrect': '#c0392b'      # Dark red
    }
    
    datasets_metrics = {}
    
    # ========== SUBPLOT 1: Accuracy Comparison ==========
    ax1 = plt.subplot(2, 3, 1)
    dataset_names = []
    accuracies = []
    
    for result_file in sorted(result_files):
        df = pd.read_csv(result_file)
        dataset_name = result_file.split('/')[-1].replace('_results.csv', '')
        
        # Calculate accuracy
        correct = df['correct'].sum()
        total = len(df)
        accuracy = (correct / total * 100) if total > 0 else 0
        
        dataset_names.append(dataset_name.replace('_', '\n'))
        accuracies.append(accuracy)
        
        datasets_metrics[dataset_name] = {
            'accuracy': accuracy,
            'total': total,
            'correct': correct
        }
    
    bars = ax1.bar(range(len(dataset_names)), accuracies, color='#3498db', alpha=0.8)
    ax1.axhline(y=95, color='red', linestyle='--', label='Target (95%)', linewidth=2)
    ax1.set_ylabel('Accuracy (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Detection Accuracy by Dataset', fontsize=14, fontweight='bold')
    ax1.set_xticks(range(len(dataset_names)))
    ax1.set_xticklabels(dataset_names, fontsize=9)
    ax1.set_ylim(85, 102)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, acc) in enumerate(zip(bars, accuracies)):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{acc:.2f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # ========== SUBPLOT 2: Residual Distribution ==========
    ax2 = plt.subplot(2, 3, 2)
    
    # Load injection attack results for detailed analysis
    injection_df = pd.read_csv("datasets/injection_attack_results.csv")
    
    normal_residuals = injection_df[injection_df['true_label'] == 'NORMAL']['residual_us']
    attack_residuals = injection_df[injection_df['true_label'] == 'ATTACK']['residual_us']
    
    ax2.hist(normal_residuals, bins=50, alpha=0.6, color=colors['normal'], 
             label=f'Normal (μ={normal_residuals.mean():.1f}µs)', density=True)
    ax2.hist(attack_residuals, bins=50, alpha=0.6, color=colors['attack'],
             label=f'Attack (μ={attack_residuals.mean():.1f}µs)', density=True)
    ax2.axvline(x=200, color='black', linestyle='--', label='Threshold (200µs)', linewidth=2)
    
    ax2.set_xlabel('Residual Error (µs)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Density', fontsize=12, fontweight='bold')
    ax2.set_title('Residual Distribution: Normal vs Attack', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, 1000)
    
    # ========== SUBPLOT 3: Confusion Matrix Heatmap ==========
    ax3 = plt.subplot(2, 3, 3)
    
    # Use injection attack as representative
    tp = len(injection_df[(injection_df['true_label'] == 'ATTACK') & 
                          (injection_df['predicted_label'] == 'ATTACK')])
    tn = len(injection_df[(injection_df['true_label'] == 'NORMAL') & 
                          (injection_df['predicted_label'] == 'NORMAL')])
    fp = len(injection_df[(injection_df['true_label'] == 'NORMAL') & 
                          (injection_df['predicted_label'] == 'ATTACK')])
    fn = len(injection_df[(injection_df['true_label'] == 'ATTACK') & 
                          (injection_df['predicted_label'] == 'NORMAL')])
    
    confusion = np.array([[tn, fp], [fn, tp]])
    
    im = ax3.imshow(confusion, cmap='RdYlGn', aspect='auto')
    ax3.set_xticks([0, 1])
    ax3.set_yticks([0, 1])
    ax3.set_xticklabels(['Predicted\nNORMAL', 'Predicted\nATTACK'], fontsize=10)
    ax3.set_yticklabels(['Actual\nNORMAL', 'Actual\nATTACK'], fontsize=10)
    ax3.set_title('Confusion Matrix\n(Injection Attack Dataset)', fontsize=14, fontweight='bold')
    
    # Add text annotations
    for i in range(2):
        for j in range(2):
            text = ax3.text(j, i, f'{confusion[i, j]:,}',
                          ha="center", va="center", color="black", fontsize=14, fontweight='bold')
    
    plt.colorbar(im, ax=ax3, fraction=0.046, pad=0.04)
    
    # ========== SUBPLOT 4: Detection Rate by Attack Type ==========
    ax4 = plt.subplot(2, 3, 4)
    
    attack_types = ['Injection\nAttack', 'Smart\nAttack', 'Fuzzing\nAttack']
    detection_rates = []
    
    for attack_file in ['injection_attack', 'smart_attack', 'fuzzing_attack']:
        df = pd.read_csv(f"datasets/{attack_file}_results.csv")
        attack_msgs = df[df['true_label'] == 'ATTACK']
        if len(attack_msgs) > 0:
            detected = len(attack_msgs[attack_msgs['predicted_label'] == 'ATTACK'])
            rate = (detected / len(attack_msgs)) * 100
            detection_rates.append(rate)
        else:
            detection_rates.append(0)
    
    bars = ax4.barh(attack_types, detection_rates, color=['#e67e22', '#9b59b6', '#e74c3c'], alpha=0.8)
    ax4.axvline(x=95, color='green', linestyle='--', label='Target (95%)', linewidth=2)
    ax4.set_xlabel('Detection Rate (%)', fontsize=12, fontweight='bold')
    ax4.set_title('Detection Rate by Attack Type', fontsize=14, fontweight='bold')
    ax4.set_xlim(85, 102)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='x')
    
    # Add value labels
    for bar, rate in zip(bars, detection_rates):
        ax4.text(rate + 0.5, bar.get_y() + bar.get_height()/2,
                f'{rate:.2f}%', va='center', fontsize=11, fontweight='bold')
    
    # ========== SUBPLOT 5: Processing Performance ==========
    ax5 = plt.subplot(2, 3, 5)
    
    message_counts = []
    dataset_labels = []
    
    for result_file in sorted(result_files):
        df = pd.read_csv(result_file)
        dataset_name = result_file.split('/')[-1].replace('_results.csv', '')
        
        normal_count = len(df[df['true_label'] == 'NORMAL'])
        attack_count = len(df[df['true_label'] == 'ATTACK'])
        
        dataset_labels.append(dataset_name.replace('_', '\n'))
        message_counts.append([normal_count, attack_count])
    
    message_counts = np.array(message_counts)
    
    x = np.arange(len(dataset_labels))
    width = 0.35
    
    ax5.bar(x, message_counts[:, 0], width, label='Normal', color=colors['normal'], alpha=0.8)
    ax5.bar(x, message_counts[:, 1], width, bottom=message_counts[:, 0],
            label='Attack', color=colors['attack'], alpha=0.8)
    
    ax5.set_ylabel('Message Count', fontsize=12, fontweight='bold')
    ax5.set_title('Dataset Composition', fontsize=14, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels(dataset_labels, fontsize=9)
    ax5.legend()
    ax5.grid(True, alpha=0.3, axis='y')
    
    # ========== SUBPLOT 6: Performance Summary Table ==========
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('tight')
    ax6.axis('off')
    
    # Create summary table
    table_data = []
    table_data.append(['Dataset', 'Accuracy', 'TPR', 'FPR'])
    
    for attack_file in ['injection_attack', 'smart_attack', 'fuzzing_attack']:
        df = pd.read_csv(f"datasets/{attack_file}_results.csv")
        
        total = len(df)
        correct = df['correct'].sum()
        accuracy = (correct / total * 100)
        
        attack_msgs = df[df['true_label'] == 'ATTACK']
        normal_msgs = df[df['true_label'] == 'NORMAL']
        
        if len(attack_msgs) > 0:
            tp = len(attack_msgs[attack_msgs['predicted_label'] == 'ATTACK'])
            tpr = (tp / len(attack_msgs)) * 100
        else:
            tpr = 0
        
        if len(normal_msgs) > 0:
            fp = len(normal_msgs[normal_msgs['predicted_label'] == 'ATTACK'])
            fpr = (fp / len(normal_msgs)) * 100
        else:
            fpr = 0
        
        name = attack_file.replace('_', ' ').title()
        table_data.append([name, f'{accuracy:.2f}%', f'{tpr:.2f}%', f'{fpr:.2f}%'])
    
    table = ax6.table(cellText=table_data, cellLoc='center', loc='center',
                     colWidths=[0.4, 0.2, 0.2, 0.2])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.5)
    
    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor('#3498db')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(table_data)):
        for j in range(4):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#ecf0f1')
    
    ax6.set_title('Performance Summary', fontsize=14, fontweight='bold', pad=20)
    
    # ========== FINALIZE ==========
    plt.suptitle('PROJECT SENTINEL-T: VALIDATION RESULTS\nPhysical-Layer Intrusion Detection on Realistic Automotive CAN Datasets',
                fontsize=16, fontweight='bold', y=0.995)
    
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    
    # Save figure
    plt.savefig('validation_results.png', dpi=300, bbox_inches='tight')
    print("✅ Visualization saved: validation_results.png")
    
    # Create individual ROC-style curve
    create_threshold_analysis()


def create_threshold_analysis():
    """Analyze performance at different threshold values."""
    
    # Load injection attack data
    df = pd.read_csv("datasets/injection_attack_results.csv")
    
    # Test different thresholds
    thresholds = np.linspace(50, 500, 50)
    tpr_values = []
    fpr_values = []
    
    for threshold in thresholds:
        # Re-classify based on threshold
        attack_msgs = df[df['true_label'] == 'ATTACK']
        normal_msgs = df[df['true_label'] == 'NORMAL']
        
        tp = len(attack_msgs[attack_msgs['residual_us'] >= threshold])
        fp = len(normal_msgs[normal_msgs['residual_us'] >= threshold])
        
        tpr = (tp / len(attack_msgs)) * 100 if len(attack_msgs) > 0 else 0
        fpr = (fp / len(normal_msgs)) * 100 if len(normal_msgs) > 0 else 0
        
        tpr_values.append(tpr)
        fpr_values.append(fpr)
    
    # Plot ROC-like curve
    plt.figure(figsize=(10, 8))
    plt.plot(fpr_values, tpr_values, 'b-', linewidth=2, label='Sentinel-T')
    plt.plot([0, 100], [0, 100], 'r--', linewidth=2, label='Random Classifier')
    
    # Mark current threshold
    current_idx = np.argmin(np.abs(thresholds - 200))
    plt.plot(fpr_values[current_idx], tpr_values[current_idx], 'go', 
             markersize=15, label=f'Current Threshold (200µs)')
    
    plt.xlabel('False Positive Rate (%)', fontsize=14, fontweight='bold')
    plt.ylabel('True Positive Rate / Detection Rate (%)', fontsize=14, fontweight='bold')
    plt.title('ROC-Style Curve: Detection Performance vs False Positive Rate',
             fontsize=16, fontweight='bold')
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.xlim(-2, 20)
    plt.ylim(80, 102)
    
    plt.tight_layout()
    plt.savefig('roc_curve.png', dpi=300, bbox_inches='tight')
    print("✅ ROC curve saved: roc_curve.png")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  GENERATING PERFORMANCE VISUALIZATIONS")
    print("="*60 + "\n")
    
    create_performance_visualizations()
    
    print("\n" + "="*60)
    print("✅ All visualizations generated successfully!")
    print("="*60)
