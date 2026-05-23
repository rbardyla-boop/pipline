#!/usr/bin/env bash
# Launch the UAF Research Workbench UI.
# Run from the pipline/ project root.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

# Load .env if dotenv CLI is available, otherwise rely on python-dotenv at runtime
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

PORT="${RESEARCH_UI_PORT:-8501}"

echo "Starting UAF Research Workbench on http://localhost:$PORT"
exec streamlit run frontend/app.py \
  --server.port "$PORT" \
  --server.headless true \
  --browser.gatherUsageStats false
