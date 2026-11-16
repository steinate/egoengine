#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
cd "$ROOT"
N=$(bash human41/usd_python.sh -c 'import numpy as np; print(len(np.load("human-natural-v4/human-animation.npz")["source_frame"]))')
limit=${EGO_RENDER_JOBS:-1}
quality=${EGO_RENDER_QUALITY:-debug}
[[ "$limit" =~ ^[1-2]$ ]] || { echo 'EGO_RENDER_JOBS must be 1 or 2'; exit 1; }
[[ "$quality" == debug || "$quality" == final ]] || { echo 'EGO_RENDER_QUALITY must be debug or final'; exit 1; }
pids=()
failed=0
for view in ego front; do
  for part in 0 1 2; do
    if (( ${#pids[@]} >= limit )); then
      wait "${pids[0]}" || failed=1
      pids=("${pids[@]:1}")
    fi
    start=$((part * N / 3)); end=$(((part + 1) * N / 3))
    bash run_env41.sh "$ROOT/human-natural-v4/render.py" --quality "$quality" --view "$view" --start "$start" --end "$end" --job "part$part" > "$ROOT/human-natural-v4/render-$view-part$part.log" 2>&1 &
    pids+=("$!")
  done
done
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if [ "$failed" != 0 ]; then echo RENDER_FAILURE; exit 1; fi
bash "$ROOT/human41/usd_python.sh" "$ROOT/human-natural-v4/encode.py" > "$ROOT/human-natural-v4/encode.log" 2>&1
echo FULL_RENDER_AND_ENCODE_DONE
