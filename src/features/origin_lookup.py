"""
Origin Airport Statistics Lookup Table

Data loaded from Network Analysis output:
- data/processed/origin_airport_stats.csv (111 airports)
- data/processed/destination_airport_stats.csv (100 airports)
- data/processed/overlap_airports.json

Analysis Period: May - September 2025
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List

# Get project root (relative to this file's location)
_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
_DATA_DIR = _PROJECT_ROOT / 'data' / 'processed'


def _load_airport_stats() -> Dict[str, dict]:
    """Load origin airport statistics from CSV."""
    csv_path = _DATA_DIR / 'origin_airport_stats.csv'

    if not csv_path.exists():
        print(f"Warning: {csv_path} not found. Using empty dict.")
        print("Run Network_Analysis_Improved_WithMaps.ipynb Section 9 to generate.")
        return {}

    df = pd.read_csv(csv_path)

    # Convert to dict: airport_code -> stats
    stats = {}
    for _, row in df.iterrows():
        stats[row['airport_code']] = {
            'mean_delay': row['mean_delay'],
            'median_delay': row['median_delay'],
            'std_delay': row['std_delay'],
            'total_flights': int(row['total_flights']),
            'impact_score': row['impact_score'],
        }

    return stats


def _load_overlap_airports() -> Dict[str, List[str]]:
    """Load overlap airport lists from JSON."""
    json_path = _DATA_DIR / 'overlap_airports.json'

    if not json_path.exists():
        print(f"Warning: {json_path} not found. Using empty lists.")
        return {'arrival_overlap': [], 'departure_overlap': []}

    with open(json_path, 'r') as f:
        return json.load(f)


# Load data on module import
ORIGIN_STATS = _load_airport_stats()
_OVERLAP_DATA = _load_overlap_airports()

# Critical overlap airports (high volume AND high delay)
CRITICAL_ARRIVAL_AIRPORTS = _OVERLAP_DATA.get('arrival_overlap', [])
CRITICAL_DEPARTURE_AIRPORTS = _OVERLAP_DATA.get('departure_overlap', [])

# High risk origins: union of arrival and departure overlap airports
HIGH_RISK_ORIGINS = list(set(CRITICAL_ARRIVAL_AIRPORTS + CRITICAL_DEPARTURE_AIRPORTS))

# Severe delay airports (hardcoded from Severe Delay Analysis report)
# These are airports with severe delays (>6 hours) - not available in CSV
SEVERE_DELAY_AIRPORTS = {
    'LGA': {'severe_count': 19, 'severe_rate': 13.57, 'risk_level': 'CRITICAL'},
    'PHL': {'severe_count': 7, 'severe_rate': 11.29, 'risk_level': 'CRITICAL'},
    'BWI': {'severe_count': 4, 'severe_rate': 7.69, 'risk_level': 'VERY_HIGH'},
    'ORD': {'severe_count': 29, 'severe_rate': 0.88, 'risk_level': 'HIGH'},
    'RDU': {'severe_count': 24, 'severe_rate': 1.81, 'risk_level': 'HIGH'},
    'ATL': {'severe_count': 14, 'severe_rate': None, 'risk_level': 'HIGH'},
    'RIC': {'severe_count': 14, 'severe_rate': None, 'risk_level': 'HIGH'},
    'MCO': {'severe_count': 13, 'severe_rate': None, 'risk_level': 'HIGH'},
    'CLT': {'severe_count': 12, 'severe_rate': None, 'risk_level': 'HIGH'},
    'PIT': {'severe_count': 11, 'severe_rate': None, 'risk_level': 'MEDIUM'},
    'IAD': {'severe_count': 11, 'severe_rate': 2.37, 'risk_level': 'MEDIUM'},
    'BNA': {'severe_count': 10, 'severe_rate': None, 'risk_level': 'MEDIUM'},
}


# ============== Helper Functions ==============

def get_origin_impact_score(airport_code: str) -> float:
    """Get impact score for an airport (flights x mean_delay)."""
    stats = ORIGIN_STATS.get(airport_code, {})
    return stats.get('impact_score', 0.0)


def get_origin_avg_delay(airport_code: str, default: float = 15.0) -> float:
    """Get average arrival delay for an airport."""
    stats = ORIGIN_STATS.get(airport_code, {})
    return stats.get('mean_delay', default)


def get_origin_flight_count(airport_code: str) -> int:
    """Get total flight count for an airport."""
    stats = ORIGIN_STATS.get(airport_code, {})
    return stats.get('total_flights', 0)


def get_severe_delay_rate(airport_code: str) -> float:
    """Get severe delay rate for an airport (% of flights with >6h delay)."""
    stats = SEVERE_DELAY_AIRPORTS.get(airport_code, {})
    return stats.get('severe_rate', 0.0) or 0.0


def is_high_risk_origin(airport_code: str) -> bool:
    """Check if airport is in the high-risk list."""
    return airport_code in HIGH_RISK_ORIGINS


def is_critical_arrival_airport(airport_code: str) -> bool:
    """Check if airport is in the critical arrival overlap list."""
    return airport_code in CRITICAL_ARRIVAL_AIRPORTS


def get_risk_level(airport_code: str) -> str:
    """Get risk level classification for an airport."""
    stats = SEVERE_DELAY_AIRPORTS.get(airport_code, {})
    return stats.get('risk_level', 'LOW')


def get_all_airports() -> List[str]:
    """Get list of all airports in the dataset."""
    return list(ORIGIN_STATS.keys())


def get_stats_dataframe() -> pd.DataFrame:
    """Get origin stats as a DataFrame."""
    if not ORIGIN_STATS:
        return pd.DataFrame()

    records = []
    for airport, stats in ORIGIN_STATS.items():
        records.append({'airport_code': airport, **stats})

    return pd.DataFrame(records)


# ============== Summary ==============

def print_summary():
    """Print summary of loaded data."""
    print("=" * 50)
    print("ORIGIN AIRPORT LOOKUP - DATA SUMMARY")
    print("=" * 50)
    print(f"Total airports loaded: {len(ORIGIN_STATS)}")
    print(f"Critical arrival airports: {len(CRITICAL_ARRIVAL_AIRPORTS)}")
    print(f"Critical departure airports: {len(CRITICAL_DEPARTURE_AIRPORTS)}")
    print(f"High risk origins: {len(HIGH_RISK_ORIGINS)}")
    print()
    if ORIGIN_STATS:
        print("Top 10 by Impact Score:")
        df = get_stats_dataframe()
        top10 = df.nlargest(10, 'impact_score')[['airport_code', 'total_flights', 'mean_delay', 'impact_score']]
        print(top10.to_string(index=False))
    print("=" * 50)


if __name__ == '__main__':
    print_summary()
