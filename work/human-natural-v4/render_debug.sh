#!/usr/bin/env bash
# Low-resolution, sampled whole-episode replay. Source timestamps stay unchanged.
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
BASE="$ROOT/human-natural-v4"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
stride=${EGO_DEBUG_STRIDE:-3}
[[ "$stride" =~ ^[1-9][0-9]*$ ]] || { echo 'EGO_DEBUG_STRIDE must be positive'; exit 1; }
# Unique directories prevent mixing earlier animation, profiles or partial jobs.
job="debug-$(date -u +%Y%m%dT%H%M%SZ)-$$"
bash "$ROOT/run_env41.sh" "$BASE/render.py" --quality debug --view both \
  --audit-sync --output "$job-sync" > "$BASE/$job-sync.log" 2>&1
bash "$ROOT/run_env41.sh" "$BASE/render.py" --quality debug --view both \
  --stride "$stride" --output "$job" > "$BASE/$job.log" 2>&1
bash "$ROOT/human41/usd_python.sh" "$BASE/encode_debug.py" --input "$job" \
  --audit "$job-sync"
echo "DEBUG_PAIRED_VIDEO_DONE $BASE/$job/delivery"
