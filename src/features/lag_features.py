"""
Lag Features for LGA Flight Delay Prediction

This module implements time-lagged features that capture temporal patterns
in flight delays. These features use historical delay information from
preceding flights to predict current flight delays.

CRITICAL: All lag features use shift() to prevent data leakage.
The delay value of the current flight is NEVER used in feature calculation.
"""

import pandas as pd
import numpy as np
from typing import List, Optional


def add_lag_features(
    df: pd.DataFrame,
    delay_col: str = 'Total_Calculated_Delay',
    datetime_col: str = 'Scheduled_Arrival_Datetime',
    date_col: str = 'Date',
    terminal_col: str = 'Terminal_Clean',
    airline_col: str = 'Marketing Airline Desc',
    origin_col: str = 'Non-PA Airport',
    verbose: bool = True
) -> pd.DataFrame:
    """
    Add time-lagged features to capture temporal delay patterns.

    Features added:
    - delay_rolling_1h: Rolling mean delay in the past 1 hour (same day)
    - delay_rolling_3h: Rolling mean delay in the past 3 hours (same day)
    - delay_rate_1h: Percentage of delayed flights in past 1 hour
    - severe_delay_count_prev: Count of severe delays (>60 min) in past 3 hours
    - terminal_delay_1h: Average delay at the same terminal in past 1 hour

    NOTE: Multi-day rolling features (airline_delay_7d, route_delay_7d) were removed
    per sponsor feedback (2026-02-04): "Once yesterday is over, today is a new day"
    - Airport operations reset at midnight; multi-day patterns don't help prediction

    IMPORTANT: All features use shift(1) to exclude the current observation
    and prevent data leakage.

    Parameters
    ----------
    df : pd.DataFrame
        Flight data with delay and datetime columns
    delay_col : str
        Name of the delay column (in minutes)
    datetime_col : str
        Name of the scheduled datetime column
    date_col : str
        Name of the date column
    terminal_col : str
        Name of the terminal column
    airline_col : str
        Name of the airline column
    origin_col : str
        Name of the origin airport column
    verbose : bool
        If True, print statistics about added features

    Returns
    -------
    pd.DataFrame
        DataFrame with lag features added
    """
    df = df.copy()

    # Ensure datetime column is datetime type
    if not pd.api.types.is_datetime64_any_dtype(df[datetime_col]):
        df[datetime_col] = pd.to_datetime(df[datetime_col])

    # Sort by datetime for proper lag calculation
    df = df.sort_values(datetime_col).reset_index(drop=True)

    # Create binary delay indicator (DOT standard: >15 min is delayed)
    df['_is_delayed'] = (df[delay_col] > 15).astype(int)

    # Create severe delay indicator (>60 min)
    df['_is_severe'] = (df[delay_col] > 60).astype(int)

    # --- Feature 1 & 2: Rolling delay mean (1h and 3h) ---
    # Group by date to prevent cross-day contamination
    # Use shift(1) to exclude current observation

    # Create a time index for rolling calculations
    df = df.set_index(datetime_col)

    # Rolling 1-hour mean (shifted)
    df['delay_rolling_1h'] = df.groupby(date_col)[delay_col].transform(
        lambda x: x.shift(1).rolling('1h', min_periods=1).mean()
    )

    # Rolling 3-hour mean (shifted)
    df['delay_rolling_3h'] = df.groupby(date_col)[delay_col].transform(
        lambda x: x.shift(1).rolling('3h', min_periods=1).mean()
    )

    # --- Feature 3: Delay rate in past 1 hour ---
    df['delay_rate_1h'] = df.groupby(date_col)['_is_delayed'].transform(
        lambda x: x.shift(1).rolling('1h', min_periods=1).mean()
    )

    # --- Feature 4: Severe delay count in past 3 hours ---
    df['severe_delay_count_prev'] = df.groupby(date_col)['_is_severe'].transform(
        lambda x: x.shift(1).rolling('3h', min_periods=1).sum()
    )

    # --- Feature 5: Terminal-specific delay (1 hour) ---
    df['terminal_delay_1h'] = df.groupby([date_col, terminal_col])[delay_col].transform(
        lambda x: x.shift(1).rolling('1h', min_periods=1).mean()
    )

    # Reset index
    df = df.reset_index()

    # NOTE: Multi-day features (airline_delay_7d, route_delay_7d) removed per sponsor feedback
    # Reason: Airport operations reset daily; "yesterday doesn't matter"

    # --- Fill NaN values ---
    # For the first observations where rolling windows have no prior data
    lag_features = [
        'delay_rolling_1h', 'delay_rolling_3h', 'delay_rate_1h',
        'severe_delay_count_prev', 'terminal_delay_1h'
    ]

    for col in lag_features:
        if col in df.columns:
            # Fill NaN with column median (or 0 for counts)
            if 'count' in col:
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna(df[col].median())

    # Drop temporary columns
    df = df.drop(columns=['_is_delayed', '_is_severe'], errors='ignore')

    if verbose:
        print("Lag Features Added:")
        for col in lag_features:
            if col in df.columns:
                print(f"  - {col}: mean={df[col].mean():.2f}, "
                      f"null_count={df[col].isna().sum()}")

    return df


