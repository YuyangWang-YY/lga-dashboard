"""
Weather Features for LGA Flight Delay Prediction

This module implements weather-related features including a combined weather
severity score. Per sponsor feedback (2026-02-04): "Maybe we can combine a
couple [weather columns] and create categories of weather."
"""

import pandas as pd
import numpy as np
from typing import Optional


def add_weather_severity_score(
    df: pd.DataFrame,
    precip_col: str = 'Precipitation',
    wind_col: str = 'Wind_Gusts',
    visibility_col: str = 'Visibility',
    verbose: bool = True
) -> pd.DataFrame:
    """
    Create a combined weather severity score from multiple weather indicators.

    This combines precipitation, wind gusts, and visibility into a single
    normalized score (0-1) that better captures overall weather conditions.

    Features added:
    - weather_severity_score: Weighted combination (0=good, 1=severe)
    - weather_category: Categorical (GOOD/MODERATE/SEVERE)

    Parameters
    ----------
    df : pd.DataFrame
        Flight data with weather columns
    precip_col : str
        Precipitation column name (inches)
    wind_col : str
        Wind gusts column name (mph)
    visibility_col : str
        Visibility column name (miles)
    verbose : bool
        Print statistics if True

    Returns
    -------
    pd.DataFrame
        DataFrame with weather severity features added
    """
    df = df.copy()

    # Check for required columns
    required_cols = [precip_col, wind_col, visibility_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        if verbose:
            print(f"Warning: Missing weather columns {missing}, skipping weather_severity_score")
        return df

    # Normalize each indicator to 0-1 scale
    # Higher values = worse weather

    # Precipitation: >0.5 inches = severe (1.0)
    precip_score = np.clip(df[precip_col].fillna(0) / 0.5, 0, 1)

    # Wind gusts: >40 mph = severe (1.0)
    wind_score = np.clip(df[wind_col].fillna(0) / 40, 0, 1)

    # Visibility: <1 mile = severe (1.0), 10 miles = good (0.0)
    # Invert so lower visibility = higher score
    vis_score = 1 - np.clip(df[visibility_col].fillna(10) / 10, 0, 1)

    # Weighted combination
    # Precipitation gets highest weight (thunderstorms are #1 cause in summer)
    df['weather_severity_score'] = (
        0.4 * precip_score +
        0.3 * wind_score +
        0.3 * vis_score
    )

    # Create categorical version
    df['weather_category'] = pd.cut(
        df['weather_severity_score'],
        bins=[-0.01, 0.3, 0.6, 1.01],
        labels=['GOOD', 'MODERATE', 'SEVERE']
    )

    # Encode category for model use
    category_map = {'GOOD': 0, 'MODERATE': 1, 'SEVERE': 2}
    df['weather_category_encoded'] = df['weather_category'].map(category_map)

    if verbose:
        print("Weather Severity Features Added:")
        print(f"  - weather_severity_score: mean={df['weather_severity_score'].mean():.3f}")
        print(f"  - weather_category distribution:")
        for cat, count in df['weather_category'].value_counts().items():
            pct = count / len(df) * 100
            print(f"      {cat}: {count} ({pct:.1f}%)")

    return df


def add_weather_alert_flags(
    df: pd.DataFrame,
    precip_col: str = 'Precipitation',
    wind_col: str = 'Wind_Gusts',
    visibility_col: str = 'Visibility',
) -> pd.DataFrame:
    """
    Add binary weather alert flags for extreme conditions.

    Features added:
    - heavy_rain_flag: 1 if precipitation > 0.3 inches
    - high_wind_flag: 1 if wind gusts > 30 mph
    - low_visibility_flag: 1 if visibility < 3 miles
    - weather_alert_count: Sum of all alert flags (0-3)

    Parameters
    ----------
    df : pd.DataFrame
        Flight data with weather columns

    Returns
    -------
    pd.DataFrame
        DataFrame with weather alert flags added
    """
    df = df.copy()

    # Individual alert flags
    if precip_col in df.columns:
        df['heavy_rain_flag'] = (df[precip_col].fillna(0) > 0.3).astype(int)
    else:
        df['heavy_rain_flag'] = 0

    if wind_col in df.columns:
        df['high_wind_flag'] = (df[wind_col].fillna(0) > 30).astype(int)
    else:
        df['high_wind_flag'] = 0

    if visibility_col in df.columns:
        df['low_visibility_flag'] = (df[visibility_col].fillna(10) < 3).astype(int)
    else:
        df['low_visibility_flag'] = 0

    # Combined alert count
    df['weather_alert_count'] = (
        df['heavy_rain_flag'] +
        df['high_wind_flag'] +
        df['low_visibility_flag']
    )

    return df


# LGA weather features (2026-02-05 updated)
WEATHER_FEATURES = [
    'Precipitation',
    'Wind_Gusts',
    'Visibility',
    'Is_Bad_Weather',
    'weather_severity_score',
    'weather_category_encoded',
    'lga_storm_flag',    # from Weather Desc keywords
    'lga_rain_flag',     # from Weather Desc keywords
    'lga_fog_flag',      # from Weather Desc keywords
]

# Origin airport weather features (expanded 2026-02-05)
ORIGIN_WEATHER_FEATURES = [
    'origin_precip',
    'origin_wind_gust',
    'origin_visibility',
    'origin_bad_weather',
    'origin_pressure',
    'origin_pressure_rapid_flag',   # from pressure_desc (79.9% null, null=0)
    'origin_dewpoint',
    'origin_cloud_cover',           # CLR=0..OVC=4
    'origin_storm_flag',            # from wx_phrase
    'origin_temp',
    'origin_pressure_change_3h',    # computed post-split in notebook 03
]
