#!/usr/bin/env bash
# Download the original PMX and build its native rig locally. No old-server inputs.
set -euo pipefail
PAIR_ROOT="$(cd "$1" && pwd)"
EGO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TMPDIR="$PAIR_ROOT/tmp"
export PIP_CACHE_DIR="$PAIR_ROOT/cache41/pip"
export PYTHONPYCACHEPREFIX="$PAIR_ROOT/cache41/pycache"
export XDG_CONFIG_HOME="$PAIR_ROOT/cache41/config"
export XDG_CACHE_HOME="$PAIR_ROOT/cache41"
mkdir -p "$PAIR_ROOT/downloads" "$PAIR_ROOT/tools" "$PAIR_ROOT/anime-human-v1/assets/amber"
export PAIR_ROOT
python3 - <<'PY'
import hashlib, os, urllib.request
from pathlib import Path
r = Path(os.environ['PAIR_ROOT'])
z = r / 'downloads/amber.zip'
if not z.exists():
    urllib.request.urlretrieve('https://activity.hdslb.com/blackboard/static/20210316/4d40bc4f98f94fbc71c235832ce3efd4/ApoSncaZI8.zip', z)
assert hashlib.sha256(z.read_bytes()).hexdigest() == '4dafd2bc1251d7c90cc68e62fd3edda29aa137ae430dc382df19d44859ce52f5'
# The publisher ZIP has inconsistent local filename encodings. unzip handles
# this warning; use it below and accept only success or its warning status.
checks = []
for base in ['https://mirrors.tuna.tsinghua.edu.cn/blender/release', 'https://ftp.nluug.nl/pub/graphics/blender/release']:
    with urllib.request.urlopen(base+'/Blender5.2/blender-5.2.2.sha256', timeout=30) as f:
        checks.append(f.read())
assert checks[0] == checks[1], 'Mirror checksum manifests disagree'
(r/'downloads/blender-5.2.2.sha256').write_bytes(checks[0])
assert b'84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168  blender-5.2.2-linux-x64.tar.xz' in checks[0]
PY
set +e
unzip -oq "$PAIR_ROOT/downloads/amber.zip" -d "$PAIR_ROOT/anime-human-v1/assets/amber"
zip_status=$?
set -e
if (( zip_status > 1 )); then exit "$zip_status"; fi
ARCHIVE="$PAIR_ROOT/downloads/blender-5.2.2-linux-x64.tar.xz"
if [[ ! -f "$ARCHIVE" ]]; then
  python3 -u "$EGO_ROOT/migration/download_ranges.py" \
    'https://mirrors.aliyun.com/blender/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz' \
    "$ARCHIVE" --size 383295504 --workers 6
fi
(cd "$PAIR_ROOT/downloads" && grep 'blender-5.2.2-linux-x64.tar.xz' blender-5.2.2.sha256 | sha256sum -c -)
if [[ ! -x "$PAIR_ROOT/tools/blender-5.2.2-linux-x64/blender" ]]; then
  tar -xJf "$ARCHIVE" -C "$PAIR_ROOT/tools"
fi
BLENDER="$PAIR_ROOT/tools/blender-5.2.2-linux-x64"
BLENDER_PYTHON="$(find "$BLENDER" -path '*/python/bin/python3.*' -type f -executable | head -n 1)"
test -n "$BLENDER_PYTHON"
"$BLENDER_PYTHON" -m pip install \
  --target "$PAIR_ROOT/anime-human-v1/tools/python-deps" \
  opencc-python-reimplemented==0.1.7 -i https://mirrors.aliyun.com/pypi/simple
"$BLENDER/blender" --background --factory-startup --python-exit-code 1 \
  --python "$PAIR_ROOT/anime-human-v1/import_amber.py"
"$BLENDER/blender" --background --factory-startup --python-exit-code 1 \
  --python "$PAIR_ROOT/anime-human-v1/export_native.py"
echo CHARACTER_READY
