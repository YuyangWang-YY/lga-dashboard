"""
Temporal Decay Sample Weights for LGA Flight Delay Prediction

Addresses the train/test distribution shift (Train 28.9% delayed → Test 18.9% delayed)
by applying exponential decay weights so the model emphasizes recent training data.

Usage:
    from src.models.temporal_weights import compute_temporal_weights, combine_temporal_and_class_weights

    # Compute temporal weights
    t_weights = compute_temporal_weights(train['Date'], cutoff_date, half_life=30)

    # For LGB/XGB: combine with class imbalance weights (replaces scale_pos_weight)
    sample_weights = combine_temporal_and_class_weights(t_weights, y_train, class_weight_ratio=4.0)
    model.fit(X_train, y_train, sample_weight=sample_weights)

    # For CatBoost: pass temporal-only weights (keep auto_class_weights='Balanced')
    model.fit(X_train, y_train, sample_weight=t_weights)
"""

import numpy as np
import pandas as pd


def compute_temporal_weights(dates, cutoff_date, half_life, min_weight=0.01):
    """
    Compute exponential decay sample weights based on temporal distance.

    Weight formula: w = exp(-ln(2) * days_ago / half_life)
    - At cutoff_date: weight = 1.0
    - At half_life days before cutoff: weight = 0.5
    - At 2*half_life days before: weight = 0.25

    Parameters
    ----------
    dates : array-like
        Date values for each training sample.
    cutoff_date : str or pd.Timestamp
        The reference date (typically train/test split date).
        Samples closer to this date get higher weight.
    half_life : float
        Number of days for weight to decay to 0.5.
        Smaller = more aggressive decay (focus on recent data).
        Typical range: 7-60 days.
    min_weight : float, default=0.01
        Minimum weight to prevent very old samples from being ignored entirely.

    Returns
    -------
    np.ndarray
        Array of weights in [min_weight, 1.0], same length as dates.
    """
    cutoff = pd.to_datetime(cutoff_date)
    days_ago = (cutoff - pd.to_datetime(dates)).dt.days.values.astype(float)
    days_ago = np.clip(days_ago, 0, None)
    weights = np.exp(-np.log(2) * days_ago / half_life)
    return np.clip(weights, min_weight, 1.0)


def combine_temporal_and_class_weights(temporal_weights, y_train, class_weight_ratio):
    """
    Combine temporal decay weights with class imbalance weights.

    This replaces scale_pos_weight for LGB/XGB by baking both
    temporal proximity and class imbalance into a single sample_weight vector.

    Positive samples (delayed=1) get multiplied by class_weight_ratio,
    negative samples (delayed=0) keep weight=1.0, then both are scaled
    by the temporal weight.

    Parameters
    ----------
    temporal_weights : np.ndarray
        Temporal decay weights from compute_temporal_weights().
    y_train : array-like
        Binary target labels (0/1).
    class_weight_ratio : float
        Weight multiplier for positive class (equivalent to scale_pos_weight).

    Returns
    -------
    np.ndarray
        Combined sample weights.
    """
    y = np.asarray(y_train)
    class_multiplier = np.where(y == 1, class_weight_ratio, 1.0)
    return temporal_weights * class_multiplier
