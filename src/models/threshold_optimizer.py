"""
Threshold Optimization for Flight Delay Classification

This module provides utilities for optimizing the classification threshold
to improve Recall while maintaining acceptable Precision.

Current Problem: Recall is only 46-48%, missing half of delayed flights.
Target: Recall >= 70% while keeping Precision > 40%
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    precision_recall_curve, roc_curve, auc,
    confusion_matrix, classification_report
)
import matplotlib.pyplot as plt


def find_optimal_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    target_recall: float = 0.70,
    min_precision: float = 0.30
) -> Tuple[float, Dict[str, float]]:
    """
    Find the optimal threshold to achieve target recall while maintaining minimum precision.

    Parameters
    ----------
    y_true : np.ndarray
        True binary labels (0 or 1)
    y_proba : np.ndarray
        Predicted probabilities for class 1
    target_recall : float
        Minimum target recall (default 0.70)
    min_precision : float
        Minimum acceptable precision (default 0.30)

    Returns
    -------
    tuple
        (optimal_threshold, metrics_dict)
    """
    thresholds = np.arange(0.10, 0.60, 0.01)
    best_threshold = 0.5
    best_metrics = None

    for thresh in thresholds:
        y_pred = (y_proba >= thresh).astype(int)
        recall = recall_score(y_true, y_pred, zero_division=0)
        precision = precision_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)

        # Check if this threshold meets our criteria
        if recall >= target_recall and precision >= min_precision:
            if best_metrics is None or f1 > best_metrics['f1']:
                best_threshold = thresh
                best_metrics = {
                    'threshold': thresh,
                    'recall': recall,
                    'precision': precision,
                    'f1': f1
                }

    # If no threshold meets criteria, find the one with highest recall
    if best_metrics is None:
        print(f"Warning: No threshold achieves target_recall={target_recall} "
              f"and min_precision={min_precision}")

        # Find threshold that gives highest recall while precision > min_precision
        for thresh in reversed(thresholds):
            y_pred = (y_proba >= thresh).astype(int)
            recall = recall_score(y_true, y_pred, zero_division=0)
            precision = precision_score(y_true, y_pred, zero_division=0)

            if precision >= min_precision:
                best_threshold = thresh
                best_metrics = {
                    'threshold': thresh,
                    'recall': recall,
                    'precision': precision,
                    'f1': f1_score(y_true, y_pred, zero_division=0)
                }
                break

    # Fallback
    if best_metrics is None:
        best_threshold = 0.35
        y_pred = (y_proba >= best_threshold).astype(int)
        best_metrics = {
            'threshold': best_threshold,
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0)
        }

    return best_threshold, best_metrics


def evaluate_at_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    threshold: float = 0.5
) -> Dict[str, float]:
    """
    Evaluate model performance at a specific threshold.

    Parameters
    ----------
    y_true : np.ndarray
        True binary labels
    y_proba : np.ndarray
        Predicted probabilities
    threshold : float
        Classification threshold

    Returns
    -------
    dict
        Dictionary of metrics
    """
    y_pred = (y_proba >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    metrics = {
        'threshold': threshold,
        'accuracy': (tp + tn) / (tp + tn + fp + fn),
        'precision': tp / (tp + fp) if (tp + fp) > 0 else 0,
        'recall': tp / (tp + fn) if (tp + fn) > 0 else 0,
        'f1': f1_score(y_true, y_pred, zero_division=0),
        'specificity': tn / (tn + fp) if (tn + fp) > 0 else 0,
        'true_positives': int(tp),
        'false_positives': int(fp),
        'true_negatives': int(tn),
        'false_negatives': int(fn),
    }

    return metrics


def get_precision_recall_curve(
    y_true: np.ndarray,
    y_proba: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Get precision-recall curve data.

    Parameters
    ----------
    y_true : np.ndarray
        True labels
    y_proba : np.ndarray
        Predicted probabilities

    Returns
    -------
    tuple
        (precision_array, recall_array, thresholds_array)
    """
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    return precision, recall, thresholds


