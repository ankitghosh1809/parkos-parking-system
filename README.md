# ParkOS — Vehicle Parking Management System

A full-stack parking lot management system. The backend is a **FastAPI** REST API backed by **PostgreSQL** (Neon in production); the frontend is a **zero-dependency HTML/CSS/JS SPA** with an industrial dark theme.

---

## Project Structure

```
parkos-parking-system/
├── api/                  # Deployed copy - what Vercel actually runs (see below)
│   └── index.py          # Vercel entrypoint, imports main:app
├── backend/               # Source of truth for local dev + tests
│   ├── auth.py           # Operator login (bearer token, no DB, no user table)
│   ├── main.py            # FastAPI app + all routes
│   ├── db.py               # Connection handling + schema setup
│   ├── parking.py         # Lot logic (park, remove, status)
│   ├── reports.py         # Daily report generator + paginated log reads
│   ├── requirements.txt
│   ├── data/               # Local report .txt output (auto-created)
│   └── tests/
│       ├── test_api.py
│       └── test_auth.py
├── frontend/
│   └── index.html         # Full SPA (no build step required)
├── scripts/
│   └── sync_backend_to_api.sh   # Run after editing backend/ - see below
└── .env.example
```

`api/` and `backend/` contain the same application code. `backend/` is
what you edit and test against locally; `api/` is the copy Vercel
actually deploys (`vercel.json` points at `api/index.py`). They're
kept as two synced copies rather than one shared module because
Vercel's Python builder bundles based on `api/`'s own contents, and a
cross-directory import hasn't been verified against a real deploy.
**After changing anything in `backend/`, run `./scripts/sync_backend_to_api.sh`
before committing** - otherwise your fix only ships to local dev, not
to the actual deployment.

---

## Features

**Backend (FastAPI)**
- `POST /api/login` — Exchange the operator password for a session token
- `POST /api/park` — Park a vehicle; returns assigned slot *(requires login)*
- `POST /api/checkout/{vehicle_number}` — Checkout, calculate fee, log session *(requires login)*
- `GET  /api/status` — Slot occupancy stats
- `GET  /api/vehicles` — Currently parked vehicles
- `GET  /api/log` — Transaction history, paginated (`?limit=&offset=`)
- `GET  /api/report` — Daily revenue report (JSON + saves `.txt`)
- `GET  /api/summary` — All-time totals

Browsing (status, vehicle list, history, reports) doesn't require
login. Only the two actions that change data - parking and checking
out a vehicle - are gated behind the operator login.

**Frontend (Vanilla SPA)**
- Dashboard with live stats + quick park/checkout
- Operator login modal (only needed for park/checkout)
- Park Vehicle & Checkout pages
- Active vehicle table with inline checkout
- Visual slot map (free / occupied)
- Daily revenue report with per-type breakdown
- Paginated transaction history (newest first, "Load More")
- Receipt modal on checkout
- Toast notifications

---

## Parking Rates

| Type  | Rate/hour |
|-------|-----------|
| Bike  | ₹10       |
| Car   | ₹30       |
| Truck | ₹60       |

Minimum charge: 1 hour.

---

## Getting Started

### 1 — Environment variables

Copy `.env.example` to `.env` and fill in real values (or export them
directly in your shell). Required:

- `DATABASE_URL` — your Postgres connection string
- `OPERATOR_PASSWORD` — the password operators use to log in
- `SECRET_KEY` — random string used to sign login tokens (`openssl rand -hex 32`)

`backend/main.py` and `db.py` will raise a clear error naming exactly
which one is missing if you forget one.

### 2 — Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 3 — Frontend

The frontend calls the API via a relative path (`const API = ""`), so
it expects to be served from the *same origin* as the API - which is
exactly how production works (Vercel serves both from one domain, see
`vercel.json`). Locally, that means opening `frontend/index.html`
directly (`file://`) won't reach the backend. Two ways to run it
locally instead:

- **Quickest**: temporarily change `const API = "";` to
  `const API = "http://localhost:8000";` near the top of the
  `<script>` block, then open `frontend/index.html` in your browser.
  Revert the line before committing.
- **Closer to production**: serve `frontend/` with any static file
  server (e.g. `python -m http.server 5500` from inside `frontend/`),
  set `ALLOWED_ORIGINS=http://localhost:5500` when starting the
  backend, and still point `API` at `http://localhost:8000` as above
  (CORS only permits the cross-origin request - it doesn't rewrite
  the relative URLs for you).

### 4 — Tests

```bash
cd backend
pytest tests/ -v
```

`test_api.py` needs `DATABASE_URL` pointed at a real (ideally scratch)
Postgres database and truncates `active_sessions`/`parking_log`
between tests. `test_auth.py` doesn't touch the database at all and
runs regardless. CI (`.github/workflows/tests.yml`) runs both against
a throwaway Postgres service container on every push/PR.

---

## Configuration

**Slot count** — edit `ParkingLot(total_slots=50)` in `backend/main.py`.

**Parking rates** — edit `PARKING_RATES` in `backend/parking.py`.

**API base URL** — change `const API = "";` in `frontend/index.html`
(see "Frontend" above for why it's empty by default).

**Allowed origins for CORS** — set `ALLOWED_ORIGINS` (comma-separated).
Defaults to `http://localhost:8000,http://127.0.0.1:8000`. Production
doesn't need this changed since the frontend and API share an origin.

---

## Security notes

- Parking and checkout require an operator login (`POST /api/login`
  with `OPERATOR_PASSWORD`, returns a signed bearer token valid for 12
  hours). Read-only endpoints are intentionally left open.
- `vehicle_number` is restricted server-side to letters, numbers,
  hyphens, and spaces (max 20 characters) and the frontend HTML-escapes
  everything it renders, closing the stored-XSS gap that used to exist
  here.
- This is deliberately a single shared operator credential, not
  per-user accounts with roles - right-sized for one login gating two
  write endpoints. If you need per-operator accounts or an
  admin/attendant role split later, replace `auth.py` rather than
  extending it in place.

---

## License

MIT — see [LICENSE](LICENSE).

## 🌐 Live Demo
[https://parkos-parking-system.vercel.app](https://parkos-parking-system.vercel.app)

Once you deploy these changes, set `OPERATOR_PASSWORD`, `SECRET_KEY`,
and (if you use it) `ALLOWED_ORIGINS` in Vercel's Project Settings →
Environment Variables — the live demo will otherwise 500 on login and
on any DB-touching route until `DATABASE_URL` and those two are set.
