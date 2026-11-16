#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
BASE="$ROOT/human-scan-v6"
bash "$BASE/render_full.sh"
cd "$ROOT/human41"
OPENBLAS_NUM_THREADS=1 bash usd_python.sh "$BASE/encode.py" > "$BASE/encode.log" 2>&1
OPENBLAS_NUM_THREADS=1 bash usd_python.sh "$BASE/package_delivery.py" > "$BASE/package.log" 2>&1
echo FULL_DELIVERY_DONE
