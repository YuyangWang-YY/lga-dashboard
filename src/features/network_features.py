"""
Network-based Features for LGA Flight Delay Prediction

This module implements features derived from the Network Analysis report.
These features capture the origin airport's historical delay patterns and risk levels.
"""

import pandas as pd
import numpy as np
from typing import Optional

from .origin_lookup import (
    ORIGIN_STATS,
    HIGH_RISK_ORIGINS,
    SEVERE_DELAY_AIRPORTS,
    CRITICAL_ARRIVAL_AIRPORTS,
    get_origin_impact_score,
    get_origin_avg_delay,
    get_severe_delay_rate,
)


def add_network_features(
    df: pd.DataFrame,
    origin_col: str = 'Non-PA Airport',
    verbose: bool = True
) -> pd.DataFrame:
    """
    Add network-based features to the flight data.

    Features added:
    - origin_impact_score: Total delay impact score (volume × avg delay)
    - origin_historical_delay: Historical average arrival delay from this origin
    - origin_severe_delay_rate: Percentage of flights with severe delays (>6h)
    - is_high_risk_origin: Binary flag for high-risk origins (used internally by route_risk_score)
    - origin_risk_level: Categorical risk level (CRITICAL/VERY_HIGH/HIGH/MEDIUM/LOW)

    NOTE (2026-02-04): is_critical_arrival_airport → post-prediction flag only.
    NOTE (2026-02-05): origin_tier removed (low SHAP importance).
    is_high_risk_origin kept internally for route_risk_score calculation.

    Parameters
    ----------
    df : pd.DataFrame
        Flight data with origin airport column
    origin_col : str
        Name of the column containing origin airport codes
    verbose : bool
        If True, print statistics about the added features

    Returns
    -------
    pd.DataFrame
        DataFrame with network features added
    """
    df = df.copy()

    # Feature 1: Origin Impact Score
    df['origin_impact_score'] = df[origin_col].map(
        lambda x: get_origin_impact_score(x)
    ).fillna(0)

    # Feature 2: Origin Historical Delay
    # Default to 15.0 min (overall mean is ~16 min for arrivals)
    df['origin_historical_delay'] = df[origin_col].map(
        lambda x: get_origin_avg_delay(x, default=15.0)
    )

    # Feature 3: Origin Severe Delay Rate
    df['origin_severe_delay_rate'] = df[origin_col].map(
        lambda x: get_severe_delay_rate(x)
    ).fillna(0)

    # Feature 4: Is High Risk Origin (binary)
    df['is_high_risk_origin'] = df[origin_col].isin(HIGH_RISK_ORIGINS).astype(int)

    # NOTE: is_critical_arrival_airport removed from training features
    # Use apply_critical_airport_flag() for post-prediction flagging

    # Feature 5: Origin Risk Level (categorical → numeric encoding)
    risk_level_map = {
        'CRITICAL': 4,
        'VERY_HIGH': 3,
        'HIGH': 2,
        'MEDIUM': 1,
        'LOW': 0
    }

    def get_risk_level_numeric(airport_code):
        stats = SEVERE_DELAY_AIRPORTS.get(airport_code, {})
        level = stats.get('risk_level', 'LOW')
        return risk_level_map.get(level, 0)

    df['origin_risk_level'] = df[origin_col].map(get_risk_level_numeric)

    if verbose:
        print("Network Features Added:")
        print(f"  - origin_impact_score: mean={df['origin_impact_score'].mean():.2f}, "
              f"max={df['origin_impact_score'].max():.2f}")
        print(f"  - origin_historical_delay: mean={df['origin_historical_delay'].mean():.2f} min")
        print(f"  - is_high_risk_origin: {df['is_high_risk_origin'].sum()} flights "
              f"({df['is_high_risk_origin'].mean()*100:.1f}%)")

    return df


def add_route_risk_score(
    df: pd.DataFrame,
    origin_col: str = 'Non-PA Airport'
) -> pd.DataFrame:
    """
    Add composite route risk score combining multiple factors.

    Risk Score = (normalized_impact + normalized_delay + severe_rate + is_high_risk) / 4

    Parameters
    ----------
    df : pd.DataFrame
        Flight data
    origin_col : str
        Column containing origin airport codes

    Returns
    -------
    pd.DataFrame
        DataFrame with route_risk_score feature added
    """
    df = df.copy()

    # Normalize impact score (0-1)
    max_impact = 153756  # ORD's impact score
    df['_norm_impact'] = df['origin_impact_score'] / max_impact

    # Normalize historical delay (0-1), cap at 100 min
    df['_norm_delay'] = (df['origin_historical_delay'].clip(upper=100) / 100)

    # Normalize severe delay rate (0-1), max is ~13.57%
    df['_norm_severe'] = (df['origin_severe_delay_rate'] / 15.0).clip(upper=1)

    # Combine into risk score
    df['route_risk_score'] = (
        df['_norm_impact'] * 0.3 +
        df['_norm_delay'] * 0.3 +
        df['_norm_severe'] * 0.2 +
        df['is_high_risk_origin'] * 0.2
    )

    # Drop temporary columns
    df = df.drop(columns=['_norm_impact', '_norm_delay', '_norm_severe'])

    return df


# Features used by the model (2026-02-05 updated)
# NOTE: is_high_risk_origin computed internally for route_risk_score but not a standalone model feature
# NOTE: origin_tier removed (low SHAP importance)
NETWORK_FEATURES = [
    'origin_impact_score',
    'origin_historical_delay',
    'origin_severe_delay_rate',
    'origin_risk_level',
    'route_risk_score',
]


def apply_critical_airport_flag(
    predictions_df: pd.DataFrame,
    origin_col: str = 'Non-PA Airport',
    prediction_col: str = 'predicted_delay'
) -> pd.DataFrame:
    """
    Post-prediction function: Add critical airport flag for dashboard display.

    This is NOT a model feature. Per sponsor feedback (2026-02-04):
    "This might be more useful as an explanatory variable, not as a predictive variable.
    After we create the predictions, we look at any flights that are delayed from that
    airport and we give it a flag or add a multiplier."

    Parameters
    ----------
    predictions_df : pd.DataFrame
        DataFrame with model predictions
    origin_col : str
        Column containing origin airport codes
    prediction_col : str
        Column containing predicted delay (binary: 1=delayed, 0=not delayed)

    Returns
    -------
    pd.DataFrame
        DataFrame with 'critical_airport_flag' added for dashboard use
    """
    predictions_df = predictions_df.copy()

    # Flag delayed flights from critical airports
    is_from_critical = predictions_df[origin_col].isin(CRITICAL_ARRIVAL_AIRPORTS)

    if prediction_col in predictions_df.columns:
        # Flag = predicted delay AND from critical airport
        predictions_df['critical_airport_flag'] = (
            (predictions_df[prediction_col] == 1) & is_from_critical
        ).astype(int)
    else:
        # Just flag if from critical airport (for pre-prediction use)
        predictions_df['is_from_critical_airport'] = is_from_critical.astype(int)

    return predictions_df
