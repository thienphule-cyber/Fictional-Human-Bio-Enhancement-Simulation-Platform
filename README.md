# Nebula

Nebula is a **fictional bio-enhancement simulation platform**. It models a
made-up "Nebula Gas" enhancement process: human profiles, gas compatibility,
device control, staged enhancement ticks, mutations, and hazard assessments,
all exposed through a REST API and a browser dashboard.

> **Disclaimer.** Nebula is a work of fiction built for demonstration and
> software practice. It does not describe real chemistry, medicine, biology, or
> any real procedure. Every gas, class, stage, mutation, and hazard label is an
> invented model value. Nothing here should be read as guidance of any kind.

---

## Stack

| Layer     | Technology                                                        |
| --------- | ----------------------------------------------------------------- |
| Backend   | Python 3.12, FastAPI, Uvicorn, Pydantic v2, NumPy                  |
| Storage   | SQLite in WAL mode (`data/nebula.db`), no ORM                      |
| Frontend  | Plain HTML/CSS/ES modules, Chart.js (CDN), no bundler              |
| API style | REST/JSON under `/api`, served same-origin as the static frontend  |

Python dependencies are pinned in `requirements.txt`:

```
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
pydantic-settings>=2.2.0
numpy>=1.26.4
python-multipart>=0.0.9
```

Chart.js is loaded from a CDN by `frontend/index.html`. For a fully offline
setup, download the UMD build to `frontend/assets/vendor/` and point the
`<script>` tag there. Three.js is reserved for future 3D views and is not
currently loaded.

---

## Project layout

```text
nebula/
├── backend/
│   ├── __init__.py
│   ├── main.py            # FastAPI app, routes, lifespan, port discovery, static mount
│   ├── config.py          # Settings
│   ├── database.py        # Connection helpers, WAL setup, schema creation, seed data
│   ├── human.py           # Profiles, parameter snapshots, physical class derivation
│   ├── nebula.py          # Gas model, hazard classifications, class ceilings
│   ├── compatibility.py   # Compatibility scoring
│   ├── mutation.py        # Mutation model and records
│   ├── devices.py         # Control devices, configurations, commands
│   ├── enhancement.py     # Sessions and the tick/stage engine
│   ├── hazard.py          # Hazard and stability assessment
│   └── analytics.py       # Trends, deltas, comparisons, reports, statistics
├── frontend/
│   ├── index.html         # The single HTML document
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js         # App shell and hash router
│       ├── api.js         # Fetch client for every endpoint
│       ├── constants.js   # Labels, colors, model vocabulary
│       ├── ui.js          # DOM, form, formatting, and toast helpers
│       ├── charts.js      # Chart.js wrappers
│       ├── dashboard.js
│       ├── profiles.js
│       ├── gases.js
│       ├── compatibility.js
│       ├── devices.js
│       ├── simulation.js
│       ├── mutations.js
│       └── analytics.js
├── data/                  # SQLite database, PID and port files (git-ignored)
├── logs/                  # Server output from start.sh (git-ignored)
├── start.sh
├── stop.sh
├── requirements.txt
├── README.md
├── LICENSE.md
└── .gitignore
```

---

## Requirements

- Python 3.12
- macOS, Linux, or WSL (the helper scripts assume a POSIX shell)
- `curl`, used by `start.sh` for health checks

---

## Setup

