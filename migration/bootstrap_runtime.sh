#!/usr/bin/env bash
# Fetch the exact 4.1 SDK directly from NVIDIA, preserving resumable downloads.
set -euo pipefail
PAIR_ROOT="$(cd "$1" && pwd)"
mkdir -p "$PAIR_ROOT/downloads"
ARCHIVE="$PAIR_ROOT/downloads/isaac-sim-4.1.0.zip"
DIGEST=a107e9b46d5f84134119112c398869b6c513e713bb7bf31e1233baa68f389ee0
URL='https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone%404.1.0-rc.7%2B4.1.14801.71533b68.gl.linux-x86_64.release.zip'
if [[ -f "$PAIR_ROOT/runtime41/.egoengine-sdk-ready" ]]; then
  test "$(cat "$PAIR_ROOT/runtime41/.egoengine-sdk-ready")" = "$DIGEST"
  test -x "$PAIR_ROOT/runtime41/kit/python/bin/python3"
  echo RUNTIME_READY
  exit 0
fi
if [[ ! -f "$ARCHIVE" ]]; then
  curl -fLsS --retry 5 --connect-timeout 20 -C - "$URL" -o "$ARCHIVE.part"
  printf '%s  %s\n' "$DIGEST" "$ARCHIVE.part" | sha256sum -c -
  mv "$ARCHIVE.part" "$ARCHIVE"
fi
printf '%s  %s\n' "$DIGEST" "$ARCHIVE" | sha256sum -c -
if [[ -d "$PAIR_ROOT/runtime41" ]] && [[ -n "$(ls -A "$PAIR_ROOT/runtime41")" ]]; then
  echo 'Existing SDK without completion marker: inspect it before extracting; refusing overwrite.' >&2
  exit 1
fi
mkdir -p "$PAIR_ROOT/runtime41"
unzip -q "$ARCHIVE" -d "$PAIR_ROOT/runtime41"
printf '%s\n' "$DIGEST" > "$PAIR_ROOT/runtime41/.egoengine-sdk-ready"
cat "$PAIR_ROOT/runtime41/VERSION"
echo RUNTIME_READY
