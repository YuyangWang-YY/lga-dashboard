"""
Probability Calibration for LGA Flight Delay Prediction

This module provides calibration utilities to make predicted probabilities
match actual delay rates. Uses isotonic regression (non-parametric),
which is well-suited for tree-based models like LightGBM.

Why calibrate? LightGBM with scale_pos_weight=4.0 outputs inflated
probabilities. E.g., predicted p=0.55 corresponds to ~40% actual delay rate.
Calibration fixes this so risk tier thresholds are directly interpretable.
"""

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
from sklearn.calibration import calibration_curve


def fit_isotonic_calibration(raw_proba, y_true):
    """
    Fit isotonic regression calibrator.

    Parameters
    ----------
    raw_proba : array-like
        Uncalibrated predicted probabilities (from model.predict_proba).
    y_true : array-like
        True binary labels (0/1).

    Returns
    -------
    IsotonicRegression
        Fitted calibrator. Use calibrator.predict(raw_proba) to calibrate.
    """
    iso_reg = IsotonicRegression(y_min=0, y_max=1, out_of_bounds='clip')
    iso_reg.fit(raw_proba, y_true)
    return iso_reg


def apply_calibration(calibrator, raw_proba):
    """
    Apply fitted calibrator to raw probabilities.

    Parameters
    ----------
    calibrator : IsotonicRegression
        Fitted calibrator from fit_isotonic_calibration.
    raw_proba : array-like
        Uncalibrated predicted probabilities.

    Returns
    -------
    np.ndarray
        Calibrated probabilities.
    """
    return calibrator.predict(raw_proba)


def compute_ece(y_true, y_proba, n_bins=10):
    """
    Compute Expected Calibration Error (ECE).

    ECE measures the average gap between predicted probability and
    actual observed rate across probability bins.

    Parameters
    ----------
    y_true : array-like
        True binary labels.
    y_proba : array-like
        Predicted probabilities.
    n_bins : int
        Number of bins for calibration assessment.

    Returns
    -------
    float
        ECE value (lower is better, 0 = perfectly calibrated).
    """
    y_true = np.asarray(y_true)
    y_proba = np.asarray(y_proba)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        mask = (y_proba >= bin_edges[i]) & (y_proba < bin_edges[i + 1])
        if mask.sum() > 0:
            avg_pred = y_proba[mask].mean()
            avg_actual = y_true[mask].mean()
            weight = mask.sum() / len(y_true)
            ece += weight * abs(avg_pred - avg_actual)

    return ece


def evaluate_calibration(y_true, raw_proba, calibrated_proba, n_bins=10):
    """
    Evaluate calibration quality before and after.

    Parameters
    ----------
    y_true : array-like
        True binary labels.
    raw_proba : array-like
        Uncalibrated probabilities.
    calibrated_proba : array-like
        Calibrated probabilities.
    n_bins : int
        Number of bins.

    Returns
    -------
    dict
        Calibration metrics: ECE, Brier Score (before and after).
    """
    return {
        'ece_before': compute_ece(y_true, raw_proba, n_bins),
        'ece_after': compute_ece(y_true, calibrated_proba, n_bins),
        'brier_before': brier_score_loss(y_true, raw_proba),
        'brier_after': brier_score_loss(y_true, calibrated_proba),
    }
