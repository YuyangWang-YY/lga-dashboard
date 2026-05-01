# LGA Flight Delay Prediction Dashboard

A real-time, data-driven scenario planning tool for predicting aircraft delays at LaGuardia Airport (LGA), built for the Airport Operations Center (AOC) by NYU CUSP.

---

## Abstract

This project creates a data-driven scenario planning tool for predicting aircraft delays at LaGuardia Airport (LGA). The Airport Operations Center (AOC) uses this tool to monitor in-day operations and redistribute resources as necessary based on the model's recommendations. The team uses Python and API calls for real-time flight, weather, and FAA alert data to develop a web application accessible on both desktop and mobile devices. The team collaborated with LGA operations staff to develop airport-specific business requirements and assumptions to provide alerts and recommendations.

---

## Project Overview

LaGuardia Airport (LGA) is one of the nation's busiest and most space-constrained hubs, facing persistent challenges in managing aircraft delays and weather impacts. These bottlenecks disrupt operations and directly impact passenger experience — heightening the risk of cancellations, prolonging taxi times, and congesting terminal areas and roadways.

This Capstone project supports the LGA Airport Operations Center (AOC) by delivering a real-time scenario planning tool that predicts flight delays and recommends proactive interventions. The tool helps the AOC minimize downstream disruptions and mitigate negative impacts on passengers and the surrounding Queens neighborhood.

The team developed a production-ready web application using Python, FastAPI, React, CatBoost machine learning models, and APIs for live flight, weather, and FAA alert data. Working closely with airport staff, the team translated business rules and operational constraints into real-time predictive logic and "what-if" scenario simulation for day-of planning.

**Deliverables include:**
- A validated ML forecasting engine (four CatBoost models)
- A live web application (desktop and mobile)
- Analysis of airfield delay patterns
- User documentation and model performance reports

---

## Research Question

> *How can real-time data be used to predict flight delays at LaGuardia Airport to proactively improve operational decision-making and maximize passenger experience?*

This project builds a decision-support tool that uses live flight, weather, and FAA alert data to analyze airfield congestion and recommend proactive actions to airport staff. The goal is to prevent excessive taxi times, mitigate delay cascades, and enhance the day-of passenger experience — especially during severe weather events and irregular operations.

---

## Dashboard — Final Product

### Key Features

| Feature | Description |
|---|---|
| **Overview Tab** | Airport-wide KPIs: predicted delays, delay rate, average predicted delay; 24-hour timeline (historical actuals + future risk); terminal stress monitoring; risk distribution (CRITICAL / HIGH / MEDIUM / LOW); top at-risk flights; delay cause breakdown; gate conflict alerts; airline rankings; FAA advisories; weather panel |
| **Arrivals Tab** | Real-time list of inbound flights, filterable by terminal/airline, sortable by risk probability/scheduled time/delay; click any flight for SHAP factor explanations |
| **Departures Tab** | Real-time list of outbound flights with the same filtering and detail panel |
| **Time Simulation** | Jump to any datetime in the historical dataset (Jan–Oct 2025); play/pause with speed controls (1×, 5×, 15×, 60×) |
| **Operating Modes** | **Balanced** (default) · **High Precision** (fewer false alarms) · **High Recall** (catch more delays) |
| **Flight Detail Panel** | Per-flight SHAP explanation, origin weather, aircraft continuity, actual vs. predicted delay comparison |

---

## Machine Learning Model Suite

Five trained models are stored in the [`models/`](models/) directory. All classifiers and regressors use **CatBoost** (gradient-boosted decision trees).

### Risk Tier Thresholds (Balanced Mode)

| Tier | Probability |
|---|---|
| CRITICAL | ≥ 0.75 |
| HIGH | 0.30 – 0.75 |
| MEDIUM | 0.15 – 0.30 |
| LOW | < 0.15 |

---

### 1. Arrival Delay Classifier — V9.0

**File:** `models/arrival_delay_classifier_v9.joblib`  
**Purpose:** Predicts whether an inbound flight will be delayed before it lands at LGA.  
**Algorithm:** CatBoost Classifier  
**Performance:** AUC-ROC = 0.808 · Optimal threshold = 0.46 · Training set ≈ 103,000 flights · pr_auc = 0.6334 · recall = 0.6539 · precision: 0.707

**Target (Y):**
- `Is_Delayed` — binary flag (1 = delayed, 0 = on-time)

**Input Features (X) — 25 total:**

*Base features (21):*

