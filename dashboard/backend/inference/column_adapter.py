"""Column-name adapter between dashboard's cleaned schema and src/features expectations.

The src/features modules (lag_features, aircraft_features, network_features) were
written for the notebook's feature-engineering schema:

    Total_Calculated_Delay         (delay in minutes)
    Scheduled_Arrival_Datetime     (datetime)
    Date                           (date)
    Terminal_Clean                 (terminal label)
    Marketing Airline Desc         (airline name)
    Non-PA Airport                 (origin/destination)
    Registration                   (tail number)

The dashboard backend's cleaned flight cache uses different names (see
data/processor.py::clean_flight_data):

    Delay_Minutes
    Scheduled_Time
    Date
    Terminal
    Airline
    Origin / Destination (depending on direction)
    Registration

This module translates between the two so we can reuse the proven feature logic
in src/features without forking it.
"""

from __future__ import annotations

import pandas as pd


# Map dashboard cleaned column → notebook feature-engineering column.
# Keys must exist in the dashboard df; values are the names src/features expects.
DASHBOARD_TO_NOTEBOOK = {
    "Delay_Minutes": "Total_Calculated_Delay",
    "Scheduled_Time": "Scheduled_Arrival_Datetime",
    "Terminal": "Terminal_Clean",
    "Airline": "Marketing Airline Desc",
    "Origin": "Non-PA Airport",        # arrivals
    "Destination": "Non-PA Airport",   # departures (one of these will exist, not both)
    # Date, Registration: same name in both schemas — no rename needed
}

# Reverse map for restoring after feature computation.
NOTEBOOK_TO_DASHBOARD = {v: k for k, v in DASHBOARD_TO_NOTEBOOK.items() if k != "Destination"}
# Note: "Destination" reverse is ambiguous; departures must be handled in caller.


def to_notebook_schema(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    """Return a copy of df with columns renamed to match notebook expectations.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned flight data from dashboard backend.
    direction : str
        "arrival" or "departure".  Used to decide whether Origin or Destination
        becomes the "Non-PA Airport" column.

    Returns
    -------
    pd.DataFrame
        Renamed copy. Original df is not mutated.
    """
    out = df.copy()
    rename_map: dict[str, str] = {}
    for src, dst in DASHBOARD_TO_NOTEBOOK.items():
        if src in out.columns and dst not in out.columns:
            rename_map[src] = dst
    out = out.rename(columns=rename_map)

    # Compose unified `Non-PA Airport` column from whichever side exists.
    if "Non-PA Airport" not in out.columns:
        if direction == "arrival" and "Origin" in out.columns:
            out["Non-PA Airport"] = out["Origin"]
        elif direction == "departure" and "Destination" in out.columns:
            out["Non-PA Airport"] = out["Destination"]
        else:
            out["Non-PA Airport"] = ""  # downstream feature lookups will fall back to defaults

    return out
