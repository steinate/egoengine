#!/usr/bin/env bash
set -euo pipefail
PAIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$PAIR_ROOT/env/python311:$PAIR_ROOT/env/curobo-built:$PAIR_ROOT/src/InternDataEngine:$PAIR_ROOT/src/InternDataEngine/workflows/simbox:$PAIR_ROOT/assets/InternDataAssets/curobo/src${PYTHONPATH:+:$PYTHONPATH}"
export TMPDIR="$PAIR_ROOT/tmp"
export XDG_CACHE_HOME="$PAIR_ROOT/cache"
export XDG_DATA_HOME="$PAIR_ROOT/cache/data"
export PIP_CACHE_DIR="$PAIR_ROOT/cache/pip"
export TORCH_EXTENSIONS_DIR="$PAIR_ROOT/cache/torch_extensions"
export CUDA_CACHE_PATH="$PAIR_ROOT/cache/cuda"
export MESA_SHADER_CACHE_DIR="$PAIR_ROOT/cache/mesa"
export OPTIX_CACHE_PATH="$PAIR_ROOT/cache/optix"
export __GL_SHADER_DISK_CACHE_PATH="$PAIR_ROOT/cache/gl"
export MAX_JOBS=4
export PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$PAIR_ROOT/cache/pycache"
export TORCH_CUDA_ARCH_LIST=8.9
export SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0+interndata20261112
cd "$PAIR_ROOT/src/InternDataEngine"
exec /isaac-sim/python.sh "$@"
