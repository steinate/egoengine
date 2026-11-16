#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
cd "$ROOT/human41"
pids=()
for part in 0 1 2; do
  start=$((part*503)); end=$((start+503)); if (( end > 1507 )); then end=1507; fi
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 bash usd_python.sh ../human-scan-v5/drive_scan.py --bake-only --start "$start" --end "$end" > "../human-scan-v5/bake-part$part.log" 2>&1 &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if (( failed )); then exit 1; fi
echo FULL_SCAN_BAKE_DONE
