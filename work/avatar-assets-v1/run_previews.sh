#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
cd "$ROOT/human41"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 bash usd_python.sh ../avatar-assets-v1/bake_assets.py > ../avatar-assets-v1/bake.log 2>&1
cd "$ROOT"
pids=()
for index in 0 1 2 3; do
 bash run_env41.sh "$ROOT/avatar-assets-v1/render_assets.py" --index "$index" > "$ROOT/avatar-assets-v1/render-$index.log" 2>&1 &
 pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
test "$failed" = 0
echo ALL_ASSET_PREVIEWS_RENDERED