```bash
cd nebula
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The database is created automatically on first start: `init_db()` builds all
tables and seeds the hazard classification reference rows. There is no separate
migration step and no test suite by design — the dashboard is the test harness.

---

## Running

### Recommended: background scripts

```bash
chmod +x start.sh stop.sh
./start.sh
```

`start.sh`:

1. finds a free local port,
2. starts `backend.main` with `nohup`, so the terminal can be closed,
3. waits for `/api/health` to answer,
4. prints a direct dashboard link and, on macOS, opens it.

Typical output:

```text
Nebula started in the background (PID 1746).
Dashboard: http://127.0.0.1:49131/#/dashboard
Log file: /Users/you/nebula/logs/nebula.log
```

Stop it with:

```bash
./stop.sh
```

| Variable       | Default | Purpose                                        |
| -------------- | ------- | ---------------------------------------------- |
| `OPEN_BROWSER` | `1`     | Set to `0` to skip opening the browser         |
| `PYTHON_BIN`   | auto    | Override the interpreter (`.venv` is preferred) |

State files live in `data/`: `nebula.pid`, `nebula.port`. Server output is
appended to `logs/nebula.log`. Running `start.sh` twice reuses the running
server instead of starting a second one.

### Manual

```bash
python -m backend.main                 # scans upward for a free port
python -m backend.main --port 9000     # start at 9000, scanning if busy
python -m backend.main --port 9000 --no-scan
python -m backend.main --host 0.0.0.0
```

| Flag        | Default     | Meaning                                              |
| ----------- | ----------- | ---------------------------------------------------- |
| `--host`    | `127.0.0.1` | Bind address                                          |
| `--port`    | `8000`      | Preferred port                                        |
| `--no-scan` | off         | Fail instead of scanning when the port is occupied    |

`main.py` binds the socket itself before handing it to Uvicorn, so the port in
the log is the port actually in use. The dashboard is served from the same
origin at `/`, so no CORS configuration is needed.

---

## Frontend routes

Navigation is hash-based inside a single page:

| Route             | Page          | Purpose                                        |
| ----------------- | ------------- | ---------------------------------------------- |
| `#/dashboard`     | Dashboard     | Platform counts, recent sessions, reference    |
| `#/profiles`      | Profiles      | Create and inspect human profiles              |
| `#/gases`         | Nebula Gas    | Gas catalogue                                  |
| `#/compatibility` | Compatibility | Score one profile against one gas              |
| `#/devices`       | Devices       | Register devices, edit config, send commands   |
| `#/simulation`    | Simulation    | Create sessions, run ticks, watch trends       |
| `#/mutations`     | Mutations     | Mutation and hazard history                    |
| `#/analytics`     | Analytics     | Trends, deltas, comparisons, reports           |

To add a page, create `frontend/js/<name>.js` exporting `render(container)` and
add one entry to `ROUTES` in `frontend/js/app.js`.

---

## API overview

All routes return JSON. Domain errors are mapped to HTTP status codes and shaped
as `{"detail": "...", "error_type": "..."}`.

**System**

```text
GET  /api/health
GET  /api/meta
```

**Humans**

```text
POST   /api/humans
GET    /api/humans
GET    /api/humans/{profile_id}
PATCH  /api/humans/{profile_id}
POST   /api/humans/{profile_id}/parameters
GET    /api/humans/{profile_id}/parameters/latest
GET    /api/humans/{profile_id}/compatibility
```

**Gases and compatibility**

```text
POST /api/gases
GET  /api/gases
GET  /api/gases/{gas_pk}
POST /api/compatibility
```

**Devices**

```text
POST  /api/devices
GET   /api/devices
GET   /api/devices/summary
GET   /api/devices/{device_id}
PATCH /api/devices/{device_id}/configuration
POST  /api/devices/{device_id}/command
GET   /api/devices/{device_id}/status
GET   /api/devices/{device_id}/effective-control
```

**Sessions and enhancement**

```text
POST /api/sessions
GET  /api/sessions
GET  /api/sessions/{session_id}
POST /api/sessions/{session_id}/start
POST /api/sessions/{session_id}/pause
POST /api/sessions/{session_id}/stop
POST /api/sessions/{session_id}/complete
POST /api/sessions/{session_id}/shutdown
POST /api/sessions/{session_id}/step
GET  /api/sessions/{session_id}/metrics
GET  /api/sessions/{session_id}/enhancements
GET  /api/sessions/{session_id}/summary
GET  /api/sessions/{session_id}/mutations
GET  /api/sessions/{session_id}/mutations/summary
```

