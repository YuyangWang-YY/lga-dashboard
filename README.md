# LGA Flight Delay Prediction — Operations Dashboard

A real-time predictive intelligence system for LaGuardia Airport (LGA) operations.  
Built on historical flight data from January–October 2025, it enables AOC staff to identify high-risk flights before delays propagate across the network.

### Option 1 — Web (No Installation Required)

Access the hosted version directly in any browser:

**URL:** [https://lga-dashboard.vercel.app/](https://lga-dashboard.vercel.app/)  
**Password:** `LGA2025`

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Model Suite](#2-model-suite)
3. [Data Features Required by AOC](#3-data-features-required-by-aoc)
4. [Dashboard Walkthrough](#4-dashboard-walkthrough)
5. [How to Start the Dashboard](#5-how-to-start-the-dashboard)
6. [Project Structure](#6-project-structure)

---

## 1. System Overview

The system combines four machine learning models into a unified operations dashboard:

| Component | Role |
|-----------|------|
| Arrival Delay Classifier | Predicts whether an inbound flight will be delayed |
| Arrival Delay Regressor | Estimates how many minutes late it will arrive |
| Departure Delay Classifier | Predicts whether an outbound flight will be delayed |
| Departure Delay Regressor | Estimates departure delay duration in minutes |

Predictions are displayed on a time-simulation interface that replays any day in the Jan–Oct 2025 dataset. Each flight shows a delay probability, a 4-tier risk level, a predicted delay range, and a SHAP-bas

ed breakdown of what is driving the risk.

---

## 2. Model Suite

### 2.1 Arrival Delay Classifier — V9.0

**Algorithm:** CatBoost Gradient Boosted Trees  
**Task:** Binary classification — will this arrival be delayed?

| Metric | Value |
|--------|-------|
| AUC (ROC) | **0.808** |
| Features | 25 (21 base + 4 engineered interactions) |
| Training set | ~103,000 flights |
| Test set | ~44,000 flights |

**Operating mode thresholds:**

| Mode | Threshold | Use Case |
|------|-----------|----------|
| Balanced | 0.39 | Default — equal weight on catching delays and avoiding false alarms |
| High Precision | 0.66 | Fewer false alarms; only flag high-confidence delays |
| High Recall | 0.29 | Catch as many delays as possible; more false positives |

**Risk tiers (probability → label):**

| Tier | Probability |
|------|------------|
| CRITICAL | ≥ 0.75 |
| HIGH | 0.30 – 0.75 |
| MEDIUM | 0.15 – 0.30 |
| LOW | < 0.15 |

---

### 2.2 Arrival Delay Regressor — V9.0

**Algorithm:** CatBoost Quantile Regressor  
**Task:** Estimate arrival delay duration at the 50th percentile (median expected delay)  
**Output:** `pred_delay_q50` — median predicted delay in minutes (clipped to ≥ 0)

The regressor only runs on flights already flagged as delayed by the classifier. It provides the "how long" answer to complement the classifier's "yes/no" answer.

---

### 2.3 Departure Delay Classifier — V9.0

**Algorithm:** CatBoost Gradient Boosted Trees + Isotonic Regression calibrator  
**Task:** Binary classification — will this departure be delayed?

| Metric | Value |
|--------|-------|
| AUC (ROC) | **0.894** |
| Features | 23 |
| Calibration ECE (before) | 0.167 |
| Calibration ECE (after) | 0.068 |

The departure model includes a post-hoc Isotonic Regression probability calibrator, significantly improving the reliability of raw probability outputs for use in risk tier assignment.

**Operating mode thresholds:**

| Mode | Threshold | Precision | Recall | F1 |
|------|-----------|-----------|--------|----|
| Balanced (0.59) | — | 0.774 | 0.680 | 0.724 |
| High Precision (0.79) | — | 0.889 | 0.603 | 0.719 |
| High Recall (0.17) | — | 0.308 | 0.905 | 0.460 |

**Risk tiers:**

| Tier | Probability |
|------|------------|
| CRITICAL | ≥ 0.80 |
| HIGH | 0.25 – 0.80 |
| MEDIUM | 0.10 – 0.25 |
| LOW | < 0.10 |

---

### 2.4 Departure Delay Regressor — V8.0

**Algorithm:** CatBoost Quantile Regressor  
**Task:** Estimate departure delay duration at the 50th percentile  
**Output:** `pred_delay_q50` — median predicted delay in minutes

---

## 3. Data Features Required by AOC

The models rely on five categories of input data. For live deployment, AOC needs to feed or compute the following features in real time.

### 3.1 LGA Airport Lag Features
*Computed from the rolling flight history at LGA — available internally*

| Feature | Description | Window |
|---------|-------------|--------|
| `delay_rate_1h` | Fraction of recent LGA flights delayed | Past 1 hour |
| `terminal_delay_1h` | Average delay across flights at the same terminal | Past 1 hour |
| `delay_rolling_3h` | Average delay across all LGA flights | Past 3 hours |
| `severe_delay_count_prev` | Count of flights delayed > 45 min | Past 3 hours |
| `lga_dep_delay_1h` | Average departure delay at LGA *(used in arrival model)* | Past 1 hour |
| `lga_arr_delay_1h` | Average arrival delay at LGA *(used in departure model)* | Past 1 hour |

### 3.2 Aircraft Continuity Features
*Requires fleet tracking — tail number to prior leg lookup*

| Feature | Description |
|---------|-------------|
| `prev_aircraft_delay` | Delay (minutes) of the same aircraft's previous arrival at LGA |
| `prev_inbound_delay` | Delay of the inbound flight for a departure (same tail number) |
| `turnaround_hours` | Time between inbound arrival and outbound departure for the same aircraft |

### 3.3 Route & Operational Encoding
*Historical rates; updated periodically from the airline's delay history*

| Feature | Description |
|---------|-------------|
| `gate_delay_rate` / `dep_gate_delay_rate` | Historical delay rate for this gate |
| `runway_delay_rate` / `dep_runway_delay_rate` | Historical delay rate for this runway |
| `airline_delay_rate` / `dep_airline_delay_rate` | Historical delay rate for this airline |
| `route_risk_score` | Composite risk score for the origin–LGA or LGA–destination route |
| `faa_delay_reason` / `dep_faa_delay_reason` | FAA-encoded delay cause category |

### 3.4 FAA Program Data
*Available via the FAA NAS Status API (`https://nasstatus.faa.gov/api/airport-events`)*

| Feature | Description |
|---------|-------------|
| `faa_delay_severity` | Ground Delay Program severity level (0–3) |
| `faa_event_duration_hours` | Duration of active FAA delay program |
| `faa_active_event_count` | Number of simultaneous FAA delay programs affecting LGA |
| `runway_config_change` | Binary flag: runway configuration changed in the past hour |
| `dep_runway_config_change` | Same, for departure runway |

### 3.5 Origin / Destination Weather
*Sourced from ASOS/METAR observations at the remote airport*

| Feature | Description | Direction |
|---------|-------------|-----------|
| `origin_dewpoint` | Dewpoint temperature (°F) at origin airport | Arrivals |
| `origin_wx_impact` | Composite weather impact score (0–10) at origin | Arrivals |
| `origin_historical_delay` | Historical delay rate at origin airport | Arrivals |
| `dest_dewpoint` | Dewpoint temperature (°F) at destination | Departures |
| `dest_wx_impact` | Composite weather impact score (0–10) at destination | Departures |
| `dest_historical_delay` | Historical delay rate at destination airport | Departures |
| `dest_pressure_change_3h` | 3-hour pressure change at destination (hPa) | Departures |
| `lga_wx_impact` | Composite weather impact score at LGA itself | Both |

### 3.6 Time Features
*Derived directly from the scheduled flight time*

| Feature | Description |
|---------|-------------|
| `Hour` | Scheduled departure/arrival hour (0–23) |
| `Month` | Calendar month (1–12) |

---

## 4. Dashboard Walkthrough

### 4.1 Simulation Timeline (top bar)

The dashboard operates as a **historical replay** of real LGA flight data.  
The top bar shows the current simulated time and controls playback speed.

| Control | Function |
|---------|----------|
| ◀ / ▶ Date arrows | Jump to previous/next day |
| ▶ / ⏸ Play/Pause | Start or stop automatic time advancement |
| Speed selector (1×, 5×, 15×, 60×) | Each real second advances the simulation by 1/5/15/60 minutes |
| Clock display | Current simulated date and time |

The default starting point is **2025-08-13 08:00** — the highest-delay day in the dataset.

---

### 4.2 Overview Page

The overview page shows the current operational picture at a glance.

**Top KPI strip**

| Card | What it means |
|------|---------------|
| Arrivals / Departures | Total flights in the ±5 hour window around current time |
| Delay Rate | % of flights predicted to be delayed |
| Avg Predicted Delay | Mean predicted delay (minutes) across all flagged flights |
| CRITICAL flights | Count of flights with delay probability ≥ 0.75 (arrivals) or ≥ 0.80 (departures) |

**Risk Distribution chart** — Stacked bar showing CRITICAL / HIGH / MEDIUM / LOW counts for arrivals and departures.

**Delay Cause Breakdown** — Four-category attribution computed from real feature thresholds:
- **Origin Weather** — significant wx_impact at the departure airport (score ≥ 2/10)
- **Aircraft Propagation** — inbound aircraft arrived late (prev delay > 20 min)
- **LGA Delay Cascade** — airport-wide backlog building (delay_rate_1h > 30%)
- **Route Congestion** — baseline airline/route/schedule risk

**Hourly Timeline** — Bar chart of predicted delay counts by hour, helping anticipate congestion waves.

**Terminal Stress** — Per-terminal CRITICAL + HIGH flight counts, useful for gate planning.

**FAA Alerts** — Live data from the FAA NAS Status API. Shows active Ground Stops and Ground Delay Programs affecting LGA. Updates every 2 minutes.

**LGA Weather** — Current (or historically replayed) conditions: temperature, wind, visibility, gust, and a severity label (Clear / Moderate / Severe).

**Top Risk Flights** — The 5 highest-probability flights in the current window, linking directly to their detail panel.

---

### 4.3 Flight List Page

A filterable, sortable table of all flights in the ±5 hour window.

**Filters available:**
- Direction (Arrivals / Departures)
- Terminal
- Airline
- Risk tier (CRITICAL / HIGH / MEDIUM / LOW)

**Columns:**
- Flight number, airline, gate/terminal
- Scheduled time
- Risk tier badge (colour-coded: red / orange / yellow / green)
- Delay probability (0–100%)
- Predicted delay at Q50 (median expected delay in minutes)

**Sort:** Click any column header. Default sort is by delay probability descending.

---

### 4.4 Flight Detail — SlideOut Panel

Click any flight to open the detail panel on the right.

**Prediction summary**
- Delay probability as a large percentage
- Risk tier badge
- Predicted delay range: Q10–Q50–Q90 (10th / 50th / 90th percentile minutes)
- Confidence indicator

**Operational Context**
Real per-flight values extracted from the feature matrix:

| Field | Description |
|-------|-------------|
| Previous aircraft delay | Minutes late the arriving aircraft's prior leg was |
| Turnaround time | Hours between inbound arrival and outbound departure |
| Route delay rate | Historical delay rate for this airline on this route |
| Origin / Destination weather | Condition description derived from wx_impact and dewpoint |

**SHAP Factor Chart**
Shows the top contributing features for this specific flight, computed by a CatBoost TreeExplainer.  
Each bar shows the SHAP value (log-odds contribution to delay probability):
- Positive values push toward delay
- Negative values push toward on-time
- Bars are colour-coded by category: weather (blue) / aircraft (orange) / cascade (red) / route (grey)

Factor level labels:
- **Major** — |SHAP| ≥ 0.05
- **Contributing** — |SHAP| ≥ 0.02
- **Minor** — |SHAP| < 0.02

---

### 4.5 Reading the Risk Tiers

| Tier | Colour | Arrivals | Departures | Recommended Action |
|------|--------|----------|------------|--------------------|
| CRITICAL | Red | ≥ 75% delay prob | ≥ 80% delay prob | Immediate coordination — gate hold, crew notification, connecting flight check |
| HIGH | Orange | 30–75% | 25–80% | Monitor closely — brief crew, check gate availability |
| MEDIUM | Yellow | 15–30% | 10–25% | Situational awareness — track inbound aircraft |
| LOW | Green | < 15% | < 10% | Normal operations |

---

## 5. How to Start the Dashboard

### Prerequisites

- Python 3.11+ with project dependencies installed (`pip install -r dashboard/backend/requirements.txt`)
- Node.js 18+ with frontend dependencies installed (`cd dashboard/frontend && npm install`)
- Model files present in `models/`
- Raw flight data present in `data/raw/LGA_Dataset/`

### Quick Start

Double-click **`start.bat`** in the project root.

The script will:
1. Check port 8000 — kill any existing process if occupied
2. Check port 5173 — kill any existing process if occupied
3. Open a new terminal window running the FastAPI backend
4. Open a new terminal window running the Vite frontend

```
LGA/
└── start.bat   ← double-click this
```

### What to expect

| Service | URL | Ready when |
|---------|-----|-----------|
| Frontend | http://localhost:5173 | Within ~5 seconds |
| Backend API | http://localhost:8000 | After ~2 minutes |
| API health check | http://localhost:8000/api/health | Returns `"status": "ok"` |

**Why does the backend take 2 minutes?**  
At startup, the backend loads all 293,000 flights (Jan–Oct 2025), runs CatBoost inference to generate delay probabilities for every flight, and builds the in-memory flight cache. The frontend will load immediately but will show no flight data until the backend reports `Dashboard ready!` in its terminal window.

### Manual start (if start.bat fails)

```bash
# Terminal 1 — Backend
cd dashboard/backend
python -m uvicorn main:app --port 8000

# Terminal 2 — Frontend
cd dashboard/frontend
npm run dev
```

### Operating modes

The backend supports three prediction modes, switchable via the UI or the `/api/config/mode` endpoint:

| Mode | Description |
|------|-------------|
| `balanced` | Default. Optimised F1 — equal penalty for false positives and negatives |
| `high_precision` | Higher threshold — only flag flights with strong evidence of delay |
| `high_recall` | Lower threshold — flag everything suspicious, accept more false positives |

---

## 6. Project Structure

```
LGA/
├── start.bat                          # One-click launcher
├── data/
│   ├── raw/LGA_Dataset/               # Source CSVs (flights, weather, FAA events)
│   └── processed/                     # Model training contexts (.pkl), feature outputs
├── models/                            # Trained .joblib model files
│   ├── arrival_delay_classifier_v9.joblib
│   ├── arrival_delay_regressor_q50_v9.joblib
│   ├── departure_delay_classifier_v9.joblib
│   ├── departure_delay_regressor_q50_v8.joblib
│   └── departure_prob_calibrator_v9.joblib
├── dashboard/
│   ├── backend/                       # FastAPI application
│   │   ├── main.py                    # App entry point, lifespan startup
│   │   ├── config.py                  # Thresholds, feature lists, SHAP labels
│   │   ├── api/                       # Endpoint routers
│   │   ├── data/                      # Data loading, FAA live, feature lookup
│   │   ├── inference/                 # Feature builder, predictor, SHAP
│   │   └── models/                    # Model file loader
│   └── frontend/                      # React + TypeScript (Vite)
│       └── src/
│           ├── components/            # UI components
│           ├── context/               # SimulationContext (time state)
│           ├── lib/                   # API client, types, utilities
│           └── pages/                 # Overview and Flight List pages
├── notebooks/                         # Training and feature-engineering notebooks
│   └── delay/
│       ├── arrival/                   # NB01–NB06: arrival model pipeline
│       └── departure/                 # Departure model pipeline
└── src/
    └── features/                      # Reusable feature computation modules
        └── lag_features.py            # Rolling lag feature computation
```
