import os
import csv
from datetime import datetime, date
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOG_FILE = os.path.join(DATA_DIR, "parking_log.csv")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

LOG_HEADERS = ["vehicle_number", "vehicle_type", "slot", "entry_time", "exit_time", "duration_hours", "fee"]


def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", newline="") as f:
        return list(csv.DictReader(f))


def generate_daily_report(target_date=None):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    if target_date is None:
        target_date = date.today()

    all_records = read_log()
    day_records = []
    for r in all_records:
        try:
            exit_dt = datetime.strptime(r["exit_time"], "%Y-%m-%d %H:%M:%S")
            if exit_dt.date() == target_date:
                day_records.append(r)
        except (ValueError, KeyError):
            continue

    total_revenue = sum(float(r.get("fee", 0)) for r in day_records)
    by_type = defaultdict(lambda: {"count": 0, "revenue": 0.0})
    for r in day_records:
        vt = r.get("vehicle_type", "unknown")
        by_type[vt]["count"] += 1
        by_type[vt]["revenue"] += float(r.get("fee", 0))

    report_path = os.path.join(REPORTS_DIR, f"report_{target_date}.txt")
    with open(report_path, "w") as f:
        f.write("=" * 50 + "\n")
        f.write(f"  DAILY PARKING REVENUE REPORT\n")
        f.write(f"  Date      : {target_date}\n")
        f.write(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total Vehicles Served : {len(day_records)}\n")
        f.write(f"Total Revenue         : Rs. {total_revenue:.2f}\n\n")
        f.write("Breakdown by Vehicle Type:\n")
        f.write("-" * 35 + "\n")
        if by_type:
            for vtype, info in sorted(by_type.items()):
                f.write(f"  {vtype.capitalize():<10} : {info['count']} vehicle(s), Rs. {info['revenue']:.2f}\n")
        else:
            f.write("  No vehicles served today.\n")
        f.write("\nTransaction Details:\n")
        f.write("-" * 35 + "\n")
        if day_records:
            f.write(f"{'#':<4}{'Vehicle No.':<18}{'Type':<8}{'Slot':<6}{'Hrs':<6}{'Fee'}\n")
            for i, r in enumerate(day_records, 1):
                f.write(f"{i:<4}{r['vehicle_number']:<18}{r['vehicle_type']:<8}{r['slot']:<6}{r['duration_hours']:<6}Rs. {float(r['fee']):.2f}\n")
        else:
            f.write("  No transactions found for this date.\n")
        f.write("\n" + "=" * 50 + "\n")

    return report_path


def get_all_time_summary():
    records = read_log()
    total_revenue = sum(float(r.get("fee", 0)) for r in records)
    by_type = defaultdict(lambda: {"count": 0, "revenue": 0.0})
    for r in records:
        vt = r.get("vehicle_type", "unknown")
        by_type[vt]["count"] += 1
        by_type[vt]["revenue"] += float(r.get("fee", 0))
    return {
        "total_sessions": len(records),
        "total_revenue": round(total_revenue, 2),
        "by_type": {k: {"count": v["count"], "revenue": round(v["revenue"], 2)} for k, v in by_type.items()},
    }
