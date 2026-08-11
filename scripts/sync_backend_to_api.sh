#!/usr/bin/env bash
# api/ and backend/ contain the same application code: backend/ is what
# you run locally and test against; api/ is the copy Vercel actually
# deploys (via api/index.py -> vercel.json). They're not imported from
# a shared module because Vercel's Python builder bundles based on the
# api/ directory's own contents, and pointing it at a sibling directory
# via sys.path isn't something we've verified works with this project's
# build config - so until that's tested against a real deploy, keeping
# two synced copies is the safer option.
#
# Usage: after changing anything in backend/, run this before committing.
#   ./scripts/sync_backend_to_api.sh
#
# reports.py is intentionally NOT byte-identical: api/reports.py writes
# to /tmp (the only writable path in a Vercel serverless function),
# while backend/reports.py writes to a local data/ directory for local
# dev. This script copies reports.py's logic too, but always restores
# the api/-specific REPORTS_DIR line afterward, so you can still edit
# report logic in backend/reports.py and have it flow through safely.

set -euo pipefail
cd "$(dirname "$0")/.."

for f in auth.py db.py main.py parking.py; do
  cp "backend/$f" "api/$f"
  echo "synced api/$f"
done

cp backend/reports.py api/reports.py
sed -i.bak \
  's|REPORTS_DIR = os.path.join(os.path.dirname(__file__), "data", "reports")|REPORTS_DIR = "/tmp/parking_data/reports"|' \
  api/reports.py
rm -f api/reports.py.bak
echo "synced api/reports.py (kept the /tmp REPORTS_DIR override)"

echo ""
echo "Done. Diff should show ONLY the REPORTS_DIR line in reports.py:"
diff backend/reports.py api/reports.py || true