**Hazard**

```text
POST /api/sessions/{session_id}/hazard/assess
GET  /api/sessions/{session_id}/hazard
GET  /api/sessions/{session_id}/hazard/summary
```

**Analytics**

```text
GET  /api/analytics/sessions/{session_id}/trends
GET  /api/analytics/sessions/{session_id}/deltas
GET  /api/analytics/enhancement-history
GET  /api/analytics/mutation-history
GET  /api/analytics/hazard-history
POST /api/analytics/compare
GET  /api/analytics/sessions/{session_id}/report
GET  /api/analytics/profiles/{profile_id}/report
GET  /api/analytics/statistics
GET  /api/analytics/recent
```

Example:

```bash
curl -s http://127.0.0.1:8000/api/analytics/statistics | python -m json.tool
```

---

## Data model

SQLite, WAL mode, twelve tables created by `init_db()`:

| Table                    | Holds                                              |
| ------------------------ | -------------------------------------------------- |
| `human_profiles`         | Subject records and derived physical class          |
| `biological_parameters`  | Per-tick snapshots of the eight parameters          |
| `nebula_gases`           | Fictional gas profiles                              |
| `hazard_classifications` | Reference rows for hazard levels 0–5                |
| `compatibility_records`  | Stored compatibility evaluations                    |
| `control_devices`        | Registered simulated devices                        |
| `device_configurations`  | Device tuning values and shutdown state             |
| `simulation_sessions`    | Session lifecycle and current tick                  |
| `enhancement_records`    | One row per tick with stage outputs                 |
| `mutation_records`       | Mutations of level 1 and above                      |
| `simulation_metrics`     | Post-tick parameter metrics                         |
| `hazard_assessments`     | Risk level, stability status, shutdown flag         |

The eight biological parameters are `muscle_density`, `bone_density`,
`cardiovascular_capacity`, `neural_activity`, `cellular_stability`,
`metabolic_efficiency`, `regeneration_index`, and `mutation_resistance`. All are
on a fictional 0–100 scale.

---

## Model notes

These constants define the invented behaviour; they live in the backend modules
and are safe to tune.

- **Compatibility weights** (`compatibility.py`): purity `0.28`, energy `0.24`,
  stability `0.28`, mutation `0.20`.
- **Tick stages** (`enhancement.py`): Absorption → Digestion → Adaptation →
  Enhancement → Mutation → Stability, with `MAX_TICK_GAIN = 2.4` and
  `_STABILITY_DRAG = 0.45`.
- **Risk levels** (`hazard.py`): 0 Safe Simulation State, 1 Low Risk,
  2 Moderate Risk, 3 High Risk, 4 Critical Risk, 5 Biological Collapse.
  A class gap of 2 or more, mutation risk of 90 or more, or stability below 15
  forces level 5; levels 4 and above recommend emergency shutdown.
- **Class ceilings** (`nebula.py`): each physical class caps the hazard level it
  may safely handle.

---

## Troubleshooting

**`ImportError: cannot import name 'ComparisonRequest' from 'backend.analytics'`**
`backend/analytics.py` does not contain the current file. Each module owns one
responsibility; check that `hazard.py` and `analytics.py` were not swapped.

**Dashboard loads but every panel is empty**
Check `logs/nebula.log` and open `/api/health` directly. A stopped backend shows
a red status bar in the header.

**Charts are missing**
Chart.js did not load. Either allow the CDN or host the UMD build locally.

**Root path returns 404**
`frontend/index.html` is missing, or `StaticFiles` is not mounted. The mount only
happens when the `frontend/` directory exists.

**Port mismatch between script and log**
Use `start.sh`; it reads the port from `data/nebula.port`, which matches the
socket the server actually bound.

**A stale process holds a port**

```bash
./stop.sh
lsof -nP -iTCP -sTCP:LISTEN | grep python
```

---

## License

MIT, with an additional notice that the project is fictional. See
[`LICENSE.md`](LICENSE.md).
