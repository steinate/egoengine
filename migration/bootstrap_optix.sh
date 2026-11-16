#!/usr/bin/env bash
# Fill the OptiX data omitted by some GPU containers, without installing a driver.
set -euo pipefail
PAIR_ROOT="$(cd "$1" && pwd)"
EGO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -r /usr/share/nvidia/nvoptix.bin ]]; then
  echo OPTIX_READY_SYSTEM
  exit 0
fi
VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | sort -u)"
if [[ "$VERSION" != 570.124.04 ]]; then
  echo "This fallback is pinned to 570.124.04; obtain nvoptix.bin matching driver $VERSION." >&2
  exit 1
fi
URL=https://download.nvidia.com/XFree86/Linux-x86_64/570.124.04/NVIDIA-Linux-x86_64-570.124.04.run
ARCHIVE="$PAIR_ROOT/downloads/NVIDIA-Linux-x86_64-570.124.04.run"
DATA="$PAIR_ROOT/env/nvidia-570.124.04"
export TMPDIR="$PAIR_ROOT/tmp"
mkdir -p "$DATA" "$TMPDIR"
if [[ ! -f "$ARCHIVE" ]]; then
  python3 -u "$EGO_ROOT/migration/download_ranges.py" "$URL" "$ARCHIVE" --size 375582187 --workers 8
fi
printf '%s  %s\n' 1b786a4b7122d7c4216c58ae4007688a4f778c196c148d919163815ee10d53c4 "$ARCHIVE" | sha256sum -c -
sh "$ARCHIVE" --check
# Use the publisher's embedded decompressor and extract only its data blob.
sh "$ARCHIVE" --extract-decompress > "$DATA/zstd"
chmod +x "$DATA/zstd"
SKIP="$(LC_ALL=C awk '/^skip=/{sub(/^skip=/,""); print; exit}' "$ARCHIVE")"
[[ "$SKIP" =~ ^[0-9]+$ ]]
tail -n +"$SKIP" "$ARCHIVE" | "$DATA/zstd" -dc | tar -xOf - --wildcards '*nvoptix.bin' > "$DATA/nvoptix.bin.part"
test "$(stat -c %s "$DATA/nvoptix.bin.part")" -gt 100000
mv "$DATA/nvoptix.bin.part" "$DATA/nvoptix.bin"
sha256sum "$DATA/nvoptix.bin" > "$DATA/nvoptix.sha256"
if [[ "${2:-}" == --system-link ]]; then
  # The sole system-path addition is this link; all bytes remain in PAIR_ROOT.
  # Refuse replacement, including a dangling link left by another deployment.
  test ! -e /usr/share/nvidia/nvoptix.bin
  test ! -L /usr/share/nvidia/nvoptix.bin
  mkdir -p /usr/share/nvidia
  ln -s "$DATA/nvoptix.bin" /usr/share/nvidia/nvoptix.bin
  echo OPTIX_READY
else
  echo "Data ready: $DATA/nvoptix.bin"
  echo "Expose this file at /usr/share/nvidia/nvoptix.bin with a container mount or --system-link."
fi

