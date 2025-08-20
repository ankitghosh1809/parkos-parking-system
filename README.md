# ParkOS — Vehicle Parking Management System

A full-stack parking lot management system. The backend is a **FastAPI** REST API with CSV-based persistence; the frontend is a **zero-dependency HTML/CSS/JS SPA** with an industrial dark theme.

---

## Project Structure

```
parking-fullstack/
├── backend/
│   ├── main.py          # FastAPI app + all routes
│   ├── parking.py       # Lot logic (park, remove, status)
│   ├── reports.py       # Daily report generator
│   ├── requirements.txt
│   ├── data/            # CSV files (auto-created at runtime)
│   └── tests/
│       └── test_api.py
└── frontend/
    └── index.html       # Full SPA (no build step required)
```

---

## Features

**Backend (FastAPI)**
- `POST /api/park` — Park a vehicle; returns assigned slot
- `POST /api/checkout/{vehicle_number}` — Checkout, calculate fee, log session
- `GET  /api/status` — Slot occupancy stats
- `GET  /api/vehicles` — Currently parked vehicles
- `GET  /api/log` — Full transaction history
- `GET  /api/report` — Daily revenue report (JSON + saves `.txt`)
- `GET  /api/summary` — All-time totals

**Frontend (Vanilla SPA)**
- Dashboard with live stats + quick park/checkout
- Park Vehicle & Checkout pages
- Active vehicle table with inline checkout
- Visual slot map (free / occupied)
- Daily revenue report with per-type breakdown
- Full transaction history (newest first)
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

### 1 — Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2 — Frontend

Just open `frontend/index.html` in your browser. No build step needed.

> The frontend assumes the API is at `http://localhost:8000`. Change the `API` constant at the top of the `<script>` block if your backend runs elsewhere.

### 3 — Tests

```bash
cd backend
pytest tests/ -v
```

---

## Configuration

**Slot count** — edit `ParkingLot(total_slots=50)` in `backend/main.py`.

**Parking rates** — edit `PARKING_RATES` in `backend/parking.py`.

**API base URL** — change `const API = 'http://localhost:8000'` in `frontend/index.html`.

---

## License

MIT