| Feature | Description |
|---|---|
| `delay_rate_1h` | Fraction of LGA flights delayed in the past hour |
| `terminal_delay_1h` | Terminal-specific average delay (past 1 h) |
| `severe_delay_count_prev` | Count of flights delayed > 45 min in the past 3 h |
| `delay_rolling_3h` | Rolling average delay across all LGA flights (3 h window) |
| `lga_dep_delay_1h` | Mean LGA departure delay (past 1 h) — cross-modal lag |
| `prev_aircraft_delay` | Same aircraft's delay on its previous arrival leg |
| `turnaround_hours` | Time between inbound arrival and next outbound departure |
| `gate_delay_rate` | Historical delay rate for the assigned gate |
| `faa_delay_reason` | FAA-encoded delay cause category |
| `runway_delay_rate` | Historical delay rate for the arrival runway |
| `airline_delay_rate` | Airline's historical delay tendency at LGA |
| `Hour` | Scheduled arrival hour (0–23) |
| `faa_delay_severity` | FAA delay program severity level (0–3) |
| `runway_config_change` | Binary: runway configuration changed in the past hour |
| `origin_dewpoint` | Dewpoint temperature (°F) at origin airport |
| `origin_historical_delay` | Historical delay rate at origin airport |
| `origin_wx_impact` | Composite weather impact score at origin (0–10) |
| `route_risk_score` | Composite route-based delay risk score |
| `lga_wx_impact` | Composite weather impact score at LGA (0–10) |
| `faa_event_duration_hours` | Duration of active FAA delay program |
| `faa_active_event_count` | Number of simultaneous FAA delay programs |

*Engineered interaction features (4, classifier only):*

| Feature | Description |
|---|---|
| `origin_dewpoint_missing` | Binary flag: was `origin_dewpoint` missing before imputation |
| `congestion_x_gate` | Interaction: `delay_rate_1h` × `gate_delay_rate` |
| `chain_x_turnaround` | Interaction: max(0, `prev_aircraft_delay`) × `turnaround_hours` |
| `congestion_accel` | Congestion acceleration: `delay_rate_1h` − (`delay_rolling_3h` / 3) |

---

### 2. Arrival Delay Regressor — V9.0 (Q50)

**File:** `models/arrival_delay_regressor_q50_v9.joblib`  
**Purpose:** Estimates the median (Q50) arrival delay in minutes for inbound flights.  
**Algorithm:** CatBoost Quantile Regressor (τ = 0.50)  
**Performance:** MAE = 20.12 min · R² = 0.2754

**Target (Y):**
- `Total_Calculated_Delay` — continuous delay in minutes

**Input Features (X) — 21 features:**  
Same as the arrival classifier base features (the 4 engineered interaction terms are not used for regression).

---

### 3. Departure Delay Classifier — V9.0

**File:** `models/departure_delay_classifier_v9.joblib`  
**Purpose:** Predicts whether an outbound flight will be delayed before it pushes back from the gate.  
**Algorithm:** CatBoost Classifier (probabilities calibrated by Model 5 below)  
**Performance:** AUC-ROC = 0.8936 · Precision = 77.4% · Recall = 68.0% · F1 = 72.4% · Optimal threshold = 0.59

**Target (Y):**
- `Is_Delayed` — binary flag (1 = delayed, 0 = on-time)

**Input Features (X) — 23 features:**

| Feature | Description |
|---|---|
| `delay_rate_1h` | Fraction of LGA flights delayed in the past hour |
| `delay_rolling_3h` | Rolling average delay across LGA (3 h window) |
| `severe_delay_count_prev` | Count of flights delayed > 45 min in the past 3 h |
| `terminal_delay_1h` | Terminal-specific average delay (past 1 h) |
| `dep_runway_config_change` | Binary: departure runway configuration changed (past 1 h) |
| `lga_arr_delay_1h` | LGA arrival congestion (past 1 h) — cross-modal lag |
| `prev_inbound_delay` | Delay of the same aircraft on its inbound leg |
| `turnaround_hours` | Gap between inbound arrival and scheduled outbound departure |
| `dep_gate_delay_rate` | Historical delay rate for the departure gate |
| `dep_airline_delay_rate` | Airline's historical departure delay rate at LGA |
| `dep_runway_delay_rate` | Historical delay rate for the departure runway |
| `dep_faa_delay_reason` | FAA delay cause category (target-encoded) |
| `Hour` | Scheduled departure hour (0–23) |
| `Month` | Calendar month (1–12) |
| `faa_delay_severity` | FAA program severity level (0–3) |
| `dest_wx_impact` | Composite weather impact score at destination (0–10) |
| `lga_wx_impact` | Composite weather impact score at LGA (0–10) |
| `dest_dewpoint` | Dewpoint temperature (°F) at destination airport |
| `dest_pressure_change_3h` | 3-hour barometric pressure change at destination (hPa) |
| `dest_historical_delay` | Historical delay rate at destination airport |
| `faa_event_duration_hours` | Duration of active FAA delay program |
| `faa_active_event_count` | Number of simultaneous FAA delay programs |
| `route_risk_score` | Destination-based composite route risk score |

---

### 4. Departure Delay Regressor — V8.0 (Q50)

**File:** `models/departure_delay_regressor_q50_v8.joblib`  
**Purpose:** Estimates the median (Q50) departure delay in minutes for outbound flights.  
**Algorithm:** CatBoost Quantile Regressor (τ = 0.50)  
**Performance:** MAE ≈ 10.75 min · R² ≈ 0.39

