#!/usr/bin/env bash
# Original Worker, immutable fresh robot episode, independent native human IK.
set -euo pipefail
PAIR_ROOT="$(cd "$1" && pwd)"
export EGO_WORKER_FRESH=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
CPU="$PAIR_ROOT/human41/usd_python.sh"
FLOW="$PAIR_ROOT/human-natural-v4"
test -f "$PAIR_ROOT/human41/assets/characters/download-provenance.json"
test -f "$FLOW/source/world-tracks.npz"
mkdir -p "$PAIR_ROOT/human41/output"
# Start from the source rig, not a previous solver's cached hand fit.
if [[ -e "$FLOW/grasp-refit.npz" ]]; then
  previous="$FLOW/previous-fits/$(date -u +%Y%m%dT%H%M%S)"
  mkdir -p "$previous"
  mv "$FLOW/grasp-refit.npz" "$previous/"
  if [[ -e "$FLOW/grasp-refit.json" ]]; then mv "$FLOW/grasp-refit.json" "$previous/"; fi
fi
bash "$CPU" "$PAIR_ROOT/human41/inspect_character.py"
bash "$CPU" "$PAIR_ROOT/human41/prepare_mocap.py"
bash "$CPU" "$FLOW/optimize.py"
bash "$CPU" "$FLOW/refit_grasp.py"
bash "$CPU" "$FLOW/optimize.py"
bash "$CPU" "$FLOW/refine_fingers.py"
bash "$CPU" "$FLOW/fix_head.py"
bash "$CPU" "$FLOW/verify_fresh.py"
bash "$CPU" "$FLOW/bake.py"
bash "$CPU" "$FLOW/ego_mask.py"
echo WORKER_MOTION_AND_SKIN_READY
