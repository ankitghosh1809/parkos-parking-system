from datetime import datetime

import psycopg2

from db import get_connection, ensure_schema

PARKING_RATES = {"car": 30, "bike": 10, "truck": 60}
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _calculate_fee(entry_time, exit_time, vehicle_type):
    delta = exit_time - entry_time
    total_seconds = delta.total_seconds()
    hours = max(1, int(total_seconds // 3600) + (1 if total_seconds % 3600 else 0))
    rate = PARKING_RATES.get(vehicle_type.lower(), 30)
    return hours, round(hours * rate, 2)


class ParkingLot:
    def __init__(self, total_slots=50):
        self.total_slots = total_slots

    def _find_free_slot(self, cur):
        cur.execute("SELECT slot FROM active_sessions")
        occupied = {row["slot"] for row in cur.fetchall()}
        for slot in range(1, self.total_slots + 1):
            if slot not in occupied:
                return slot
        return None

    def park_vehicle(self, vehicle_number, vehicle_type):
        conn = get_connection()
        try:
            ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM active_sessions WHERE vehicle_number = %s",
                    (vehicle_number,),
                )
                if cur.fetchone():
                    return None  # already parked

                slot = self._find_free_slot(cur)
                if slot is None:
                    return None  # lot full

                entry_time = datetime.now()
                try:
                    cur.execute(
                        """
                        INSERT INTO active_sessions
                            (slot, vehicle_number, vehicle_type, entry_time)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (slot, vehicle_number, vehicle_type, entry_time),
                    )
                except psycopg2.IntegrityError:
                    conn.rollback()
                    return None
            conn.commit()
            return slot
        finally:
            conn.close()

    def remove_vehicle(self, vehicle_number):
        conn = get_connection()
        try:
            ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slot, vehicle_type, entry_time
                    FROM active_sessions WHERE vehicle_number = %s
                    """,
                    (vehicle_number,),
                )
                found = cur.fetchone()
                if not found:
                    return None

                exit_time = datetime.now()
                duration, fee = _calculate_fee(
                    found["entry_time"], exit_time, found["vehicle_type"]
                )

                cur.execute(
                    """
                    INSERT INTO parking_log
                        (vehicle_number, vehicle_type, slot, entry_time,
                         exit_time, duration_hours, fee)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        vehicle_number,
                        found["vehicle_type"],
                        found["slot"],
                        found["entry_time"],
                        exit_time,
                        duration,
                        fee,
                    ),
                )
                cur.execute(
                    "DELETE FROM active_sessions WHERE vehicle_number = %s",
                    (vehicle_number,),
                )
            conn.commit()
            return int(found["slot"]), duration, fee
        finally:
            conn.close()

    def get_parked_vehicles(self):
        conn = get_connection()
        try:
            ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT slot, vehicle_number, vehicle_type, entry_time
                    FROM active_sessions ORDER BY slot
                    """
                )
                rows = cur.fetchall()
            return [
                {
                    "slot": row["slot"],
                    "vehicle_number": row["vehicle_number"],
                    "vehicle_type": row["vehicle_type"],
                    "entry_time": row["entry_time"].strftime(DATE_FMT),
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_status(self):
        conn = get_connection()
        try:
            ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM active_sessions")
                occupied = cur.fetchone()["n"]
            available = self.total_slots - occupied
            pct = (occupied / self.total_slots * 100) if self.total_slots else 0
            return {
                "total": self.total_slots,
                "occupied": occupied,
                "available": available,
                "occupancy_pct": round(pct, 1),
            }
        finally:
            conn.close()
