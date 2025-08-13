import os, sys, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import parking as parking_module
from parking import ParkingLot
from reports import generate_daily_report, get_all_time_summary


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(parking_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(parking_module, "ACTIVE_FILE", str(tmp_path / "active_sessions.csv"))
    monkeypatch.setattr(parking_module, "LOG_FILE", str(tmp_path / "parking_log.csv"))

    import reports as rm
    monkeypatch.setattr(rm, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(rm, "LOG_FILE", str(tmp_path / "parking_log.csv"))
    monkeypatch.setattr(rm, "REPORTS_DIR", str(tmp_path / "reports"))
    yield


class TestParking:
    def test_park_success(self):
        lot = ParkingLot(10)
        assert lot.park_vehicle("WB-01-AB-1234", "car") == 1

    def test_duplicate_blocked(self):
        lot = ParkingLot(10)
        lot.park_vehicle("WB-01-AB-1234", "car")
        assert lot.park_vehicle("WB-01-AB-1234", "car") is None

    def test_lot_full(self):
        lot = ParkingLot(2)
        lot.park_vehicle("WB-01-AB-0001", "car")
        lot.park_vehicle("WB-01-AB-0002", "car")
        assert lot.park_vehicle("WB-01-AB-0003", "car") is None

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