# NOTE: add_hourly_lag_features() function removed per sponsor feedback (2026-02-04)
# Reason: hour_delay_prev_day and hour_delay_rolling_7d use multi-day data
# "Once yesterday is over, today is a new day" - airport operations reset at midnight


def add_congestion_features(
    df: pd.DataFrame,
    datetime_col: str = 'Scheduled_Arrival_Datetime',
    date_col: str = 'Date',
    terminal_col: str = 'Terminal_Clean',
    verbose: bool = True
) -> pd.DataFrame:
    """
    Add airport congestion features based on flight counts.

    Features added:
    - arrivals_prev_1h: Number of arrivals in the past 1 hour
    - arrivals_prev_3h: Number of arrivals in the past 3 hours
    - terminal_arrivals_prev_1h: Terminal-specific arrivals in past 1 hour

    Parameters
    ----------
    df : pd.DataFrame
        Flight data
    datetime_col : str
        Datetime column name
    date_col : str
        Date column name
    terminal_col : str
        Terminal column name
    verbose : bool
        Print statistics if True

    Returns
    -------
    pd.DataFrame
        DataFrame with congestion features added
    """
    df = df.copy()

    # Ensure datetime type
    if not pd.api.types.is_datetime64_any_dtype(df[datetime_col]):
        df[datetime_col] = pd.to_datetime(df[datetime_col])

    # Sort by datetime
    df = df.sort_values(datetime_col).reset_index(drop=True)

    # Create count column (each row is 1 flight)
    df['_flight_count'] = 1

    # Set datetime as index for rolling
    df = df.set_index(datetime_col)

    # Arrivals in past 1 hour (shifted)
    df['arrivals_prev_1h'] = df.groupby(date_col)['_flight_count'].transform(
        lambda x: x.shift(1).rolling('1h', min_periods=0).sum()
    )

    # Arrivals in past 3 hours (shifted)
    df['arrivals_prev_3h'] = df.groupby(date_col)['_flight_count'].transform(
        lambda x: x.shift(1).rolling('3h', min_periods=0).sum()
    )

    # Terminal-specific arrivals in past 1 hour
    df['terminal_arrivals_prev_1h'] = df.groupby([date_col, terminal_col])['_flight_count'].transform(
        lambda x: x.shift(1).rolling('1h', min_periods=0).sum()
    )

    # Reset index
    df = df.reset_index()

    # Drop temporary column
    df = df.drop(columns=['_flight_count'])

    # Fill NaN with 0 (no prior flights)
    for col in ['arrivals_prev_1h', 'arrivals_prev_3h', 'terminal_arrivals_prev_1h']:
        df[col] = df[col].fillna(0)

    if verbose:
        print("Congestion Features Added:")
        print(f"  - arrivals_prev_1h: mean={df['arrivals_prev_1h'].mean():.1f}")
        print(f"  - arrivals_prev_3h: mean={df['arrivals_prev_3h'].mean():.1f}")
        print(f"  - terminal_arrivals_prev_1h: mean={df['terminal_arrivals_prev_1h'].mean():.1f}")

    return df


# List of all lag features for easy reference
# NOTE: Multi-day features removed per sponsor feedback (2026-02-04)
LAG_FEATURES = [
    'delay_rolling_1h',
    'delay_rolling_3h',
    'delay_rate_1h',
    'severe_delay_count_prev',
    'terminal_delay_1h',
]

