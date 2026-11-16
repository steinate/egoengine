#!/usr/bin/env bash
set -euo pipefail
PAIR_ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
GS_ROOT="$PAIR_ROOT/gaussian-ego"
export PYTHONPATH="$GS_ROOT/site:$GS_ROOT/GHOST:$GS_ROOT/GHOST/submodules/manopth:$PAIR_ROOT/env/python310"
export TMPDIR="$PAIR_ROOT/tmp"
export PIP_CACHE_DIR="$PAIR_ROOT/cache41/pip"
export TORCH_EXTENSIONS_DIR="$GS_ROOT/torch_extensions"
export CUDA_HOME="$PAIR_ROOT/env/cuda-11.8"
export CC="$PAIR_ROOT/env/gcc11/usr/bin/gcc-11"
export CXX="$PAIR_ROOT/env/gcc11/usr/bin/g++-11"
export PATH="$PAIR_ROOT/env/python310/ninja/data/bin:$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/nvidia/lib:/usr/local/nvidia/lib64:$CUDA_HOME/lib64"
export MAX_JOBS=4 TORCH_CUDA_ARCH_LIST=8.9 PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$GS_ROOT/pycache"
cd "$GS_ROOT/GHOST"
exec "$PAIR_ROOT/runtime41/python.sh" "$@"
