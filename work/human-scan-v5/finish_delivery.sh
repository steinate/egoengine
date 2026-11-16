#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
BASE="$ROOT/human-scan-v5"
if [[ -n "${WAIT_RENDER_PID:-}" ]]; then
  while kill -0 "$WAIT_RENDER_PID" 2>/dev/null; do sleep 5; done
  test -s "$BASE/render/verification-both-part0.json"
fi
START_PART="${START_PART:-0}" bash "$BASE/render_full.sh"
cd "$ROOT/human41"
OPENBLAS_NUM_THREADS=1 bash usd_python.sh "$BASE/encode.py" > "$BASE/encode.log" 2>&1
OPENBLAS_NUM_THREADS=1 bash usd_python.sh "$BASE/package_delivery.py" > "$BASE/package.log" 2>&1
echo FULL_DELIVERY_DONE
