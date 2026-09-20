# 🛰️ Orbit Sentinel

### Autonomous space traffic monitoring and maneuver evaluation

Orbit Sentinel is a full-stack Space Situational Awareness project for tracking close approaches between satellites, scoring collision risk, and evaluating autonomous avoidance responses.

It includes a FastAPI backend, a React + Vite dashboard, TLE ingestion, scheduler-driven monitoring, a TinyDB fallback mode, and a live conjunction feed for operational visibility.

---

## What this project includes

- TLE ingestion and catalog refresh workflow
- orbital propagation and conjunction screening
- risk scoring and Kessler cascade modeling
- maneuver evaluation and maneuver history tracking
- live dashboard with telemetry and audit information
- MongoDB optional mode with built-in TinyDB fallback
- scheduler-based risk checks for automatic maneuver triggers

---

## Operational notes

- The app prefers CelesTrak for live TLE data and falls back to SatNOGS if needed.
- Fallback sources may be older than a live catalog, so the orbital state can be stale.
- The automatic maneuver loop depends on recent risk data and a fresh conjunction record set.
- The "maneuvers today" value reflects stored maneuver records and can remain at zero until the scheduler or a manual trigger creates data.

---

## Quick start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Optional: MongoDB if you want to run with a database backend instead of TinyDB

### Local development

```bash
# install backend dependencies
python -m pip install -r backend/requirements.txt

# install frontend dependencies
npm install

# start backend from the repo root
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# start frontend in a second terminal
npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:8000
API docs: http://localhost:8000/docs

### Docker

```bash
cp .env.example .env
docker compose up --build
```

---

## Tech stack

### Backend
- FastAPI
- Python 3.10+
- APScheduler
- SGP4
- TinyDB / MongoDB
- NumPy / SciPy
- scikit-learn
- PyTorch
- Stable-Baselines3
- WebSocket API

### Frontend
- React 18
- TypeScript
- Vite
- Zustand
- Three.js
- Recharts

---

## Project structure

```text
orbit-sentinel/
├── backend/
│   ├── core/
│   │   ├── scheduler.py
│   │   ├── tle_ingestion.py
│   │   ├── conjunction_detector.py
│   │   ├── risk_scorer.py
│   │   ├── maneuver_calculator.py
│   │   ├── secondary_check.py
│   │   ├── sgp4_propagator.py
│   │   ├── spatial_index.py
│   │   ├── webhook_dispatcher.py
│   │   ├── cascade_simulator.py
│   │   └── screening.py
│   ├── db/
│   │   ├── mongo_client.py
│   │   ├── tinydb_client.py
│   │   ├── conjunction_repo.py
│   │   ├── maneuver_repo.py
│   │   ├── satellite_repo.py
│   │   ├── audit_repo.py
│   │   ├── risk_config_repo.py
│   │   └── kessler_history_repo.py
│   ├── ml/
│   │   ├── collision_probability_ann.py
│   │   ├── trajectory_lstm.py
│   │   ├── rl_maneuver_agent.py
│   │   ├── marl_coordinator.py
│   │   ├── model_registry.py
│   │   └── feature_engineering.py
│   ├── routers/
│   │   ├── conjunction_router.py
│   │   ├── maneuver_router.py
│   │   ├── analytics_router.py
│   │   ├── tle_router.py
│   │   ├── satellite_router.py
│   │   ├── audit_router.py
│   │   ├── risk_config_router.py
│   │   └── websocket_router.py
│   ├── tests/
│   │   └── test_physics.py
│   ├── config.py
│   ├── main.py
│   └── requirements.txt
│
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── api/
│   ├── components/
│   ├── hooks/
│   ├── pages/
│   ├── store/
│   └── utils/
├── public/
├── docs/
│   └── screenshots/
├── ml_models/
├── rust_sgp4/
├── docker-compose.yml
├── .env.example
├── package.json
├── README.md
├── INTEGRATION_CHECKLIST.md
├── metadata.json
├── vite.config.ts
├── index.html
└── runtime.txt
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `USE_TINYDB` | `true` | Force TinyDB mode instead of MongoDB |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `orbit_sentinel` | Database name for the backend |
| `SPACETRACK_USERNAME` | — | Optional Space-Track credentials |
| `SPACETRACK_PASSWORD` | — | Optional Space-Track credentials |
| `CONJUNCTION_THRESHOLD_KM` | `5.0` | Close-approach screening threshold |
| `PROPAGATION_HOURS` | `72` | Propagation window used in screening |
| `TLE_REFRESH_INTERVAL_MINUTES` | `10` | Scheduler refresh interval |
| `RISK_THRESHOLD` | `0.0001` | Minimum risk score for automatic maneuver checks |
| `WEBHOOK_SECRET` | `changeme` | Secret used for webhook or API validation |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed frontend origin for CORS |

---

## Main API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/conjunctions/active` | GET | Active unresolved conjunctions |
| `/api/conjunctions/{id}` | GET | Detailed conjunction data |
| `/api/conjunctions/{id}/trigger_response` | POST | Trigger an autonomous response |
| `/api/maneuvers/recent` | GET | Recent maneuver history |
| `/api/tle/status` | GET | Current TLE refresh and status data |
| `/api/tle/refresh` | POST | Force TLE refresh |
| `/api/analytics/kessler_risk` | GET | Current Kessler risk output |
| `/api/audit` | GET | Audit log |
| `/ws` | WebSocket | Live update stream |

---

## Feature notes

- The app uses a scheduler-driven threshold loop to check unresolved conjunctions against the configured risk threshold.
- The fallback database layer keeps the app running locally without MongoDB.
- The project is intended to behave gracefully when live TLE access is limited or blocked.
- Data quality is directly tied to the freshness of the TLE source and the health of the scheduler loop.

---

## Validation

A targeted regression check is included for the TinyDB threshold logic used by the scheduler fallback layer.

```bash
cd backend
pytest tests/test_physics.py -k tinydb_threshold_filters_support_gt_and_ne -q
```

---

## Credits

- CelesTrak and SatNOGS for TLE data feeds
- Python-sgp4 for orbital propagation
- FastAPI, React, and supporting ML libraries for the app stack
- The broader orbital mechanics and debris-risk community for reference models and operational standards

---







