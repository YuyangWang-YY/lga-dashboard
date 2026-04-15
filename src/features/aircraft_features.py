"""
Aircraft Continuity Features for LGA Flight Delay Prediction (V5.0)

Tracks the same aircraft (by Registration / tail number) across consecutive
LGA arrivals.  When the turnaround is short (< 8 h), the previous arrival's
delay is a strong predictor of the current one (3-5x lift).

Reference: "Delay-Absorption Two-Stage Model" (arXiv 2512.08197)
  - AUC 0.865 → 0.898, Precision 72% → 82% with inbound aircraft features

CRITICAL: Must be called AFTER train/test split to prevent data leakage.
Uses shift(1) so the current flight's own delay is never included.
"""

import pandas as pd
import numpy as np


# Features produced by this module
AIRCRAFT_FEATURES = [
    'prev_aircraft_delay',
    'prev_aircraft_delayed',
    'turnaround_hours',
    'turnaround_buffer',
]


def compute_prev_aircraft_delay(
    df: pd.DataFrame,
    registration_col: str = 'Registration',
    datetime_col: str = 'Scheduled_Arrival_Datetime',
    delay_col: str = 'Total_Calculated_Delay',
    max_gap_hours: float = 8.0,
    min_turnaround_hours: float = 0.75,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Self-join on Registration: find the same aircraft's previous LGA arrival
    and extract its delay as a feature.

    Only keeps pairs where turnaround < max_gap_hours (signal disappears
    beyond ~8 h based on exploratory analysis).

    Features added
    --------------
    prev_aircraft_delay : float
        Previous arrival delay in minutes (NaN if no short-turnaround match).
    prev_aircraft_delayed : float
        1.0 if previous arrival was delayed (>15 min), 0.0 otherwise, NaN if
        no match.
    turnaround_hours : float
        Hours between the two consecutive arrivals of the same aircraft.
    turnaround_buffer : float
        turnaround_hours - min_turnaround_hours (45 min default).
        Negative means the aircraft had less than the minimum expected
        ground time.

    Parameters
    ----------
    df : pd.DataFrame
        Flight data (train or test-with-context).
    registration_col : str
        Column containing aircraft tail number (N-number).
    datetime_col : str
        Scheduled arrival datetime column.
    delay_col : str
        Total delay column (minutes).
    max_gap_hours : float
        Maximum turnaround to consider (hours). Pairs beyond this are
        treated as no-match.
    min_turnaround_hours : float
        Minimum expected ground time (hours) for buffer calculation.
    verbose : bool
        Print coverage statistics.

    Returns
    -------
    pd.DataFrame
        Input DataFrame with 4 new columns appended.
    """
    df = df.copy()

    # Ensure types
    if not pd.api.types.is_datetime64_any_dtype(df[datetime_col]):
        df[datetime_col] = pd.to_datetime(df[datetime_col])

    # Sort by aircraft then time so shift(1) gives the previous arrival
    # for the same aircraft
    df = df.sort_values([registration_col, datetime_col]).reset_index(drop=True)

    # Previous arrival time and delay for the same aircraft
    grp = df.groupby(registration_col)
    prev_time = grp[datetime_col].shift(1)
    prev_delay = grp[delay_col].shift(1)

    # Turnaround gap in hours
    gap_hours = (df[datetime_col] - prev_time).dt.total_seconds() / 3600

    # Only keep short turnarounds (strong signal region)
    valid = (gap_hours > 0) & (gap_hours <= max_gap_hours)

    df['prev_aircraft_delay'] = np.where(valid, prev_delay, np.nan)
    df['prev_aircraft_delayed'] = np.where(
        valid, (prev_delay > 15).astype(float), np.nan
    )
    df['turnaround_hours'] = np.where(valid, gap_hours, np.nan)
    df['turnaround_buffer'] = np.where(
        valid, gap_hours - min_turnaround_hours, np.nan
    )

    # --- Fill NaN with median (for flights without a short-turnaround match) ---
    for col in AIRCRAFT_FEATURES:
        if col == 'prev_aircraft_delayed':
            # Binary: fill with overall delay rate as prior
            df[col] = df[col].fillna(0.0)
        else:
            median_val = df[col].median() if df[col].notna().any() else 0.0
            df[col] = df[col].fillna(median_val)

    if verbose:
        n_valid = valid.sum()
        pct = n_valid / len(df) * 100
        print(f"Aircraft Continuity Features (V5.0):")
        print(f"  Flights with short-turnaround match: {n_valid:,} / {len(df):,} ({pct:.1f}%)")
        for col in AIRCRAFT_FEATURES:
            print(f"  - {col}: mean={df[col].mean():.2f}, "
                  f"non-null={df[col].notna().sum():,}")

    return df
