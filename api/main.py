import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import date

from auth import check_password, create_token, require_auth
from parking import ParkingLot, VehicleAlreadyParkedError, LotFullError
from reports import (
    count_log_entries,
    generate_daily_report,
    get_all_time_summary,
    read_log,
)

app = FastAPI(
    title="Parking Management API",
    description="REST API for the Vehicle Parking Management System",
    version="1.0.0",
)

# Same-origin in production (frontend and API are served from the same
# Vercel deployment - see vercel.json), so this only matters for local
# dev against a separately-served frontend. Configure ALLOWED_ORIGINS
# as a comma-separated list if you need to call the API from elsewhere.
_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_credentials=False,  # auth uses a Bearer token, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

lot = ParkingLot(total_slots=50)

VEHICLE_NUMBER_PATTERN = re.compile(r"^[A-Z0-9\- ]{1,20}$")


# ── request/response models ────────────────────────────────

class ParkRequest(BaseModel):
    vehicle_number: str
    vehicle_type: str

    @field_validator("vehicle_type")
    @classmethod
    def validate_type(cls, v):
        allowed = {"car", "bike", "truck"}
        if v.lower() not in allowed:
            raise ValueError(f"vehicle_type must be one of: {', '.join(allowed)}")
        return v.lower()

    @field_validator("vehicle_number")
    @classmethod
    def validate_number(cls, v):
        v = v.strip().upper()
        if not v:
            raise ValueError("vehicle_number cannot be empty")
        if not VEHICLE_NUMBER_PATTERN.match(v):
            raise ValueError(
                "vehicle_number may only contain letters, numbers, "
                "hyphens, and spaces (max 20 characters)"
            )
        return v


class LoginRequest(BaseModel):
    password: str


# ── auth ───────────────────────────────────────────────────

@app.post("/api/login", summary="Operator login")
def login(body: LoginRequest):
    """Exchanges the shared operator password for a bearer token."""
    if not check_password(body.password):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    return {"token": create_token()}


# ── routes ─────────────────────────────────────────────────

@app.get("/api/status", summary="Get lot status")
def get_status():
    """Returns total, occupied, and available slot counts."""
    return lot.get_status()


@app.get("/api/vehicles", summary="List parked vehicles")
def list_vehicles():
    """Returns all currently parked vehicles."""
    return {"vehicles": lot.get_parked_vehicles()}


@app.post("/api/park", summary="Park a vehicle", dependencies=[Depends(require_auth)])
def park_vehicle(body: ParkRequest):
    """Parks a vehicle and returns the assigned slot. Requires operator login."""
    try:
        slot = lot.park_vehicle(body.vehicle_number, body.vehicle_type)
    except VehicleAlreadyParkedError:
        raise HTTPException(
            status_code=409,
            detail=f"{body.vehicle_number} is already parked in the lot.",
        )
    except LotFullError:
        raise HTTPException(
            status_code=409,
            detail="The lot is full. No free slots are available right now.",
        )
    return {
        "message": "Vehicle parked successfully",
        "vehicle_number": body.vehicle_number,
        "vehicle_type": body.vehicle_type,
        "slot": slot,
    }


@app.post(
    "/api/checkout/{vehicle_number}",
    summary="Checkout a vehicle",
    dependencies=[Depends(require_auth)],
)
def checkout_vehicle(vehicle_number: str):
    """Removes a vehicle, logs the session, and returns the fee. Requires operator login."""
    result = lot.remove_vehicle(vehicle_number.strip().upper())
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Vehicle '{vehicle_number}' not found in the parking lot.",
        )
    slot, duration, fee = result
    return {
        "message": "Vehicle checked out successfully",
        "vehicle_number": vehicle_number.upper(),
        "slot": slot,
        "duration_hours": duration,
        "fee": fee,
    }


@app.get("/api/log", summary="Transaction history")
def transaction_log(limit: int = 50, offset: int = 0):
    """Returns completed parking sessions, most recent first, paginated."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return {
        "records": read_log(limit=limit, offset=offset),
        "total": count_log_entries(),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/report", summary="Generate daily report")
def daily_report(report_date: str = None):
    """Generates a daily revenue report. Defaults to today."""
    target = None
    if report_date:
        try:
            target = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    records = read_log()
    from datetime import datetime
    today = target or date.today()

    day_records = []
    for r in records:
        try:
            exit_dt = datetime.strptime(r["exit_time"], "%Y-%m-%d %H:%M:%S")
            if exit_dt.date() == today:
                day_records.append(r)
        except (ValueError, KeyError):
            continue

    total_revenue = sum(float(r.get("fee", 0)) for r in day_records)
    from collections import defaultdict
    by_type = defaultdict(lambda: {"count": 0, "revenue": 0.0})
    for r in day_records:
        vt = r.get("vehicle_type", "unknown")
        by_type[vt]["count"] += 1
        by_type[vt]["revenue"] += float(r.get("fee", 0))

    # also save the txt file
    generate_daily_report(target)

    return {
        "date": str(today),
        "total_vehicles": len(day_records),
        "total_revenue": round(total_revenue, 2),
        "breakdown": dict(by_type),
        "transactions": day_records,
    }


@app.get("/api/summary", summary="All-time stats")
def all_time_summary():
    return get_all_time_summary()


@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "message": "Parking Management API is running. Visit /docs for the API reference."}
