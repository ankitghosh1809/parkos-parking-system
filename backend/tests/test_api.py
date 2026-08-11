import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db
from parking import ParkingLot, VehicleAlreadyParkedError, LotFullError
from reports import (
    count_log_entries,
    generate_daily_report,
    get_all_time_summary,
    read_log,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - point it at a scratch Postgres/Neon branch to run these tests",
)


@pytest.fixture(autouse=True)
def clean_tables():
    conn = db.get_connection()
    db.ensure_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE active_sessions, parking_log RESTART IDENTITY")
    conn.commit()
    conn.close()
    yield


class TestParking:
    def test_park_success(self):
        lot = ParkingLot(10)
        assert lot.park_vehicle("WB-01-AB-1234", "car") == 1

    def test_duplicate_blocked(self):
        lot = ParkingLot(10)
        lot.park_vehicle("WB-01-AB-1234", "car")
        with pytest.raises(VehicleAlreadyParkedError):
            lot.park_vehicle("WB-01-AB-1234", "car")

    def test_lot_full(self):
        lot = ParkingLot(2)
        lot.park_vehicle("WB-01-AB-0001", "car")
        lot.park_vehicle("WB-01-AB-0002", "car")
        with pytest.raises(LotFullError):
            lot.park_vehicle("WB-01-AB-0003", "car")

    def test_duplicate_and_full_are_distinguishable(self):
        """The two failure modes used to both just return None - make
        sure a caller can actually tell them apart now."""
        lot = ParkingLot(1)
        lot.park_vehicle("WB-01-AB-0001", "car")
        with pytest.raises(VehicleAlreadyParkedError):
            lot.park_vehicle("WB-01-AB-0001", "bike")
        with pytest.raises(LotFullError):
            lot.park_vehicle("WB-01-AB-9999", "bike")

    def test_sequential_slots(self):
        lot = ParkingLot(10)
        assert lot.park_vehicle("WB-01-AB-0001", "car") == 1
        assert lot.park_vehicle("WB-01-AB-0002", "bike") == 2

    def test_remove_unknown(self):
        assert ParkingLot().remove_vehicle("XX-00-ZZ-9999") is None

    def test_remove_frees_slot(self):
        lot = ParkingLot(1)
        lot.park_vehicle("WB-01-AB-1234", "car")
        lot.remove_vehicle("WB-01-AB-1234")
        assert lot.park_vehicle("WB-01-AB-9999", "bike") == 1

    def test_fee_positive(self):
        lot = ParkingLot(10)
        lot.park_vehicle("WB-01-AB-1234", "car")
        _, _, fee = lot.remove_vehicle("WB-01-AB-1234")
        assert fee >= 0

    def test_status(self):
        lot = ParkingLot(10)
        lot.park_vehicle("WB-01-AB-0001", "car")
        s = lot.get_status()
        assert s["occupied"] == 1 and s["available"] == 9


class TestReports:
    def test_report_created(self):
        assert os.path.exists(generate_daily_report())

    def test_summary_structure(self):
        s = get_all_time_summary()
        assert "total_sessions" in s and "total_revenue" in s


class TestPagination:
    def _log_n_sessions(self, n):
        lot = ParkingLot(n)
        for i in range(n):
            plate = f"WB-01-AB-{i:04d}"
            lot.park_vehicle(plate, "car")
            lot.remove_vehicle(plate)

    def test_count_matches_inserted_rows(self):
        self._log_n_sessions(5)
        assert count_log_entries() == 5

    def test_limit_caps_results(self):
        self._log_n_sessions(5)
        assert len(read_log(limit=2)) == 2

    def test_offset_skips_results(self):
        self._log_n_sessions(5)
        page_1 = read_log(limit=2, offset=0)
        page_2 = read_log(limit=2, offset=2)
        assert page_1 != page_2

    def test_no_limit_returns_everything(self):
        self._log_n_sessions(5)
        assert len(read_log()) == 5
