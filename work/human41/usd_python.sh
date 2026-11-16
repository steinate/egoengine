#!/usr/bin/env bash
set -euo pipefail
PAIR=/vepfs/public/pengjiaqi/interndata-human-pair
export LD_LIBRARY_PATH="$PAIR/runtime41/kit/exts/omni.usd.libs/bin:$PAIR/runtime41/kit"
export PYTHONPATH="$PAIR/env/python310"
export PYTHONPYCACHEPREFIX="$PAIR/cache41/pycache"
exec "$PAIR/runtime41/kit/python/bin/python3" "$@"