**Target (Y):**
- `Dep_Calculated_Delay` — continuous delay in minutes

**Input Features (X) — 23 features:**  
Same as the departure delay classifier (all 23 features listed above).

---

### 5. Departure Probability Calibrator — V9.0

**File:** `models/departure_prob_calibrator_v9.joblib`  
**Purpose:** Post-processes raw departure classifier output into well-calibrated probabilities.  
**Algorithm:** Isotonic Regression  
**Performance:** Raw ECE = 0.1672 → Calibrated ECE = 0.0677

**Input:** Raw probability score from the departure delay classifier  
**Output:** Calibrated probability (0–1) used for risk tier assignment

---

### Model Summary Table

| Model File | Type | Algorithm | Y Target | Features | Key Metric |
|---|---|---|---|---|---|
| `arrival_delay_classifier_v9.joblib` | Classifier | CatBoost | `Is_Delayed` (binary) | 25 | AUC = 0.808 |
| `arrival_delay_regressor_q50_v9.joblib` | Quantile Regressor | CatBoost Q50 | `Total_Calculated_Delay` (min) | 21 | MAE = 20.12 min |
| `departure_delay_classifier_v9.joblib` | Classifier | CatBoost | `Is_Delayed` (binary) | 23 | AUC = 0.894 |
| `departure_delay_regressor_q50_v8.joblib` | Quantile Regressor | CatBoost Q50 | `Dep_Calculated_Delay` (min) | 23 | MAE ≈ 10.75 min |
| `departure_prob_calibrator_v9.joblib` | Calibrator | Isotonic Regression | Calibrated probability | 1 | ECE = 0.068 |

---

## Accessing the Dashboard

There are two ways to open the dashboard:

### Option 1 — Web (No Installation Required)

Access the hosted version directly in any browser:

**URL:** [https://lga-dashboard.vercel.app/](https://lga-dashboard.vercel.app/)  
**Password:** `LGA2025`

### Option 2 — Local (Windows)

Run the dashboard on your own machine for offline or development use.

#### Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **Node.js 18+** — [nodejs.org](https://nodejs.org/)
- **Python dependencies** — install once from the project root:
  ```
  pip install -r dashboard/backend/requirements.txt
  ```
- **Node dependencies** — install once from the frontend folder:
  ```
  cd dashboard/frontend
  npm install
  ```

#### Starting the Dashboard

1. Open **File Explorer** and navigate to the project root folder (`LGA/`).
2. Double-click **`start.bat`** (or run it from a terminal).
3. Two terminal windows will open automatically:
   - **Backend** on port `8000` — loads ~293,000 historical flights and runs CatBoost inference. Wait until the terminal logs **"Dashboard ready!"** (approximately 2 minutes).
   - **Frontend** on port `5173` — ready within ~5 seconds.
4. Open your browser and go to: [http://localhost:5173](http://localhost:5173)
5. Enter password **`LGA2025`** when prompted.

> **Note:** Do not close either terminal window while using the dashboard. The backend must finish loading before the frontend will display data.

---

## Project Structure

```
LGA/
├── start.bat                        # One-click Windows launcher
├── README.md
├── dashboard/
│   ├── backend/                     # FastAPI application (Python)
│   │   ├── main.py                  # App entry point
│   │   ├── api/                     # Route handlers (overview, flights, config)
│   │   ├── models/                  # Model loader and inference
│   │   ├── inference/               # SHAP explainer
│   │   ├── data/                    # Data processing, FAA live API integration
│   │   └── requirements.txt
│   └── frontend/                    # React + TypeScript (Vite)
│       └── src/
│           ├── App.tsx
│           ├── components/          # UI components
│           ├── context/             # SimulationContext, ConfigContext
│           └── hooks/               # Data-fetching hooks
├── models/                          # Trained .joblib model files
├── scripts/                         # Model training scripts
├── notebooks/                       # Jupyter notebooks for model development
│   └── delay/
│       ├── arrival/                 # Arrival model pipeline
│       └── departure/               # Departure model pipeline
├── data/
│   ├── raw/LGA_Dataset/             # Source CSV files
│   └── processed/                   # Processed training datasets
└── data_dictionary/                 # Feature definitions (Excel/Word)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Recharts, Radix UI |
| Backend | FastAPI, Uvicorn, pandas, numpy |
| ML Models | CatBoost, scikit-learn, SHAP |
| Deployment | Vercel (frontend), local FastAPI (backend) |
| Data Sources | Historical BTS/OAG flight data, FAA Traffic Management API, weather APIs |

---

## Team

NYU Center for Urban Science and Progress (CUSP) — Capstone Project (Yuyang Wang, Ruisi Dai, Yijie Tang) 

Sponsor: Port Authority of New York and New Jersey / LaGuardia Airport
