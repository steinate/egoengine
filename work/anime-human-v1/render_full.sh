#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
BASE="$ROOT/anime-human-v1"
N="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["frames"])' "$BASE/source/scene-meta.json")"
cd "$ROOT"
pids=()
for view in ego front; do
  target="$ROOT/cache41/kit-anime-$view-full/cache"
  mkdir -p "$target"
  if [[ -d "$ROOT/cache41/kit-anime-both-preview/cache" ]]; then
    cp -a "$ROOT/cache41/kit-anime-both-preview/cache/." "$target/"
  fi
  bash run_env41.sh "$BASE/render.py" --view "$view" --start 0 --end "$N" --job full > "$BASE/render-$view.log" 2>&1 &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if (( failed )); then exit 1; fi
cd "$ROOT/human41"
OPENBLAS_NUM_THREADS=1 bash usd_python.sh "$BASE/encode.py" > "$BASE/encode.log" 2>&1
echo FULL_AMBER_PAIR_DONE
