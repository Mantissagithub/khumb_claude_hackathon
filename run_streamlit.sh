#!/usr/bin/env bash
# Launch the unified KumbhSeva Streamlit app.
set -euo pipefail
cd "$(dirname "$0")"
exec ./venv/bin/streamlit run streamlit_app.py "$@"
