import os
import csv
from datetime import datetime

PARKING_RATES = {
    "car": 30,
    "bike": 10,
    "truck": 60,
}

# FIX: Use /tmp — writable on Vercel serverless, unlike the deploy directory
DATA_DIR    = "/tmp/parking_data"
ACTIVE_FILE = os.path.join(DATA_DIR, "active_sessions.csv")
LOG_FILE    = os.path.join(DATA_DIR, "parking_log.csv")

ACTIVE_HEADERS = ["slot", "vehicle_number", "vehicle_type", "entry_time"]
LOG_HEADERS    = ["vehicle_number", "vehicle_type", "slot", "entry_time", "exit_time", "duration_hours", "fee"]


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_active_sessions():
    _ensure_data_dir()
    if not os.path.exists(ACTIVE_FILE):
        return []
    with open(ACTIVE_FILE, "r", newline="") as f:
        return list(csv.DictReader(f))


def _write_active_sessions(sessions):
    _ensure_data_dir()
    with open(ACTIVE_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ACTIVE_HEADERS)
        writer.writeheader()
        writer.writerows(sessions)


def _append_to_log(record):
    _ensure_data_dir()
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)
        writer.writerow(record)


def _calculate_fee(entry_time_str, exit_time, vehicle_type):
    entry_time = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
    delta = exit_time - entry_time
    total_seconds = delta.total_seconds()
    hours = max(1, int(total_seconds / 3600) + (1 if total_seconds % 3600 > 0 else 0))
    rate = PARKING_RATES.get(vehicle_type.lower(), 30)
    return hours, round(hours * rate, 2)


class ParkingLot:
    def __init__(self, total_slots=50):
        self.total_slots = total_slots

    def _get_occupied_slots(self):
        return {int(s["slot"]) for s in _read_active_sessions()}

    def _find_free_slot(self):
        occupied = self._get_occupied_slots()
        for slot in range(1, self.total_slots + 1):
            if slot not in occupied:
                return slot
        return None

    def park_vehicle(self, vehicle_number: str, vehicle_type: str):
        sessions = _read_active_sessions()
        for s in sessions:
            if s["vehicle_number"] == vehicle_number:
                return None  # already parked

        slot = self._find_free_slot()
        if slot is None:
            return None  # lot full

        entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sessions.append({
            "slot": slot,
            "vehicle_number": vehicle_number,
            "vehicle_type": vehicle_type,
            "entry_time": entry_time,
        })
        _write_active_sessions(sessions)
        return slot

    def remove_vehicle(self, vehicle_number: str):
        sessions = _read_active_sessions()
        found = None
        remaining = []

        for s in sessions:
            if s["vehicle_number"] == vehicle_number:
                found = s
            else:
                remaining.append(s)

        if not found:
            return None

        exit_time = datetime.now()
        duration, fee = _calculate_fee(found["entry_time"], exit_time, found["vehicle_type"])

        _append_to_log({
            "vehicle_number": vehicle_number,
            "vehicle_type": found["vehicle_type"],
            "slot": found["slot"],
            "entry_time": found["entry_time"],
            "exit_time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_hours": duration,
            "fee": fee,
        })
        _write_active_sessions(remaining)
        return int(found["slot"]), duration, fee

    def get_parked_vehicles(self):
        sessions = _read_active_sessions()
        sessions.sort(key=lambda x: int(x["slot"]))
        return sessions

    def get_status(self):
        occupied = len(_read_active_sessions())
        available = self.total_slots - occupied
        pct = (occupied / self.total_slots * 100) if self.total_slots else 0
        return {
            "total": self.total_slots,
            "occupied": occupied,
            "available": available,
            "occupancy_pct": round(pct, 1),
        }
