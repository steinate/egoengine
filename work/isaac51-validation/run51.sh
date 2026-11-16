#!/usr/bin/env bash
set -euo pipefail
ROOT=/vepfs/public/pengjiaqi/interndata-human-pair
export PYTHONPATH="$ROOT/env/python311"
export TMPDIR="$ROOT/tmp"
export XDG_CACHE_HOME="$ROOT/validation51/cache"
export XDG_DATA_HOME="$ROOT/validation51/cache/data"
export PYTHONPYCACHEPREFIX="$ROOT/validation51/cache/pycache"
export CUDA_CACHE_PATH="$ROOT/validation51/cache/cuda"
export MESA_SHADER_CACHE_DIR="$ROOT/validation51/cache/mesa"
export OPTIX_CACHE_PATH="$ROOT/validation51/cache/optix"
export __GL_SHADER_DISK_CACHE_PATH="$ROOT/validation51/cache/gl"
export PYTHONUNBUFFERED=1
cd "$ROOT/validation51"
exec /isaac-sim/python.sh "$@"