def plot_threshold_analysis(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    target_recall: float = 0.70,
    figsize: Tuple[int, int] = (15, 5),
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create comprehensive threshold analysis plots.

    Includes:
    1. Precision-Recall curve
    2. Metrics vs Threshold
    3. Confusion matrix at optimal threshold

    Parameters
    ----------
    y_true : np.ndarray
        True labels
    y_proba : np.ndarray
        Predicted probabilities
    target_recall : float
        Target recall for optimal threshold
    figsize : tuple
        Figure size
    save_path : str, optional
        Path to save the figure

    Returns
    -------
    matplotlib.Figure
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    # Plot 1: Precision-Recall Curve
    precision, recall, thresholds = precision_recall_curve(y_true, y_proba)
    pr_auc = auc(recall, precision)

    axes[0].plot(recall, precision, 'b-', linewidth=2, label=f'PR Curve (AUC={pr_auc:.3f})')
    axes[0].axhline(y=0.4, color='r', linestyle='--', alpha=0.5, label='Min Precision (0.40)')
    axes[0].axvline(x=target_recall, color='g', linestyle='--', alpha=0.5, label=f'Target Recall ({target_recall})')
    axes[0].set_xlabel('Recall')
    axes[0].set_ylabel('Precision')
    axes[0].set_title('Precision-Recall Curve')
    axes[0].legend(loc='best')
    axes[0].grid(True, alpha=0.3)

    # Plot 2: Metrics vs Threshold
    thresholds_range = np.arange(0.1, 0.7, 0.01)
    recalls = []
    precisions = []
    f1s = []

    for thresh in thresholds_range:
        y_pred = (y_proba >= thresh).astype(int)
        recalls.append(recall_score(y_true, y_pred, zero_division=0))
        precisions.append(precision_score(y_true, y_pred, zero_division=0))
        f1s.append(f1_score(y_true, y_pred, zero_division=0))

    axes[1].plot(thresholds_range, recalls, 'g-', label='Recall', linewidth=2)
    axes[1].plot(thresholds_range, precisions, 'b-', label='Precision', linewidth=2)
    axes[1].plot(thresholds_range, f1s, 'r-', label='F1 Score', linewidth=2)
    axes[1].axvline(x=0.5, color='gray', linestyle='--', alpha=0.5, label='Default (0.5)')

    # Find and mark optimal threshold
    optimal_thresh, optimal_metrics = find_optimal_threshold(y_true, y_proba, target_recall)
    axes[1].axvline(x=optimal_thresh, color='purple', linestyle='-', linewidth=2,
                    label=f'Optimal ({optimal_thresh:.2f})')

    axes[1].set_xlabel('Threshold')
    axes[1].set_ylabel('Score')
    axes[1].set_title('Metrics vs Classification Threshold')
    axes[1].legend(loc='best')
    axes[1].grid(True, alpha=0.3)

    # Plot 3: Comparison at different thresholds
    thresholds_to_compare = [0.50, 0.40, 0.35, optimal_thresh]
    metrics_list = []
    for thresh in thresholds_to_compare:
        metrics = evaluate_at_threshold(y_true, y_proba, thresh)
        metrics_list.append(metrics)

    x = np.arange(4)
    width = 0.25

    recalls_bar = [m['recall'] for m in metrics_list]
    precisions_bar = [m['precision'] for m in metrics_list]
    f1s_bar = [m['f1'] for m in metrics_list]

    axes[2].bar(x - width, recalls_bar, width, label='Recall', color='green', alpha=0.7)
    axes[2].bar(x, precisions_bar, width, label='Precision', color='blue', alpha=0.7)
    axes[2].bar(x + width, f1s_bar, width, label='F1', color='red', alpha=0.7)

    axes[2].set_xticks(x)
    axes[2].set_xticklabels([f'{t:.2f}' for t in thresholds_to_compare])
    axes[2].set_xlabel('Threshold')
    axes[2].set_ylabel('Score')
    axes[2].set_title('Metrics Comparison at Different Thresholds')
    axes[2].legend(loc='upper right')
    axes[2].axhline(y=target_recall, color='green', linestyle='--', alpha=0.3)
    axes[2].axhline(y=0.4, color='blue', linestyle='--', alpha=0.3)
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Figure saved to {save_path}")

    return fig


def get_business_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    threshold: float = 0.5
) -> Dict[str, any]:
    """
    Calculate business-relevant metrics for flight delay prediction.

    Parameters
    ----------
    y_true : np.ndarray
        True labels (1 = delayed, 0 = on-time)
    y_proba : np.ndarray
        Predicted probabilities
    threshold : float
        Classification threshold

    Returns
    -------
    dict
        Business metrics
    """
    y_pred = (y_proba >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    total = len(y_true)
    total_delayed = y_true.sum()
    total_ontime = total - total_delayed

    metrics = {
        'threshold': threshold,

        # Operational metrics
        'delayed_flights_caught': int(tp),
        'delayed_flights_missed': int(fn),
        'false_alarms': int(fp),
        'correct_ontime': int(tn),

        # Percentages
        'pct_delays_caught': tp / total_delayed * 100 if total_delayed > 0 else 0,
        'pct_delays_missed': fn / total_delayed * 100 if total_delayed > 0 else 0,
        'false_alarm_rate': fp / total_ontime * 100 if total_ontime > 0 else 0,

        # Workload metrics (how many alerts need to be processed)
        'total_alerts': int(tp + fp),
        'alert_accuracy': tp / (tp + fp) * 100 if (tp + fp) > 0 else 0,

        # Summary
        'summary': f"At threshold {threshold:.2f}: "
                   f"Catch {tp / total_delayed * 100:.1f}% of delays, "
                   f"with {fp / (tp + fp) * 100:.1f}% false alarms" if (tp + fp) > 0 else "No predictions"
    }

    return metrics


def recommend_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    operation_mode: str = 'balanced'
) -> Tuple[float, str]:
    """
    Recommend threshold based on operational requirements.

    Parameters
    ----------
    y_true : np.ndarray
        True labels
    y_proba : np.ndarray
        Predicted probabilities
    operation_mode : str
        'high_recall': Prioritize catching delays (accept more false alarms)
        'balanced': Balance between recall and precision
        'high_precision': Prioritize alert accuracy (accept missing some delays)

    Returns
    -------
    tuple
        (recommended_threshold, explanation)
    """
    if operation_mode == 'high_recall':
        # Target 80% recall, accept 30% precision
        thresh, metrics = find_optimal_threshold(y_true, y_proba, target_recall=0.80, min_precision=0.25)
        explanation = (f"High Recall Mode: Threshold {thresh:.2f} catches {metrics['recall']*100:.1f}% "
                       f"of delays with {metrics['precision']*100:.1f}% precision. "
                       "Best for critical operations where missing delays is costly.")

    elif operation_mode == 'high_precision':
        # Target 60% precision, accept 50% recall
        thresh, metrics = find_optimal_threshold(y_true, y_proba, target_recall=0.50, min_precision=0.55)
        explanation = (f"High Precision Mode: Threshold {thresh:.2f} has {metrics['precision']*100:.1f}% "
                       f"alert accuracy with {metrics['recall']*100:.1f}% delay capture rate. "
                       "Best when false alarms are disruptive.")

    else:  # balanced
        thresh, metrics = find_optimal_threshold(y_true, y_proba, target_recall=0.70, min_precision=0.40)
        explanation = (f"Balanced Mode: Threshold {thresh:.2f} achieves {metrics['recall']*100:.1f}% recall "
                       f"and {metrics['precision']*100:.1f}% precision (F1={metrics['f1']:.3f}). "
                       "Recommended for general airport operations.")

    return thresh, explanation
