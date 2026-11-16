#!/usr/bin/env bash
set -euo pipefail
PAIR="$(cd "$1" && pwd)"
REPORTS="$2"
TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$REPORTS"
bash "$PAIR/run_env41.sh" -m unittest human_pair.test_geometry > "$REPORTS/geometry.log" 2>&1
bash "$PAIR/human41/usd_python.sh" "$PAIR/anime-human-v1/verify.py" > "$REPORTS/motion.log" 2>&1
bash "$PAIR/run_env41.sh" "$TOOLS/audit_runtime.py" "$PAIR" "$REPORTS/runtime.json" > "$REPORTS/runtime.log" 2>&1
bash "$PAIR/run_env41.sh" "$PAIR/anime-human-v1/render.py" \
  --frames 0,780,1506 --preview --view both --job migration-smoke > "$REPORTS/render.log" 2>&1
echo RESTORED_RUNTIME_AND_RENDER_PASSED
