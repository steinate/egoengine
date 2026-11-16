#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
cd "$ROOT/human41"
OPENBLAS_NUM_THREADS=1 bash usd_python.sh ../human-scan-v5/verify_cache.py > ../human-scan-v5/cache-verification.log 2>&1
cd "$ROOT"
pids=()
for part in 0 1 2; do
  if (( part < ${START_PART:-0} )); then continue; fi
  start=$((part*503)); end=$((start+503)); if (( end > 1507 )); then end=1507; fi
  # Default to sequential launches; at most two warmed workers may be requested.
  # Seed each isolated portable directory with the verified preview's cache.
  target="$ROOT/cache41/kit-v3-both-part$part/cache"
  mkdir -p "$target"
  cp -a "$ROOT/cache41/kit-v3-both-scan-test/cache/." "$target/"
  bash run_env41.sh "$ROOT/human-scan-v5/render.py" --start "$start" --end "$end" --job "part$part" > "$ROOT/human-scan-v5/render-part$part.log" 2>&1 &
  pids+=("$!")
  if (( ${#pids[@]} >= ${MAX_RENDER_JOBS:-1} )); then
    wait "${pids[0]}"
    pids=("${pids[@]:1}")
  fi
done
for pid in "${pids[@]}"; do wait "$pid"; done
echo FULL_SCAN_RENDER_DONE
