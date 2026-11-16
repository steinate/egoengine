#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
cd "$ROOT"
pids=()
for view in ego front; do
  for part in 0 1 2; do
    start=$((part * 500)); end=$((start + 500)); if [ "$part" = 2 ]; then end=1507; fi
    bash run_env41.sh "$ROOT/human-natural-v4/render.py" --view "$view" --start "$start" --end "$end" --job "part$part" > "$ROOT/human-natural-v4/render-$view-part$part.log" 2>&1 &
    pids+=("$!")
  done
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if [ "$failed" != 0 ]; then echo RENDER_FAILURE; exit 1; fi
python3 "$ROOT/human-natural-v4/encode.py" > "$ROOT/human-natural-v4/encode.log" 2>&1
echo FULL_RENDER_AND_ENCODE_DONE