# Extended features include congestion metrics
LAG_FEATURES_EXTENDED = LAG_FEATURES + [
    'arrivals_prev_1h',
    'arrivals_prev_3h',
    'terminal_arrivals_prev_1h',
]

# V4.0 lag features (added for departure/taxi/runway/capacity/missed approach)
V4_LAG_FEATURES = [
    'avg_taxi_in_1h',
    'runway_config_change',
    'lga_dep_delay_1h',
    'lga_capacity_util',
    'missed_approach_1h',
]

# All lag features combined
LAG_FEATURES_ALL = LAG_FEATURES_EXTENDED + V4_LAG_FEATURES

# Removed features (for reference):
# - airline_delay_7d: 7-day rolling by airline
# - route_delay_7d: 7-day rolling by route
# - hour_delay_prev_day: previous day same hour
# - hour_delay_rolling_7d: 7-day rolling by hour


def compute_v4_lag_features(
    df_flights: pd.DataFrame,
    df_departures: Optional[pd.DataFrame] = None,
    df_missed: Optional[pd.DataFrame] = None,
    datetime_col: str = 'Scheduled_Arrival_Datetime',
    date_col: str = 'Date',
    verbose: bool = True
) -> pd.DataFrame:
    """
    Compute V4.0 lag features from departure data, taxi times, runway changes,
    and missed approaches.

    IMPORTANT: Must be called AFTER train/test split to prevent leakage.
    Uses shift() or previous-hour aggregation to exclude current observation.

    Features added:
    - avg_taxi_in_1h: Rolling mean of Total Taxi Time Calc in past 1 hour
    - runway_config_change: 1 if arrival runway changed vs previous flight in past 1h
    - lga_dep_delay_1h: Mean departure delay in the previous hour (hourly aggregation)
    - lga_capacity_util: (arrivals_1h + departures_1h) / 71 (FAA slot cap)
    - missed_approach_1h: Count of missed approaches in the current hour

    Parameters
    ----------
    df_flights : pd.DataFrame
        Flight data (train or test with context)
    df_departures : pd.DataFrame, optional
        Departure data with Scheduled_Departure_Datetime and Dep_Calculated_Delay
    df_missed : pd.DataFrame, optional
        Missed approach data with MA_Datetime
    datetime_col : str
        Scheduled arrival datetime column
    date_col : str
        Date column
    verbose : bool
        Print statistics if True

    Returns
    -------
    pd.DataFrame
        DataFrame with V5 lag features added
    """
    df = df_flights.copy()

    # Drop pre-existing V4.0 lag columns to avoid merge suffix collisions
    # (happens when context rows from train already have these columns)
    existing_v4 = [c for c in V4_LAG_FEATURES if c in df.columns]
    if existing_v4:
        df = df.drop(columns=existing_v4)

    if not pd.api.types.is_datetime64_any_dtype(df[datetime_col]):
        df[datetime_col] = pd.to_datetime(df[datetime_col])

    df = df.sort_values(datetime_col).reset_index(drop=True)

    # --- avg_taxi_in_1h: rolling mean taxi-in time past 1h ---
    if 'Total Taxi Time Calc' in df.columns:
        taxi_numeric = pd.to_numeric(df['Total Taxi Time Calc'], errors='coerce')
        df['_taxi_numeric'] = taxi_numeric
        df = df.set_index(datetime_col)
        df['avg_taxi_in_1h'] = df.groupby(date_col)['_taxi_numeric'].transform(
            lambda x: x.shift(1).rolling('1h', min_periods=1).mean()
        )
        df = df.reset_index()
        df.drop(columns=['_taxi_numeric'], inplace=True)
    else:
        df['avg_taxi_in_1h'] = np.nan

    # --- runway_config_change: did runway change in past 1h? ---
    rwy_col = 'Runway_Clean' if 'Runway_Clean' in df.columns else 'Arrival Runway'
    if rwy_col in df.columns:
        df = df.set_index(datetime_col)
        df['_rwy_shifted'] = df.groupby(date_col)[rwy_col].shift(1)
        df['_rwy_changed'] = (
            (df[rwy_col] != df['_rwy_shifted']) &
            df['_rwy_shifted'].notna()
        ).astype(int)
        df['runway_config_change'] = df.groupby(date_col)['_rwy_changed'].transform(
            lambda x: x.rolling('1h', min_periods=1).max()
        )
        df = df.reset_index()
        df.drop(columns=['_rwy_shifted', '_rwy_changed'], inplace=True)
    else:
        df['runway_config_change'] = 0

    # --- lga_dep_delay_1h: mean departure delay in previous hour ---
    # Uses hourly aggregation (O(n+m)) instead of per-flight rolling (O(n*m))
    if df_departures is not None and len(df_departures) > 0:
        deps = df_departures.copy()
        dep_ts_col = 'Scheduled_Departure_Datetime'
        if not pd.api.types.is_datetime64_any_dtype(deps[dep_ts_col]):
            deps[dep_ts_col] = pd.to_datetime(deps[dep_ts_col])
        deps = deps.dropna(subset=[dep_ts_col, 'Dep_Calculated_Delay'])
        deps['_dep_hour'] = deps[dep_ts_col].dt.floor('h')

        dep_hourly = deps.groupby('_dep_hour')['Dep_Calculated_Delay'].mean().reset_index()
        dep_hourly.columns = ['_match_hour', 'lga_dep_delay_1h']

        # Use PREVIOUS hour to avoid leakage
        df['_match_hour'] = df[datetime_col].dt.floor('h') - pd.Timedelta(hours=1)
        df = df.merge(dep_hourly, on='_match_hour', how='left')
        df.drop(columns=['_match_hour'], inplace=True)
    else:
        df['lga_dep_delay_1h'] = np.nan

    # --- lga_capacity_util: (arr_1h + dep_1h) / 71 ---
    if 'arrivals_prev_1h' in df.columns and df_departures is not None and len(df_departures) > 0:
        deps = df_departures.copy()
        dep_ts_col = 'Scheduled_Departure_Datetime'
        if not pd.api.types.is_datetime64_any_dtype(deps[dep_ts_col]):
            deps[dep_ts_col] = pd.to_datetime(deps[dep_ts_col])
        deps = deps.dropna(subset=[dep_ts_col])
        deps['_dep_hour'] = deps[dep_ts_col].dt.floor('h')

        dep_counts = deps.groupby('_dep_hour').size().reset_index(name='_dep_count')
        dep_counts.columns = ['_cap_hour', '_dep_count']

        # Use previous hour for departure counts
        df['_cap_hour'] = df[datetime_col].dt.floor('h') - pd.Timedelta(hours=1)
        df = df.merge(dep_counts, on='_cap_hour', how='left')
        df['_dep_count'] = df['_dep_count'].fillna(0)
        df['lga_capacity_util'] = (df['arrivals_prev_1h'] + df['_dep_count']) / 71.0
        df.drop(columns=['_cap_hour', '_dep_count'], inplace=True)
    else:
        df['lga_capacity_util'] = np.nan

    # --- missed_approach_1h: count in current hour ---
    if df_missed is not None and len(df_missed) > 0:
        missed = df_missed.copy()
        if not pd.api.types.is_datetime64_any_dtype(missed['MA_Datetime']):
            missed['MA_Datetime'] = pd.to_datetime(missed['MA_Datetime'])
        missed = missed.dropna(subset=['MA_Datetime'])
        missed['_ma_hour'] = missed['MA_Datetime'].dt.floor('h')

        ma_counts = missed.groupby('_ma_hour').size().reset_index(name='missed_approach_1h')
        ma_counts.columns = ['_ma_match_hour', 'missed_approach_1h']

        # Use current hour (missed approaches are observable in real-time)
        df['_ma_match_hour'] = df[datetime_col].dt.floor('h')
        df = df.merge(ma_counts, on='_ma_match_hour', how='left')
        df['missed_approach_1h'] = df['missed_approach_1h'].fillna(0)
        df.drop(columns=['_ma_match_hour'], inplace=True)
    else:
        df['missed_approach_1h'] = 0

    # --- Fill NaN ---
    for col in V4_LAG_FEATURES:
        if col in df.columns:
            if col in ('runway_config_change', 'missed_approach_1h'):
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna(df[col].median() if df[col].notna().any() else 0)

    if verbose:
        print("V4.0 Lag Features Added:")
        for col in V4_LAG_FEATURES:
            if col in df.columns:
                null_pct = df[col].isna().sum() / len(df) * 100
                print(f"  - {col}: mean={df[col].mean():.2f}, null={null_pct:.1f}%")

    return df
