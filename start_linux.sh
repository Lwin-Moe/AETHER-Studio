#!/usr/bin/env bash
set -euo pipefail

# Worker ကို background process အဖြစ်စတင်ပြီး UI ကို foreground တွင် run ရန်
python worker.py &
worker_pid=$!
trap 'kill "$worker_pid" 2>/dev/null || true' EXIT INT TERM
streamlit run app.py --server.address=0.0.0.0
