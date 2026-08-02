#!/usr/bin/env bash
# Run the Streamlit ops/dev dashboard.
# Expects intotheopen-backend installed editable in the active venv, or a
# sibling checkout (see dashboard/app.py sys.path fallback).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Keep ./data → sibling backend data/ so npy/jsonl/csv stay shared.
bash "$ROOT/scripts/ensure-shared-data.sh"

PARENT="$(dirname "$ROOT")"
for candidate in \
  "$PARENT/intotheopen-backend" \
  "$PARENT/ITO-RND" \
  "$PARENT/ITO Testing Visual Mock"
do
  if [[ -f "$candidate/config/settings.py" ]]; then
    export PYTHONPATH="${candidate}${PYTHONPATH:+:$PYTHONPATH}"
    # Prefer backend venv if this repo has none.
    if [[ ! -x "$ROOT/.venv/bin/streamlit" && -x "$candidate/.venv/bin/streamlit" ]]; then
      STREAMLIT="$candidate/.venv/bin/streamlit"
    fi
    break
  fi
done

STREAMLIT="${STREAMLIT:-$ROOT/.venv/bin/streamlit}"

if [[ ! -x "$STREAMLIT" ]]; then
  echo "Missing streamlit — create a venv and:"
  echo "  pip install -e ../intotheopen-backend"
  echo "  pip install -r requirements.txt"
  exit 1
fi

echo "Starting dashboard-for-devs on http://localhost:8501"
exec "$STREAMLIT" run dashboard/app.py --server.headless true --server.port 8501
