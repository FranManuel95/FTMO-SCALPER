#!/usr/bin/env bash
# Lanza el dashboard de observabilidad.
#
# Uso:
#   ./dashboard/run_dashboard.sh                      # default: http://localhost:8501
#   FTMO_EVENTS_DB=/path/to/events.db ./dashboard/run_dashboard.sh
#   FTMO_INITIAL_BALANCE=100000 ./dashboard/run_dashboard.sh

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v streamlit &>/dev/null; then
  echo "❌ streamlit no instalado. Ejecuta:"
  echo "   pip install -e .[dashboard]"
  exit 1
fi

PORT="${PORT:-8501}"
DB_PATH="${FTMO_EVENTS_DB:-data/events.db}"

echo "📊 Dashboard FTMO Scalper"
echo "   DB: $DB_PATH"
echo "   URL: http://localhost:$PORT"
echo ""

exec streamlit run dashboard/app.py \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false
