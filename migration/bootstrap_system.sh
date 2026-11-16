#!/usr/bin/env bash
# Download/extract Ubuntu packages inside the deployment, without global installs.
set -euo pipefail
PAIR_ROOT="$(cd "$1" && pwd)"
mkdir -p "$PAIR_ROOT/cache41/apt/lists/partial" "$PAIR_ROOT/cache41/apt/archives/partial" \
  "$PAIR_ROOT/downloads/system" "$PAIR_ROOT/env/system" "$PAIR_ROOT/tmp/apt"
export TMPDIR="$PAIR_ROOT/tmp/apt"
cat > "$PAIR_ROOT/downloads/system/sources.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.aliyun.com/ubuntu noble main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.aliyun.com/ubuntu noble-updates main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.aliyun.com/ubuntu noble-security main universe
EOF
options=(-o "Dir::State::lists=$PAIR_ROOT/cache41/apt/lists"
  -o "Dir::Cache=$PAIR_ROOT/cache41/apt"
  -o "Dir::Etc::sourcelist=$PAIR_ROOT/downloads/system/sources.list"
  -o "Dir::Etc::sourceparts=-" -o "Dir::Etc::parts=-"
  -o "APT::Sandbox::User=root" -o "Acquire::Languages=none"
  -o "Acquire::https::Timeout=30" -o "Acquire::Retries=3")
apt-get "${options[@]}" update
apt-get "${options[@]}" --download-only --no-install-recommends -y install \
  gcc-11 g++-11 ffmpeg fonts-dejavu-core rsync ripgrep
for package in "$PAIR_ROOT/cache41/apt/archives/"*.deb; do
  dpkg-deb -x "$package" "$PAIR_ROOT/env/system"
done
mkdir -p "$PAIR_ROOT/env/gcc11"
# Preserve the original wrapper's expected GCC prefix without duplicate packages.
if [[ ! -e "$PAIR_ROOT/env/gcc11/usr" ]]; then
  ln -s ../system/usr "$PAIR_ROOT/env/gcc11/usr"
fi
if [[ ! -e "$PAIR_ROOT/env/system/usr/lib/x86_64-linux-gnu/libstdc++.so.6" ]]; then
  ln -s /usr/lib/x86_64-linux-gnu/libstdc++.so.6 "$PAIR_ROOT/env/system/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
fi
# dpkg-deb extraction does not run update-alternatives. Resolve these privately
# for FFmpeg's filters instead of altering the host's BLAS/LAPACK configuration.
for library in blas lapack; do
  directory="$PAIR_ROOT/env/system/usr/lib/x86_64-linux-gnu"
  if [[ -e "$directory/$library/lib$library.so.3" && ! -e "$directory/lib$library.so.3" ]]; then
    ln -s "$library/lib$library.so.3" "$directory/lib$library.so.3"
  fi
done
"$PAIR_ROOT/env/system/usr/bin/gcc-11" --version
echo SYSTEM_PACKAGES_READY
