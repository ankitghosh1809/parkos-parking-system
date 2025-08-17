import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import date

from parking import ParkingLot
from reports import generate_daily_report, get_all_time_summary, read_log

app = FastAPI(
    title="Parking Management API",
    description="REST API for the Vehicle Parking Management System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

lot = ParkingLot(total_slots=50)


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
        return v


# ── routes ─────────────────────────────────────────────────

@app.get("/api/status", summary="Get lot status")
def get_status():
    """Returns total, occupied, and available slot counts."""
    return lot.get_status()


@app.get("/api/vehicles", summary="List parked vehicles")
def list_vehicles():
    """Returns all currently parked vehicles."""
    return {"vehicles": lot.get_parked_vehicles()}


@app.post("/api/park", summary="Park a vehicle")
def park_vehicle(body: ParkRequest):
    """Parks a vehicle and returns the assigned slot."""
    slot = lot.park_vehicle(body.vehicle_number, body.vehicle_type)
    if slot is None:
        raise HTTPException(
            status_code=409,
            detail="Could not park vehicle. It may already be parked or the lot is full.",
        )
    return {
        "message": "Vehicle parked successfully",
        "vehicle_number": body.vehicle_number,
        "vehicle_type": body.vehicle_type,
        "slot": slot,
    }


@app.post("/api/checkout/{vehicle_number}", summary="Checkout a vehicle")
def checkout_vehicle(vehicle_number: str):
    """Removes a vehicle, logs the session, and returns the fee."""
    result = lot.remove_vehicle(vehicle_number.upper())
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
def transaction_log():
    """Returns all completed parking sessions."""
    return {"records": read_log()}


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
-e 

# Vercel serverless handler
from mangum import Mangum
handler = Mangum(app)
