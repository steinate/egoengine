#!/usr/bin/env bash
set -euo pipefail
R=/vepfs/public/pengjiaqi/interndata-human-pair
mkdir -p "$R/tmp/apt"
chmod 1777 "$R/tmp/apt"
export TMPDIR="$R/tmp/apt"
mkdir -p "$R/cache41/apt/lists/partial" "$R/cache41/apt/archives/partial" "$R/downloads/gcc11" "$R/env/gcc11"
cat > "$R/downloads/gcc11.sources.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.aliyun.com/ubuntu noble main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.aliyun.com/ubuntu noble-updates main universe
EOF
opts=(-o "Dir::State::lists=$R/cache41/apt/lists" -o "Dir::Cache=$R/cache41/apt" -o "Dir::Etc::sourcelist=$R/downloads/gcc11.sources.list" -o "Dir::Etc::sourceparts=-" -o "Dir::Etc::parts=-" -o "Acquire::Languages=none" -o "Acquire::https::Timeout=20" -o "Acquire::Retries=1")
apt-get "${opts[@]}" update
cd "$R/downloads/gcc11"
apt-get "${opts[@]}" download gcc-11 g++-11 cpp-11 libgcc-11-dev libstdc++-11-dev
for deb in ./*.deb; do dpkg-deb -x "$deb" "$R/env/gcc11"; done
mkdir -p "$R/env/gcc11/usr/lib/x86_64-linux-gnu"
ln -s /usr/lib/x86_64-linux-gnu/libstdc++.so.6 "$R/env/gcc11/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
"$R/env/gcc11/usr/bin/gcc-11" --version
"$R/env/gcc11/usr/bin/g++-11" --version
