#!/usr/bin/env bash
set -euo pipefail
if (( $# < 2 )); then
  echo "Usage: bash migration/run_engine.sh DEPLOYMENT_ROOT PYTHON_ARGS..." >&2
  exit 2
fi
PAIR_ROOT="$(cd "$1" && pwd)"
shift
ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$ENGINE_ROOT/launcher.py" ]]; then
  echo "InternDataEngine checkout is missing at $ENGINE_ROOT" >&2
  exit 1
fi
ASSET_LINK="$ENGINE_ROOT/workflows/simbox/assets"
if [[ ! -e "$ASSET_LINK" && ! -L "$ASSET_LINK" ]]; then
  ln -s "$PAIR_ROOT/assets/InternDataAssets" "$ASSET_LINK"
fi
if [[ "$(readlink -f "$ASSET_LINK")" != "$PAIR_ROOT/assets/InternDataAssets" ]]; then
  echo "Existing asset path differs; refusing to overwrite $ASSET_LINK" >&2
  exit 1
fi
export PYTHONPATH="$PAIR_ROOT/env/python310:$PAIR_ROOT/env/curobo41-built:$ENGINE_ROOT:$ENGINE_ROOT/workflows/simbox:$PAIR_ROOT/assets/InternDataAssets/curobo/src"
export TMPDIR="$PAIR_ROOT/tmp"
export XDG_CACHE_HOME="$PAIR_ROOT/cache41"
export XDG_DATA_HOME="$PAIR_ROOT/cache41/data"
export PIP_CACHE_DIR="$PAIR_ROOT/cache41/pip"
export TORCH_EXTENSIONS_DIR="$PAIR_ROOT/cache41/torch_extensions"
export CUDA_CACHE_PATH="$PAIR_ROOT/cache41/cuda"
export MESA_SHADER_CACHE_DIR="$PAIR_ROOT/cache41/mesa"
export OPTIX_CACHE_PATH="$PAIR_ROOT/cache41/optix"
export __GL_SHADER_DISK_CACHE_PATH="$PAIR_ROOT/cache41/gl"
export MAX_JOBS=4
export CUDA_HOME="$PAIR_ROOT/env/cuda-11.8"
export CC="$PAIR_ROOT/env/gcc11/usr/bin/gcc-11"
export CXX="$PAIR_ROOT/env/gcc11/usr/bin/g++-11"
export PATH="$PAIR_ROOT/env/python310/ninja/data/bin:$PAIR_ROOT/env/python310/bin:$CUDA_HOME/bin:$PATH"
export PYTHONEXE="$PAIR_ROOT/runtime41/kit/python/bin/python3"
export LD_LIBRARY_PATH="/usr/local/nvidia/lib:/usr/local/nvidia/lib64:$CUDA_HOME/lib64"
export PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="$PAIR_ROOT/cache41/pycache"
export TORCH_CUDA_ARCH_LIST=8.9
export ISAAC_SIM_PATH="$PAIR_ROOT/runtime41"
export SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0+interndata20261112
cd "$ENGINE_ROOT"
exec "$PAIR_ROOT/runtime41/python.sh" "$@"
